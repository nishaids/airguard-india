# Comprehension study protocol (not authorised to run)

**Status: NOT AUTHORISED.** No participant may be approached and no data
collected before institutional ethics approval and written informed consent.
This file is the protocol, written in advance so that approval can be sought
against something specific, and so that nobody later assembles a study out of
whatever data happens to be lying around. `results/user_study.json` does not
exist and must not be created by any means other than a run of this protocol.

## Question

Does a cohort-specific advisory card change what a reader understands and what
they say they would do, compared with the official AQI card for the same day and
place?

This is a question about comprehension and stated intention. It is not a
question about health outcomes, and the study cannot answer one.

## Design

Within-subject, two conditions, order randomised per participant:

- **A.** A card showing the CPCB AQI value, its band and the standard general
  advisory text.
- **B.** The AirGuard card for the participant's chosen cohort: the same day and
  place, the forecast with its interval once intervals exist, the cohort band and
  one plain-language action.

Each participant sees both, for two different days drawn from the same set, so
no participant judges the same day twice. Target n = 30, which is enough to
describe a difference and not enough to settle one; the analysis reports an
effect size with its interval, not a verdict.

## Measures

1. **Comprehension.** Four fixed questions per card: what the number refers to,
   whether it is measured or modelled, what the recommended action is, and
   whether it applies to the participant specifically. Scored against a key
   written before any participant is recruited.
2. **Intended protective action.** One forced-choice item on what they would do
   tomorrow, plus a free-text reason, coded blind to condition.
3. **System Usability Scale**, ten standard items, once per condition.
4. **Misreading probes.** Two items that ask what a withheld confidence value or
   an interval means, to detect whether the interface creates false precision.

## What will not be collected

- Names, phone numbers, email addresses, or anything else that identifies a
  participant. Responses carry a random id and nothing else.
- Health conditions as a personal record. Cohort is chosen as a *scenario* to
  read the card for, and the instruction says so explicitly.
- Location more precise than the city used in the stimulus.
- Analytics of any kind during the session.

## Consent

Written informed consent before anything is shown, stating: the purpose, that
participation is voluntary, that they may stop at any moment without giving a
reason, that nothing in it is medical advice, that the data is anonymous and
cannot be withdrawn after submission because it cannot be identified, and who to
contact. Consent forms are stored separately from responses.

## Analysis, fixed in advance

- Primary: difference in comprehension score between conditions, paired, with a
  bootstrap interval.
- Secondary: SUS difference; proportion choosing a protective action; misreading
  probe rates.
- Every outcome above is reported whether or not it favours the system. A
  comprehension result that favours the official card is a finding and will be
  published as one.
- No subgroup analysis beyond the preregistered cohort split, and no
  significance claim from n = 30.

## Reporting

The paper reports the ethics approval reference, the design, n, and the measured
effects with intervals. IEEE requires an ethics statement for human-subject
research, and the manuscript carries one that currently says no such data was
collected, which remains true until this protocol runs.

## Before this can run

1. Institutional ethics approval at Rajalakshmi Engineering College.
2. Approved consent form and participant information sheet.
3. A named investigator responsible for the data.
4. Stimuli frozen: the exact cards, days and places, committed as fixtures.
5. The comprehension key written and committed before recruitment.
