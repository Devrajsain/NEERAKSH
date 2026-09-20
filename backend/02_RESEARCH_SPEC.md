# Research Specification --- Bayesian Forward-Ensemble Oil Spill Attribution

## PURPOSE

This document is the local implementation reference for the Bayesian
oil-spill attribution upgrade.

It distills the supplied research paper:

**Breivik et al. (2025), "The Bayesian backtracking problem in oceanic
drift modelling," Ocean Modelling 194, 102505**

and the supplied:

**Oil Spill Origin Attribution --- Methodology**

Antigravity should use this document instead of requiring the original
PDF/DOCX.

------------------------------------------------------------------------

# 1. CORE SCIENTIFIC IDEA

Naive backward drift is not always a reliable source-identification
method.

For a smooth deterministic advection problem:

``` text
dx/dt = v(x,t)
```

backward integration can be obtained by reversing the sign of the
velocity/time step.

With diffusion:

``` text
dX =
(v(X,t) + div(K(X,t))) dt
+
sqrt(2K(X,t)) dW
```

the backward stochastic formulation reverses the flow component while
retaining the diffusion structure.

However, practical ocean drift can contain:

-   convergent flow
-   divergent flow
-   diffusion
-   model error
-   discontinuous state changes
-   irreversible processes

These can make naive long-duration backward integration unreliable.

------------------------------------------------------------------------

# 2. WHY OIL IS A SPECIAL CASE

Oil is not simply a passive reversible particle.

The supplied methodology identifies:

-   evaporation
-   emulsification
-   viscosity/weathering changes

as irreversible/history-dependent processes.

Therefore:

``` text
reverse velocity
```

does NOT mean:

``` text
reverse oil weathering
```

A backward model cannot simply reconstruct the previous physical oil
state unless the history is known.

For this reason, the oil attribution workflow should use backward
integration only to narrow the candidate region and then perform the
actual source attribution with forward modelling.

------------------------------------------------------------------------

# 3. CONVERGENCE PROBLEM

Floating material can accumulate in horizontally convergent regions.

If the slick is observed inside a convergence zone, the observation may
not reveal how long the oil has been there.

This is a structural ambiguity rather than merely a measurement-quality
problem.

Therefore candidates affected strongly by convergence should expose a
confidence warning.

Possible flag:

``` text
STRONG_CONVERGENCE
```

------------------------------------------------------------------------

# 4. RECOMMENDED ARCHITECTURE

The research methodology adapts the paper into this oil-spill workflow:

``` text
1. Detect slick
2. Short backward pre-filter
3. Extract AIS candidates
4. Forward OpenOil ensemble
5. Compute likelihood
6. Compute Bayesian posterior
7. Report uncertainty/confidence
```

The backward run is a search-area reducer.

The forward ensemble is the source-attribution engine.

------------------------------------------------------------------------

# 5. STEP 1 --- DETECTION

Feature 1 provides the observed oil slick:

``` text
observation position
observation polygon
centroid
extent/area
detection time T
```

Treat this as the observation:

``` text
y_T
```

------------------------------------------------------------------------

# 6. STEP 2 --- SHORT BACKWARD PREFILTER

Run backward only for a short configurable interval.

Recommended initial default:

``` text
12 hours
```

Allowed:

``` text
6–24 hours
```

Output:

``` text
candidate spatial region
candidate temporal window
```

Do NOT output a final source point from this stage.

Metadata:

``` json
{
  "role": "SEARCH_PREFILTER_ONLY"
}
```

------------------------------------------------------------------------

# 7. STEP 3 --- AIS CANDIDATE HYPOTHESES

Within the backward-derived region/time window:

``` text
AIS records
```

become candidate release hypotheses.

Each hypothesis contains:

``` text
MMSI
release latitude
release longitude
release timestamp
```

Conceptually:

``` text
C_i = (MMSI_i, x_i, y_i, S_i)
```

The candidate release time is important.

Do not treat vessel identity alone as the hypothesis.

------------------------------------------------------------------------

# 8. STEP 4 --- FORWARD ENSEMBLE

For each candidate:

``` text
candidate release position/time
        ↓
ensemble perturbations
        ↓
OpenOil
        ↓
CMEMS currents
+
ERA5 winds
        ↓
forward to observation time
```

Perturb sources may include:

-   AIS position uncertainty
-   release-time uncertainty
-   diffusion
-   oil-property uncertainty
-   observation uncertainty
-   environmental/model uncertainty

The supplied methodology specifically requires forward weathering
through OpenOil.

------------------------------------------------------------------------

# 9. OBSERVATION UNCERTAINTY

For observation k:

``` text
y_k = observed position
T_k = observation time
sigma_k = position uncertainty
```

Time uncertainty can be represented by:

``` text
tau
```

and a tolerance interval:

``` text
[T - tau, T + tau]
```

For a Gaussian observation model, use `sigma_k` explicitly.

------------------------------------------------------------------------

# 10. SINGLE-OBSERVATION THRESHOLD LIKELIHOOD

A simple baseline likelihood is:

``` text
L(y_T | candidate)
≈

number of ensemble members
that enter the observation region

/

total ensemble members
```

The observation region is defined by spatial uncertainty `sigma`, and
the matching can be evaluated within `[T - tau, T + tau]`.

This is useful for testing.

------------------------------------------------------------------------

# 11. GAUSSIAN LIKELIHOOD

For observation k and trajectory n:

``` text
L(k | n)
=
1 / (2*pi*sigma_k^2)
*
exp(
    -r_(n,k)^2 / (2*sigma_k^2)
)
```

where:

``` text
r_(n,k)
=
distance(
    simulated position of trajectory n at T_k,
    observed position y_k
)
```

Use numerically stable log form in implementation:

``` text
log L(k | n)
=
-log(2*pi*sigma_k^2)
-
r_(n,k)^2 / (2*sigma_k^2)
```

------------------------------------------------------------------------

# 12. MULTIPLE OBSERVATIONS

Suppose the same oil-spill event has observations:

``` text
k = 1 ... K
```

For a trajectory/candidate:

``` text
L(candidate | all observations)
=
PRODUCT_k L(k | candidate)
```

Numerically:

``` text
log_L(candidate)
=
SUM_k log_L(k | candidate)
```

This allows multiple satellite observations to sharpen the posterior.

------------------------------------------------------------------------

# 13. BAYESIAN POSTERIOR

For candidate c:

``` text
P(c | observations)
∝
P(c)
*
PRODUCT_k L(k | c)
```

Normalize:

``` text
P(c | observations)
=
[
P(c) * PRODUCT_k L(k | c)
]
/
[
SUM_j P(j) * PRODUCT_k L(k | j)
]
```

The final candidate probabilities must satisfy:

``` text
SUM_c P(c | observations) ≈ 1
```

------------------------------------------------------------------------

# 14. PRIOR

Default:

``` text
uniform prior across valid AIS candidate hypotheses
```

Later the system may support domain-informed priors based on information
such as:

-   vessel class
-   AIS gaps
-   loitering behavior
-   other documented domain factors

But the initial implementation should keep the prior mechanism explicit
and separate from likelihood.

Do not encode suspicion directly into a Bayesian posterior.

------------------------------------------------------------------------

# 15. EXISTING FEATURE 3 SCORE

The existing deterministic score can remain.

Example existing evidence dimensions:

``` text
Origin presence
Behavior anomaly
Dwell
AIS gap
Approach/departure
```

The old score is:

``` text
0–100
```

The Bayesian result is:

``` text
0–1 posterior probability
```

These are not mathematically equivalent.

Keep them separate.

------------------------------------------------------------------------

# 16. CONFIDENCE

A posterior value alone is not sufficient.

Candidates should expose structural/model limitations.

Potential confidence flags:

``` text
STRONG_CONVERGENCE
COASTAL_BEACHING_INTERACTION
WEATHERING_UNCERTAINTY_HIGH
ENVIRONMENTAL_DATA_INCOMPLETE
AIS_TIME_UNCERTAINTY_HIGH
PARTICLE_LOSS_HIGH
MODEL_ERROR_HIGH
INSUFFICIENT_ENSEMBLE
```

A candidate can have a relatively high posterior while still having low
confidence if the model is operating in a regime known to be
structurally problematic.

------------------------------------------------------------------------

# 17. MODEL ERROR

The paper emphasizes that model error can exceed the random
perturbations used to represent aleatoric uncertainty.

Therefore the architecture should eventually support environmental
forcing perturbations such as:

``` text
u' = u * (1 + epsilon_u)
v' = v * (1 + epsilon_v)
```

with optional temporal correlation.

This should initially be an extension point unless a robust
implementation already exists.

------------------------------------------------------------------------

# 18. MULTIPLE OBSERVATIONS AND TRAJECTORY POSTERIOR

The research approach naturally represents a posterior over
trajectories.

Each trajectory has:

``` text
starting position
starting time
posterior probability
```

The set of trajectory start points therefore represents a posterior
distribution over possible origins.

This is more informative than returning only one deterministic point.

------------------------------------------------------------------------

# 19. FORWARD VS BACKWARD ROLE

Use:

``` text
BACKWARD
=
cheap region reduction / pre-filter
```

Use:

``` text
FORWARD
=
final physical attribution
```

The research paper recommends forward modelling whenever practical,
while noting that a backward-forward procedure can reduce computational
cost by narrowing the initial area.

------------------------------------------------------------------------

# 20. OIL-SPECIFIC EXTENSION

The supplied methodology extends the generic Bayesian framework
specifically for oil:

``` text
generic drifting object
        ↓
oil spill
        ↓
OpenOil
        ↓
weathering
```

This is important because oil weathering is not reversible.

The implementation must not simulate:

``` text
backward evaporation
backward emulsification
```

as if these processes could simply be undone.

------------------------------------------------------------------------

# 21. OUTPUT PHILOSOPHY

The final output should be a probabilistic candidate distribution:

``` text
candidate vessel
candidate release position
candidate release time
prior
likelihood
posterior
confidence
confidence flags
trajectory information
```

Not merely:

``` text
"Vessel X caused the spill."
```

The system is a model-based attribution tool and should expose
uncertainty.

------------------------------------------------------------------------

# 22. IMPORTANT LIMITATIONS

The implementation should explicitly recognize:

1.  environmental forcing error
2.  incomplete AIS coverage
3.  AIS position/time uncertainty
4.  observation uncertainty
5.  oil weathering uncertainty
6.  convergence zones
7.  coastline/beaching
8.  computational cost of large ensembles
9.  historical environmental-data coverage
10. sensitivity to initial release-time assumptions

These limitations should be visible in diagnostics/provenance.

------------------------------------------------------------------------

# 23. RESEARCH-TO-CODE MAPPING

  -----------------------------------------------------------------------
  Research concept                    Implementation
  ----------------------------------- -----------------------------------
  Observation `y_T`                   Feature 1 slick observation

  Incident time `S`                   AIS candidate release timestamp

  Prior `P(c)`                        AIS candidate prior

  Lagrangian trajectories             OpenOil forward ensemble

  `sigma`                             observation spatial uncertainty

  `tau`                               observation time uncertainty

  Likelihood                          threshold / Gaussian

  Multiple observations               product of likelihoods / sum of
                                      log-likelihoods

  Posterior                           normalized Bayesian candidate
                                      probability

  Backward model                      short pre-filter

  Weathering                          OpenOil forward process

  Model uncertainty                   ensemble + future forcing
                                      perturbation

  Confidence                          convergence/weathering/data
                                      diagnostics
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 24. IMPLEMENTATION PRIORITY

## P0

-   short backward pre-filter
-   AIS candidate hypotheses
-   OpenOil adapter
-   candidate-specific forward ensembles
-   likelihood
-   Bayesian posterior
-   sigma/tau
-   confidence flags
-   tests

## P1

-   multiple satellite observations
-   posterior GeoJSON
-   posterior entropy
-   environmental model-error perturbations

## P2

-   optimized parallel execution
-   advanced priors
-   richer oil-property uncertainty
-   advanced posterior visualization

------------------------------------------------------------------------

# 25. SUCCESS CRITERIA

The new implementation should satisfy:

``` text
Backward
→ pre-filter only

AIS
→ release hypotheses

OpenOil
→ forward physical simulation

Likelihood
→ observation matching

Bayes
→ normalized posterior

Confidence
→ explicit uncertainty/physics diagnostics

Existing Feature 2
→ preserved

Existing Feature 3
→ preserved

Tests
→ passing

Provenance
→ reproducible
```
