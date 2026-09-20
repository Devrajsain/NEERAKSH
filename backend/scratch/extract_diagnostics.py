import sys
import os
import json
import numpy as np
from shapely.geometry import shape, Point
from datetime import datetime, timezone
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db import SessionLocal
from app.models.case import ForensicCase
from app.models.spill import SpillDetection
from app.feature2.geo.coordinates import haversine_distance_km
import csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_diagnostics():
    db = SessionLocal()
    case = db.query(ForensicCase).first()
    if not case:
        print("No cases found.")
        return
        
    spill = db.query(SpillDetection).filter(SpillDetection.case_id == case.id).first()
    if not spill:
        print("No spill found for case.")
        return

    # Use the pipeline exactly as it runs in the real backend
    # but hook into the orchestrator locally to extract diagnostics
    from app.bayesian.orchestrator import BayesianPipelineOrchestrator
    from app.bayesian.config import bayesian_settings
    from app.bayesian.schemas import BayesianPipelineRequest, OpenOilEnsembleConfig
    from app.feature2.schemas.input_schema import SlickDetectionInput, GeoJSONGeometry, CentroidCoordinates
    
    # We will instantiate the components just like pipeline.py does,
    # but we'll run the simulation and extract the exact spatial data.
    from app.feature2.data.currents.mock import MockCurrentsProvider
    from app.feature2.data.wind.mock import MockWindProvider
    
    currents_provider = MockCurrentsProvider()
    wind_provider = MockWindProvider()

    orchestrator = BayesianPipelineOrchestrator(
        currents_provider=currents_provider,
        wind_provider=wind_provider
    )
    
    spill_data = SlickDetectionInput(
        spill_id=spill.id,
        observation_time=datetime.fromisoformat(spill.detection_timestamp),
        geometry=GeoJSONGeometry(**spill.polygon_geojson),
        centroid=CentroidCoordinates(latitude=spill.origin_latitude, longitude=spill.origin_longitude),
        area_sq_km=spill.area_km2,
        perimeter_km=spill.length_km + spill.width_km
    )
    
    ais_data = []
    if case.csv_path and os.path.exists(case.csv_path):
        with open(case.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ais_data.append(row)
                
    request = BayesianPipelineRequest(spill_data=spill_data, ais_data=ais_data)
    orchestrator.simulation_runner.config = OpenOilEnsembleConfig(environment_margin_deg=0.5)
    
    # Run the prefilter and candidate generation
    from app.bayesian.candidate_generator import generate_candidate_hypotheses
    
    prefilter_result = orchestrator.prefilter_engine.run_prefilter(
        source=spill_data
    )
    
    candidate_result = generate_candidate_hypotheses(
        prefilter_result=prefilter_result,
        ais_source=ais_data,
    )
    
    # Environmental provenance
    print("\n" + "="*50)
    print("ENVIRONMENTAL PROVENANCE (TASK 5)")
    print("="*50)
    print(f"ERA5 Wind Provider Active File: {wind_provider.active_filepath}")
    print(f"CMEMS Currents Provider Active File: {currents_provider.active_filepath}")
    
    if wind_provider.active_filepath and os.path.exists(wind_provider.active_filepath):
        import netCDF4
        ds = netCDF4.Dataset(wind_provider.active_filepath)
        print(f"ERA5 Variables: {list(ds.variables.keys())}")
        ds.close()
    if currents_provider.active_filepath and os.path.exists(currents_provider.active_filepath):
        import netCDF4
        ds = netCDF4.Dataset(currents_provider.active_filepath)
        print(f"CMEMS Variables: {list(ds.variables.keys())}")
        ds.close()

    spill_poly = shape(spill_data.geometry.model_dump())
    
    # Run OpenOil and extract specific spatial metrics for each candidate
    print("\n" + "="*50)
    print("OPENOIL SPATIAL & TEMPORAL DIAGNOSTICS (TASK 2 & 3)")
    print("="*50)
    
    simulations = []
    likelihoods = []
    
    for cand in candidate_result.candidates:
        print(f"\n--- Candidate: {cand.candidate_id} (MMSI: {cand.mmsi}) ---")
        sim = orchestrator.simulation_runner.run_candidate(
            candidate=cand,
            observation_time=spill_data.observation_time
        )
        simulations.append(sim)
        
        print(f"Status: {sim.status}")
        if sim.status != "SUCCESS":
            print("Simulation failed. Skipping.")
            continue
            
        print(f"Ensemble Size Requested: {sim.ensemble_size_requested}")
        
        valid_particles = []
        active_count = 0
        stranded_count = 0
        
        for p in sim.final_particle_states:
            if p.original_status_code != 2:
                valid_particles.append(p)
            if p.status == "active":
                active_count += 1
            if p.status == "stranded":
                stranded_count += 1
                
        print(f"Valid Particle Count: {len(valid_particles)}")
        print(f"Active Particle Count: {active_count}")
        print(f"Stranded Particle Count: {stranded_count}")
        
        inside_count = 0
        distances_m = []
        
        for p in valid_particles:
            pt = Point(p.longitude, p.latitude)
            if pt.within(spill_poly):
                inside_count += 1
                distances_m.append(0.0)
            else:
                # Approximate distance to the polygon in meters using haversine on the nearest point
                nearest = spill_poly.exterior.interpolate(spill_poly.exterior.project(pt))
                dist_km = haversine_distance_km(p.latitude, p.longitude, nearest.y, nearest.x)
                distances_m.append(dist_km * 1000.0)
                
        print(f"Particles Inside Geometry: {inside_count}")
        if distances_m:
            print(f"Min Distance to Geometry: {np.min(distances_m):.2f} m")
            print(f"Median Distance to Geometry: {np.median(distances_m):.2f} m")
            print(f"Max Distance to Geometry: {np.max(distances_m):.2f} m")
            
        print(f"\n--- Time Alignment (Task 3) ---")
        print(f"Simulation Start (Release): {sim.release_timestamp}")
        print(f"Simulation End: {sim.actual_final_timestamp}")
        print(f"Spill Observation: {sim.requested_observation_timestamp}")
        
        # Likelihood Diagnostic (Task 4)
        lh = orchestrator.likelihood_engine.evaluate(
            observations=[spill_data],
            simulation_result=sim
        )
        likelihoods.append(lh)
        
        print(f"\n--- Likelihood Diagnostic (Task 4) ---")
        print(f"Likelihood Mode: {lh.likelihood_mode}")
        print(f"Candidate Likelihood: {lh.likelihood}")
        
        for obs in lh.per_observation_diagnostics:
            print(f"Compatible Particles (Intersection): {obs.compatible_particle_count}")
            print(f"Valid Particles Used: {obs.valid_particle_count}")
            print(f"Evaluated At: {obs.evaluation_timestamp}")
            print(f"Temporal Mismatch: {obs.final_time_offset_seconds}s")
            print(f"Threshold Distance Evaluated: threshold (requires strict intersection, sigma is not applied as a soft margin)")
        

if __name__ == "__main__":
    run_diagnostics()
