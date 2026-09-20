"""
Phase 2 — AIS Candidate Release Hypothesis Generation Tests.

This test suite verifies the behaviours specified for Phase 2, particularly:
1. One MMSI = one candidate hypothesis, preserving all valid observations.
2. Spatial/temporal filtering correctly accepts/rejects individual observations.
3. Legacy fields (release_latitude/longitude/time) use the first valid observation.
4. SOG/COG preservation.
"""

import math
import pytest
from datetime import datetime, timedelta, timezone

from app.bayesian.candidate_generator import (
    generate_candidate_hypotheses,
    _make_candidate_id,
    _point_inside_or_on_boundary,
    _build_shapely_polygon,
    _ensure_utc,
)
from app.bayesian.config import BayesianCandidateConfig
from app.bayesian.schemas import (
    BayesianCandidateHypothesis,
    BayesianPrefilterResult,
    CandidateGenerationResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEARCH_POLYGON_GEOJSON = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [10.0, 55.0],
                [12.0, 55.0],
                [12.0, 57.0],
                [10.0, 57.0],
                [10.0, 55.0],
            ]
        ],
    },
}

T0 = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
T_START = T0 - timedelta(hours=12)
T_END = T0

def _make_prefilter(polygon=None, start=None, end=None, obs=None):
    return BayesianPrefilterResult(
        role="SEARCH_PREFILTER_ONLY",
        observation_time=obs or T0,
        prefilter_start_time=start or T_START,
        prefilter_end_time=end or T_END,
        backward_horizon_hours=12.0,
        candidate_spatial_region=polygon or SEARCH_POLYGON_GEOJSON,
        active_particle_count=100,
    )

def _ais(mmsi, lat, lon, ts, sog=None, cog=None):
    return {
        "mmsi": mmsi,
        "latitude": lat,
        "longitude": lon,
        "timestamp": ts.isoformat() if isinstance(ts, datetime) else ts,
        "sog": sog,
        "cog": cog,
    }


# ===================================================================
# TEST 1 & 2 — Grouping and Observation Retention
# ===================================================================

class TestGrouping:
    def test_10_observations_1_mmsi_is_1_candidate(self):
        """TEST 1: 10 AIS observations, 1 MMSI -> exactly 1 candidate, 10 observations retained."""
        pf = _make_prefilter()
        ais = []
        for i in range(10):
            ts = T_START + timedelta(hours=1, minutes=i*5)
            ais.append(_ais("111111111", 56.0, 11.0, ts))
            
        result = generate_candidate_hypotheses(pf, ais)
        assert result.candidate_count == 1
        
        candidate = result.candidates[0]
        assert candidate.mmsi == "111111111"
        assert len(candidate.observations) == 10

    def test_multiple_mmsis_are_grouped_correctly(self):
        """TEST 2: 10 observations MMSI A, 20 MMSI B, 5 MMSI C -> exactly 3 candidates."""
        pf = _make_prefilter()
        ais = []
        for i in range(10): ais.append(_ais("AAA", 56.0, 11.0, T_START + timedelta(hours=1, minutes=i)))
        for i in range(20): ais.append(_ais("BBB", 56.0, 11.0, T_START + timedelta(hours=1, minutes=i)))
        for i in range(5): ais.append(_ais("CCC", 56.0, 11.0, T_START + timedelta(hours=1, minutes=i)))
            
        result = generate_candidate_hypotheses(pf, ais)
        assert result.candidate_count == 3
        
        c_A = next(c for c in result.candidates if c.mmsi == "AAA")
        c_B = next(c for c in result.candidates if c.mmsi == "BBB")
        c_C = next(c for c in result.candidates if c.mmsi == "CCC")
        
        assert len(c_A.observations) == 10
        assert len(c_B.observations) == 20
        assert len(c_C.observations) == 5

# ===================================================================
# TEST 3 — Chronological sorting
# ===================================================================

class TestSorting:
    def test_observations_chronologically_sorted(self):
        """TEST 3: Verify observations are chronologically sorted."""
        pf = _make_prefilter()
        # Add out of order
        ais = [
            _ais("123", 56.0, 11.0, T_START + timedelta(hours=3)),
            _ais("123", 56.0, 11.0, T_START + timedelta(hours=1)),
            _ais("123", 56.0, 11.0, T_START + timedelta(hours=2)),
        ]
        result = generate_candidate_hypotheses(pf, ais)
        obs = result.candidates[0].observations
        
        assert obs[0].timestamp < obs[1].timestamp < obs[2].timestamp
        
        # Verify legacy fields use the first observation
        assert result.candidates[0].release_time == obs[0].timestamp

# ===================================================================
# TEST 4 & 5 — SOG/COG Preservation
# ===================================================================

class TestSogCog:
    def test_sog_cog_preserved(self):
        """TEST 4: Verify SOG/COG are preserved."""
        pf = _make_prefilter()
        ais = [_ais("123", 56.0, 11.0, T_START + timedelta(hours=1), sog=12.5, cog=180.0)]
        result = generate_candidate_hypotheses(pf, ais)
        obs = result.candidates[0].observations[0]
        assert obs.sog == 12.5
        assert obs.cog == 180.0

    def test_missing_sog_cog_remains_none(self):
        """TEST 5: Verify missing SOG/COG remain None (not 0)."""
        pf = _make_prefilter()
        ais = [_ais("123", 56.0, 11.0, T_START + timedelta(hours=1), sog=None, cog=None)]
        result = generate_candidate_hypotheses(pf, ais)
        obs = result.candidates[0].observations[0]
        assert obs.sog is None
        assert obs.cog is None

# ===================================================================
# TEST 6 — max_candidates applies to MMSIs
# ===================================================================

class TestMaxCandidates:
    def test_max_candidates_applies_to_mmsi(self):
        """TEST 6: Verify max_candidates applies to MMSIs, not rows."""
        pf = _make_prefilter()
        cfg = BayesianCandidateConfig(bayesian_max_candidates=2)
        
        ais = []
        # 3 unique MMSIs, 5 rows each
        for mmsi in ["A", "B", "C"]:
            for i in range(5):
                ais.append(_ais(mmsi, 56.0, 11.0, T_START + timedelta(hours=1, minutes=i)))
                
        result = generate_candidate_hypotheses(pf, ais, config=cfg)
        
        # 3 MMSIs total, limit 2
        assert result.total_valid_candidates == 3
        assert result.candidate_count == 2
        assert result.truncated is True
        
        # The candidates that survived should still have 5 observations each
        assert len(result.candidates[0].observations) == 5
        assert len(result.candidates[1].observations) == 5

# ===================================================================
# TEST 11 — No-candidate case
# ===================================================================

class TestNoCandidates:
    def test_empty_ais_yields_zero_candidates(self):
        """TEST 11: Verify no-candidate case."""
        pf = _make_prefilter()
        result = generate_candidate_hypotheses(pf, [])
        assert result.candidate_count == 0

    def test_all_outside_yields_zero_candidates(self):
        pf = _make_prefilter()
        ais = [_ais("123", 90.0, 90.0, T_START + timedelta(hours=1))] # Outside spatial
        result = generate_candidate_hypotheses(pf, ais)
        assert result.candidate_count == 0

# ===================================================================
# TEST 13 — Arbitrary MMSIs
# ===================================================================

class TestArbitraryMMSIs:
    def test_arbitrary_mmsis_and_counts(self):
        """TEST 13: Verify arbitrary MMSIs and arbitrary observation counts."""
        pf = _make_prefilter()
        ais = [
            _ais("RANDOM_1", 56.0, 11.0, T_START + timedelta(hours=1)),
            _ais("RANDOM_2", 56.0, 11.0, T_START + timedelta(hours=1)),
            _ais("RANDOM_2", 56.0, 11.0, T_START + timedelta(hours=2)),
        ]
        result = generate_candidate_hypotheses(pf, ais)
        assert result.candidate_count == 2
        
        mmsi_counts = {c.mmsi: len(c.observations) for c in result.candidates}
        assert mmsi_counts["RANDOM_1"] == 1
        assert mmsi_counts["RANDOM_2"] == 2
