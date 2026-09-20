from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any, List
import math

from ..feature2.schemas.input_schema import SlickDetectionInput
from ..feature2.data.domain import SentinelObservationDomain, EnvironmentalQueryDomain
from ..feature2.data.base import EnvironmentalDataProvider
from ..feature2.simulation.backward.engine import BackwardSimulationEngine, BackwardSimulationResult
from ..feature2.data.time_utils import normalize_to_utc
from ..feature2.geo.coordinates import meters_to_lat_deg, meters_to_lon_deg

from .config import bayesian_settings
from .schemas import BayesianPrefilterResult

class BayesianBackwardPrefilter:
    """
    Service for Phase 1 Bayesian short backward prefilter.
    
    This service reuses the existing BackwardSimulationEngine to run a short
    (6-24 hour) backward simulation for the sole purpose of defining a candidate
    spatial region and temporal window for Phase 2 AIS candidate generation.
    """
    
    def __init__(
        self,
        currents_provider: EnvironmentalDataProvider,
        wind_provider: Optional[EnvironmentalDataProvider] = None,
    ):
        self.currents_provider = currents_provider
        self.wind_provider = wind_provider

    def run_prefilter(
        self,
        source: Union[SlickDetectionInput, SentinelObservationDomain, Dict[str, Any]],
        observation_time: Optional[Union[datetime, str]] = None,
        backward_horizon_hours: Optional[float] = None,
        dt_seconds: float = 600.0,
        query_domain: Optional[EnvironmentalQueryDomain] = None,
    ) -> BayesianPrefilterResult:
        """
        Executes the short backward prefilter.
        """
        # Resolve observation time
        if observation_time is None:
            if isinstance(source, dict):
                obs_t = source.get("observation_time")
            else:
                obs_t = source.observation_time
            sim_t0 = normalize_to_utc(obs_t)
        else:
            sim_t0 = normalize_to_utc(observation_time)
            
        # Determine horizon
        horizon_hours = backward_horizon_hours
        if horizon_hours is None:
            horizon_hours = bayesian_settings.prefilter.bayesian_prefilter_hours
            
        # Validate horizon
        if not (6.0 <= horizon_hours <= 24.0):
            raise ValueError(f"backward_horizon_hours must be between 6.0 and 24.0, got {horizon_hours}")
            
        # Initialize legacy engine
        engine = BackwardSimulationEngine(
            currents_provider=self.currents_provider,
            wind_provider=self.wind_provider
        )
        
        # Run simulation
        duration_seconds = horizon_hours * 3600.0
        
        try:
            result: BackwardSimulationResult = engine.simulate_backward(
                initial_particles=source,
                observation_time=sim_t0,
                duration_seconds=duration_seconds,
                dt_seconds=dt_seconds,
                query_domain=query_domain
            )
            
            # Compute spatial region (GeoJSON bounding box polygon over all steps + spread)
            spatial_region = self._compute_spatial_region(result)
            
            prefilter_start_time = sim_t0 - timedelta(hours=horizon_hours)
            prefilter_end_time = sim_t0
            
            return BayesianPrefilterResult(
                role="SEARCH_PREFILTER_ONLY",
                observation_time=sim_t0,
                prefilter_start_time=prefilter_start_time,
                prefilter_end_time=prefilter_end_time,
                backward_horizon_hours=horizon_hours,
                candidate_spatial_region=spatial_region,
                active_particle_count=result.active_particle_count
            )
        except Exception as e:
            import traceback
            import logging
            log = logging.getLogger(__name__)
            
            spill_id = source.get("spill_id", "UNKNOWN") if isinstance(source, dict) else getattr(source, "spill_id", "UNKNOWN")
            source_type = type(source).__name__
            curr_prov = self.currents_provider.provider_name if self.currents_provider else "None"
            wind_prov = self.wind_provider.provider_name if self.wind_provider else "None"
            
            num_particles = "UNKNOWN"
            if 'result' in locals():
                num_particles = getattr(result, "active_particle_count", "UNKNOWN_FROM_RESULT")
            
            log.error(
                f"DIAGNOSTIC EXCEPTION TRACE:\n"
                f"Spill ID: {spill_id}\n"
                f"Observation Timestamp: {sim_t0}\n"
                f"Candidate Source Type: {source_type}\n"
                f"Current Provider Type: {curr_prov}\n"
                f"Wind Provider Type: {wind_prov}\n"
                f"Resolved Particles (if any): {num_particles}\n"
                f"Exception Type: {type(e).__name__}\n"
                f"Exception Message: {str(e)}\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
            raise
        
    def _compute_spatial_region(self, result: BackwardSimulationResult) -> Dict[str, Any]:
        """
        Derives a bounding box GeoJSON Polygon containing all active particle states
        across the entire backward trajectory. This ensures the region genuinely covers
        the spatial extent of the simulation.
        """
        min_lat, max_lat = 90.0, -90.0
        min_lon, max_lon = 180.0, -180.0
        
        for traj in result.trajectories:
            for state in traj.states:
                if getattr(state, "is_active", True) or getattr(state, "active", True):
                    min_lat = min(min_lat, state.latitude)
                    max_lat = max(max_lat, state.latitude)
                    min_lon = min(min_lon, state.longitude)
                    max_lon = max(max_lon, state.longitude)
                    
        # Ensure bounds are valid
        min_lat = max(-90.0, min_lat)
        max_lat = min(90.0, max_lat)
        
        # Construct GeoJSON Polygon representing the bounding box
        coords = [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat]
            ]
        ]
        
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coords
            },
            "properties": {
                "description": "Prefilter candidate search bounding box"
            }
        }
