import pytest
from datetime import datetime, timezone
import pandas as pd

from app.feature3.cleaning import clean_and_validate_ais
from app.feature3.schemas import Feature2OriginContext, ReleaseTimeWindowContract, LatLon, Feature3EngineConfig
from app.feature3.engine import run_feature3_engine

def test_ais_data_contract_zeros_and_missing():
    # Construct a dataset to test 0s and missing values
    # We will use two vessels to prove data doesn't leak between them
    
    # Vessel 1: Has valid 0 SOG and 0 COG
    vessel1_mmsi = "111111111"
    # Vessel 2: Has missing SOG and missing COG
    vessel2_mmsi = "222222222"
    
    raw_csv = [
        {
            "mmsi": vessel1_mmsi,
            "timestamp": "2026-09-20T10:00:00Z",
            "lat": "10.0",
            "lon": "20.0",
            "sog": "0.0",  # string "0.0" which was fine, but let's test numeric 0 too later
            "cog": "0",
            "vessel_name": "Vessel Zero"
        },
        {
            "mmsi": vessel1_mmsi,
            "timestamp": "2026-09-20T10:10:00Z",
            "lat": "10.1",
            "lon": "20.1",
            "sog": 0.0,    # numeric 0.0
            "cog": 0,      # numeric 0
        },
        {
            "mmsi": vessel2_mmsi,
            "timestamp": "2026-09-20T10:05:00Z",
            "lat": "10.05",
            "lon": "20.05",
            "sog": "",     # empty string -> missing
            "cog": None,   # explicitly None -> missing
            "vessel_name": "Vessel Missing"
        },
        {
            "mmsi": vessel2_mmsi,
            "timestamp": "2026-09-20T10:15:00Z",
            "lat": "10.15",
            "lon": "20.15",
            # sog not provided at all -> missing
            # cog not provided at all -> missing
        }
    ]
    
    # Test cleaning layer
    records, stats = clean_and_validate_ais(raw_csv)
    
    assert len(records) == 4
    
    v1_recs = [r for r in records if r.mmsi == vessel1_mmsi]
    v2_recs = [r for r in records if r.mmsi == vessel2_mmsi]
    
    # Verify cleaning preserves 0.0 and doesn't coerce missing
    assert v1_recs[0].sog == 0.0
    assert v1_recs[0].cog == 0.0
    assert v1_recs[1].sog == 0.0
    assert v1_recs[1].cog == 0.0
    
    assert v2_recs[0].sog is None
    assert v2_recs[0].cog is None
    assert v2_recs[1].sog is None
    assert v2_recs[1].cog is None
    
    # Test engine layer (feature 3 scoring & API serialization)
    f2_context = Feature2OriginContext(
        spill_id="TEST_SPILL",
        origin=LatLon(latitude=10.05, longitude=20.05),
        release_window=ReleaseTimeWindowContract(
            start=datetime(2026, 9, 20, 9, 30, tzinfo=timezone.utc),
            end=datetime(2026, 9, 20, 10, 30, tzinfo=timezone.utc),
        ),
        uncertainty_radius_km=15.0
    )
    
    # We want these vessels to be candidates, which they will be because they are near origin
    response = run_feature3_engine(
        feature2_context=f2_context,
        ais_data=raw_csv,
        config=Feature3EngineConfig(search_radius_km=100.0)
    )
    
    assert response.candidate_count == 2
    
    res_v1 = next(v for v in response.vessels if v.mmsi == vessel1_mmsi)
    res_v2 = next(v for v in response.vessels if v.mmsi == vessel2_mmsi)
    
    # API Contract verification for Vessel 1 (Actual zeros)
    assert res_v1.speed_kts == 0.0
    assert res_v1.heading_deg == 0.0
    # The closest approach point should have 0.0
    assert res_v1.evidence.sog_at_origin_kn == 0.0
    
    # API Contract verification for Vessel 2 (Missing data)
    assert res_v2.speed_kts is None
    assert res_v2.heading_deg is None
    # Closest approach SOG should be missing
    assert res_v2.evidence.sog_at_origin_kn is None
    
    # Verify baseline score didn't crash and median SOG is None for Vessel 2
    assert res_v2.evidence.event_median_sog_kn is None
    
    # Verify that JSON serialization actually exports None as null, not dropped or defaulted to 0
    res_v2_dict = res_v2.model_dump(mode='json')
    assert res_v2_dict["speed_kts"] is None
    assert res_v2_dict["heading_deg"] is None

def test_speed_kts_end_to_end_numeric_contract():
    """
    1. Check speed_kts is float domain type.
    2. Check valid numbers (e.g. 15.5) are preserved exactly.
    3. Check zeros are preserved exactly as 0.0.
    4. Check missing preserves as None.
    """
    raw_csv = [
        {"mmsi": "A1", "timestamp": "2026-09-20T10:00:00Z", "lat": 10.0, "lon": 20.0, "sog": 15.5},
        {"mmsi": "A2", "timestamp": "2026-09-20T10:00:00Z", "lat": 10.1, "lon": 20.1, "sog": 0.0},
        {"mmsi": "A3", "timestamp": "2026-09-20T10:00:00Z", "lat": 10.2, "lon": 20.2, "sog": None},
    ]

    f2_context = Feature2OriginContext(
        spill_id="TEST_SPILL_2",
        origin=LatLon(latitude=10.1, longitude=20.1),
        release_window=ReleaseTimeWindowContract(
            start=datetime(2026, 9, 20, 9, 30, tzinfo=timezone.utc),
            end=datetime(2026, 9, 20, 10, 30, tzinfo=timezone.utc),
        ),
        uncertainty_radius_km=150.0
    )
    
    response = run_feature3_engine(
        feature2_context=f2_context,
        ais_data=raw_csv,
        config=Feature3EngineConfig(search_radius_km=100.0)
    )

    res_v1 = next(v for v in response.vessels if v.mmsi == "A1")
    res_v2 = next(v for v in response.vessels if v.mmsi == "A2")
    res_v3 = next(v for v in response.vessels if v.mmsi == "A3")

    assert res_v1.speed_kts == 15.5
    assert res_v1.model_dump(mode='json')["speed_kts"] == 15.5
    assert type(res_v1.speed_kts) is float

    assert res_v2.speed_kts == 0.0
    assert res_v2.model_dump(mode='json')["speed_kts"] == 0.0
    assert type(res_v2.speed_kts) is float

    assert res_v3.speed_kts is None
    assert res_v3.model_dump(mode='json')["speed_kts"] is None
