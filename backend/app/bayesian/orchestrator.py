import logging
from typing import Optional
from datetime import datetime, timezone

from app.feature2.data.base import EnvironmentalDataProvider
from app.feature3.engine import run_feature3_engine
from app.bayesian.schemas import (
    BayesianPipelineRequest,
    BayesianPrefilterResult,
    CandidateGenerationResult,
    OpenOilSimulationResult,
    CandidateLikelihood,
    BayesianPosteriorResult,
    PhysicsAwareConfidence,
    AttributionProvenance,
    FinalAttributionReport
)
from app.bayesian.prefilter import BayesianBackwardPrefilter
from app.bayesian.candidate_generator import generate_candidate_hypotheses
from app.bayesian.openoil_runner import OpenOilSimulationRunner
from app.bayesian.likelihood import LikelihoodEngine, ObservationLikelihoodDiagnostics
from app.bayesian.posterior import BayesianPosteriorEngine
from app.bayesian.confidence import PhysicsAwareConfidenceEngine
from app.bayesian.final_attribution import FinalAttributionEngine
from app.feature2.uncertainty.spatial_error import compute_ensemble_step_statistics
from app.bayesian.config import bayesian_settings

logger = logging.getLogger(__name__)

class BayesianPipelineOrchestrator:
    """
    Service orchestrating the complete end-to-end Bayesian attribution pipeline.
    
    Coordinates the strictly decoupled, read-only algorithmic phases:
    1. Prefilter
    2. Candidate Generation
    3C. OpenOil Forward Simulation
    4. Likelihood
    5. Posterior
    6. Confidence
    7. Feature 3 (Optional Supplemental Evidence)
    8. Final Attribution
    """

    def __init__(
        self,
        currents_provider: EnvironmentalDataProvider,
        wind_provider: Optional[EnvironmentalDataProvider] = None
    ):
        self.currents_provider = currents_provider
        self.wind_provider = wind_provider
        
        self.prefilter_engine = BayesianBackwardPrefilter(
            currents_provider=currents_provider,
            wind_provider=wind_provider
        )
        self.simulation_runner = OpenOilSimulationRunner(
            currents_provider=currents_provider,
            wind_provider=wind_provider
        )
        self.likelihood_engine = LikelihoodEngine(config=bayesian_settings.likelihood)
        self.posterior_engine = BayesianPosteriorEngine()
        self.confidence_engine = PhysicsAwareConfidenceEngine()
        self.final_engine = FinalAttributionEngine()

    def run_pipeline(
        self,
        request: BayesianPipelineRequest
    ) -> FinalAttributionReport:
        """
        Executes the full pipeline sequentially and returns the final attribution report.
        """
        spill_id = request.spill_data.spill_id
        logger.info(f"Starting E2E Bayesian Pipeline for spill {spill_id}")
        
        # ---------------------------------------------------------
        # PHASE 1: PREFILTER
        # ---------------------------------------------------------
        logger.info(f"[{spill_id}] Phase 1: Prefilter")
        prefilter_result = self.prefilter_engine.run_prefilter(
            source=request.spill_data,
            observation_time=request.spill_data.observation_time
        )
        
        # ---------------------------------------------------------
        # PHASE 2: CANDIDATE GENERATION
        # ---------------------------------------------------------
        logger.info(f"[{spill_id}] Phase 2: Candidate Generation")
        candidate_result = generate_candidate_hypotheses(
            prefilter_result=prefilter_result,
            ais_source=request.ais_data
        )
        
        # DEBUG
        for c in candidate_result.candidates:
            print(f"CANDIDATE ID: {c.candidate_id}, MMSI: {c.mmsi}")

        
        if candidate_result.candidate_count == 0:
            # Short-circuit if no candidates found
            return self._build_empty_report(spill_id, candidate_result, "No valid AIS candidates found in search window.")
            
        # ---------------------------------------------------------
        # PHASE 3C & PHASE 4: OPENOIL SIMULATION + LIKELIHOOD
        # ---------------------------------------------------------
        logger.info(f"[{spill_id}] Phase 3C & 4: OpenOil Simulation and Likelihood for {candidate_result.candidate_count} candidates")
        likelihoods = []
        simulations = []
        
        for candidate in candidate_result.candidates:
            sim_result = self.simulation_runner.run_candidate(
                candidate=candidate,
                observation_time=request.spill_data.observation_time
            )
            simulations.append(sim_result)
            
            if sim_result.status == "SUCCESS":
                likelihood = self.likelihood_engine.evaluate(
                    observations=[request.spill_data],
                    simulation_result=sim_result
                )
            else:
                likelihood = CandidateLikelihood(
                    candidate_id=candidate.candidate_id,
                    mmsi=candidate.mmsi,
                    likelihood=0.0,
                    log_likelihood=None,
                    evaluation_status="EVALUATION_UNAVAILABLE",
                    likelihood_mode="threshold",
                    observation_count=1,
                    per_observation_diagnostics=[ObservationLikelihoodDiagnostics(
                        spill_id=request.spill_data.spill_id,
                        observation_time=request.spill_data.observation_time,
                        simulation_actual_final_time=sim_result.actual_final_timestamp or request.spill_data.observation_time,
                        final_time_offset_seconds=0.0,
                        observation_time_tolerance_seconds=self.likelihood_engine.config.observation_time_tolerance_seconds,
                        temporal_compatible=False,
                        total_particles=0,
                        active_particles=0,
                        stranded_particles=0,
                        other_terminal_particles=0,
                        valid_particles_used=0,
                        excluded_status_particles=0,
                        likelihood=0.0,
                        log_likelihood=None,
                        error_message="Simulation failed"
                    )]
                )
                
            likelihoods.append(likelihood)
            
        # ---------------------------------------------------------
        # PHASE 5: POSTERIOR
        # ---------------------------------------------------------
        logger.info(f"[{spill_id}] Phase 5: Bayesian Posterior computation")
        posterior_result = self.posterior_engine.compute_posterior(
            candidates_result=candidate_result,
            likelihoods=likelihoods
        )
        
        if posterior_result.status == "NO_POSITIVE_LIKELIHOOD":
            logger.warning(f"[{spill_id}] Phase 5 returned NO_POSITIVE_LIKELIHOOD.")

        # ---------------------------------------------------------
        # PHASE 6: PHYSICS-AWARE CONFIDENCE
        # ---------------------------------------------------------
        logger.info(f"[{spill_id}] Phase 6: Physics-Aware Confidence")
        ensemble_stats_map = {}
        for s in simulations:
            timestamp_to_use = s.actual_final_timestamp or s.requested_observation_timestamp
            if s.final_particle_states and timestamp_to_use:
                try:
                    stats = compute_ensemble_step_statistics(timestamp_to_use, s.final_particle_states)
                    ensemble_stats_map[s.candidate_id] = stats
                except Exception as e:
                    logger.warning(f"[{spill_id}] Failed to calculate step statistics for {s.candidate_id}: {e}")
                    ensemble_stats_map[s.candidate_id] = None
            else:
                ensemble_stats_map[s.candidate_id] = None

        confidence_results = self.confidence_engine.compute_confidence(
            posterior_result=posterior_result,
            candidates_result=candidate_result,
            simulations=simulations,
            likelihoods=likelihoods,
            ensemble_stats=ensemble_stats_map
        )
        
        # ---------------------------------------------------------
        # FEATURE 3: SUPPLEMENTAL DETERMINISTIC EVIDENCE
        # ---------------------------------------------------------
        feature3_response = None
        if request.feature2_context is not None:
            logger.info(f"[{spill_id}] Feature 3: Extracting Supplemental Evidence")
            try:
                feature3_response = run_feature3_engine(
                    feature2_context=request.feature2_context,
                    ais_data=request.ais_data
                )
            except Exception as e:
                logger.error(f"[{spill_id}] Feature 3 integration failed: {e}")
                feature3_response = None
        else:
            logger.info(f"[{spill_id}] Feature 3: Skipped (No deterministic origin context provided)")

        # ---------------------------------------------------------
        # FINAL ATTRIBUTION
        # ---------------------------------------------------------
        logger.info(f"[{spill_id}] Final Attribution")
        provenance = AttributionProvenance(
            environmental_data_provider=self.currents_provider.provider_name if self.currents_provider else "UNKNOWN",
            simulation_engine="OpenOil",
            bayesian_configuration=request.bayesian_config or bayesian_settings.model_dump(),
            truncation_metadata={
                "truncated": candidate_result.truncated,
                "strategy": candidate_result.truncation_strategy
            }
        )
        
        report = self.final_engine.generate_report(
            spill_id=spill_id,
            posterior_result=posterior_result,
            confidence_results=confidence_results,
            feature3_response=feature3_response,
            provenance=provenance
        )
        
        return report

    def _build_empty_report(self, spill_id: str, candidate_result: CandidateGenerationResult, reason: str) -> FinalAttributionReport:
        posterior_result = BayesianPosteriorResult(
            status="VALIDATION_ERROR",
            hypothesis_space_truncated=candidate_result.truncated,
            candidate_limit=candidate_result.candidate_limit,
            total_valid_candidates=candidate_result.total_valid_candidates,
            returned_candidate_count=0,
            prior_mode=candidate_result.prior_mode,
            evaluated_candidate_count=0,
            positive_likelihood_candidate_count=0,
            normalization_constant=0.0,
            log_normalization_constant=None,
            posterior_sum=0.0,
            posteriors=[]
        )
        prov = AttributionProvenance(
            environmental_data_provider=self.currents_provider.provider_name if self.currents_provider else "UNKNOWN",
            simulation_engine="OpenOil",
            bayesian_configuration=bayesian_settings.model_dump(),
            truncation_metadata={}
        )
        report = self.final_engine.generate_report(spill_id, posterior_result, [], None, prov)
        report.errors.append(reason)
        return report
