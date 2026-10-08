"""Run live ingestion for one source or all of them.

    python -m src.ingestion.run --source weather --dry-run
    python -m src.ingestion.run --source cpcb --source openaq
    python -m src.ingestion.run --all
    python -m src.ingestion.run --all --dry-run --limit 3

``--dry-run`` retrieves and validates without touching the database, and is the
first thing to run against any new source or key. ``--limit`` shrinks the run
for a quick check: the number of records for CPCB and FIRMS, and the number of
locations for OpenAQ and weather.

Each source succeeds or fails on its own. One provider being down does not stop
the others, and the exit code is non-zero if any source failed.

Nothing printed here contains a credential: counts, timings, a status, and a
few sample records. Failure reasons are redacted before they are shown.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from src import config
from src.ingestion import cpcb, firms, matching, openaq, validation, weather
from src.ingestion import settings as settings_mod
from src.ingestion.base import Batch, CredentialMissing, SourceUnavailable
from src.ingestion.http import HttpClient, HttpError
from src.ingestion.schemas import IngestionRun, RunStatus, utc_now

LOGGER = config.get_logger(__name__)

CONNECTORS: Dict[str, Any] = {"cpcb": cpcb, "openaq": openaq, "firms": firms, "weather": weather}
ORDER = ("cpcb", "openaq", "firms", "weather")  # cpcb first: openaq stations are matched against it


class _RedactingFilter(logging.Filter):
    """Last line of defence: scrub secrets from every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = settings_mod.redact(record.getMessage())
        record.args = ()
        return True


def install_log_redaction() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, _RedactingFilter) for f in handler.filters):
            handler.addFilter(_RedactingFilter())
    for name in list(logging.root.manager.loggerDict):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, _RedactingFilter) for f in handler.filters):
                handler.addFilter(_RedactingFilter())


def _validate(batch: Batch, settings: settings_mod.Settings) -> None:
    now = utc_now()
    seen: set = set()
    for record in batch.records:
        if batch.kind == "air_quality":
            validation.validate_observation(record, now, settings, seen)
        elif batch.kind == "fire":
            validation.validate_fire(record, now, settings, seen)
        else:
            validation.validate_weather(record, seen)


def _pick_samples(kind: str, records: List[Any], count: int = 3) -> List[Any]:
    """A few records to show. For weather, prefer tomorrow over the next hour."""
    if kind == "weather":
        ahead = [r for r in records if r.lead_time_hours >= 24]
        seen, picked = set(), []
        for record in ahead or records:
            if record.location_label not in seen:
                seen.add(record.location_label)
                picked.append(record)
        return picked[:count]
    return records[:count]


def run_source(
    name: str,
    store: Any = None,
    dry_run: bool = True,
    limit: Optional[int] = None,
    settings: Optional[settings_mod.Settings] = None,
    client: Optional[HttpClient] = None,
    context: Optional[Dict[str, Batch]] = None,
) -> Tuple[IngestionRun, List[Any]]:
    """Ingest one source. Never raises: a failure is returned as a FAILED run."""
    settings = settings or settings_mod.get_settings()
    connector = CONNECTORS[name]
    run = IngestionRun(source=connector.SOURCE, started_at=utc_now(), dry_run=dry_run)
    samples: List[Any] = []
    context = context if context is not None else {}

    try:
        if store is not None and not dry_run:
            store.start_run(run)

        batch: Batch = connector.collect(client=client, settings=settings, limit=limit)
        _validate(batch, settings)

        # An aggregator's stations are checked against the official feed's.
        if name == "openaq":
            reference_batch = context.get("cpcb")
            reference = reference_batch.stations if reference_batch else (store.load_stations(cpcb.SOURCE) if store is not None and not dry_run else [])
            linked = matching.link_stations(reference, batch.stations, settings.station_match_metres)
            if reference:
                run.notes.append(f"{linked} of {len(batch.stations)} stations matched to a CPCB station")
            if reference_batch:
                superseded = matching.resolve_modelling_preference(reference_batch.records, batch.records, batch.stations)
                if superseded:
                    run.notes.append(f"{superseded} readings duplicate an official reading for the same monitor and hour; excluded from modelling")

        clean, flagged, rejected = validation.split(batch.records)
        duplicates = [r for r in rejected if any(f.code == "DUPLICATE_IN_BATCH" for f in r.quality_flags)]
        rejections = batch.rejected + [validation.rejection_of(r) for r in rejected if r not in duplicates]

        run.retrieved = max(batch.retrieved, len(batch.records))
        run.accepted = len(clean) + len(flagged)
        run.flagged = len(flagged)
        run.duplicates = len(duplicates)
        run.rejected = len(rejections)
        run.notes.extend(batch.notes)
        samples = _pick_samples(batch.kind, clean + flagged)
        context[name] = batch

        if store is not None and not dry_run:
            keep = clean + flagged
            if batch.kind == "air_quality":
                store.upsert_stations(batch.stations)
                run.written = store.insert_observations(keep, run)
            elif batch.kind == "fire":
                run.written = store.insert_fires(keep, run)
            else:
                run.written = store.insert_forecasts(keep, run)
            store.insert_rejections(rejections, run)

        run.status = RunStatus.PARTIAL if batch.partial else RunStatus.SUCCESS

    except CredentialMissing as exc:
        # For the official feed, say plainly that it is unavailable: nothing is substituted for it.
        run.error = f"{cpcb.UNAVAILABLE} {exc}" if name == "cpcb" else str(exc)
    except SourceUnavailable as exc:
        run.error = settings_mod.redact(exc)
    except HttpError as exc:
        run.error = f"{cpcb.UNAVAILABLE} {exc}" if name == "cpcb" else str(exc)
    except Exception as exc:  # noqa: BLE001 - one source must never take the others down
        run.error = settings_mod.redact(f"{exc.__class__.__name__}: {exc}")
        LOGGER.exception("%s: unexpected failure", name)

    run.finished_at = utc_now()
    if store is not None and not dry_run:
        try:
            store.finish_run(run)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("could not record the run: %s", settings_mod.redact(exc))
    return run, samples


# --------------------------------------------------------------------------- #
# Presentation
# --------------------------------------------------------------------------- #
def describe(record: Any) -> str:
    """One line for a sample record: provider, place, parameter, value, times, quality."""
    retrieved = f"{record.retrieved_at:%Y-%m-%d %H:%M}Z"
    quality = record.quality_state.value
    flags = ",".join(sorted({f.code for f in record.quality_flags}))
    if flags:
        quality += f" [{flags}]"

    if hasattr(record, "pollutant"):
        shown, unit = (
            (f"{record.normalized_value:g}", record.normalized_unit)
            if record.normalized_value is not None
            else (f"{record.raw_value} (raw)", record.raw_unit or "unit not published")
        )
        place = f"{record.station_name or record.source_station_id}, {record.city or '?'}"
        kind = "MEASURED" if record.source_type.value == "measured" else "MODELLED"
        return f"{record.source} | {kind} | {place} | {record.pollutant} | {shown} | {unit} | observed {record.observed_at:%Y-%m-%d %H:%M}Z | retrieved {retrieved} | {quality}"

    if hasattr(record, "acquired_at"):
        frp = f"{record.frp_mw:g}" if record.frp_mw is not None else "n/a"
        return (
            f"{record.source} | SATELLITE FIRE DETECTION | {record.latitude:.3f},{record.longitude:.3f} | fire radiative power | {frp} | MW | "
            f"acquired {record.acquired_at:%Y-%m-%d %H:%M}Z ({record.satellite}, confidence {record.confidence}) | retrieved {retrieved} | {quality}"
        )

    values = ", ".join(f"{k}={v:g}{record.units.get(k, '')}" for k, v in record.variables.items() if v is not None)
    issued = f"{record.issued_at:%Y-%m-%d %H:%M}Z" if record.issued_at else "unknown"
    return (
        f"{record.source} | WEATHER FORECAST ({record.model}) | {record.location_label} | {values} | "
        f"valid {record.valid_at:%Y-%m-%d %H:%M}Z (+{record.lead_time_hours:.0f}h) | run {issued} | retrieved {retrieved} | {quality}"
    )


def print_report(results: List[Tuple[str, IngestionRun, List[Any]]], dry_run: bool, out: Callable[[str], None] = print) -> None:
    out("")
    out("=" * 104)
    out(f"AirGuard live ingestion  |  {'DRY RUN - nothing written' if dry_run else 'writing to database'}")
    out("=" * 104)
    out(f"{'source':18s} {'status':8s} {'retrieved':>9s} {'accepted':>9s} {'flagged':>8s} {'rejected':>9s} {'dupes':>6s} {'written':>8s}  {'start':8s} {'end':8s}")
    out("-" * 104)
    for _, run, _ in results:
        end = f"{run.finished_at:%H:%M:%S}" if run.finished_at else ""
        out(
            f"{run.source:18s} {run.status.value:8s} {run.retrieved:>9,} {run.accepted:>9,} {run.flagged:>8,} "
            f"{run.rejected:>9,} {run.duplicates:>6,} {run.written:>8,}  {run.started_at:%H:%M:%S} {end}"
        )
    out("-" * 104)
    for _, run, samples in results:
        out(f"\n[{run.source}] {run.status.value}")
        if run.error:
            out(f"  reason: {settings_mod.redact(run.error)}")
        for note in run.notes:
            out(f"  note:   {settings_mod.redact(note)}")
        for record in samples:
            out(f"  sample: {settings_mod.redact(describe(record))}")
    out("")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AirGuard live data ingestion")
    parser.add_argument("--source", action="append", choices=sorted(CONNECTORS), help="source to run; may be repeated")
    parser.add_argument("--all", action="store_true", help="run every source")
    parser.add_argument("--dry-run", action="store_true", help="retrieve and validate, write nothing")
    parser.add_argument("--limit", type=int, default=None, help="shrink the run for a quick check")
    args = parser.parse_args(argv)

    if not args.all and not args.source:
        parser.error("choose --source NAME (repeatable) or --all")

    for stream in (sys.stdout, sys.stderr):  # a Windows console may not be UTF-8
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    settings_mod.load_env()
    install_log_redaction()
    names = [n for n in ORDER if args.all or n in (args.source or [])]

    store = None
    if not args.dry_run:
        from src.ingestion import db

        try:
            store = db.PostgresStore()
        except (db.DatabaseError, CredentialMissing) as exc:
            print(f"database: {exc}")
            print("Nothing was written. Re-run with --dry-run to test the sources without a database.")
            return 1

    context: Dict[str, Batch] = {}
    client = HttpClient()
    results = [(name, *run_source(name, store, args.dry_run, args.limit, client=client, context=context)) for name in names]
    print_report(results, args.dry_run)

    if store is not None:
        store.close()
    return 1 if any(run.status is RunStatus.FAILED for _, run, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
