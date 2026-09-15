import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models.case import ForensicCase
from app.models.vessel import VesselAttribution
from app.models.spill import SpillDetection
from app.models.feature2_result import Feature2Result
from app.tasks.pipeline import execute_5step_pipeline
from app.routers.cases import _persist_vessel_records, _persist_feature2_result

def rerun_case(case_id):
    db = SessionLocal()
    try:
        case_obj = db.query(ForensicCase).filter(ForensicCase.id == case_id).first()
        if not case_obj:
            print(f"Case {case_id} not found.")
            return

        print(f"Re-running pipeline for {case_id}...")
        summary = execute_5step_pipeline(
            case_id=case_id,
            image_path=case_obj.image_path,
            csv_path=case_obj.csv_path,
            center_lat=case_obj.center_latitude,
            center_lon=case_obj.center_longitude
        )

        case_obj.summary_json = summary
        
        spill_info = summary.get("spill", {})
        drift_info = summary.get("drift")

        # Update Spill
        spill_obj = db.query(SpillDetection).filter(SpillDetection.case_id == case_id).first()
        if spill_obj and drift_info:
            spill_obj.origin_latitude = drift_info.get("origin_latitude")
            spill_obj.origin_longitude = drift_info.get("origin_longitude")
            spill_obj.origin_timestamp = drift_info.get("origin_timestamp") or ""
            spill_obj.drift_trajectory_json = drift_info.get("drift_trajectory") or []

        # Re-save Vessel entries
        db.query(VesselAttribution).filter(VesselAttribution.case_id == case_id).delete()
        if summary.get("vessels"):
            _persist_vessel_records(db, case_id, summary.get("vessels", []))
            print(f"Added {len(summary.get('vessels'))} vessels.")

        # Re-save Feature 2 entries
        db.query(Feature2Result).filter(Feature2Result.case_id == case_id).delete()
        if summary.get("feature2"):
            _persist_feature2_result(db, case_id, summary)

        db.commit()
        print("Success! Data re-generated.")
    finally:
        db.close()

if __name__ == "__main__":
    rerun_case("SLK-D2DB")
