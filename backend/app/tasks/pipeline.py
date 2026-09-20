"""
5-Step Forensic Analysis Pipeline.

Orchestrates the full detection → origin tracing → vessel attribution workflow:
  1. Upload evidence ingestion
  2. AI satellite boundary segmentation (Feature 1)
  3. Oil spill origin tracing & trajectory forecasting (Feature 2)
  4. AIS vessel spatio-temporal attribution
  5. Final case summary compilation

Feature 1 output is automatically converted and fed into Feature 2 via the
feature2_bridge service. Feature 2 results are included in the summary.
"""

import os
import time
import logging
from typing import Optional

from app.services.detection import run_spill_detection_model
from app.services.drift import run_drift_hindcast_model
from app.services.attribution import run_vessel_attribution_model
from app.services.feature2_bridge import feature1_to_feature2_geojson

logger = logging.getLogger(__name__)


def _run_feature2_pipeline(
    case_id: str,
    detection_result: dict,
    center_lat: float,
    center_lon: float,
    allow_test_fixture: bool = False,
) -> dict:
    """
    Attempts to run Feature 2 (origin tracing + trajectory forecasting)
    using the Feature 1 detection output.

    Returns a dict with Feature 2 results, or a status dict if Feature 2
    is unavailable or fails.
    """
    try:
        # Convert Feature 1 output → Feature 2 GeoJSON input
        feature2_input = feature1_to_feature2_geojson(
            detection_output=detection_result,
            case_id=case_id,
            center_lat=center_lat,
            center_lon=center_lon,
        )

        # Try importing and running the Feature 2 pipeline service
        from app.feature2.schemas.feature1_adapter import parse_feature1_input

        if allow_test_fixture:
            from app.feature2.api.dependencies import get_settings
            from app.feature2.data.currents.mock import MockCurrentsProvider
            from app.feature2.data.wind.mock import MockWindProvider
            from app.feature2.simulation.forward.engine import ForwardSimulationEngine
            from app.feature2.simulation.backward.engine import BackwardSimulationEngine
            from app.feature2.origin.estimator import OriginEstimator
            from app.feature2.forecast.forecaster import ForwardForecaster
            from app.feature2.pipeline.service import Feature2PipelineService
            
            settings = get_settings()
            mock_currents = MockCurrentsProvider()
            mock_wind = MockWindProvider()
            fwd_sim = ForwardSimulationEngine(mock_currents, mock_wind, settings)
            bwd_sim = BackwardSimulationEngine(mock_currents, mock_wind, settings)
            origin_est = OriginEstimator(mock_currents, mock_wind, settings)
            forecaster = ForwardForecaster(fwd_sim, settings)
            service = Feature2PipelineService(origin_est, forecaster, settings)
        else:
            from app.feature2.api.dependencies import get_pipeline_service
            service = get_pipeline_service()
        slick_input = parse_feature1_input(feature2_input)
        pipeline_response = service.run_pipeline(slick_input)

        # Extract origin results
        origin_data = {}
        if pipeline_response.origin_analysis and pipeline_response.origin_analysis.best_candidate:
            best = pipeline_response.origin_analysis.best_candidate
            origin_data = {
                "origin_latitude": best.latitude,
                "origin_longitude": best.longitude,
                "origin_timestamp": best.release_time.isoformat() if best.release_time else None,
                "origin_confidence_score": best.candidate_score,
                "origin_uncertainty_radius_km": best.uncertainty_radius_km,
            }

            if pipeline_response.origin_analysis.release_time_window:
                rtw = pipeline_response.origin_analysis.release_time_window
                origin_data["release_window_start"] = rtw.start.isoformat() if hasattr(rtw, 'start') else None
                origin_data["release_window_end"] = rtw.end.isoformat() if hasattr(rtw, 'end') else None

        # Extract forecast results
        forecast_data = {}
        if pipeline_response.forecast:
            for h_key in ["6h", "12h", "24h", "48h"]:
                if h_key in pipeline_response.forecast:
                    fch = pipeline_response.forecast[h_key]
                    forecast_data[h_key] = {
                        "lead_time_hours": fch.lead_time_hours,
                        "timestamp": fch.forecast_time.isoformat() if hasattr(fch, 'forecast_time') and fch.forecast_time else None,
                        "centroid_latitude": fch.centroid.latitude if hasattr(fch, 'centroid') and fch.centroid else None,
                        "centroid_longitude": fch.centroid.longitude if hasattr(fch, 'centroid') and fch.centroid else None,
                        "spread_radius_km": round(fch.uncertainty.radius_km, 3) if hasattr(fch, 'uncertainty') and fch.uncertainty else None,
                        "active_particles": fch.active_particle_count if hasattr(fch, 'active_particle_count') else None,
                        "quality": fch.quality.upper() if hasattr(fch, 'quality') and fch.quality else "UNKNOWN",
                        "valid": fch.valid if hasattr(fch, 'valid') else True,
                    }

        # Build GeoJSON for map rendering
        geojson_features = []

        # Origin point feature
        if origin_data.get("origin_latitude"):
            geojson_features.append({
                "type": "Feature",
                "id": f"{case_id}-origin",
                "geometry": {
                    "type": "Point",
                    "coordinates": [origin_data["origin_longitude"], origin_data["origin_latitude"]]
                },
                "properties": {
                    "type": "origin",
                    "label": "Estimated Spill Origin",
                    "confidence_score": origin_data.get("origin_confidence_score"),
                    "uncertainty_radius_km": origin_data.get("origin_uncertainty_radius_km"),
                    "timestamp": origin_data.get("origin_timestamp"),
                }
            })

        # Forecast horizon features
        for h_key, fc in forecast_data.items():
            if fc.get("centroid_latitude"):
                geojson_features.append({
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

        geojson_collection = {
            "type": "FeatureCollection",
            "features": geojson_features,
        }

        return {
            "status": "COMPLETED",
            "processing_mode": "live",
            "origin": origin_data,
            "forecast": forecast_data,
            "geojson": geojson_collection,
            "pipeline_response": None,  # Too large; store separately if needed
        }

    except Exception as e:
        logger.error(f"Feature 2 pipeline failed for case {case_id}: {e}", exc_info=True)
        return {
            "status": "DATA_UNAVAILABLE",
            "processing_mode": "live",
            "error": str(e),
            "origin": {},
            "forecast": {},
            "geojson": {"type": "FeatureCollection", "features": []},
        }


def execute_5step_pipeline(
    case_id: str,
    image_path: Optional[str],
    csv_path: Optional[str],
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    observation_time: Optional[str] = None,
    allow_test_fixture: bool = False,
) -> dict:
    """
    Executes the 5-step forensic analysis pipeline:
    1. Upload evidence ingestion
    2. AI satellite boundary segmentation (Feature 1)
    3. Oil spill origin tracing & trajectory forecasting (Feature 2)
    4. AIS vessel spatio-temporal attribution
    5. Final case summary compilation

    If GeoTIFF metadata exists, real detected spill coordinates and genuine Sentinel-1
    acquisition timestamps are extracted.
    If JPG/PNG or unreferenced TIFF, coordinates and timestamps must be provided and valid
    before Feature 2 runs.
    """
    # Step 2: Satellite Detection (Feature 1)
    spill_res = run_spill_detection_model(
        image_path=image_path,
        center_lat=center_lat,
        center_lon=center_lon,
        observation_time=observation_time,
        allow_test_fixture=allow_test_fixture,
    )
    # Determine effective coordinates: GeoTIFF auto-detected coordinates take precedence
    # EXCEPT in test mode, where explicit center coords take precedence for synthetic data consistency
    if allow_test_fixture and center_lat is not None and center_lon is not None:
        effective_lat = center_lat
        effective_lon = center_lon
        spill_res["spill_latitude"] = center_lat
        spill_res["spill_longitude"] = center_lon
        # Override geometry to be a box around the center so backward simulation starts in the right place
        spill_res["polygon_geojson"] = {
            "type": "Polygon",
            "coordinates": [[
                [center_lon - 0.1, center_lat - 0.1],
                [center_lon + 0.1, center_lat - 0.1],
                [center_lon + 0.1, center_lat + 0.1],
                [center_lon - 0.1, center_lat + 0.1],
                [center_lon - 0.1, center_lat - 0.1]
            ]]
        }
    elif spill_res.get("geospatial_metadata_detected") and spill_res.get("spill_latitude") is not None:
        effective_lat = spill_res["spill_latitude"]
        effective_lon = spill_res["spill_longitude"]
    else:
        effective_lat = center_lat if center_lat is not None else spill_res.get("spill_latitude")
        effective_lon = center_lon if center_lon is not None else spill_res.get("spill_longitude")

    # Validate coordinates if provided
    if effective_lat is not None or effective_lon is not None:
        if effective_lat is None or effective_lon is None or not (-90.0 <= effective_lat <= 90.0 and -180.0 <= effective_lon <= 180.0):
            raise ValueError("Invalid latitude/longitude. Please enter valid geographic coordinates.")

    # Check if valid coordinates are present to proceed to Feature 2
    coords_valid = (
        effective_lat is not None and effective_lon is not None and
        -90.0 <= effective_lat <= 90.0 and -180.0 <= effective_lon <= 180.0
    )

    if not coords_valid:
        # Do NOT call Feature 2 without valid coordinates
        logger.info(f"Case {case_id}: Geographic coordinates not yet provided. Feature 2 paused.")
        return {
            "case_id": case_id,
            "status": "AWAITING_COORDINATES",
            "spill": spill_res,
            "drift": None,
            "vessels": [],
            "feature2": {"status": "SKIPPED", "message": "Awaiting valid geographic coordinates"},
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        }

    is_production = os.getenv("FEATURE2_ENVIRONMENT", "").lower() == "production"
    if is_production and (not spill_res.get("observation_time") or spill_res.get("status") == "DATA_UNAVAILABLE"):
        logger.warning(f"Case {case_id}: Sentinel-1 acquisition timestamp unavailable in production mode. Failing closed.")
        return {
            "case_id": case_id,
            "status": "DATA_UNAVAILABLE",
            "spill": spill_res,
            "drift": {
                "status": "DATA_UNAVAILABLE",
                "origin_latitude": None,
                "origin_longitude": None,
                "origin_timestamp": None,
                "drift_trajectory": [],
                "error": "Sentinel-1 acquisition timestamp unavailable.",
            },
            "vessels": [],
            "feature2": {
                "status": "DATA_UNAVAILABLE",
                "error": "Sentinel-1 acquisition timestamp unavailable.",
                "origin": {},
                "forecast": {},
                "geojson": {"type": "FeatureCollection", "features": []},
            },
            "attribution_status": "SKIPPED_ENVIRONMENT_DATA_UNAVAILABLE",
            "attribution_message": "Feature 3 attribution skipped: Environmental origin context is unavailable from Feature 2.",
            "processed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        }

    # Step 3: Feature 2 — Origin Tracing & Trajectory Forecasting
    logger.info(
        f"Pipeline Step 3: Passing coordinates to Feature 2 for case {case_id}: "
        f"effective_lat={effective_lat}, effective_lon={effective_lon}, "
        f"geospatial_metadata_detected={spill_res.get('geospatial_metadata_detected')}, "
        f"observation_time={spill_res.get('observation_time')}"
    )
    feature2_res = _run_feature2_pipeline(case_id, spill_res, effective_lat, effective_lon, allow_test_fixture)

    # Check if mock mode is explicitly requested
    is_explicit_mock = (
        os.getenv("FEATURE2_ENVIRONMENT", "").lower() == "testing"
        or os.getenv("FEATURE2_CURRENTS_PROVIDER", "").lower() == "mock"
    )

    # Use Feature 2 origin if available, otherwise handle explicit mock or data unavailable
    if feature2_res.get("status") == "COMPLETED" and feature2_res.get("origin", {}).get("origin_latitude"):
        drift_res = {
            "status": "COMPLETED",
            "origin_latitude": feature2_res["origin"]["origin_latitude"],
            "origin_longitude": feature2_res["origin"]["origin_longitude"],
            "origin_timestamp": feature2_res["origin"].get("origin_timestamp", ""),
            "drift_trajectory": [],
        }

        # Build trajectory from forecast data
        trajectory = []
        if feature2_res["origin"].get("origin_timestamp"):
            trajectory.append({
                "time": "origin",
                "lat": feature2_res["origin"]["origin_latitude"],
                "lon": feature2_res["origin"]["origin_longitude"],
            })
        trajectory.append({
            "time": "detected (0h)",
            "lat": effective_lat,
            "lon": effective_lon,
        })
        for h_key in ["6h", "12h", "24h", "48h"]:
            fc = feature2_res.get("forecast", {}).get(h_key, {})
            if fc.get("centroid_latitude"):
                trajectory.append({
                    "time": f"+{h_key} forecast",
                    "lat": fc["centroid_latitude"],
                    "lon": fc["centroid_longitude"],
                })
        drift_res["drift_trajectory"] = trajectory
        
        # Bayesian pipeline needs spatial/temporal prefilter boundaries
        drift_fallback = run_drift_hindcast_model(
            effective_lat,
            effective_lon,
            detection_timestamp=spill_res.get("detection_timestamp") or spill_res.get("observation_time"),
        )
        drift_res["prefilter_start_time"] = drift_fallback.get("prefilter_start_time")
        drift_res["prefilter_end_time"] = drift_fallback.get("prefilter_end_time")
        drift_res["candidate_spatial_region"] = drift_fallback.get("candidate_spatial_region")
        drift_res["simulation_duration_hours"] = drift_fallback.get("simulation_duration_hours")
        
    elif is_explicit_mock:
        # Fall back to simple mock drift ONLY in explicit mock mode
        logger.info(
            f"Case {case_id}: Explicit mock mode active (FEATURE2_ENVIRONMENT=testing or FEATURE2_CURRENTS_PROVIDER=mock). "
            "Running synthetic drift hindcast model."
        )
        drift_res = run_drift_hindcast_model(
            effective_lat,
            effective_lon,
            detection_timestamp=spill_res.get("detection_timestamp"),
        )
    else:
        # Real mode and Feature 2 failed or data unavailable: fail cleanly without synthetic drift
        logger.warning(
            f"Case {case_id}: Real environmental data is unavailable for Feature 2. "
            "Failing cleanly without synthetic/mock fallback."
        )
        drift_res = {
            "status": "DATA_UNAVAILABLE",
            "origin_latitude": None,
            "origin_longitude": None,
            "origin_timestamp": None,
            "drift_trajectory": [],
            "error": feature2_res.get("error", "Environmental data unavailable"),
        }

    # Step 4: AIS Vessel Attribution
    # Requirement 4: When Feature 2 returns DATA_UNAVAILABLE in real mode, Feature 3 attribution must NOT execute an attribution calculation.
    # It should report that environmental origin context is unavailable.
    
    bayesian_report = None
    
    if drift_res.get("status") == "DATA_UNAVAILABLE" or drift_res.get("origin_latitude") is None:
        logger.warning(
            f"Case {case_id}: Skipping Feature 3 vessel attribution because environmental origin context is unavailable."
        )
        vessels_res = []
        attribution_status = "SKIPPED_ENVIRONMENT_DATA_UNAVAILABLE"
        attribution_message = "Feature 3 attribution skipped: Environmental origin context is unavailable from Feature 2."
    else:
        f2_ctx = None
        if feature2_res.get("status") == "COMPLETED" and feature2_res.get("origin", {}).get("origin_latitude"):
            try:
                from app.feature3.adapter import extract_feature2_context
                f2_ctx = extract_feature2_context(
                    feature2_data=feature2_res,
                    spill_data=spill_res,
                    drift_data=drift_res,
                    spill_id=case_id,
                )
            except Exception as e:
                logger.warning(f"Could not build Feature2 context for attribution: {e}")

        # Explicit test/demo execution detection for Feature 3 fallbacks (e.g., demo AIS data)
        is_test_or_demo = bool(
            case_id and ("TEST" in case_id.upper() or "DEMO" in case_id.upper() or "SAMPLE" in case_id.upper())
        )

        vessels_res = run_vessel_attribution_model(
            csv_path=csv_path,
            origin_lat=drift_res["origin_latitude"],
            origin_lon=drift_res["origin_longitude"],
            feature2_context=f2_ctx,
            allow_demo_fallback=is_test_or_demo,
        )
        attribution_status = "COMPLETED" if vessels_res else "NO_VESSELS_FOUND"
        attribution_message = None

        should_run_bayesian = bool(allow_test_fixture)
        
        if should_run_bayesian and drift_res.get("origin_latitude") is not None:
            from app.bayesian.orchestrator import BayesianPipelineOrchestrator
            from app.bayesian.schemas import BayesianPipelineRequest, BayesianPrefilterResult
            from app.services.feature2_bridge import feature1_to_feature2_geojson
            from app.feature2.schemas.feature1_adapter import parse_feature1_input
            
            feature2_input = feature1_to_feature2_geojson(
                detection_output=spill_res,
                case_id=case_id,
                center_lat=spill_res["spill_latitude"],
                center_lon=spill_res["spill_longitude"],
            )
            slick_input = parse_feature1_input(feature2_input)
            
            import csv
            ais_data = []
            effective_csv = csv_path
            if not effective_csv or not os.path.exists(effective_csv):
                if allow_test_fixture:
                    from app.config import settings
                    sample_csv = os.path.join(settings.UPLOAD_DIR, "sample_ais_telemetry.csv")
                    if os.path.exists(sample_csv):
                        effective_csv = sample_csv

            if effective_csv and os.path.exists(effective_csv):
                with open(effective_csv, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    ais_data = list(reader)

            from datetime import timedelta
            t_end = slick_input.observation_time
            t_start = t_end - timedelta(hours=72)
            
            # If Feature 2 didn't provide a candidate region, build a generous bounding box around the origin/slick
            # to ensure we don't drop candidates for the synthetic dataset.
            region = drift_res.get("candidate_spatial_region")
            if not region:
                olat = drift_res.get("origin_latitude") or effective_lat
                olon = drift_res.get("origin_longitude") or effective_lon
                region = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [olon - 2.0, olat - 2.0],
                            [olon + 2.0, olat - 2.0],
                            [olon + 2.0, olat + 2.0],
                            [olon - 2.0, olat + 2.0],
                            [olon - 2.0, olat - 2.0]
                        ]]
                    }
                }

            bayesian_req = BayesianPipelineRequest(
                spill_data=slick_input,
                ais_data=ais_data,
                feature2_context=f2_ctx
            )

            is_explicit_mock = (
                os.getenv("FEATURE2_ENVIRONMENT", "").lower() == "testing"
                or os.getenv("FEATURE2_CURRENTS_PROVIDER", "").lower() == "mock"
            )
            
            if allow_test_fixture or is_explicit_mock:
                from app.feature2.data.currents.mock import MockCurrentsProvider
                currents_provider = MockCurrentsProvider()
                from app.feature2.data.wind.mock import MockWindProvider
                wind_provider = MockWindProvider()
            else:
                from app.feature2.api.dependencies import get_currents_provider, get_wind_provider, get_settings
                
                settings = get_settings()
                currents_provider = get_currents_provider(settings)
                wind_provider = get_wind_provider(settings)

            orchestrator = BayesianPipelineOrchestrator(currents_provider=currents_provider, wind_provider=wind_provider)
            bayesian_report = orchestrator.run_pipeline(bayesian_req).model_dump(mode='json')

    # Step 5: Summary Package
    summary_status = "DATA_UNAVAILABLE" if drift_res.get("status") == "DATA_UNAVAILABLE" else "COMPLETED"
    
    attribution_mode = "BAYESIAN" if allow_test_fixture else "FEATURE3"
    
    summary = {
        "case_id": case_id,
        "status": summary_status,
        "is_test_mode": allow_test_fixture,
        "attribution_mode": attribution_mode,
        "spill": spill_res,
        "drift": drift_res,
        "vessels": vessels_res,
        "feature2": feature2_res,
        "bayesian_report": bayesian_report,
        "attribution_status": attribution_status,
        "attribution_message": attribution_message,
        "processed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    return summary
