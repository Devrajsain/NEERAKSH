import os
from typing import Literal
from pydantic import BaseModel, Field

class BayesianPrefilterConfig(BaseModel):
    """Configuration for the Bayesian backward prefilter (Phase 1)."""
    bayesian_prefilter_hours: float = Field(
        default=float(os.getenv("BAYESIAN_PREFILTER_HOURS", "12.0")),
        ge=6.0,
        le=24.0,
        description="Backward horizon in hours for the short prefilter search window."
    )


class LikelihoodConfig(BaseModel):
    """
    Configuration for Phase 4 Bayesian Likelihood Engine.
    """
    likelihood_mode: Literal["threshold", "gaussian"] = Field(
        default="threshold",
        description="Mode for likelihood calculation: 'threshold' (polygon geometric) or 'gaussian' (centroid distance)."
    )
    gaussian_sigma_m: float = Field(
        default=500.0,
        gt=0.0,
        description="Engineering configuration default for positional uncertainty (sigma) in meters. "
                    "This represents the spatial standard deviation of the likelihood density. "
                    "It is NOT a scientifically validated default, and should be explicitly configured."
    )
    observation_time_tolerance_seconds: float = Field(
        default=3600.0,
        ge=0.0,
        description="Maximum allowed difference between actual simulation final time and observation time."
    )
    include_stranded_particles: bool = Field(
        default=False,
        description="If True, evaluate stranded particles. If False, exclude them from spatial calculations."
    )
    include_other_terminal_particles: bool = Field(
        default=False,
        description="If True, evaluate other terminal status particles. If False, exclude them."
    )


class BayesianCandidateConfig(BaseModel):
    """Configuration for the Bayesian AIS candidate generation (Phase 2)."""
    bayesian_max_candidates: int = Field(
        default=int(os.getenv("BAYESIAN_MAX_CANDIDATES", "5000")),
        ge=1,
        description=(
            "Maximum number of candidate release hypotheses to return. "
            "This is a COMPUTATIONAL LIMIT, not a scientific ranking mechanism. "
            "If the total valid candidate count exceeds this value, the output "
            "explicitly reports truncation metadata."
        ),
    )
    bayesian_prior_mode: str = Field(
        default="UNIFORM",
        description=(
            "Prior distribution mode.  Currently only 'UNIFORM' is supported, "
            "assigning prior_i = 1/N over the returned candidate set."
        ),
    )


class BayesianSettings(BaseModel):
    """Master configuration for the Bayesian module."""
    prefilter: BayesianPrefilterConfig = Field(default_factory=BayesianPrefilterConfig)
    candidate: BayesianCandidateConfig = Field(default_factory=BayesianCandidateConfig)
    likelihood: LikelihoodConfig = Field(default_factory=LikelihoodConfig)

# Global default settings instance for the bayesian module
bayesian_settings = BayesianSettings()

