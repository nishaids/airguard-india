# AirGuard India — project memory for Claude Code

## What this is
AirGuard India: nationwide next-day AQI forecasting + cohort health advisories for India.
Live: https://webapp-phi-taupe.vercel.app · Repo: github.com/nishaids/airguard-india
Stack: Next.js on Vercel, Python serverless API (/api/air-quality/summary, /api/research/status),
Supabase (storage + scheduled jobs), static research JSON in /data, legacy Streamlit app.
Goal: national-level research system + 6-page IEEE conference paper + Medium article.

## Source of truth
- Full spec: docs/MASTER_SPEC.md (Parts A–I, limitations L01–L52, work packages WP0–WP9).
  Identical copy of `../AIRGUARD_CODEX_MASTER_PROMPT.md`, placed inside the repo so the
  Part B limitation table is version-controlled with the code it describes.
- Progress: docs/PROGRESS.md — ALWAYS read first, ALWAYS update before ending a session.
- Human-only tasks: HUMAN_ACTIONS.md.
- Read only the spec section needed for the current work package; do not load the whole spec every time.

## Hard rules
1. No fabricated numbers: every number in UI/paper comes from a committed script → results/*.json.
2. No fabricated references: verify every BibTeX entry by DOI or official URL; drop what can't be verified.
3. Issue-time discipline: no forecast feature may use data unavailable at 20:00 IST on the issue day.
   Reanalysis (ERA5, CAMS reanalysis) = retrospective analyses only.
4. Keep honesty features: measured vs modelled labels, readiness gates, claims-not-supported list,
   prospective ledger. Never mark a gate passed without its evidence artefact.
5. Never bypass CAPTCHAs, logins or terms of service. Credential needed → add to HUMAN_ACTIONS.md, move on.
6. Secrets never in code, logs, static JSON or client bundle.
7. Attribution ≠ causation; no clinical claims; HAI is an advisory heuristic, not medical advice.
8. Work on a feature branch per work package; small commits; run tests before each commit.
   Do not push or deploy to production unless I say so.

## Working style (token budget matters)
- Plan before editing a work package; show the plan, then execute.
- Prefer targeted reads (grep, specific line ranges) over reading whole large files.
- Never print large data files or JSON to the terminal; summarise with scripts (head, counts, shapes).
- Long-running jobs (downloads, backtests): write scripts, run them, log to logs/, report only summaries.
- After each completed task: commit, tick it in docs/PROGRESS.md, note the next step.
- If context is getting long: update docs/PROGRESS.md first, then tell me to start a fresh session.

## Commands (update as the Makefile evolves)
- make test · make data · make backtest · make results · make figures · make paper
- The Makefile dispatches every target to `python -m src.research.reproduce <target>`.
- Local Python lives in `.venv-live/` (3.10). Full suites:
  `./.venv-live/Scripts/python.exe -m pytest -q` (344 tests),
  and in `webapp/`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.
