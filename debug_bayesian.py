import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add backend directory to path
backend_dir = Path("backend").resolve()
sys.path.insert(0, str(backend_dir))

from app.tasks.pipeline import execute_5step_pipeline
from app.bayesian.config import bayesian_settings

import argparse

def run_debug():
    parser = argparse.ArgumentParser(description="Debug Bayesian Execution")
    parser.add_argument("--image-path", required=True, help="Path to the synthetic oil spill TIFF")
    parser.add_argument("--csv-path", required=True, help="Path to the synthetic AIS CSV")
    args = parser.parse_args()

    # Set to testing so it uses mock current provider
    os.environ["FEATURE2_ENVIRONMENT"] = "testing"
    
    # Run the pipeline just like the integration test
    image_path = Path(args.image_path)
    csv_path = Path(args.csv_path)
    
    # We explicitly pass allow_test_fixture=True to simulate the frontend checkbox
    summary = execute_5step_pipeline(
        case_id="TEST_SYNTHETIC_DEBUG",
        image_path=str(image_path),
        csv_path=str(csv_path),
        center_lat=41.6,
        center_lon=2.7,
        observation_time="2024-01-14T21:00:00Z",
        allow_test_fixture=True
    )
    
    # Let's test the generator directly
    import csv
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        ais_data = list(reader)
        
    from app.bayesian.schemas import BayesianPrefilterResult
    from app.bayesian.candidate_generator import generate_candidate_hypotheses
    import dateutil.parser
    
    t0 = dateutil.parser.parse("2024-01-15T10:00:00Z")
    from datetime import timedelta
    t_start = t0 - timedelta(hours=72)
    
    prefilter = BayesianPrefilterResult(
        role="SEARCH_PREFILTER_ONLY",
        spill_id="TEST_SYNTHETIC_DEBUG",
        observation_time=t0,
        prefilter_start_time=t_start,
        prefilter_end_time=t0,
        backward_horizon_hours=72.0,
        candidate_spatial_region={
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[1.5999, 40.7506], [2.9120, 40.7506], [2.9120, 42.2494], [1.5999, 42.2494], [1.5999, 40.7506]]
                ]
            }
        },
        active_particle_count=100
    )
    
    res = generate_candidate_hypotheses(prefilter, ais_data)
    print(f"Candidates generated directly: {res.candidate_count}")
    
    # Print exactly why the first one fails
    from app.bayesian.candidate_generator import _build_shapely_polygon, _ensure_utc, _in_temporal_window, _point_inside_or_on_boundary
    from app.feature3.cleaning import clean_and_validate_ais
    cleaned, _ = clean_and_validate_ais(ais_data)
    poly = _build_shapely_polygon(prefilter.candidate_spatial_region)
    for rec in cleaned:
        rec_ts = _ensure_utc(rec.timestamp)
        t_pass = _in_temporal_window(rec_ts, t_start, t0)
        s_pass = _point_inside_or_on_boundary(poly, rec.longitude, rec.latitude)
        print(f"MMSI: {rec.mmsi}, TS: {rec_ts}, Lat/Lon: {rec.latitude}/{rec.longitude}, Temporal: {t_pass}, Spatial: {s_pass}")
        break

if __name__ == "__main__":
    run_debug()
