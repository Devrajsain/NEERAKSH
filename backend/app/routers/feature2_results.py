"""
API endpoints for Feature 2 results (origin tracing & trajectory forecasting).
These endpoints serve stored Feature 2 pipeline outputs for frontend consumption.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any, Dict

from app.db import get_db
from app.models.feature2_result import Feature2Result
from app.models.case import ForensicCase
from app.schemas.feature2_result import Feature2ResultResponse, Feature2GeoJSONResponse, OriginResponse, ForecastHorizonResponse

router = APIRouter(prefix="/feature2-results", tags=["Feature 2 Results"])


@router.get("/{case_id}", response_model=Feature2ResultResponse)
def get_feature2_result(case_id: str, db: Session = Depends(get_db)):
    """Returns the stored Feature 2 analysis for a specific case."""
    result = db.query(Feature2Result).filter(Feature2Result.case_id == case_id).first()
    if not result:
        case_obj = db.query(ForensicCase).filter(ForensicCase.id == case_id).first()
        if case_obj and case_obj.summary_json and "feature2" in case_obj.summary_json:
            f2 = case_obj.summary_json.get("feature2") or {}
            origin = f2.get("origin") or {}
            drift = case_obj.summary_json.get("drift") or {}
            return Feature2Result(
                id=f"f2-{case_id}",
                case_id=case_id,
                status=f2.get("status", "SKIPPED"),
                processing_mode=f2.get("processing_mode", "mock"),
                origin_latitude=origin.get("origin_latitude"),
                origin_longitude=origin.get("origin_longitude"),
                origin_timestamp=origin.get("origin_timestamp"),
                origin_confidence_score=origin.get("origin_confidence_score"),
                origin_uncertainty_radius_km=origin.get("origin_uncertainty_radius_km"),
                release_window_start=origin.get("release_window_start"),
                release_window_end=origin.get("release_window_end"),
                forecast_json=f2.get("forecast") or {},
                geojson_feature_collection=f2.get("geojson") or {},
                error_message=f2.get("error") or drift.get("error"),
                created_at=case_obj.created_at if getattr(case_obj, "created_at", None) else None,
            )
        raise HTTPException(status_code=404, detail=f"No Feature 2 results found for case {case_id}")
    return result


@router.get("/{case_id}/geojson")
def get_feature2_geojson(case_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns Feature 2 GeoJSON FeatureCollection for map rendering.
    Contains origin points, forecast horizon centroids, and drift trajectories.
    """
    result = db.query(Feature2Result).filter(Feature2Result.case_id == case_id).first()
    if not result:
        case_obj = db.query(ForensicCase).filter(ForensicCase.id == case_id).first()
        if case_obj and case_obj.summary_json and "feature2" in case_obj.summary_json:
            f2 = case_obj.summary_json.get("feature2") or {}
            return f2.get("geojson") or {"type": "FeatureCollection", "features": []}
        raise HTTPException(status_code=404, detail=f"No Feature 2 results found for case {case_id}")

    if result.geojson_feature_collection:
        return result.geojson_feature_collection

    # Build GeoJSON from stored fields if the pre-built collection is missing
    features = []

    if result.origin_latitude and result.origin_longitude:
        features.append({
            "type": "Feature",
            "id": f"{case_id}-origin",
            "geometry": {
                "type": "Point",
                "coordinates": [result.origin_longitude, result.origin_latitude]
            },
            "properties": {
                "type": "origin",
                "label": "Estimated Spill Origin",
                "confidence_score": result.origin_confidence_score,
                "uncertainty_radius_km": result.origin_uncertainty_radius_km,
                "timestamp": result.origin_timestamp,
            }
        })

    if result.forecast_json:
        for h_key in ["6h", "12h", "24h", "48h"]:
            fc = result.forecast_json.get(h_key, {})
            if fc.get("centroid_latitude"):
                features.append({
                    "type": "Feature",
                    "id": f"{case_id}-forecast-{h_key}",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [fc["centroid_longitude"], fc["centroid_latitude"]]
                    },
                    "properties": {
                        "type": "forecast",
                        "horizon": h_key,
                        "label": f"+{h_key} Forecast",
                        "spread_radius_km": fc.get("spread_radius_km"),
                        "quality": fc.get("quality"),
                        "timestamp": fc.get("timestamp"),
                    }
                })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


@router.get("/{case_id}/forecast")
def get_feature2_forecast(case_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Returns just the forecast horizons for a case."""
    result = db.query(Feature2Result).filter(Feature2Result.case_id == case_id).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"No Feature 2 results found for case {case_id}")

    return {
        "case_id": case_id,
        "status": result.status,
        "forecast": result.forecast_json or {},
    }


@router.get("/{case_id}/origin")
def get_feature2_origin(case_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Returns just the origin tracing results for a case."""
    result = db.query(Feature2Result).filter(Feature2Result.case_id == case_id).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"No Feature 2 results found for case {case_id}")

    return {
        "case_id": case_id,
        "status": result.status,
        "origin": {
            "latitude": result.origin_latitude,
            "longitude": result.origin_longitude,
            "timestamp": result.origin_timestamp,
            "confidence_score": result.origin_confidence_score,
            "uncertainty_radius_km": result.origin_uncertainty_radius_km,
            "release_window_start": result.release_window_start,
            "release_window_end": result.release_window_end,
        },
    }


@router.get("/", response_model=List[Feature2ResultResponse])
def list_feature2_results(db: Session = Depends(get_db)):
    """Lists all stored Feature 2 results."""
    return db.query(Feature2Result).all()
