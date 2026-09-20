import math
from typing import List, Dict

from app.bayesian.schemas import (
    CandidateGenerationResult,
    CandidateLikelihood,
    BayesianPosteriorResult,
    CandidatePosterior
)

class BayesianPosteriorEngine:
    """Engine for Phase 5 Bayesian Posterior computation."""

    def compute_posterior(
        self, 
        candidates_result: CandidateGenerationResult, 
        likelihoods: List[CandidateLikelihood]
    ) -> BayesianPosteriorResult:
        
        # 1. Validation of Candidate Alignment
        candidate_map = {c.candidate_id: c for c in candidates_result.candidates}
        likelihood_map = {l.candidate_id: l for l in likelihoods}
        
        errors = []
        if set(candidate_map.keys()) != set(likelihood_map.keys()):
            errors.append("Mismatch between Phase 2 candidates and Phase 4 likelihood results.")
            
            # Identify specific mismatches
            missing_in_likelihood = set(candidate_map.keys()) - set(likelihood_map.keys())
            if missing_in_likelihood:
                errors.append(f"Candidates missing likelihood: {missing_in_likelihood}")
            
            missing_in_candidates = set(likelihood_map.keys()) - set(candidate_map.keys())
            if missing_in_candidates:
                errors.append(f"Likelihoods for unknown candidates: {missing_in_candidates}")
                
            return self._build_error_result(candidates_result, "VALIDATION_ERROR", errors)
            
        if len(likelihoods) != len(likelihood_map):
            errors.append("Duplicate likelihood entries found for the same candidate.")
            return self._build_error_result(candidates_result, "VALIDATION_ERROR", errors)
            
        # 2. Prior Validation
        prior_sum = 0.0
        for c in candidates_result.candidates:
            if c.prior_probability < 0:
                errors.append(f"Negative prior found for candidate {c.candidate_id}: {c.prior_probability}")
                return self._build_error_result(candidates_result, "VALIDATION_ERROR", errors)
            prior_sum += c.prior_probability
            
        if candidates_result.candidates and not math.isclose(prior_sum, 1.0, rel_tol=1e-3, abs_tol=1e-3):
            errors.append(f"Priors do not sum to 1.0 (sum={prior_sum})")
            return self._build_error_result(candidates_result, "VALIDATION_ERROR", errors)
            
        # 3. Log-Space Computation (unnormalized)
        log_weights = []
        valid_log_weights = []
        
        for c in candidates_result.candidates:
            prior = c.prior_probability
            l = likelihood_map[c.candidate_id]
            
            if prior == 0.0:
                log_prior = None
            else:
                log_prior = math.log(prior)
                
            log_likelihood = l.log_likelihood
            if log_prior is None or log_likelihood is None:
                log_weight = None
            else:
                log_weight = log_prior + log_likelihood
            
            log_weights.append(log_weight)
            if log_weight is not None:
                valid_log_weights.append(log_weight)
                
        # 4. Zero-Likelihood / Normalization Check
        if not valid_log_weights or max(valid_log_weights) == float('-inf'):
            return self._build_zero_likelihood_result(candidates_result, candidate_map, likelihood_map, log_weights)
            
        # 5. Numerically Stable Log-Sum-Exp
        max_log_weight = max(valid_log_weights)
        sum_exp = sum(math.exp(w - max_log_weight) for w in valid_log_weights)
        log_Z = max_log_weight + math.log(sum_exp)
        Z = math.exp(log_Z)
        
        # 6. Posterior Computation
        posteriors = []
        posterior_sum = 0.0
        positive_count = len(valid_log_weights)
        
        for idx, c in enumerate(candidates_result.candidates):
            log_weight = log_weights[idx]
            l = likelihood_map[c.candidate_id]
            
            if log_weight is None or log_Z is None:
                posterior_prob = 0.0
            else:
                log_posterior = log_weight - log_Z
                posterior_prob = math.exp(log_posterior)
                
            posterior_sum += posterior_prob
            
            posteriors.append(
                CandidatePosterior(
                    candidate_id=c.candidate_id,
                    mmsi=c.mmsi,
                    release_latitude=c.release_position['latitude'],
                    release_longitude=c.release_position['longitude'],
                    release_timestamp=c.release_time,
                    prior=c.prior_probability,
                    likelihood=l.likelihood,
                    log_likelihood=l.log_likelihood,
                    unnormalized_log_weight=log_weight,
                    posterior_probability=posterior_prob,
                    likelihood_mode=l.likelihood_mode,
                    evaluation_status="SUCCESS",
                    warnings=l.warnings
                )
            )

        # 7. Build Result
        return BayesianPosteriorResult(
            status="SUCCESS",
            hypothesis_space_truncated=candidates_result.hypothesis_space_truncated,
            candidate_limit=candidates_result.candidate_limit,
            total_valid_candidates=candidates_result.total_valid_candidates,
            returned_candidate_count=candidates_result.candidate_count,
            prior_mode=candidates_result.prior_mode,
            evaluated_candidate_count=len(posteriors),
            positive_likelihood_candidate_count=positive_count,
            normalization_constant=Z,
            log_normalization_constant=log_Z,
            posterior_sum=posterior_sum,
            posteriors=posteriors,
            errors=[],
            warnings=[],
            provenance={}
        )

    def _build_error_result(self, candidates_result: CandidateGenerationResult, status: str, errors: List[str]) -> BayesianPosteriorResult:
        return BayesianPosteriorResult(
            status=status,
            hypothesis_space_truncated=candidates_result.hypothesis_space_truncated,
            candidate_limit=candidates_result.candidate_limit,
            total_valid_candidates=candidates_result.total_valid_candidates,
            returned_candidate_count=candidates_result.candidate_count,
            prior_mode=candidates_result.prior_mode,
            evaluated_candidate_count=0,
            positive_likelihood_candidate_count=0,
            normalization_constant=0.0,
            log_normalization_constant=None,
            posterior_sum=0.0,
            posteriors=[],
            errors=errors,
            warnings=[]
        )

    def _build_zero_likelihood_result(
        self, 
        candidates_result: CandidateGenerationResult,
        candidate_map: Dict,
        likelihood_map: Dict,
        log_weights: List[float]
    ) -> BayesianPosteriorResult:
        posteriors = []
        for idx, c in enumerate(candidates_result.candidates):
            log_weight = log_weights[idx]
            l = likelihood_map[c.candidate_id]
            posteriors.append(
                CandidatePosterior(
                    candidate_id=c.candidate_id,
                    mmsi=c.mmsi,
                    release_latitude=c.release_position['latitude'],
                    release_longitude=c.release_position['longitude'],
                    release_timestamp=c.release_time,
                    prior=c.prior_probability,
                    likelihood=l.likelihood,
                    log_likelihood=l.log_likelihood,
                    unnormalized_log_weight=log_weight,
                    posterior_probability=0.0,
                    likelihood_mode=l.likelihood_mode,
                    evaluation_status="NO_POSITIVE_LIKELIHOOD",
                    warnings=l.warnings
                )
            )

        return BayesianPosteriorResult(
            status="NO_POSITIVE_LIKELIHOOD",
            hypothesis_space_truncated=candidates_result.hypothesis_space_truncated,
            candidate_limit=candidates_result.candidate_limit,
            total_valid_candidates=candidates_result.total_valid_candidates,
            returned_candidate_count=candidates_result.candidate_count,
            prior_mode=candidates_result.prior_mode,
            evaluated_candidate_count=len(posteriors),
            positive_likelihood_candidate_count=0,
            normalization_constant=0.0,
            log_normalization_constant=float('-inf'),
            posterior_sum=0.0,
            posteriors=posteriors,
            errors=[],
            warnings=[]
        )
