import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_serializer

from app.feature2.schemas.input_schema import SlickDetectionInput
from app.feature3.schemas import Feature2OriginContext, AISRecord


class BayesianPrefilterResult(BaseModel):
    """
    Result of the Phase 1 Bayesian short backward prefilter.
    
    IMPORTANT: This is a search-region/time reduction only.
    It does NOT represent a final origin, confirmed origin, 
    or most probable source.
    """
    role: Literal["SEARCH_PREFILTER_ONLY"] = Field(
        default="SEARCH_PREFILTER_ONLY",
        description="Explicitly marks this as a search-area reducer, not a final attribution."
    )
    
    observation_time: datetime = Field(
        ..., 
        description="Observation timestamp T0 (UTC)."
    )
    prefilter_start_time: datetime = Field(
        ..., 
        description="Earliest time in the backward prefilter search window (UTC)."
    )
    prefilter_end_time: datetime = Field(
        ..., 
        description="Latest time in the backward prefilter search window (UTC). Usually close to T0."
    )
    backward_horizon_hours: float = Field(
        ..., 
        description="The horizon in hours configured for this prefilter run (e.g. 12.0)."
    )
    
    candidate_spatial_region: Dict[str, Any] = Field(
        ...,
        description="GeoJSON representation of the candidate search corridor/region."
    )
    
    # We can include diagnostic info, but avoid huge payloads
    active_particle_count: int = Field(
        ..., 
        description="Number of particles retained at the end of the backward prefilter run."
    )


# ---------------------------------------------------------------------------
# Phase 2 — AIS Candidate Release Hypotheses
# ---------------------------------------------------------------------------

class BayesianCandidateHypothesis(BaseModel):
    """
    A single candidate release hypothesis: (MMSI, release_position, release_time).

    A candidate is NOT merely a vessel/MMSI.  Multiple AIS observations from
    the same vessel at different times produce independent hypotheses.

    The ``candidate_id`` is deterministic and uniquely encodes the MMSI,
    release timestamp, latitude and longitude so that identical AIS records
    always map to the same identity.

    IMPORTANT — Phase 2 only assigns a uniform prior.  No likelihood,
    posterior, or attribution ranking is computed here.
    """

    candidate_id: str = Field(
        ...,
        description=(
            "Deterministic identifier encoding the vessel hypothesis. "
            "Format: '{mmsi}'."
        ),
    )
    mmsi: str = Field(..., description="Maritime Mobile Service Identity.")
    release_position: Dict[str, float] = Field(
        ...,
        description="{'latitude': float, 'longitude': float} of the release point.",
    )
    release_time: datetime = Field(
        ...,
        description="UTC timestamp of the AIS observation used as the release time.",
    )
    prior_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Initial Bayesian prior probability (uniform = 1/N).",
    )
    interpolation_status: Literal["OBSERVED", "INTERPOLATED"] = Field(
        default="OBSERVED",
        description=(
            "Whether this hypothesis derives from an actual AIS observation "
            "or from an interpolated position.  Phase 2 only produces OBSERVED."
        ),
    )
    data_quality_flags: List[str] = Field(
        default_factory=list,
        description="Quality/validation flags inherited from the AIS cleaning pipeline.",
    )
    vessel_name: Optional[str] = Field(None, description="Vessel display name if available.")
    vessel_type: Optional[str] = Field(None, description="Vessel category if available.")
    flag: Optional[str] = Field(None, description="Vessel flag state if available.")
    observations: List[AISRecord] = Field(
        default_factory=list,
        description="Complete ordered sequence of valid AIS observations for this vessel hypothesis."
    )


class CandidateGenerationResult(BaseModel):
    """
    Complete output of the Phase 2 AIS candidate-generation pipeline.

    Architectural semantics
    -----------------------
    Phase 2 answers:
        "Which AIS release hypotheses exist inside the physically bounded
         search window?"

    It does NOT answer:
        "Which vessel caused the spill?"

    The distinction is:
        Feature 2 legacy origin estimation  ≠  Phase 1 Bayesian search
        pre-filter  ≠  Phase 2 AIS release hypothesis  ≠  future
        likelihood  ≠  future Bayesian posterior.
    """

    # --- Prefilter provenance ---
    prefilter_role: Literal["SEARCH_PREFILTER_ONLY"] = Field(
        default="SEARCH_PREFILTER_ONLY",
        description="Echoed from the Phase 1 prefilter to preserve semantics.",
    )

    # --- Candidate counts ---
    candidate_count: int = Field(
        ...,
        description="Number of candidate hypotheses actually returned in this result.",
    )
    total_valid_candidates: int = Field(
        ...,
        description=(
            "Total number of candidates that passed spatial, temporal and "
            "quality filtering BEFORE any truncation was applied."
        ),
    )
    candidate_limit: Optional[int] = Field(
        None,
        description="Configured maximum number of candidates (None = unlimited).",
    )
    truncated: bool = Field(
        default=False,
        description="True if total_valid_candidates exceeded candidate_limit.",
    )
    truncation_strategy: Optional[str] = Field(
        None,
        description=(
            "The deterministic selection strategy applied when truncation occurred.  "
            "This is a COMPUTATIONAL FILTER, not scientific attribution evidence."
        ),
    )

    # --- Prior semantics ---
    prior_mode: str = Field(
        default="UNIFORM",
        description=(
            "Prior distribution mode.  'UNIFORM' = equal weight across returned candidates.  "
            "When truncation occurred this becomes 'UNIFORM_OVER_RETURNED_CANDIDATES'."
        ),
    )
    prior_candidate_count: int = Field(
        ...,
        description=(
            "Number of candidates over which the uniform prior is normalised.  "
            "Equal to candidate_count (the returned set)."
        ),
    )
    hypothesis_space_truncated: bool = Field(
        default=False,
        description=(
            "True when the returned candidates are a strict subset of the full "
            "hypothesis space.  A future Bayesian posterior computed over this set "
            "is normalised only over the returned candidates, NOT the full space."
        ),
    )

    # --- Candidates ---
    candidates: List[BayesianCandidateHypothesis] = Field(
        default_factory=list,
        description="The list of candidate release hypotheses.",
    )

    # --- AIS audit ---
    ais_audit: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit statistics from the AIS cleaning/validation pipeline.",
    )


# ---------------------------------------------------------------------------
# Phase 3C — OpenOil Forward Ensemble
# ---------------------------------------------------------------------------

class OpenOilEnsembleConfig(BaseModel):
    """Configuration for the Bayesian OpenOil forward simulation."""
    ensemble_size: int = Field(
        default=50,
        gt=0,
        description="Number of Lagrangian particles to simulate per candidate hypothesis."
    )
    time_step_seconds: int = Field(
        default=900,
        gt=0,
        description="Internal simulation time step in seconds."
    )
    time_step_output_seconds: int = Field(
        default=3600,
        gt=0,
        description="Output/history interval in seconds."
    )
    release_radius_m: float = Field(
        default=1000.0,
        ge=0.0,
        description="Initial release-footprint/position uncertainty assumption (meters)."
    )
    environment_margin_deg: float = Field(
        default=1.5,
        gt=0.0,
        description="Computational coverage margin (degrees) for the environmental query bounding box."
    )
    oil_type: str = Field(
        default="Generic Diesel",
        description="Oil type string for ADIOS DB / OpenOil initialization."
    )
    random_seed: Optional[int] = Field(
        default=None,
        description="Optional seed for reproducible dispersion."
    )


class ParticleState(BaseModel):
    """Final state of a single Lagrangian particle at observation time."""
    longitude: float
    latitude: float
    status: str
    original_status_code: int
    mass_oil_kg: Optional[float] = None
    mass_evaporated_kg: Optional[float] = None
    mass_dispersed_kg: Optional[float] = None
    mass_biodegraded_kg: Optional[float] = None
    fraction_evaporated_percent: Optional[float] = None
    water_fraction_percent: Optional[float] = None
    density_kg_m3: Optional[float] = None
    viscosity_m2_s: Optional[float] = None


class WeatheringSummary(BaseModel):
    """Aggregate weathering metrics across the ensemble."""
    mean_mass_oil_kg: Optional[float] = None
    mean_fraction_evaporated_percent: Optional[float] = None
    mean_density_kg_m3: Optional[float] = None


class OpenOilSimulationResult(BaseModel):
    """Complete result of a Bayesian OpenOil forward ensemble for one candidate."""
    candidate_id: str
    mmsi: str
    status: Literal[
        "SUCCESS", 
        "SUCCESS_WITH_WARNINGS",
        "VALIDATION_ERROR", 
        "ENVIRONMENTAL_DATA_INCOMPLETE",
        "OPENDRIFT_INITIALIZATION_ERROR",
        "OPENDRIFT_READER_ERROR",
        "OPENDRIFT_SIMULATION_ERROR",
        "OUTPUT_EXTRACTION_ERROR"
    ]
    
    release_timestamp: datetime
    requested_observation_timestamp: datetime
    actual_final_timestamp: Optional[datetime] = None
    simulation_duration_hours: Optional[float] = None
    final_time_offset_seconds: Optional[float] = None
    
    ensemble_size_requested: int
    ensemble_size_returned: Optional[int] = None
    active_particle_count: Optional[int] = None
    stranded_particle_count: Optional[int] = None
    other_terminal_particle_count: Optional[int] = None
    
    final_particle_states: List[ParticleState] = Field(default_factory=list)
    weathering_summary: Optional[WeatheringSummary] = None
    
    environmental_metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 4 — Bayesian Likelihood
# ---------------------------------------------------------------------------

class ObservationLikelihoodDiagnostics(BaseModel):
    """Diagnostics for a single observation likelihood calculation."""
    spill_id: str
    observation_time: datetime
    simulation_actual_final_time: Optional[datetime] = None
    final_time_offset_seconds: Optional[float] = None
    observation_time_tolerance_seconds: float
    
    temporal_compatible: bool
    
    total_particles: int
    active_particles: int
    stranded_particles: int
    other_terminal_particles: int
    valid_particles_used: int
    excluded_status_particles: int
    
    compatible_count: Optional[int] = None
    compatible_fraction: Optional[float] = None
    
    gaussian_sigma_m: Optional[float] = None
    
    likelihood: float
    log_likelihood: Optional[float] = None
    error_message: Optional[str] = None

    @field_serializer('log_likelihood')
    def serialize_inf(self, v: Optional[float], _info) -> Optional[float]:
        if v is not None and (math.isinf(v) or math.isnan(v)):
            return None
        return v


class CandidateLikelihood(BaseModel):
    """Result of Phase 4 Bayesian Likelihood for one candidate."""
    candidate_id: str
    likelihood_mode: Literal["threshold", "gaussian"]
    
    likelihood: float
    log_likelihood: Optional[float] = None
    
    observation_count: int
    per_observation_diagnostics: List[ObservationLikelihoodDiagnostics] = Field(default_factory=list)
    
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer('log_likelihood')
    def serialize_inf(self, v: Optional[float], _info) -> Optional[float]:
        if v is not None and (math.isinf(v) or math.isnan(v)):
            return None
        return v


# ---------------------------------------------------------------------------
# Phase 5 — Bayesian Posterior
# ---------------------------------------------------------------------------

class CandidatePosterior(BaseModel):
    """Normalized Bayesian posterior probability for a single candidate."""
    candidate_id: str
    mmsi: str
    release_latitude: float
    release_longitude: float
    release_timestamp: datetime
    
    prior: float
    likelihood: float
    log_likelihood: Optional[float] = None
    
    unnormalized_log_weight: Optional[float] = None
    posterior_probability: float
    
    likelihood_mode: Literal["threshold", "gaussian"]
    evaluation_status: str
    warnings: List[str] = Field(default_factory=list)

    @field_serializer('log_likelihood', 'unnormalized_log_weight')
    def serialize_inf(self, v: Optional[float], _info) -> Optional[float]:
        if v is not None and (math.isinf(v) or math.isnan(v)):
            return None
        return v


class BayesianPosteriorResult(BaseModel):
    """Complete output of the Phase 5 Bayesian Posterior computation."""
    status: Literal["SUCCESS", "NO_POSITIVE_LIKELIHOOD", "VALIDATION_ERROR"]
    
    hypothesis_space_truncated: bool
    candidate_limit: Optional[int] = None
    total_valid_candidates: Optional[int] = None
    returned_candidate_count: int
    prior_mode: str
    
    evaluated_candidate_count: int
    positive_likelihood_candidate_count: int
    
    normalization_constant: float
    log_normalization_constant: Optional[float] = None
    posterior_sum: float
    
    posteriors: List[CandidatePosterior] = Field(default_factory=list)
    
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer('log_normalization_constant')
    def serialize_inf(self, v: Optional[float], _info) -> Optional[float]:
        if v is not None and (math.isinf(v) or math.isnan(v)):
            return None
        return v


# ---------------------------------------------------------------------------
# Phase 6 — Physics-Aware Confidence
# ---------------------------------------------------------------------------

class ConfidenceDiagnostic(BaseModel):
    """A specific measurable diagnostic for confidence evaluation."""
    metric_name: str
    value: Optional[float] = None
    unit: str
    status: Literal["MEASURED", "UNAVAILABLE", "NOT_APPLICABLE"]


class ConfidenceFlag(BaseModel):
    """A flag describing a confidence-affecting condition."""
    flag_name: str
    description: str
    severity: Literal["QUALIFICATION", "WARNING", "CRITICAL"]
    triggered: bool
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    threshold_status: Literal["ESTABLISHED", "THRESHOLD_REQUIRES_CALIBRATION", "NOT_APPLICABLE"] = "NOT_APPLICABLE"


class PhysicsAwareConfidence(BaseModel):
    """Phase 6 confidence qualification for a candidate."""
    candidate_id: str
    
    # STRICTLY READ-ONLY from Phase 5
    posterior_probability: float
    
    confidence_level: Literal["INDETERMINATE"] = "INDETERMINATE"
    
    diagnostics: List[ConfidenceDiagnostic] = Field(default_factory=list)
    flags: List[ConfidenceFlag] = Field(default_factory=list)
    
    hypothesis_space_truncated: bool
    candidate_limit: Optional[int] = None
    total_valid_candidates: Optional[int] = None
    returned_candidate_count: Optional[int] = None
    prior_mode: Optional[str] = None
    
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Final Attribution & Reporting
# ---------------------------------------------------------------------------

class SupplementalDeterministicEvidence(BaseModel):
    """Container for Feature 3 deterministic metrics to ensure mathematical isolation."""
    feature3_overall_score: Optional[float] = Field(None, description="Deterministic 0-100 score from Feature 3.")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Raw Feature 3 metrics.")
    risk_class: Optional[str] = None


class FinalCandidateRecord(BaseModel):
    """
    Unified read-only representation of a candidate's evaluated state.
    """
    candidate_id: str
    mmsi: str
    release_latitude: float
    release_longitude: float
    release_timestamp: datetime
    
    # Bayesian State (Phase 5)
    evaluation_status: str
    prior_probability: float
    likelihood: float
    posterior_probability: float
    
    # Physics Confidence (Phase 6)
    confidence_level: Literal["INDETERMINATE"]
    confidence_diagnostics: List[ConfidenceDiagnostic] = Field(default_factory=list)
    confidence_flags: List[ConfidenceFlag] = Field(default_factory=list)
    
    # Feature 3
    supplemental_deterministic_evidence: SupplementalDeterministicEvidence


class AttributionProvenance(BaseModel):
    """Provenance data spanning the pipeline."""
    environmental_data_provider: Optional[str] = None
    simulation_engine: Optional[str] = None
    bayesian_configuration: Dict[str, Any] = Field(default_factory=dict)
    truncation_metadata: Dict[str, Any] = Field(default_factory=dict)


class FinalAttributionReport(BaseModel):
    """
    Machine-readable read-only aggregation of Phases 1-6 and Feature 3.
    Does NOT invent attribution decisions, winners, or composite scores.
    """
    spill_id: str
    report_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    status: Literal["SUCCESS", "NO_POSITIVE_LIKELIHOOD", "VALIDATION_ERROR"]
    
    hypothesis_space_truncated: bool
    candidate_limit: Optional[int] = None
    total_valid_candidates: Optional[int] = None
    returned_candidate_count: int
    evaluated_candidate_count: int
    unavailable_candidate_count: int
    unavailable_candidate_ids: List[str] = Field(default_factory=list)
    prior_mode: str
    
    # Phase 5 Normalization exactly preserved
    normalization_constant: float
    log_normalization_constant: Optional[float] = None
    posterior_sum: float
    
    candidates: List[FinalCandidateRecord] = Field(default_factory=list)
    
    provenance: AttributionProvenance
    
    limitations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    @field_serializer('log_normalization_constant')
    def serialize_inf(self, v: Optional[float], _info) -> Optional[float]:
        if v is not None and (math.isinf(v) or math.isnan(v)):
            return None
        return v


class FinalAttributionRequest(BaseModel):
    """Payload to request final attribution aggregation."""
    spill_id: str
    posterior_result: BayesianPosteriorResult
    confidence_results: List[PhysicsAwareConfidence]
    feature3_response: Optional[Any] = None  # Using Any to avoid circular import with Feature3AttributionResponse
    provenance: AttributionProvenance


class BayesianPipelineRequest(BaseModel):
    """Payload to initiate the full E2E Bayesian Attribution Pipeline."""
    spill_data: SlickDetectionInput
    ais_data: List[Dict[str, Any]] = Field(
        ...,
        description="List of raw AIS telemetry records in dict format."
    )
    feature2_context: Optional[Feature2OriginContext] = Field(
        default=None,
        description="Optional pre-computed deterministic Feature 2 origin context for Feature 3 integration. If not provided, Feature 3 is skipped."
    )
    bayesian_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional config overrides for the pipeline."
    )
