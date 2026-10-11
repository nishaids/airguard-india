# Why our air quality app told Avadi to worry about ozone

*A build log from three students who kept finding out their forecast was less
certain than it looked.*

---

One evening in October, our app looked at Avadi — a suburb in the north-west of
Chennai — and announced that tomorrow's air would be dominated by ozone. Not
dust. Not smoke from somewhere upwind. Ozone, at 135 out of 141 on the index.

That is an odd thing for a Chennai October. Ask anyone who has lived through a
post-monsoon month in a big Indian city and they will tell you the problem is
particles: traffic, construction, burning. So we did the thing you are supposed
to do when a number surprises you, which is to stop being pleased that the app
produced a number at all and start asking where the number came from.

The answer taught us more about forecasting than any tutorial did.

## What our app actually does, in one paragraph

AirGuard India takes a global atmospheric forecast, converts its pollutant
concentrations into the index the Central Pollution Control Board defines, and
turns that into advice for different groups of people — children, older adults,
people with asthma, people who work outdoors. It runs at
[webapp-phi-taupe.vercel.app](https://webapp-phi-taupe.vercel.app), it is free,
and it covers the country rather than a handful of cities.

The global forecast is CAMS, run by the European Centre for Medium-Range Weather
Forecasts as part of Copernicus. It is genuinely good science. It is also
computed on a grid of roughly 45 kilometres per cell, which means one number
covers Avadi, central Chennai and a fair amount of farmland in between. Our app
can tell you what the model says about your cell. It cannot tell you what the
air is like on your street, and we had to learn to write that down in the
interface instead of in a footnote we hoped nobody would read.

## The ozone was the model's opinion, not a measurement

Here is the thing we had half-understood: a forecast is not an observation, and
a global model's chemistry is not a local truth.

The literature on this is not shy. Regional models have been reported to
overestimate surface ozone over India by something like a third, and the reason
is chemical rather than careless. Ozone is destroyed near sources of nitrogen
oxides — busy roads, in other words — and if a model underestimates how much
nitrogen oxide is around, it will leave too much ozone standing. A 45-kilometre
cell cannot see a busy road.

So the ozone number was not a bug. It was the model being a model. What was
wrong was our presentation: we showed it the way you would show a measurement,
and a reasonable person would read it as one.

That became a rule for us. Every value in the app now says whether it was
measured at a monitoring station or produced by a model, and the model values
say which grid they came from. It made the interface busier. It made the
interface honest.

## Then we looked for the measurements, and they were not there

If a model can be biased, the fix is well known: compare it against ground
stations over a long period, learn the bias, correct it. India has the stations
for this. There were 565 continuous monitors in the national network in 2025.

Getting at their history turned out to be the hard part. The government's
real-time data path we had been relying on was failing outright. The open
aggregator we fell back to, OpenAQ, gave us plenty of station names that looked
right — state pollution control board sites in Vijayawada, Amritsar, Bengaluru —
but when we asked for their hourly history, most of them returned nothing at
all. Out of the first twenty we walked, seven had retrievable hours.

Those seven were enough to be useful and far too few to be a national result.
We pulled a year of hourly values for them and ran the official averaging rules:
twenty-four-hour means for particles, eight-hour running maxima for ozone and
carbon monoxide, at least sixteen valid hours before a day counts at all. That
produced 861 station-days with a genuine index value — the first real daily
targets the project has ever had.

It also produced a sentence we did not enjoy writing. One of those stations
reports only fine particles. A year of it cannot produce a single valid daily
index, because the official index needs several pollutants before it will speak.
Rows of data are not the same thing as evidence.

## The honest scoreboard

Somewhere in here we stopped trying to make the project look finished and
started trying to make it legible.

The app now carries a readiness board: seventeen things that would have to be
true before we could claim our forecast is accurate for India. Five of them are
true. The twelve that are not are listed, with the reason, where anyone can see
them. There is a second list of claims our own system does not support —
"AirGuard improves on CAMS" is on it, because we have not shown that and we are
not going to imply it.

The uncomfortable part of building that board was realising how easy it is to
tick a box that cannot be unticked. One of ours was a scheduled job that issues
tomorrow's forecast at 20:00 India time and freezes it, so that later we can
check what we said against what happened. The status page reported the schedule
as active, which it was. Zero forecasts had ever been stored, which was also
true. An active schedule had been standing in for a working one.

It works now. On 11 October 2026 it issued and froze twelve forecasts, and the
record started growing forward from that day. We cannot manufacture the missing
days, and we refuse to. Thirty days of track record takes thirty days.

## What we withheld on purpose

A confidence number is the most dangerous thing a prediction interface can show,
because people read it as a probability whether or not it is one.

Our older classifier reported a score for its top category. On test data, the
days it scored at 95% or more were right about 89% of the time, and the
training had been resampled in a way that distorts those scores further. It was
not a probability. So the percentage is gone from the interface. In its place it
says the confidence is withheld, and why. When we have proper calibrated
intervals — there is good machinery for this, and we have built the scaffolding
— the number can come back with a meaning attached.

We did the same with our health index. The first version multiplied pollutant
sub-indices by vulnerability factors we had chosen ourselves: 1.55 for children
and nitrogen dioxide, 1.70 for cardiac patients and fine particles, and so on.
They were plausible. They were also ours, which means the headline finding they
produced — that cohort advice differs from the official index on two-thirds of
days — was partly just a restatement of our own choices.

The rebuilt version uses the published-risk approach the Canadian health index
pioneered and that a recent Indian study applied to Delhi and Varanasi. It needs
real coefficients from the epidemiological literature, with their units and
exposure windows checked by someone qualified to check them. Until that review
happens, every coefficient in the file sits at "not adopted", every cohort
factor is exactly 1.0 with a written reason, and the index returns no value.
A blank is more useful than an invented number.

## Limitations, stated plainly

- The forecast is a global model's output on a ~45 km grid, uncorrected, and
  not yet validated against Indian stations.
- The measured data comes from OpenAQ and its upstream operators. It is not a
  CPCB export, and we never label it as one.
- Ammonia and lead are absent from the model input, so the index can understate
  conditions where ammonia matters, such as agricultural areas.
- The prospective record began on 11 October 2026 and is days old.
- The cohort index is an advisory heuristic with no adopted coefficients, and it
  has never been validated against any health outcome.
- Guidance is available in English only. Hindi and Tamil health text will not be
  published until a named native reviewer approves each string, because a
  mistranslated instruction about going outside is worse than no translation.

**This is general information, not medical advice.** If you have a heart or lung
condition, your clinician's advice beats our index on every day of the year.

## What we would tell another student team

Build the honesty features first. Readiness gates, measured-versus-modelled
labels, a list of claims you cannot support, a frozen record that cannot be
backdated. They are not decoration and they are not modesty. They are what let
you find out that your scheduler was not running, that your confidence score was
not a probability, and that your headline health finding was partly a mirror.

Every one of those discoveries was unpleasant for an afternoon and made the
project better. The ozone in Avadi is still there in tomorrow's forecast. It
just no longer pretends to be a fact.

---

*AirGuard India is open and runs on data from OpenAQ and its upstream operators,
Open-Meteo, the Copernicus Atmosphere Monitoring Service and NASA FIRMS, with the
index method from the Central Pollution Control Board. A research manuscript
describing the system and its evaluation protocol is in preparation and has not
been submitted; no accuracy result is claimed in it or here.*
