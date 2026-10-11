# An air-quality app should tell you what it actually knows

Unpublished draft. Research evidence is still collecting. Publication is held
until the requested paper-submission milestone and author review.

An air-quality dashboard can look current while quietly showing a historical
record. A date picker, a familiar city name and a confident number can make that
mistake difficult to notice. In AirGuard India, the historical record ends in
2020. That record is useful for research and replay. It cannot describe the air
outside today, and it cannot supply tomorrow's forecast from current conditions.
The first requirement for the live product was therefore simple: the application
must make time and source identity visible wherever it displays a number.

The operational pages now ask a different question from the historical pages.
They start with a selected location and retrieve current conditions, modelled
pollutant concentrations and weather context. They show tomorrow as the next
calendar day in India Standard Time. Historical replay remains available through
its own route, with its date range stated. The distinction is part of the data
contract, not only a sentence in a footer. A live-source failure cannot silently
send the user back to an old observation.

A second distinction matters just as much: measured and modelled air quality
are different kinds of evidence. OpenAQ provides actual station measurements
and retains the identity of the upstream provider and station owner. A station
may be nearby yet have too few pollutants, missing hourly coverage or readings
that are several days old. In those cases it is misleading to call the result a
current measured AQI. The system keeps those observations and their timestamps,
but it labels them according to their real freshness and coverage.

Where eligible measured data is absent, the operational forecast uses CAMS
global concentrations delivered through Open-Meteo. This makes a broad area
estimate possible, including places outside the historical study cities. The
trade-off is resolution. The configured product has a coarse model grid and
hourly values interpolated from a less frequent native output. A model grid
cannot resolve a road junction, a person's commute or local indoor exposure.
Displaying more decimal places would not remove that limitation. The interface
keeps the model source, issue time and approximate resolution beside the result.

The application also keeps its independent sources independent. NASA FIRMS
supplies satellite thermal detections as fire context. Those detections are not
pollutant measurements, and they do not automatically change the AQI. Weather
provides context for wind, humidity, temperature and mixing, without a hidden
hand-tuned correction. CPCB's optional government feed currently fails on the
local network before receiving an HTTP response. That failure is recorded as a
failure of CPCB access. Neither OpenAQ nor CAMS is renamed CPCB to make the
source list appear complete.

Turning concentrations into an index requires another layer of care. A central
calculation handles pollutant units, adequate hourly coverage and the different
averaging windows. Daily particulate and gas summaries must not be assembled
from incompatible stations or incomplete windows. The system also treats
open-ended severe concentration bands as lower bounds. It does not invent an
exact extreme value and then include that invented value in regression-error
statistics. A readable category can remain useful even when an exact numerical
quantity is unsupported.

Planning a lower-exposure outdoor period is a related but different calculation.
An official rolling index shares much of its input between consecutive hours,
so it is not an instantaneous measure of within-day changes. AirGuard's window
comparison uses hourly concentration-derived indicators, a consistent set of
available pollutants and complete two-hour periods within practical daytime
hours. It labels that result as a relative comparison. A relatively lower value
does not mean safe exposure, and a shallow boundary layer or local emissions can
change what a person experiences. Missing dominant pollutants must not create
an artificial clean period.

All these distinctions would be fragile if they existed only in the interface.
The database stores records with source provenance, observation or valid time,
retrieval time and validation flags. Unique keys prevent the same record from
being counted again during a repeated ingestion. A replay check can therefore
verify duplicate prevention against real stored samples. Data-quality problems
remain auditable rather than disappearing through an unexplained cleaning step.
The public API exposes a normalized response while raw tables remain private.

Scheduled collection makes this a continuing system instead of a one-time demo.
Refresh jobs retrieve inputs, a prefetch prepares popular locations, and a
separate fixed-time protocol attempts issuance at 20:00 IST. A monitoring page
distinguishes successful job dispatch from successful forecast issuance. That
distinction matters: a scheduler can run correctly while a provider is down or
while no station meets the research eligibility rules. The appropriate outcome
is a recorded failed or partial attempt, not a forecast manufactured afterward
with a convenient earlier timestamp.

The same principle shapes evaluation. A forecast must be saved before its
target day. Its input availability and issue time must be preserved. The target
must later be constructed from sufficiently complete measured data for the same
station and calendar day. Choosing a different station after seeing the outcome
would change the experiment. Substituting reanalysis for an archived forecast
would also change the experiment, because reanalysis may contain information
unavailable to the original forecaster. Those substitutions can produce an
impressive score for a question the operational system never actually answered.

The expanded research protocol is preregistered around those constraints. It
requires substantial station coverage and a year of training data, separates
calibration from testing, reserves a final temporal test and asks for spatial
and regional checks. Persistence, climatology and raw CAMS remain explicit
baselines. An India-specific correction should earn its place by improving
held-out predictions on comparable rows. Software tests can verify that a split
does not leak future outcomes, but they cannot establish that a model forecasts
well. Real matched records are still necessary.

Uncertainty also needs evidence. A plotted daily range shows variation through
the forecast day; it is not a prediction interval. An interval deserves that
name only after its method and coverage have been evaluated against outcomes.
The research framework includes interval-scoring and adaptive calibration
primitives, but the consumer forecast currently displays no validated interval.
Likewise, conservative cohort guidance is not a personalized clinical-risk
estimate. Unsupported health modifiers remain neutral until a verified evidence
review supports a defensible exposure definition and coefficient.

Performance and usability have practical scientific consequences. Slow pages
encourage screenshots without context; crowded mobile menus can hide methods
and source labels. The release therefore shares location state across operational
pages, provides chart data in a table, supports retry after an outage and uses
caches with explicit freshness boundaries. The source map distinguishes station
context from modelled grid estimates and loads only when requested. These are
product improvements that make the evidence easier to inspect. They are not
evidence of health benefit or better forecast skill.

Several gates remain before stronger research claims are possible. Historical
CAMS forecast access requires the archive account and dataset terms. Eligible
station outcomes must accumulate or be acquired with adequate provenance.
Population-impact calculations need a licensed, versioned population grid and
must report uncovered areas instead of treating them as clean. A usability pilot
needs consent and an ethics determination before recruitment. Hindi and Tamil
health guidance needs qualified native review. The paper also needs confirmed
authors, a human-edited reference list and an actual conference call.

The release is therefore a live operational application and a foundation for a
prospective study. Its most useful improvement is not a new headline accuracy
number. It is a chain of evidence that can explain where each estimate came
from, when its inputs were available, what failed and what remains uncertain.
That chain allows future improvements to be tested without changing the meaning
of the task halfway through. As measured outcomes arrive, the ledger can become
a track record. Until then, the honest forecast is a labelled model estimate,
with its limitations visible to the person using it.
