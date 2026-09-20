from typing import List, Dict, Optional, Any
from app.bayesian.schemas import (
    BayesianPosteriorResult,
    CandidatePosterior,
    CandidateGenerationResult,
    OpenOilSimulationResult,
    CandidateLikelihood,
    PhysicsAwareConfidence,
    ConfidenceDiagnostic,
    ConfidenceFlag
)
from app.feature2.schemas.simulation_schema import EnsembleStepStatistics

class PhysicsAwareConfidenceEngine:
    """Engine for Phase 6 Physics-Aware Confidence computation."""

    def compute_confidence(
        self,
        posterior_result: BayesianPosteriorResult,
        candidates_result: CandidateGenerationResult,
        simulations: List[OpenOilSimulationResult],
        likelihoods: List[CandidateLikelihood],
        ensemble_stats: Dict[str, Optional[EnsembleStepStatistics]]
    ) -> List[PhysicsAwareConfidence]:
        """
        Computes physics-aware confidence for each candidate without modifying posteriors.
        
        Args:
            posterior_result: The output from Phase 5 (contains read-only posteriors).
            candidates_result: The output from Phase 2 (prior and metadata).
            simulations: The output from Phase 3C (OpenOil results).
            likelihoods: The output from Phase 4 (likelihood results).
            ensemble_stats: Feature 2 spatial dispersion statistics mapping candidate_id -> EnsembleStepStatistics.
        """
        sim_map = {s.candidate_id: s for s in simulations}
        lh_map = {l.candidate_id: l for l in likelihoods}
        
        results = []
        
        for posterior in posterior_result.posteriors:
            candidate_id = posterior.candidate_id
            sim = sim_map.get(candidate_id)
            lh = lh_map.get(candidate_id)
            stats = ensemble_stats.get(candidate_id)
            
            conf = self._evaluate_candidate(
                posterior=posterior,
                posterior_metadata=posterior_result,
                candidates_result=candidates_result,
                sim=sim,
                lh=lh,
                stats=stats
            )
            results.append(conf)
            
        return results

    def _evaluate_candidate(
        self,
        posterior: CandidatePosterior,
        posterior_metadata: BayesianPosteriorResult,
        candidates_result: CandidateGenerationResult,
        sim: Optional[OpenOilSimulationResult],
        lh: Optional[CandidateLikelihood],
        stats: Optional[EnsembleStepStatistics]
    ) -> PhysicsAwareConfidence:
        
        diagnostics = []
        flags = []
        
        # 1. Ensemble Retention
        retention = None
        if sim and sim.ensemble_size_requested and sim.ensemble_size_requested > 0 and sim.active_particle_count is not None:
            retention = sim.active_particle_count / sim.ensemble_size_requested
            diagnostics.append(
                ConfidenceDiagnostic(
                    metric_name="ensemble_retention_fraction",
                    value=retention,
                    unit="fraction",
                    status="MEASURED"
                )
            )
            flags.append(
                ConfidenceFlag(
                    flag_name="LOW_ENSEMBLE_RETENTION",
                    description="Fraction of active particles is critically low.",
                    severity="WARNING",
                    triggered=(retention < 0.5),
                    metric_name="ensemble_retention_fraction",
                    metric_value=retention,
                    threshold=0.5,
                    threshold_status="THRESHOLD_REQUIRES_CALIBRATION"
                )
            )
        else:
            diagnostics.append(
                ConfidenceDiagnostic(
                    metric_name="ensemble_retention_fraction",
                    unit="fraction",
                    status="UNAVAILABLE"
                )
            )

        # 2. Coastline Interaction
        coastline_frac = None
        if sim and sim.ensemble_size_requested and sim.ensemble_size_requested > 0 and sim.stranded_particle_count is not None:
            coastline_frac = sim.stranded_particle_count / sim.ensemble_size_requested
            diagnostics.append(
                ConfidenceDiagnostic(
                    metric_name="stranded_fraction",
                    value=coastline_frac,
                    unit="fraction",
                    status="MEASURED"
                )
            )
            flags.append(
                ConfidenceFlag(
                    flag_name="STRONG_COASTLINE_INTERACTION",
                    description="Significant portion of the ensemble interacted with the coastline.",
                    severity="WARNING",
                    triggered=(coastline_frac > 0.2),
                    metric_name="stranded_fraction",
                    metric_value=coastline_frac,
                    threshold=0.2,
                    threshold_status="THRESHOLD_REQUIRES_CALIBRATION"
                )
            )
        else:
            diagnostics.append(
                ConfidenceDiagnostic(
                    metric_name="stranded_fraction",
                    unit="fraction",
                    status="UNAVAILABLE"
                )
            )
            
        # 3. Temporal Mismatch
        temporal_compatible = True
        offset = None
        if lh and lh.per_observation_diagnostics:
            # Check the first observation for temporal details
            obs_diag = lh.per_observation_diagnostics[0]
            temporal_compatible = obs_diag.temporal_compatible
            if obs_diag.final_time_offset_seconds is not None:
                offset = abs(obs_diag.final_time_offset_seconds)
                diagnostics.append(
                    ConfidenceDiagnostic(
                        metric_name="temporal_mismatch_seconds",
                        value=offset,
                        unit="s",
                        status="MEASURED"
                    )
                )
            else:
                diagnostics.append(
                    ConfidenceDiagnostic(
                        metric_name="temporal_mismatch_seconds",
                        unit="s",
                        status="UNAVAILABLE"
                    )
                )
        else:
            diagnostics.append(
                ConfidenceDiagnostic(
                    metric_name="temporal_mismatch_seconds",
                    unit="s",
                    status="UNAVAILABLE"
                )
            )
            
        flags.append(
            ConfidenceFlag(
                flag_name="TEMPORAL_MISMATCH",
                description="Final simulated timestamp was not temporally compatible with the observation.",
                severity="CRITICAL",
                triggered=not temporal_compatible,
                metric_name="temporal_compatible",
                metric_value=0.0 if not temporal_compatible else 1.0,
                threshold=1.0,
                threshold_status="ESTABLISHED"
            )
        )
        
        # 4. Spatial Dispersion
        dispersion = None
        if stats and stats.spread_radius_m is not None:
            dispersion = stats.spread_radius_m
            diagnostics.append(
                ConfidenceDiagnostic(
                    metric_name="spread_radius_m",
                    value=dispersion,
                    unit="m",
                    status="MEASURED"
                )
            )
            flags.append(
                ConfidenceFlag(
                    flag_name="HIGH_SPATIAL_DISPERSION",
                    description="Spatial dispersion of the ensemble is unusually high.",
                    severity="WARNING",
                    triggered=(dispersion > 5000.0),
                    metric_name="spread_radius_m",
                    metric_value=dispersion,
                    threshold=5000.0,
                    threshold_status="THRESHOLD_REQUIRES_CALIBRATION"
                )
            )
        else:
            diagnostics.append(
                ConfidenceDiagnostic(
                    metric_name="spread_radius_m",
                    unit="m",
                    status="UNAVAILABLE"
                )
            )
            
        # 5. Missing Metrics (Weathering, AIS, Env)
        # Weathering Sensitivity
        weathering_val = None
        if sim and sim.weathering_summary and sim.weathering_summary.mean_fraction_evaporated_percent is not None:
            weathering_val = sim.weathering_summary.mean_fraction_evaporated_percent
            diagnostics.append(ConfidenceDiagnostic(metric_name="weathering_sensitivity", value=weathering_val, unit="fraction", status="MEASURED"))
        else:
            diagnostics.append(ConfidenceDiagnostic(metric_name="weathering_sensitivity", unit="fraction", status="UNAVAILABLE"))

        # AIS Temporal Uncertainty
        ais_uncertainty = None
        if posterior_metadata.total_valid_candidates > 0:
            # We use the time gap between T0 and the closest observation in time
            closest_dt = 999999.0
            t0 = None
            if sim and sim.requested_observation_timestamp:
                t0 = sim.requested_observation_timestamp
            
            # Find the candidate matching this posterior
            cand = next((c for c in candidates_result.candidates if c.candidate_id == posterior.candidate_id), None)
            
            if t0 and cand and cand.observations:
                for obs in cand.observations:
                    dt = abs((obs.timestamp - t0).total_seconds())
                    if dt < closest_dt:
                        closest_dt = dt
                if closest_dt < 999999.0:
                    ais_uncertainty = closest_dt
                    diagnostics.append(ConfidenceDiagnostic(metric_name="ais_temporal_uncertainty", value=ais_uncertainty, unit="s", status="MEASURED"))
                else:
                    diagnostics.append(ConfidenceDiagnostic(metric_name="ais_temporal_uncertainty", unit="s", status="UNAVAILABLE"))
            else:
                diagnostics.append(ConfidenceDiagnostic(metric_name="ais_temporal_uncertainty", unit="s", status="UNAVAILABLE"))
        else:
            diagnostics.append(ConfidenceDiagnostic(metric_name="ais_temporal_uncertainty", unit="s", status="UNAVAILABLE"))

        # Environmental Data Completeness
        env_completeness = None
        if sim and sim.environmental_metadata:
            wind = sim.environmental_metadata.get("wind_provider")
            curr = sim.environmental_metadata.get("currents_provider")
            
            score = 0.0
            if curr and curr != "UNKNOWN":
                score += 0.5
            if wind and wind != "UNKNOWN":
                score += 0.5
                
            env_completeness = score
            diagnostics.append(ConfidenceDiagnostic(metric_name="environmental_data_completeness", value=env_completeness, unit="fraction", status="MEASURED"))
        else:
            diagnostics.append(ConfidenceDiagnostic(metric_name="environmental_data_completeness", unit="fraction", status="UNAVAILABLE"))
        
        # 6. Hypothesis Space Truncation
        truncated = posterior_metadata.hypothesis_space_truncated
        flags.append(
            ConfidenceFlag(
                flag_name="HYPOTHESIS_SPACE_TRUNCATED",
                description="Posterior is conditional only on the returned candidate set.",
                severity="QUALIFICATION",
                triggered=truncated,
                threshold_status="ESTABLISHED"
            )
        )

        return PhysicsAwareConfidence(
            candidate_id=posterior.candidate_id,
            posterior_probability=posterior.posterior_probability,  # MUST NEVER MODIFY
            confidence_level="INDETERMINATE",
            diagnostics=diagnostics,
            flags=flags,
            hypothesis_space_truncated=truncated,
            candidate_limit=posterior_metadata.candidate_limit,
            total_valid_candidates=posterior_metadata.total_valid_candidates,
            returned_candidate_count=posterior_metadata.returned_candidate_count,
            prior_mode=posterior_metadata.prior_mode
        )
