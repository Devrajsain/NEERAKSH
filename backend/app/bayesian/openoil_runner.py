"""
Phase 3C: Bayesian OpenOil Forward Simulation Layer.
Executes forward Lagrangian simulations for generated AIS candidate hypotheses.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import math

from pydantic import ValidationError
import numpy as np

try:
    import opendrift
    from opendrift.models.openoil import OpenOil
    from opendrift.readers import reader_netCDF_CF_generic
except ImportError:
    # Handle environments where opendrift is missing gracefully during module import
    opendrift = None
    OpenOil = None
    reader_netCDF_CF_generic = None

from .schemas import (
    BayesianCandidateHypothesis,
    OpenOilEnsembleConfig,
    OpenOilSimulationResult,
    ParticleState,
    WeatheringSummary
)
from ..feature2.data.wind.era5 import ERA5WindProvider
from ..feature2.data.currents.copernicus import CopernicusCurrentsProvider
from ..feature2.schemas.simulation_schema import EnvironmentalQueryWindow

logger = logging.getLogger(__name__)


class OpenOilSimulationRunner:
    """
    Orchestrates the Bayesian forward simulation of a single candidate hypothesis
    using the genuine OpenDrift OpenOil model.
    """

    def __init__(
        self,
        wind_provider: ERA5WindProvider,
        currents_provider: CopernicusCurrentsProvider,
        config: Optional[OpenOilEnsembleConfig] = None
    ):
        self.wind_provider = wind_provider
        self.currents_provider = currents_provider
        self.config = config or OpenOilEnsembleConfig()
        
    def run_candidate(
        self,
        candidate: BayesianCandidateHypothesis,
        observation_time: datetime
    ) -> OpenOilSimulationResult:
        """
        Executes the OpenOil forward ensemble for the given candidate.
        
        Args:
            candidate: The Phase 2 Bayesian Candidate Hypothesis.
            observation_time: The requested observation timestamp (T0).
            
        Returns:
            OpenOilSimulationResult with final particle states and statuses.
        """
        # 1. Validate timestamps
        rel_time = candidate.release_time
        if not rel_time.tzinfo:
            rel_time = rel_time.replace(tzinfo=timezone.utc)
        if not observation_time.tzinfo:
            observation_time = observation_time.replace(tzinfo=timezone.utc)
            
        if rel_time >= observation_time:
            return self._build_error_result(
                candidate, 
                observation_time, 
                "VALIDATION_ERROR", 
                "Release time must be strictly before observation time."
            )
            
        sim_duration_secs = (observation_time - rel_time).total_seconds()
        sim_duration_hours = sim_duration_secs / 3600.0

        # 2. Environmental Coverage
        min_lat = min(obs.latitude for obs in candidate.observations)
        max_lat = max(obs.latitude for obs in candidate.observations)
        min_lon = min(obs.longitude for obs in candidate.observations)
        max_lon = max(obs.longitude for obs in candidate.observations)
        
        env_window = EnvironmentalQueryWindow(
            min_lat=min_lat - self.config.environment_margin_deg,
            max_lat=max_lat + self.config.environment_margin_deg,
            min_lon=min_lon - self.config.environment_margin_deg,
            max_lon=max_lon + self.config.environment_margin_deg,
            start_time=rel_time,
            end_time=observation_time
        )
        
        if self.currents_provider is None:
            return self._build_error_result(
                candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                f"Currents provider is required for simulation but was not resolved or injected. Time range: {env_window.start_time.isoformat()} to {env_window.end_time.isoformat()}, bounds: [{env_window.min_lat:.2f}, {env_window.max_lat:.2f}, {env_window.min_lon:.2f}, {env_window.max_lon:.2f}].",
                sim_duration_hours
            )

        if self.wind_provider is None:
            return self._build_error_result(
                candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                f"Wind provider is required for simulation but was not resolved or injected. Time range: {env_window.start_time.isoformat()} to {env_window.end_time.isoformat()}, bounds: [{env_window.min_lat:.2f}, {env_window.max_lat:.2f}, {env_window.min_lon:.2f}, {env_window.max_lon:.2f}].",
                sim_duration_hours
            )

        try:
            wind_success = self.wind_provider.fetch_grid(env_window)
            if not wind_success:
                cache_status = "Available" if getattr(self.wind_provider, 'active_filepath', None) else "Unavailable"
                return self._build_error_result(
                    candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                    f"Wind provider '{getattr(self.wind_provider, 'provider_name', 'Unknown')}' failed to fetch grid for bounds: [{env_window.min_lat:.2f}, {env_window.max_lat:.2f}, {env_window.min_lon:.2f}, {env_window.max_lon:.2f}] over window {env_window.start_time.isoformat()} to {env_window.end_time.isoformat()}. Local cache: {cache_status}.",
                    sim_duration_hours
                )
        except Exception as e:
            return self._build_error_result(
                candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                f"Wind provider error: {str(e)}", sim_duration_hours
            )
            
        try:
            curr_success = self.currents_provider.fetch_grid(env_window)
            if not curr_success:
                cache_status = "Available" if getattr(self.currents_provider, 'active_filepath', None) else "Unavailable"
                return self._build_error_result(
                    candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                    f"Currents provider '{getattr(self.currents_provider, 'provider_name', 'Unknown')}' failed to fetch grid for bounds: [{env_window.min_lat:.2f}, {env_window.max_lat:.2f}, {env_window.min_lon:.2f}, {env_window.max_lon:.2f}] over window {env_window.start_time.isoformat()} to {env_window.end_time.isoformat()}. Local cache: {cache_status}.",
                    sim_duration_hours
                )
        except Exception as e:
            return self._build_error_result(
                candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                f"Currents provider error: {str(e)}", sim_duration_hours
            )
            
        # Get active filepaths via public accessor
        wind_file = self.wind_provider.active_filepath
        curr_file = self.currents_provider.active_filepath
        
        if not wind_file and not getattr(self.wind_provider, "mock_reader", None):
            return self._build_error_result(
                candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                f"Wind provider '{getattr(self.wind_provider, 'provider_name', 'Unknown')}' succeeded but no local NetCDF file was produced for OpenDrift. Time range: {env_window.start_time.isoformat()} to {env_window.end_time.isoformat()}.",
                sim_duration_hours
            )
            
        if not curr_file and not getattr(self.currents_provider, "mock_reader", None):
            return self._build_error_result(
                candidate, observation_time, "ENVIRONMENTAL_DATA_INCOMPLETE",
                f"Currents provider '{getattr(self.currents_provider, 'provider_name', 'Unknown')}' succeeded but no local NetCDF file was produced for OpenDrift. Time range: {env_window.start_time.isoformat()} to {env_window.end_time.isoformat()}.",
                sim_duration_hours
            )
        
        # 3. OpenOil Initialization
        if OpenOil is None:
            return self._build_error_result(
                candidate, observation_time, "OPENDRIFT_INITIALIZATION_ERROR",
                "opendrift package is not installed.", sim_duration_hours
            )
            
        try:
            o = OpenOil(loglevel=50)
            if self.config.random_seed is not None:
                np.random.seed(self.config.random_seed)
        except Exception as e:
            return self._build_error_result(
                candidate, observation_time, "OPENDRIFT_INITIALIZATION_ERROR",
                f"Failed to instantiate OpenOil: {str(e)}", sim_duration_hours
            )
            
        # 4. Reader Construction
        try:
            readers = []
            if wind_file:
                readers.append(reader_netCDF_CF_generic.Reader(wind_file))
            elif getattr(self.wind_provider, "mock_reader", None):
                readers.append(self.wind_provider.mock_reader)
                
            if curr_file:
                readers.append(reader_netCDF_CF_generic.Reader(curr_file))
            elif getattr(self.currents_provider, "mock_reader", None):
                readers.append(self.currents_provider.mock_reader)
                
            if readers:
                o.add_reader(readers)
            else:
                return self._build_error_result(
                    candidate, observation_time, "OPENDRIFT_READER_ERROR",
                    "No valid readers constructed from providers.", sim_duration_hours
                )
        except Exception as e:
            return self._build_error_result(
                candidate, observation_time, "OPENDRIFT_READER_ERROR",
                f"Failed to construct OpenDrift readers: {str(e)}", sim_duration_hours
            )
            
        # 5. Particle Seeding
        obs_time_naive = observation_time.replace(tzinfo=None)
        
        # Extract arrays of release points from the vessel's trajectory
        lons = [obs.longitude for obs in candidate.observations]
        lats = [obs.latitude for obs in candidate.observations]
        times = [obs.timestamp.replace(tzinfo=None) for obs in candidate.observations]
        
        N = len(lons)
        
        try:
            if N == 1:
                o.seed_elements(
                    lon=lons[0],
                    lat=lats[0],
                    time=times[0],
                    number=self.config.ensemble_size,
                    radius=self.config.release_radius_m,
                    oil_type=self.config.oil_type
                )
            else:
                base_particles = self.config.ensemble_size // N
                remainder = self.config.ensemble_size % N
                actual_ensemble_size = self.config.ensemble_size
                
                # OpenDrift requires the length of time arrays to match 'number' if length > 2
                repeated_lons = []
                repeated_lats = []
                repeated_times = []
                for i, (lon, lat, t) in enumerate(zip(lons, lats, times)):
                    pts = base_particles + (1 if i < remainder else 0)
                    if pts > 0:
                        repeated_lons.extend([lon] * pts)
                        repeated_lats.extend([lat] * pts)
                        repeated_times.extend([t] * pts)
                
                # Seed elements across all observed points. 
                # These are alternative/possible release hypotheses associated with the vessel's 
                # observed trajectory, not simultaneous independent spills.
                o.seed_elements(
                    lon=repeated_lons,
                    lat=repeated_lats,
                    time=repeated_times,
                    number=actual_ensemble_size,
                    radius=self.config.release_radius_m,
                    oil_type=self.config.oil_type
                )
        except Exception as e:
            return self._build_error_result(
                candidate, observation_time, "OPENDRIFT_INITIALIZATION_ERROR",
                f"Failed to seed elements: {str(e)}", sim_duration_hours
            )
            
        # 6. Forward Simulation
        try:
            o.run(
                end_time=obs_time_naive,
                time_step=self.config.time_step_seconds,
                time_step_output=self.config.time_step_output_seconds,
                outfile=None  # Memory export
            )
        except (Exception, SystemExit) as e:
            return self._build_error_result(
                candidate, observation_time, "OPENDRIFT_SIMULATION_ERROR",
                f"Simulation run failed: {str(e)}", sim_duration_hours
            )
            
        # 7. Observation-Time Extraction
        try:
            def get_prop(name: str):
                try:
                    if hasattr(o, 'history') and name in o.history:
                        arr = o.history[name][-1, :]
                        if hasattr(arr, 'values'):
                            arr = arr.values
                        return np.asarray(arr).flatten()
                    
                    arr = o.get_property(name)[0]
                    if hasattr(arr, 'values'):
                        arr = arr.values
                    if arr is not None and getattr(arr, 'ndim', 1) > 1:
                        arr = arr[-1, :]
                    return np.asarray(arr).flatten() if arr is not None else None
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to extract {name}: {e}")
                    return None
            
            # Resolve actual final timestamp
            actual_final_timestamp = observation_time
            if hasattr(o, 'history') and hasattr(o.history, 'coords') and 'time' in o.history.coords:
                times = o.history['time'].values
                final_time_np = times[-1]
                actual_final_timestamp = datetime.fromtimestamp(
                    final_time_np.astype('datetime64[s]').astype(int), tz=timezone.utc
                )
            
            final_time_offset = (actual_final_timestamp - observation_time).total_seconds()
            
            # Resolve dynamic statuses
            status_categories = getattr(o, 'status_categories', ['active'])
            
            # Extract arrays
            lons = get_prop('lon')
            lats = get_prop('lat')
            statuses = get_prop('status')
            
            if lons is None or lats is None or statuses is None:
                raise RuntimeError("Could not extract fundamental lon/lat/status arrays.")
                
            mass_oil = get_prop('mass_oil')
            mass_evaporated = get_prop('mass_evaporated')
            mass_dispersed = get_prop('mass_dispersed')
            mass_biodegraded = get_prop('mass_biodegraded')
            fraction_evaporated = get_prop('fraction_evaporated')
            water_fraction = get_prop('water_fraction')
            density = get_prop('density')
            viscosity = get_prop('viscosity')
            
            particles = []
            active_count = 0
            stranded_count = 0
            other_count = 0
            
            for i in range(len(lons)):
                lon_val = float(lons[i])
                lat_val = float(lats[i])
                status_code = int(statuses[i])
                
                # Normalize status
                if 0 <= status_code < len(status_categories):
                    status_str = status_categories[status_code]
                else:
                    status_str = "unknown"
                    
                if status_str == 'active':
                    active_count += 1
                elif status_str == 'stranded':
                    stranded_count += 1
                else:
                    other_count += 1
                    
                p = ParticleState(
                    longitude=lon_val,
                    latitude=lat_val,
                    status=status_str,
                    original_status_code=status_code,
                    mass_oil_kg=float(mass_oil[i]) if mass_oil is not None else None,
                    mass_evaporated_kg=float(mass_evaporated[i]) if mass_evaporated is not None else None,
                    mass_dispersed_kg=float(mass_dispersed[i]) if mass_dispersed is not None else None,
                    mass_biodegraded_kg=float(mass_biodegraded[i]) if mass_biodegraded is not None else None,
                    fraction_evaporated_percent=float(fraction_evaporated[i]) if fraction_evaporated is not None else None,
                    water_fraction_percent=float(water_fraction[i]) if water_fraction is not None else None,
                    density_kg_m3=float(density[i]) if density is not None else None,
                    viscosity_m2_s=float(viscosity[i]) if viscosity is not None else None
                )
                particles.append(p)
                
            # Weathering Summary
            def get_mean(arr):
                if arr is not None and len(arr) > 0:
                    val = float(np.nanmean(arr))
                    if not math.isnan(val):
                        return val
                return None
                
            w_summary = WeatheringSummary(
                mean_mass_oil_kg=get_mean(mass_oil),
                mean_fraction_evaporated_percent=get_mean(fraction_evaporated),
                mean_density_kg_m3=get_mean(density)
            )
            
            result = OpenOilSimulationResult(
                candidate_id=candidate.candidate_id,
                mmsi=candidate.mmsi,
                status="SUCCESS",
                release_timestamp=rel_time,
                requested_observation_timestamp=observation_time,
                actual_final_timestamp=actual_final_timestamp,
                simulation_duration_hours=sim_duration_hours,
                final_time_offset_seconds=final_time_offset,
                ensemble_size_requested=self.config.ensemble_size,
                ensemble_size_returned=len(particles),
                active_particle_count=active_count,
                stranded_particle_count=stranded_count,
                other_terminal_particle_count=other_count,
                final_particle_states=particles,
                weathering_summary=w_summary,
                environmental_metadata={
                    "wind_provider": self.wind_provider.provider_name,
                    "currents_provider": self.currents_provider.provider_name
                },
                provenance={
                    "opendrift_version": getattr(opendrift, '__version__', 'unknown') if opendrift else 'unknown',
                    "config": self.config.model_dump()
                }
            )
            return result

        except Exception as e:
            return self._build_error_result(
                candidate, observation_time, "OUTPUT_EXTRACTION_ERROR",
                f"Failed to extract properties from simulation: {str(e)}", sim_duration_hours
            )

    def _build_error_result(
        self,
        candidate: BayesianCandidateHypothesis,
        observation_time: datetime,
        status: str,
        message: str,
        duration_hours: Optional[float] = None
    ) -> OpenOilSimulationResult:
        logger.error(f"[OpenOilSimulationRunner] {status} for {candidate.candidate_id}: {message}")
        return OpenOilSimulationResult(
            candidate_id=candidate.candidate_id,
            mmsi=candidate.mmsi,
            status=status,
            release_timestamp=candidate.release_time,
            requested_observation_timestamp=observation_time,
            simulation_duration_hours=duration_hours,
            ensemble_size_requested=self.config.ensemble_size,
            error_message=message
        )
