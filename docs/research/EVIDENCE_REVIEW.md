# HAI v2 and evidence review gate

The current operational product uses CPCB category guidance, not an estimated
individual disease risk or HAI v2 coefficient. Legacy HAI results remain labelled
historical. `src/research/health_index.py` supplies a neutral modifier of 1 for
unsupported evidence and rejects unreviewed modifiers. Its dimensionless exposure
ratios are exploratory and are never presented as clinical probabilities.

Before a coefficient becomes eligible, record the exact source identifier,
publication year, study population and geography, exposure duration, pollutant
units, outcome, effect estimate and confidence interval, confounding adjustment,
applicable cohort, normalization definition and independent human verification.
Reject invented coefficients, incompatible exposure windows and unsupported
transfer of long-term relative risk to a one-day individual risk estimate.

Report sensitivity only across verified defensible coefficients. Separate
association, predictive performance and causal benefit. Indian evidence and WHO
guidance must be read from primary sources. The final reference list requires
human editing under the supplied request; this file does not populate it.

Status: PENDING verified coefficients and human evidence review. No empirical
sensitivity, health-benefit, cluster-stability or causal-effect result is claimed.
