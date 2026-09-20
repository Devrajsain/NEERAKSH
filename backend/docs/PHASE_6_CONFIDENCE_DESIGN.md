# Phase 6 — Physics-Aware Confidence Design Specification

## 1. Current Available Diagnostics
Based on the inspection of the pipeline up to Phase 5, the following mathematically explicit diagnostics are exposed:

- **Phase 2 (Candidate Generation)**: `candidate_limit`, `total_valid_candidates`, `hypothesis_space_truncated`.
- **Phase 3C (OpenOil)**: `ensemble_size_requested`, `active_particle_count`, `stranded_particle_count`, `other_terminal_particle_count`, `final_time_offset_seconds`, `simulation_duration_hours`.
- **Phase 4 (Likelihood)**: `temporal_compatible`, `compatible_count`, `excluded_status_particles`.
- **Feature 2 (Uncertainty)**: `spread_radius_m` (spatial dispersion metric).

## 2. Proposed Confidence Factors

### A. Ensemble Retention
- **Physical Meaning**: Fraction of particles that completed the simulation actively versus terminating early (stranded/beach, evaporation, errors).
- **Exact Input**: `active_particle_count` / `ensemble_size_requested` (from Phase 3C).
- **Unit**: Dimensionless fraction [0.0, 1.0].
- **Calculation**: `fraction = active_particle_count / ensemble_size_requested`.
- **Interpretation**: Higher is better. Retaining more active particles indicates a well-behaved offshore simulation, maintaining statistical power.
- **Missing Data**: If `ensemble_size_requested` is 0 or unavailable, set to `UNAVAILABLE`.

### B. Coastline Interaction
- **Physical Meaning**: Fraction of the ensemble that stranded on the coastline.
- **Exact Input**: `stranded_particle_count` / `ensemble_size_requested` (from Phase 3C).
- **Unit**: Dimensionless fraction [0.0, 1.0].
- **Calculation**: `fraction = stranded_particle_count / ensemble_size_requested`.
- **Interpretation**: Lower is better. High interaction heavily relies on the resolution and quality of the landmask and wave interactions which contain high physical uncertainty.
- **Missing Data**: If `stranded_particle_count` is None, set to `UNAVAILABLE`.

### C. Temporal Mismatch
- **Physical Meaning**: Absolute temporal difference between the observation and the final valid simulation timestep.
- **Exact Input**: `abs(final_time_offset_seconds)` (from Phase 3C / 4).
- **Unit**: Seconds.
- **Calculation**: `abs(final_time_offset_seconds)`.
- **Interpretation**: Lower is better. Absolute offsets closer to 0 imply perfect temporal alignment with the SAR satellite pass.
- **Missing Data**: If unavailable, use `0` assuming perfect alignment natively achieved.

### D. Spatial Dispersion
- **Physical Meaning**: Statistical spatial variance/spread of the oil plume.
- **Exact Input**: `spread_radius_m` from Feature 2's `EnsembleStepStatistics`.
- **Unit**: Meters.
- **Calculation**: Direct measurement of `spread_radius_m` at the final timestep.
- **Interpretation**: Lower is better, though extreme cohesion could also imply issues. Very large spread reduces geometric confidence in specific localization.
- **Missing Data**: `UNAVAILABLE`.

## 3. Confidence Flags & Thresholds

We propose the following flags. Note that all thresholds are **THRESHOLD_REQUIRES_CALIBRATION**.

- **`LOW_ENSEMBLE_RETENTION`**
  - **Trigger**: Ensemble Retention < 0.5 (50%).
  - **Severity**: WARNING.

- **`STRONG_COASTLINE_INTERACTION`**
  - **Trigger**: Coastline Interaction > 0.2 (20%).
  - **Severity**: WARNING.

- **`TEMPORAL_MISMATCH`**
  - **Trigger**: `temporal_compatible == False` (driven by Phase 4's `observation_time_tolerance_seconds`).
  - **Severity**: CRITICAL.

- **`HIGH_SPATIAL_DISPERSION`**
  - **Trigger**: `spread_radius_m > 5000` (5 km).
  - **Severity**: WARNING.

- **`HYPOTHESIS_SPACE_TRUNCATED`**
  - **Trigger**: `hypothesis_space_truncated == True`.
  - **Severity**: QUALIFICATION. (Explicitly denotes that the posterior applies only to the subset returned).

## 4. Missing Metrics (Not Currently Available)

The following conceptually valid metrics are NOT currently defensible due to missing pipeline exposure:
1. **Weathering Sensitivity**: OpenOil provides raw weathering quantities (`mass_evaporated`, etc.) but NOT a sensitivity gradient. We cannot declare confidence based merely on high evaporation without running multi-oil permutations to measure actual sensitivity.
2. **AIS Interpolation Uncertainty**: Phase 2 currently hardcodes `interpolation_status = "OBSERVED"` for all hypotheses.
3. **Environmental Completeness**: The provider schemas do not explicitly export fractional % coverage (e.g. "95% of grid cells were successfully retrieved"). 

## 5. Missing Data & Environmental Failure Handling
- **Environmental Failure**: If a simulation strictly fails (e.g., `ENVIRONMENTAL_DATA_INCOMPLETE`), it is assigned an `evaluation_status="EVALUATION_UNAVAILABLE"`. It does NOT receive "LOW" confidence. It is mathematically excluded.
- **Missing Diagnostics**: If a diagnostic metric cannot be evaluated, its flag must be explicitly marked `status="NOT_APPLICABLE"` or `status="UNAVAILABLE"`, differentiating it from a successfully measured "good" or "concerning" state.

## 6. Proposed Schemas

```python
class ConfidenceDiagnostic(BaseModel):
    metric_name: str
    value: Optional[float] = None
    unit: str
    status: Literal["MEASURED", "UNAVAILABLE", "NOT_APPLICABLE"]

class ConfidenceFlag(BaseModel):
    flag_name: str
    description: str
    severity: Literal["QUALIFICATION", "WARNING", "CRITICAL"]
    triggered: bool

class PhysicsAwareConfidence(BaseModel):
    candidate_id: str
    posterior_probability: float  # STRICTLY READ-ONLY
    
    confidence_level: Literal["INDETERMINATE"]  # Avoiding HIGH/LOW until scientific validation is approved
    
    diagnostics: List[ConfidenceDiagnostic] = Field(default_factory=list)
    confidence_flags: List[ConfidenceFlag] = Field(default_factory=list)
    
    hypothesis_space_truncated: bool
    warnings: List[str] = Field(default_factory=list)
```

## 7. Explicit Separation from Posterior
- The `posterior_probability` field in `PhysicsAwareConfidence` is populated directly from the Phase 5 output.
- It is strictly **READ-ONLY**.
- We mathematically forbid: `confidence = posterior * weight`.
- We mathematically forbid: using Phase 3 Features (Origin Presence, Dwell Time) to modify the Bayesian posterior under the guise of "confidence".

## 8. Implementation Risks & Required Approvals
- **Risk**: Stakeholders may wrongly interpret `posterior_probability = 0.9` with `confidence_level = LOW` as a contradiction. Clear UI/UX messaging must accompany Phase 6 output to explain that the model is confident in the candidate relative to peers, but the absolute environment simulation implies high error margins.
- **Required Scientific Approval**: Thresholds for `LOW_ENSEMBLE_RETENTION` (0.5), `STRONG_COASTLINE_INTERACTION` (0.2), and `HIGH_SPATIAL_DISPERSION` (5000m) require scientific calibration before Phase 6 can be merged into production.
