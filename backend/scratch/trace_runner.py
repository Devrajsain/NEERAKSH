import asyncio
from datetime import datetime, timezone
import json
from app.bayesian.openoil_runner import OpenOilSimulationRunner
from app.bayesian.schemas import OpenOilEnsembleConfig, BayesianCandidateHypothesis, AISRecord
from app.feature2.api.dependencies import get_currents_provider, get_wind_provider, get_settings

async def main():
    settings = get_settings()
    currents = get_currents_provider(settings)
    wind = get_wind_provider(settings)
    
    runner = OpenOilSimulationRunner(
        config=OpenOilEnsembleConfig(
            ensemble_size=50,
            time_step_seconds=900,
            time_step_output_seconds=3600,
            release_radius_m=1000.0,
            environment_margin_deg=1.5,
            oil_type="Generic Diesel"
        ),
        currents_provider=currents,
        wind_provider=wind
    )
    
    candidate = BayesianCandidateHypothesis(
        candidate_id="999888777",
        mmsi="999888777",
        release_position={"latitude": 41.5, "longitude": 2.5},
        release_time=datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc),
        prior_probability=0.5,
        observations=[
            AISRecord(
                mmsi="999888777", 
                timestamp=datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc), 
                latitude=41.5, 
                longitude=2.5
            ),
        ],
    )
    
    obs_time = datetime(2026, 9, 15, 9, 0, 0, tzinfo=timezone.utc)
    
    print("Running candidate...")
    res = runner.run_candidate(candidate, obs_time)
    
    print(f"Status: {res.status}")
    print(f"Error: {res.error_message}")
    print(f"Warnings: {res.warnings}")
    print(f"Requested Size: {res.ensemble_size_requested}")
    print(f"Returned Size: {res.ensemble_size_returned}")
    print(f"Active: {res.active_particle_count}")
    print(f"Stranded: {res.stranded_particle_count}")
    print(f"Other: {res.other_terminal_particle_count}")
    print(f"Weathering: {res.weathering_summary}")
    
    if res.final_particle_states:
        print(f"First particle status: {res.final_particle_states[0].status}")
        print(f"First particle mass_oil_kg: {res.final_particle_states[0].mass_oil_kg}")
        print(f"First particle lon/lat: {res.final_particle_states[0].longitude}, {res.final_particle_states[0].latitude}")
        
    print(f"Wind provider: {res.environmental_metadata.get('wind_provider')}")
    print(f"Currents provider: {res.environmental_metadata.get('currents_provider')}")
    print(f"Actual wind file: {wind.active_filepath}")
    print(f"Actual currents file: {currents.active_filepath}")
    
if __name__ == "__main__":
    asyncio.run(main())
