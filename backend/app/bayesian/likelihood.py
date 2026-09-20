import math
from typing import List, Optional
from shapely.geometry import shape, Point

from app.bayesian.config import LikelihoodConfig
from app.bayesian.schemas import (
    OpenOilSimulationResult,
    CandidateLikelihood,
    ObservationLikelihoodDiagnostics,
    ParticleState
)
from app.feature2.schemas.input_schema import SlickDetectionInput
from app.feature2.geo.coordinates import haversine_distance_km

class LikelihoodEngine:
    def __init__(self, config: LikelihoodConfig):
        self.config = config

    def evaluate(self, observations: List[SlickDetectionInput], simulation_result: OpenOilSimulationResult) -> CandidateLikelihood:
        """
        Evaluate likelihood of a candidate given a set of observations.
        """
        candidate_id = simulation_result.candidate_id
        mode = self.config.likelihood_mode
        
        joint_log_likelihood = 0.0
        joint_likelihood = 1.0
        
        per_obs_diagnostics = []
        errors = []
        warnings = []
        
        for obs in observations:
            try:
                diag = self._evaluate_single_observation(obs, simulation_result)
                per_obs_diagnostics.append(diag)
                
                if diag.error_message:
                    errors.append(f"Observation {obs.spill_id}: {diag.error_message}")
                    joint_likelihood = 0.0
                    joint_log_likelihood = float('-inf')
                else:
                    if diag.likelihood == 0.0:
                        joint_likelihood = 0.0
                        joint_log_likelihood = float('-inf')
                    elif joint_likelihood > 0.0:
                        joint_likelihood *= diag.likelihood
                        joint_log_likelihood += diag.log_likelihood
            except Exception as e:
                errors.append(f"Observation {obs.spill_id} failed: {str(e)}")
                joint_likelihood = 0.0
                joint_log_likelihood = float('-inf')
                
                diag = ObservationLikelihoodDiagnostics(
                    spill_id=obs.spill_id,
                    observation_time=obs.observation_time,
                    simulation_actual_final_time=simulation_result.actual_final_timestamp,
                    final_time_offset_seconds=simulation_result.final_time_offset_seconds,
                    observation_time_tolerance_seconds=self.config.observation_time_tolerance_seconds,
                    temporal_compatible=False,
                    total_particles=0,
                    active_particles=0,
                    stranded_particles=0,
                    other_terminal_particles=0,
                    valid_particles_used=0,
                    excluded_status_particles=0,
                    likelihood=0.0,
                    log_likelihood=float('-inf'),
                    error_message=str(e)
                )
                per_obs_diagnostics.append(diag)

        return CandidateLikelihood(
            candidate_id=candidate_id,
            likelihood_mode=mode,
            likelihood=joint_likelihood,
            log_likelihood=joint_log_likelihood,
            observation_count=len(observations),
            per_observation_diagnostics=per_obs_diagnostics,
            warnings=warnings,
            errors=errors,
            provenance={
                "likelihood_config": self.config.model_dump(),
                "simulation_status": simulation_result.status
            }
        )

    def _evaluate_single_observation(self, obs: SlickDetectionInput, sim: OpenOilSimulationResult) -> ObservationLikelihoodDiagnostics:
        # 1. Temporal validation
        actual_time = sim.actual_final_timestamp
        if actual_time is None:
            return self._build_error_diag(obs, sim, "Simulation lacks actual_final_timestamp.")
            
        time_diff = abs((actual_time - obs.observation_time).total_seconds())
        if time_diff > self.config.observation_time_tolerance_seconds:
            return self._build_error_diag(
                obs, sim, 
                f"Temporal incompatibility: {time_diff}s > {self.config.observation_time_tolerance_seconds}s"
            )

        # 2. Particle filtering and status tracking
        total = len(sim.final_particle_states)
        active = 0
        stranded = 0
        other = 0
        valid_used = 0
        excluded = 0
        
        valid_particles: List[ParticleState] = []
        
        for p in sim.final_particle_states:
            # Count status
            is_active = (p.status.lower() == "active")
            is_stranded = (p.status.lower() == "stranded")
            
            if is_active:
                active += 1
            elif is_stranded:
                stranded += 1
            else:
                other += 1
                
            # Filter
            include = False
            if is_active:
                include = True
            elif is_stranded and self.config.include_stranded_particles:
                include = True
            elif (not is_active and not is_stranded) and self.config.include_other_terminal_particles:
                include = True
                
            if not include:
                excluded += 1
                continue
                
            if not math.isnan(p.latitude) and not math.isnan(p.longitude):
                valid_particles.append(p)
                valid_used += 1
            else:
                excluded += 1
        
        if valid_used == 0:
            return self._build_error_diag(
                obs, sim, 
                "No valid particles available for spatial likelihood evaluation.",
                total, active, stranded, other, valid_used, excluded, temporal_compatible=True
            )
            
        # 3. Spatial likelihood calculation
        if self.config.likelihood_mode == "threshold":
            return self._calc_threshold(obs, sim, valid_particles, total, active, stranded, other, valid_used, excluded)
        elif self.config.likelihood_mode == "gaussian":
            return self._calc_gaussian(obs, sim, valid_particles, total, active, stranded, other, valid_used, excluded)
        else:
            return self._build_error_diag(obs, sim, f"Unknown mode: {self.config.likelihood_mode}")

    def _calc_threshold(self, obs, sim, valid_particles, total, active, stranded, other, valid_used, excluded) -> ObservationLikelihoodDiagnostics:
        geom = shape(obs.geometry.model_dump())
        compatible_count = 0
        
        for p in valid_particles:
            pt = Point(p.longitude, p.latitude)
            if geom.covers(pt):
                compatible_count += 1
                
        frac = compatible_count / valid_used
        L = frac
        log_L = math.log(L) if L > 0 else float('-inf')
        
        return ObservationLikelihoodDiagnostics(
            spill_id=obs.spill_id,
            observation_time=obs.observation_time,
            simulation_actual_final_time=sim.actual_final_timestamp,
            final_time_offset_seconds=sim.final_time_offset_seconds,
            observation_time_tolerance_seconds=self.config.observation_time_tolerance_seconds,
            temporal_compatible=True,
            total_particles=total,
            active_particles=active,
            stranded_particles=stranded,
            other_terminal_particles=other,
            valid_particles_used=valid_used,
            excluded_status_particles=excluded,
            compatible_count=compatible_count,
            compatible_fraction=frac,
            likelihood=L,
            log_likelihood=log_L
        )

    def _calc_gaussian(self, obs, sim, valid_particles, total, active, stranded, other, valid_used, excluded) -> ObservationLikelihoodDiagnostics:
        sigma_m = self.config.gaussian_sigma_m
        if sigma_m <= 0:
            return self._build_error_diag(obs, sim, f"Invalid sigma: {sigma_m} <= 0")
            
        obs_lat = obs.centroid.latitude
        obs_lon = obs.centroid.longitude
        
        sum_Li = 0.0
        
        for p in valid_particles:
            r_m = haversine_distance_km(p.latitude, p.longitude, obs_lat, obs_lon) * 1000.0
            
            # L_i = 1 / (2*pi*sigma^2) * exp(-r^2 / (2*sigma^2))
            var = sigma_m * sigma_m
            prefactor = 1.0 / (2.0 * math.pi * var)
            exponent = -(r_m * r_m) / (2.0 * var)
            
            # Prevent underflow to 0 if exponent is very small, python math.exp handles it by returning 0.0
            # which is mathematically acceptable for extreme distances.
            try:
                L_i = prefactor * math.exp(exponent)
            except OverflowError:
                L_i = 0.0
                
            sum_Li += L_i
            
        L = sum_Li / valid_used
        log_L = math.log(L) if L > 0 else float('-inf')
        
        return ObservationLikelihoodDiagnostics(
            spill_id=obs.spill_id,
            observation_time=obs.observation_time,
            simulation_actual_final_time=sim.actual_final_timestamp,
            final_time_offset_seconds=sim.final_time_offset_seconds,
            observation_time_tolerance_seconds=self.config.observation_time_tolerance_seconds,
            temporal_compatible=True,
            total_particles=total,
            active_particles=active,
            stranded_particles=stranded,
            other_terminal_particles=other,
            valid_particles_used=valid_used,
            excluded_status_particles=excluded,
            gaussian_sigma_m=sigma_m,
            likelihood=L,
            log_likelihood=log_L
        )

    def _build_error_diag(self, obs, sim, msg: str, 
                          total=0, active=0, stranded=0, other=0, valid=0, excluded=0, 
                          temporal_compatible=False) -> ObservationLikelihoodDiagnostics:
        return ObservationLikelihoodDiagnostics(
            spill_id=obs.spill_id,
            observation_time=obs.observation_time,
            simulation_actual_final_time=sim.actual_final_timestamp,
            final_time_offset_seconds=sim.final_time_offset_seconds,
            observation_time_tolerance_seconds=self.config.observation_time_tolerance_seconds,
            temporal_compatible=temporal_compatible,
            total_particles=total,
            active_particles=active,
            stranded_particles=stranded,
            other_terminal_particles=other,
            valid_particles_used=valid,
            excluded_status_particles=excluded,
            likelihood=0.0,
            log_likelihood=float('-inf'),
            error_message=msg
        )
