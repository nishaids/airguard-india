# Prospective usability and population-impact protocol

Status: protocol draft; recruitment, data collection and clinical claims disabled.

Population exposure uses unique disjoint population cells matched to the forecast
date and product version. Count Poor-or-worse modelled estimates (>200), report
covered and uncovered population separately, retain product licence/hash and do
not infer a country's exposure from only monitored cities. The implementation in
`src/research/impact.py` rejects duplicates and mismatched dates. No population
file is currently configured, so the real estimate is PENDING.

Proposed usability pilot: compare task completion, comprehension of measured vs
modelled labels, timestamp interpretation, chart/table navigation, and warning
comprehension across agreed cohorts. Predefine tasks, sample size and analysis
before recruitment. Do not measure or advertise prevention of disease from an
uncontrolled usability pilot. Require institutional ethics determination and
documented participant consent before involving people.

Collect only task outcomes and optional agreed demographics. Avoid names,
precise home coordinates and health diagnoses unless the approved protocol
requires them. Document retention, access controls and withdrawal handling.
Notifications require explicit opt-in, a supported delivery channel, quiet hours
and reviewed English/Hindi/Tamil copy. None are sent by the current application.

Native Hindi and Tamil health copy requires named qualified reviewers, review
date and approved revision hash. English remains the released language until
that review exists. An install manifest is present; offline data must retain its
retrieval time and stale label before any future service-worker cache is enabled.
