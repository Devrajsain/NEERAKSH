"""
Phase 2 — AIS Candidate Release Hypothesis Generator.

Consumes the Phase-1 Bayesian prefilter result (search region + search window)
together with an AIS dataset and produces a set of candidate release hypotheses.

Architectural semantics
-----------------------
Phase 2 answers:
    "Which AIS release hypotheses exist inside the physically bounded
     search window?"

It does NOT answer:
    "Which vessel caused the spill?"

The distinction is:
    Feature 2 legacy origin estimation  ≠  Phase 1 Bayesian search pre-filter
    ≠  Phase 2 AIS release hypothesis  ≠  future likelihood
    ≠  future Bayesian posterior.

A candidate is (MMSI, release_position, release_time).  Multiple AIS
observations from the same vessel at different times produce independent
hypotheses.  Phase 2 does NOT rank, score, or weight candidates beyond a
uniform prior of 1/N.

Spatial filtering
-----------------
Uses Shapely to test whether each AIS point falls inside OR on the boundary
of the Phase-1 ``candidate_spatial_region`` GeoJSON polygon.
The boundary predicate is ``polygon.covers(point)`` which is equivalent to
``polygon.contains(point) | polygon.touches(point)`` — i.e. points exactly
on the boundary are INCLUDED.

Temporal filtering
------------------
Only AIS observations whose UTC-aware timestamps satisfy
``prefilter_start_time <= timestamp <= prefilter_end_time``
are accepted.

AIS quality
-----------
Delegates to the existing ``app.feature3.cleaning.clean_and_validate_ais``
pipeline for normalisation, deduplication, validation and quality flagging.
Records rejected by that pipeline are never promoted to candidates.

Interpolation
-------------
Phase 2 uses only OBSERVED AIS positions.  No interpolated positions are
generated or included.

Truncation
----------
If the number of valid candidates exceeds ``bayesian_max_candidates`` the
output is deterministically truncated by sorting on (mmsi, timestamp) and
taking the first N.  This is a pure COMPUTATIONAL FILTER — it does not use
Feature 3 scores, behavior anomalies, dwell, AIS gaps, or any ranking.
The output explicitly reports truncation metadata.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from shapely.geometry import Point as ShapelyPoint, shape as shapely_shape

from ..feature3.cleaning import clean_and_validate_ais
from ..feature3.schemas import AISRecord

from .config import BayesianCandidateConfig, bayesian_settings
from .schemas import (
    BayesianCandidateHypothesis,
    BayesianPrefilterResult,
    CandidateGenerationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deterministic candidate-ID generation
# ---------------------------------------------------------------------------

def _make_candidate_id(mmsi: str) -> str:
    """
    Build a deterministic candidate ID from the hypothesis MMSI.
    """
    return f"{mmsi}"


# ---------------------------------------------------------------------------
# Spatial predicate
# ---------------------------------------------------------------------------

def _build_shapely_polygon(geojson: Dict[str, Any]):
    """
    Accepts a GeoJSON Feature or raw Geometry dict and returns a Shapely
    geometry suitable for spatial filtering.

    Raises ``ValueError`` if the GeoJSON cannot be parsed.
    """
    if geojson.get("type") == "Feature":
        geom = geojson.get("geometry")
        if geom is None:
            raise ValueError("GeoJSON Feature has no 'geometry' key.")
        return shapely_shape(geom)
    return shapely_shape(geojson)


def _point_inside_or_on_boundary(polygon, lon: float, lat: float) -> bool:
    """
    Returns True when the point is inside the polygon OR exactly on its
    boundary.

    Uses ``polygon.covers(point)`` which is the union of ``contains`` and
    ``touches``.  This ensures that AIS positions coinciding with a polygon
    edge or vertex are never accidentally discarded due to floating-point
    geometry.
    """
    pt = ShapelyPoint(lon, lat)
    return bool(polygon.covers(pt))


# ---------------------------------------------------------------------------
# Temporal predicate
# ---------------------------------------------------------------------------

def _ensure_utc(dt: datetime) -> datetime:
    """Coerce a datetime to UTC.  Naive datetimes are assumed UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _in_temporal_window(ts: datetime, start: datetime, end: datetime) -> bool:
    """Inclusive check: start <= ts <= end.  All inputs must be UTC-aware."""
    return start <= ts <= end


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_candidate_hypotheses(
    prefilter_result: BayesianPrefilterResult,
    ais_source: Union[str, bytes, List[Dict[str, Any]]],
    config: Optional[BayesianCandidateConfig] = None,
) -> CandidateGenerationResult:
    """
    Generate candidate release hypotheses from a Phase-1 prefilter result
    and an AIS dataset.

    Parameters
    ----------
    prefilter_result
        Output of :class:`BayesianBackwardPrefilter.run_prefilter`.
        Must have ``role == "SEARCH_PREFILTER_ONLY"``.
    ais_source
        Raw AIS data in any format accepted by
        ``app.feature3.cleaning.clean_and_validate_ais`` (CSV string/bytes,
        list-of-dicts, etc.).
    config
        Optional override for candidate-generation settings.

    Returns
    -------
    CandidateGenerationResult
        Containing the filtered, deduplicated candidate set with uniform
        priors and explicit truncation metadata.
    """
    # ------------------------------------------------------------------
    # 0. Validate prefilter semantics
    # ------------------------------------------------------------------
    if prefilter_result.role != "SEARCH_PREFILTER_ONLY":
        raise ValueError(
            f"prefilter_result.role must be 'SEARCH_PREFILTER_ONLY', "
            f"got '{prefilter_result.role}'."
        )

    cfg = config or bayesian_settings.candidate

    # ------------------------------------------------------------------
    # 1. Parse spatial region
    # ------------------------------------------------------------------
    polygon = _build_shapely_polygon(prefilter_result.candidate_spatial_region)

    # ------------------------------------------------------------------
    # 2. Parse temporal window (UTC-aware, inclusive)
    # ------------------------------------------------------------------
    t_start = _ensure_utc(prefilter_result.prefilter_start_time)
    t_end = _ensure_utc(prefilter_result.prefilter_end_time)

    # ------------------------------------------------------------------
    # 3. Clean & validate AIS using existing Feature 3 pipeline
    # ------------------------------------------------------------------
    cleaned_records, audit_stats = clean_and_validate_ais(ais_source)

    # ------------------------------------------------------------------
    # 4. Filter: spatial + temporal & Group by MMSI
    # ------------------------------------------------------------------
    # Map MMSI -> list of valid AIS observations
    mmsi_groups: Dict[str, List[AISRecord]] = {}

    import sys
    print(f"CAND_GEN DEBUG: Pre-filter start time: {t_start}, end time: {t_end}", file=sys.stderr)
    print(f"CAND_GEN DEBUG: Bounding Box GeoJSON: {prefilter_result.candidate_spatial_region}", file=sys.stderr)

    for rec in cleaned_records:
        rec_ts = _ensure_utc(rec.timestamp)

        # Temporal gate
        t_pass = _in_temporal_window(rec_ts, t_start, t_end)
        if not t_pass:
            print(f"CAND_GEN DEBUG: FAIL TEMPORAL -> MMSI {rec.mmsi} at {rec_ts}", file=sys.stderr)
            continue

        # Spatial gate (boundary-inclusive)
        s_pass = _point_inside_or_on_boundary(polygon, rec.longitude, rec.latitude)
        if not s_pass:
            print(f"CAND_GEN DEBUG: FAIL SPATIAL -> MMSI {rec.mmsi} at {rec.latitude},{rec.longitude}", file=sys.stderr)
            continue

        if rec.mmsi not in mmsi_groups:
            mmsi_groups[rec.mmsi] = []
            
        # Add to group
        mmsi_groups[rec.mmsi].append(rec)
        
    valid_hypotheses: List[BayesianCandidateHypothesis] = []
    
    # ------------------------------------------------------------------
    # 5. Build one candidate hypothesis per MMSI
    # ------------------------------------------------------------------
    for mmsi, obs_list in mmsi_groups.items():
        # Sort observations chronologically
        obs_list.sort(key=lambda x: _ensure_utc(x.timestamp))
        
        # Determine deduplication/uniqueness by converting to a string repr
        unique_obs = []
        seen_reprs = set()
        for obs in obs_list:
            repr_str = f"{_ensure_utc(obs.timestamp).isoformat()}_{obs.latitude:.6f}_{obs.longitude:.6f}"
            if repr_str not in seen_reprs:
                seen_reprs.add(repr_str)
                unique_obs.append(obs)

        if not unique_obs:
            continue

        # First valid chronologically sorted observation used for legacy fields
        first_obs = unique_obs[0]
        first_ts = _ensure_utc(first_obs.timestamp)
        cid = _make_candidate_id(mmsi)

        valid_hypotheses.append(
            BayesianCandidateHypothesis(
                candidate_id=cid,
                mmsi=mmsi,
                release_position={
                    "latitude": first_obs.latitude,
                    "longitude": first_obs.longitude,
                },
                release_time=first_ts,
                prior_probability=0.0,  # placeholder, assigned below
                interpolation_status="OBSERVED",
                data_quality_flags=list(first_obs.quality_flags),
                vessel_name=first_obs.vessel_name,
                vessel_type=first_obs.vessel_type,
                flag=first_obs.flag,
                observations=unique_obs
            )
        )

    # ------------------------------------------------------------------
    # 5b. Sort deterministically for reproducibility & truncation
    # ------------------------------------------------------------------
    valid_hypotheses.sort(key=lambda h: (h.mmsi, h.release_time))

    total_valid = len(valid_hypotheses)
    max_candidates = cfg.bayesian_max_candidates

    # ------------------------------------------------------------------
    # 6. Truncation
    # ------------------------------------------------------------------
    truncated = total_valid > max_candidates
    if truncated:
        returned = valid_hypotheses[:max_candidates]
        truncation_strategy = "DETERMINISTIC_SORT_MMSI_TIMESTAMP"
        prior_mode = "UNIFORM_OVER_RETURNED_CANDIDATES"
    else:
        returned = valid_hypotheses
        truncation_strategy = None
        prior_mode = "UNIFORM"

    # ------------------------------------------------------------------
    # 7. Assign uniform prior over returned set
    # ------------------------------------------------------------------
    n = len(returned)
    if n > 0:
        uniform_prior = 1.0 / n
        for h in returned:
            h.prior_probability = uniform_prior

    # ------------------------------------------------------------------
    # 8. Build result
    # ------------------------------------------------------------------
    return CandidateGenerationResult(
        prefilter_role="SEARCH_PREFILTER_ONLY",
        candidate_count=n,
        total_valid_candidates=total_valid,
        candidate_limit=max_candidates,
        truncated=truncated,
        truncation_strategy=truncation_strategy,
        prior_mode=prior_mode,
        prior_candidate_count=n,
        hypothesis_space_truncated=truncated,
        candidates=returned,
        ais_audit=audit_stats,
    )
