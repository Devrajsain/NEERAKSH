# Final Attribution & Reporting — Design Specification

## 1. Existing Architecture Discovered
The current pipeline consists of strictly decoupled mathematical layers:
- **Phase 1-2**: Generates `BayesianCandidateHypothesis` entries representing distinct AIS releases. Truncation metadata is captured.
- **Phase 3C-4**: Simulates candidate releases via OpenOil and calculates Bayesian likelihoods based on SAR observations.
- **Phase 5**: Computes normalized Bayesian `CandidatePosterior`.
- **Phase 6**: Evaluates `PhysicsAwareConfidence` containing diagnostic flags (e.g. `LOW_ENSEMBLE_RETENTION`, `HYPOTHESIS_SPACE_TRUNCATED`) while explicitly isolating them from the posterior.
- **Feature 3**: Produces deterministic `VesselAttributionResult` (0-100 score) evaluating spatial/kinematic anomalies (`origin_presence`, `behavior_anomaly`).

## 2. Final Attribution Data Flow
The Final Attribution layer acts as an aggregator. It will:
1. Ingest `BayesianPosteriorResult` (Phase 5).
2. Ingest `PhysicsAwareConfidence` results (Phase 6).
3. Ingest `Feature3AttributionResponse` (Feature 3).
4. Map Feature 3 evidence to Bayesian candidates via MMSI and temporal alignment.
5. Produce a unified, machine-readable `FinalAttributionReport`.
It will **NOT** modify or recalculate any probabilities or scores.

## 3. Candidate-Level Output Design
Each evaluated candidate will be represented using:
- **Identity**: `candidate_id`, `mmsi`, `release_latitude`, `release_longitude`, `release_timestamp` (Exact preservation from Phase 2).
- **Bayesian State**: `prior`, `likelihood`, `posterior_probability`.
- **Confidence State**: `confidence_level`, `diagnostics`, `flags`.
- **Supplemental Evidence**: Extracted relevant Feature 3 `RawEvidenceMetrics` and `overall_score`.

## 4. Posterior Interpretation
The posterior remains mathematically defined as `P(candidate | observation)`.
- **Constraint**: If `hypothesis_space_truncated == True`, the report MUST explicitly state: *"Posterior probability within the evaluated candidate hypothesis set."*
- We will strictly avoid absolute language like *"This vessel has an X% probability of causing the spill."*

## 5. Same-MMSI Multi-Hypothesis Treatment
**Design**: Hypotheses belonging to the same MMSI (but different release times/positions) will remain **distinct and separate** in the final report.
**Reasoning**: A valid vessel-level marginalization `P(MMSI | Y) = SUM P(hypothesis | Y)` requires all hypotheses to be collectively exhaustive and mutually exclusive. Given truncation and AIS gaps, this assumption is unsafe. Vessel-level aggregation is deferred to future scientific approval.

## 6. Truncated Hypothesis-Space Semantics
The final report schema will prominently surface at the root level:
- `hypothesis_space_truncated`
- `candidate_limit`
- `total_valid_candidates`
- `returned_candidate_count`
- `evaluated_candidate_count`
If truncated, a mandatory root-level limitation warning is appended to the report.

## 7. Confidence Presentation
- `confidence_level` will remain `INDETERMINATE` as established in Phase 6.
- It will NOT be reinterpreted or overridden as LOW/MEDIUM/HIGH in the final layer.
- `confidence_flags` (e.g., `HIGH_SPATIAL_DISPERSION`, `TEMPORAL_MISMATCH`) will be exposed directly as qualification tags on the candidate.

## 8. Zero / Unavailable Cases
- **Zero Likelihood**: If the Phase 5 result is `NO_POSITIVE_LIKELIHOOD`, the final report status is `NO_POSITIVE_LIKELIHOOD`. No candidates are assigned posterior probabilities. No "winner" is selected.
- **Simulation Failure**: Candidates failing OpenOil (e.g., environmental data incomplete) receive an `EVALUATION_UNAVAILABLE` tag. They do not receive a low posterior; they are excluded from the normalization space.
- **Missing Coverage**: Exposed via `evaluated_candidate_count` vs `returned_candidate_count`.

## 9. Feature 3 Separation
Feature 3 results will be nested under a `supplemental_deterministic_evidence` block within the candidate representation.
**Mathematical Isolation**:
- Feature 3 scores (0-100) are NOT fed into likelihoods or priors.
- No composite weighted score will be generated.
- Feature 3 fields (like `dwell_minutes_inside_zone`, `closest_approach_distance_km`) will be exposed purely for explanatory forensics.

## 10. Evidence Traceability
Every value in the final report maps strictly to an upstream phase:
- *Posterior* -> Phase 5
- *Temporal Compatibility* -> Phase 4
- *Stranding/Retention* -> Phase 3C / Phase 6
- *Deterministic Kinematics* -> Feature 3
No narrative generation will be employed to invent causal links between these decoupled pipelines.

## 11. Provenance Design
The report will include a `provenance` block aggregating:
- `environmental_data_provider` (e.g., Copernicus).
- `simulation_engine` (e.g., OpenDrift version).
- `bayesian_configuration` (e.g., `ensemble_size`, `gaussian_sigma_m`, `prior_mode`).
- `truncation_metadata`.

## 12. Proposed API Contract
**Endpoint**: `POST /api/v1/attribution/bayesian_final_report`
**Request Schema**: 
- Accepts `spill_id` and parameters to fetch prior Phase 1-6 and Feature 3 results from the database.
**Response Schema**: `FinalAttributionReport` (Structured JSON).
**Semantics**: Strictly read-only aggregation. Returns HTTP 200 on success. 

## 13. Proposed Frontend Contract
The frontend should construct views based on these distinct JSON blocks:
1. **Attribution Summary**: Global status, truncation warnings.
2. **Posterior Distribution**: Visualization of probabilities (candidates MAY be sorted by posterior descending, provided it is clearly labeled as a "Presentation Sort Order" and not an accusatory ranking).
3. **Candidate Evidence Breakdown**: Detailed view per candidate isolating Bayesian likelihoods, Phase 6 physics confidence, and Feature 3 deterministic scores.
4. **Data Provenance & Limitations**.

## 14. Proposed Report / Export Contract
- **Primary Export**: Machine-readable JSON.
- **Secondary (Future)**: A generated PDF/HTML report that visually maps to the Frontend Contract, preserving the distinct separation of Bayesian probability and physics confidence without inventing conclusive narratives.

## 15. Decision-Rule Status
**Finding**: There is currently NO scientifically approved rule for declaring "attribution established" or identifying a "winner".
**Resolution**: The design DOES NOT invent a decision rule. The layer serves solely as an evidence presentation mechanism.

## 16. Required Tests
1. Single candidate execution.
2. Multiple candidates execution.
3. Multiple hypotheses for the same MMSI (ensure distinct preservation).
4. Similar posterior candidates.
5. Truncated hypothesis space (ensure warnings map correctly).
6. No positive likelihood (`NO_POSITIVE_LIKELIHOOD` handling).
7. Unavailable candidate evaluation handling.
8. INDETERMINATE confidence pass-through.
9. Confidence flags mapping.
10. Posterior immutability (input == output).
11. Feature 3 structural isolation.
12. Provenance preservation.
13. Machine-readable API schema validation.
14. Assertion that `winner` or `top_candidate` fields do not exist.
15. Assertion that no new attribution score is computed.

## 17. Open Scientific Questions
1. How and when should vessel-level marginalization (MMSI grouping) be formally introduced?
2. What calibration thresholds must be reached to move `confidence_level` from `INDETERMINATE` to actionable categories?

## 18. Items Requiring Human Approval
- Final API endpoint naming convention.
- UI mockups validating the separation of Bayesian posterior vs. Feature 3 scores.
- Endorsement of the `INDETERMINATE` confidence display for end-users.
