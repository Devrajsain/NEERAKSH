from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

from app.bayesian.schemas import (
    BayesianPosteriorResult,
    PhysicsAwareConfidence,
    FinalAttributionReport,
    FinalCandidateRecord,
    SupplementalDeterministicEvidence,
    AttributionProvenance
)
from app.feature3.schemas import Feature3AttributionResponse, VesselAttributionResult

class FinalAttributionEngine:
    """
    Read-only aggregator producing the Final Attribution Report.
    MUST NOT modify probabilities, drop unavailable evaluated candidates,
    or create new attribution scores/winner flags.
    """

    def generate_report(
        self,
        spill_id: str,
        posterior_result: BayesianPosteriorResult,
        confidence_results: List[PhysicsAwareConfidence],
        feature3_response: Optional[Feature3AttributionResponse],
        provenance: AttributionProvenance
    ) -> FinalAttributionReport:
        
        # 1. Map confidence results by candidate_id
        conf_map = {c.candidate_id: c for c in confidence_results}
        
        # 2. Map feature 3 results by MMSI
        f3_map: Dict[str, VesselAttributionResult] = {}
        if feature3_response:
            for v in feature3_response.vessels:
                f3_map[v.mmsi] = v
                
        # 3. Evaluate candidate coverages
        evaluated_candidates = posterior_result.evaluated_candidate_count
        returned_candidates = posterior_result.returned_candidate_count
        
        unavailable_ids = []
        for p in posterior_result.posteriors:
            if p.evaluation_status == "EVALUATION_UNAVAILABLE":
                unavailable_ids.append(p.candidate_id)
                
        unavailable_candidates = len(unavailable_ids)

        # 4. Build Final Candidate Records
        final_candidates = []
        for p in posterior_result.posteriors:
            c_id = p.candidate_id
            conf = conf_map.get(c_id)
            f3_res = f3_map.get(p.mmsi)
            
            # Confidence handling
            if conf:
                c_level = conf.confidence_level
                c_diags = conf.diagnostics
                c_flags = conf.flags
            else:
                c_level = "INDETERMINATE"
                c_diags = []
                c_flags = []
                if "Phase 6 physics-aware confidence data is missing for one or more candidates." not in posterior_result.warnings:
                    posterior_result.warnings.append("Phase 6 physics-aware confidence data is missing for one or more candidates.")
                
            # Feature 3 mapping
            if f3_res:
                supp_ev = SupplementalDeterministicEvidence(
                    feature3_overall_score=f3_res.overall_score,
                    metrics=f3_res.evidence.model_dump(),
                    risk_class=f3_res.risk_class
                )
            else:
                supp_ev = SupplementalDeterministicEvidence()

            final_candidates.append(
                FinalCandidateRecord(
                    candidate_id=c_id,
                    mmsi=p.mmsi,
                    release_latitude=p.release_latitude,
                    release_longitude=p.release_longitude,
                    release_timestamp=p.release_timestamp,
                    evaluation_status=p.evaluation_status,
                    prior_probability=p.prior,
                    likelihood=p.likelihood,
                    posterior_probability=p.posterior_probability,  # IMMUTABLE
                    confidence_level=c_level,
                    confidence_diagnostics=c_diags,
                    confidence_flags=c_flags,
                    supplemental_deterministic_evidence=supp_ev
                )
            )
            
        # 5. Build limitations
        limitations = []
        if posterior_result.hypothesis_space_truncated:
            limitations.append("Posterior probability within the evaluated candidate hypothesis set.")
            
        has_unavailable = any(
            diag.status == "UNAVAILABLE" 
            for c in final_candidates 
            for diag in c.confidence_diagnostics
        )
        if has_unavailable:
            limitations.append("One or more physics-confidence metrics could not be calculated due to unavailable data.")
            
        if not limitations:
            limitations.append("No active limitations")
            
        # 6. Build report
        report = FinalAttributionReport(
            spill_id=spill_id,
            status=posterior_result.status,
            hypothesis_space_truncated=posterior_result.hypothesis_space_truncated,
            candidate_limit=posterior_result.candidate_limit,
            total_valid_candidates=posterior_result.total_valid_candidates,
            returned_candidate_count=posterior_result.returned_candidate_count,
            evaluated_candidate_count=evaluated_candidates,
            unavailable_candidate_count=unavailable_candidates,
            unavailable_candidate_ids=unavailable_ids,
            prior_mode=posterior_result.prior_mode,
            normalization_constant=posterior_result.normalization_constant,
            log_normalization_constant=posterior_result.log_normalization_constant,
            posterior_sum=posterior_result.posterior_sum,
            candidates=final_candidates,
            provenance=provenance,
            limitations=limitations,
            warnings=posterior_result.warnings,
            errors=posterior_result.errors
        )
        
        return report
