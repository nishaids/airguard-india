# Translation review ledger — Hindi and Tamil

AirGuard's health guidance tells people whether to change what they do outdoors.
Guidance that is wrong in Tamil or Hindi is worse than English the reader has to
work at, so no non-English string is served until a named human has approved
that exact string. This file is the ledger; `webapp/app/lib/messages.ts` is the
gate that enforces it.

## Current state

| Locale | Strings translated | Strings approved | Health strings approved | Reviewer |
| --- | --- | --- | --- | --- |
| English (`en`) | 11 of 11 | 11 of 11 | yes | source language |
| Hindi (`hi`) | 0 of 11 | 0 of 11 | no | none |
| Tamil (`ta`) | 0 of 11 | 0 of 11 | no | none |

Nothing but English reaches a reader today. The gate falls back to English for
any string without a reviewer, so a partially reviewed locale degrades to mixed
English rather than to unreviewed health text.

## How a string becomes servable

1. A translator proposes the text for one key in `catalogue` in
   `webapp/app/lib/messages.ts`.
2. A named reviewer who is a native speaker of that language reads the exact
   string in context — not a glossary, the rendered page — and checks that it
   states the same action, the same strength of recommendation and the same
   absence of a clinical claim as the English.
3. The reviewer's name and the date go in that entry's `reviewedBy` and
   `reviewedAt`, and a row goes in the log below.
4. `npm test` asserts the gate: an entry with text but no reviewer is not
   served, and an approved UI string does not make the health strings servable.

A reviewer approves individual strings. There is no locale-level approval,
because the failure this prevents is a reviewed navigation label dragging an
unreviewed advisory onto the page with it.

## What a reviewer must not be asked to do

- Approve machine translation in bulk. The point of the review is the reading.
- Approve health text outside their native language.
- Approve a string whose English source has since changed. Changing the English
  clears the approval: re-approval is a new row below.

## Review log

| Date | Locale | Keys approved | Reviewer | Notes |
| --- | --- | --- | --- | --- |
| — | — | — | — | No review has taken place. |

## Why next-intl is not installed yet

The work package names next-intl, and it remains the intended library. It is not
wired up while every non-English string is unreviewed: its locale-prefixed
routes and provider plumbing would add a dependency and a public surface
(`/hi/...`, `/ta/...`) that can only serve English anyway, and the part that
prevents harm is the per-string gate, which does not need it. The catalogue in
`messages.ts` is deliberately shaped like a next-intl message namespace, so
adopting it later is a move, not a rewrite.

## Who to ask

Named Tamil and Hindi reviewers have not been supplied. This is recorded in
`HUMAN_ACTIONS.md` under "Tamil/Hindi review". Until then the honest public
position is the current one: English only, with the limitation stated.
