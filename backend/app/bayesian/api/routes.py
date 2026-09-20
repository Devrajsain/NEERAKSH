from fastapi import APIRouter, HTTPException, Body
from typing import Any
import logging

from app.bayesian.schemas import (
    FinalAttributionRequest,
    FinalAttributionReport,
    BayesianPipelineRequest
)
from app.bayesian.final_attribution import FinalAttributionEngine
from app.bayesian.orchestrator import BayesianPipelineOrchestrator
from app.feature2.data.currents.copernicus import CopernicusForecastCurrentsProvider

# We import Feature3 response locally if needed, but since it's passed as Any in the request,
# we cast it inside the endpoint to ensure type-checking works without circular loops.
from app.feature3.schemas import Feature3AttributionResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bayesian_attribution"])

@router.post(
    "/bayesian_final_report",
    response_model=FinalAttributionReport,
    summary="Generate Final Bayesian Attribution Report",
    description="""
    Aggregates Phase 5 Posteriors, Phase 6 Confidence, and Feature 3 Supplemental Evidence
    into a structured read-only Final Attribution Report.
    Does NOT modify Bayesian probabilities or invent new attribution scores.
    """
)
async def generate_final_report(request: FinalAttributionRequest = Body(...)):
    try:
        engine = FinalAttributionEngine()
        
        # Cast Feature 3 response if provided
        f3_resp = None
        if request.feature3_response:
            # We parse it directly in case it comes as a raw dict
            f3_resp = Feature3AttributionResponse.model_validate(request.feature3_response)

        report = engine.generate_report(
            spill_id=request.spill_id,
            posterior_result=request.posterior_result,
            confidence_results=request.confidence_results,
            feature3_response=f3_resp,
            provenance=request.provenance
        )
        
        return report

    except Exception:
        logger.exception("Internal error generating final attribution report")
        raise HTTPException(status_code=500, detail="Internal server error generating final attribution report.")

@router.post(
    "/attribution_pipeline",
    response_model=FinalAttributionReport,
    summary="Execute End-to-End Bayesian Attribution Pipeline",
    description="""
    Executes the full pipeline sequentially:
    Phase 1 (Prefilter) -> Phase 2 (Candidate Gen) -> Phase 3C (OpenOil) -> Phase 4 (Likelihood)
    -> Phase 5 (Posterior) -> Phase 6 (Confidence) -> Feature 3 (Optional) -> Final Attribution.
    """
)
async def execute_attribution_pipeline(request: BayesianPipelineRequest = Body(...)):
    try:
        # Dependency injection for environmental provider (e.g. default to a placeholder or Copernicus)
        # Note: In production, we'd inject this via Depends, but for simplicity we instantiate it
        # or use a default one. In the context of tests, the orchestrator handles it.
        # Here we just initialize a basic Copernicus provider.
        from app.feature2.data.currents.copernicus import CopernicusConfig
        currents_provider = CopernicusForecastCurrentsProvider(config=CopernicusConfig(dataset_id="cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m", u_var="uo", v_var="vo"))

        orchestrator = BayesianPipelineOrchestrator(
            currents_provider=currents_provider,
            wind_provider=None
        )

        report = orchestrator.run_pipeline(request)
        return report

    except Exception:
        logger.exception("Internal error executing Bayesian pipeline")
        raise HTTPException(status_code=500, detail="Internal server error executing Bayesian pipeline.")

@router.post(
    "/attribution_pipeline_by_case/{case_id}",
    response_model=FinalAttributionReport,
    summary="Execute Bayesian Attribution Pipeline for a specific Case ID",
    description="Loads the case data from the database and runs the Bayesian pipeline."
)
async def execute_attribution_pipeline_by_case(case_id: str):
    try:
        from app.db import SessionLocal
        from app.models.case import ForensicCase
        import os
        import csv
        
        db = SessionLocal()
        try:
            case_obj = db.query(ForensicCase).filter(ForensicCase.id == case_id).first()
            if not case_obj:
                raise HTTPException(status_code=404, detail="Case not found")
                
            summary = case_obj.summary_json or {}
            spill_res = summary.get("spill", {})
            
            if not spill_res:
                raise HTTPException(status_code=400, detail="Case has no spill detection data")
                
            from app.services.feature2_bridge import feature1_to_feature2_geojson
            from app.feature2.schemas.feature1_adapter import parse_feature1_input
            
            feature2_input = feature1_to_feature2_geojson(
                detection_output=spill_res,
                case_id=case_id,
                center_lat=spill_res.get("spill_latitude", case_obj.center_latitude),
                center_lon=spill_res.get("spill_longitude", case_obj.center_longitude),
            )
            slick_input = parse_feature1_input(feature2_input)
            
            ais_data = []
            if case_obj.csv_path and os.path.exists(case_obj.csv_path):
                with open(case_obj.csv_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    ais_data = list(reader)
                    
            from app.bayesian.schemas import BayesianPipelineRequest
            
            f2_ctx = None
            try:
                drift_res = summary.get("drift", {})
                feature2_res = summary.get("feature2", {})
                if feature2_res.get("status") == "COMPLETED" and feature2_res.get("origin", {}).get("origin_latitude"):
                    from app.feature3.adapter import extract_feature2_context
                    f2_ctx = extract_feature2_context(
                        feature2_data=feature2_res,
                        spill_data=spill_res,
                        drift_data=drift_res,
                        spill_id=case_id,
                    )
            except Exception as e:
                logger.warning(f"Could not build Feature2 context for attribution: {e}")
                
            bayesian_req = BayesianPipelineRequest(
                spill_data=slick_input,
                ais_data=ais_data,
                feature2_context=f2_ctx
            )
            
            from app.feature2.data.currents.copernicus import CopernicusConfig, CopernicusForecastCurrentsProvider
            
            is_explicit_mock = (
                os.getenv("FEATURE2_ENVIRONMENT", "").lower() == "testing"
                or os.getenv("FEATURE2_CURRENTS_PROVIDER", "").lower() == "mock"
            )
            
            if is_explicit_mock:
                from app.feature2.data.currents.mock import MockCurrentsProvider
                currents_provider = MockCurrentsProvider()
                from app.feature2.data.wind.mock import MockWindProvider
                wind_provider = MockWindProvider()
            else:
                from app.feature2.api.dependencies import get_currents_provider, get_wind_provider, get_settings
                
                settings = get_settings()
                currents_provider = get_currents_provider(settings)
                wind_provider = get_wind_provider(settings)
                
            orchestrator = BayesianPipelineOrchestrator(
                currents_provider=currents_provider,
                wind_provider=wind_provider
            )
            
            report = orchestrator.run_pipeline(bayesian_req)
            
            # Save the report to the case summary
            summary["bayesian_report"] = report.model_dump()
            summary["attribution_mode"] = "BAYESIAN"
            case_obj.summary_json = summary
            db.commit()
            
            return report
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Internal error executing Bayesian pipeline by case")
        raise HTTPException(status_code=500, detail="Internal server error executing Bayesian pipeline by case.")
