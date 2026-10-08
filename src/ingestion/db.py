"""Storage for ingested records.

Two stores share one interface. :class:`PostgresStore` is the real one.
:class:`MemoryStore` enforces the same uniqueness keys in a dictionary, so the
idempotency logic can be unit-tested without a database; it is not a substitute
for testing against PostgreSQL, where the constraints themselves live.

Idempotency
-----------
Every insert is ``ON CONFLICT DO NOTHING`` against a uniqueness key defined in
``db/migrations/001_live_ingestion.sql``. Running the same ingestion twice
writes the data once. Quality flags are written only for rows that were
actually inserted, so they are not duplicated either.

The connection string is read from ``DATABASE_URL`` and is never logged; a
connection failure is reported by its class and a redacted message.

Commands::

    python -m src.ingestion.db migrate    # apply db/migrations/*.sql
    python -m src.ingestion.db status     # row counts and the latest runs
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src import config
from src.ingestion import settings as settings_mod
from src.ingestion.base import CredentialMissing
from src.ingestion.schemas import (
    AirQualityObservation,
    FireDetection,
    IngestionRun,
    RejectedRecord,
    Station,
    WeatherForecast,
)
from src.ingestion.weather import VARIABLES as WEATHER_VARIABLES

LOGGER = config.get_logger(__name__)
MIGRATIONS_DIR = config.PROJECT_ROOT / "db" / "migrations"
TABLES = (
    "source_registry", "stations", "air_quality_observations", "weather_forecasts",
    "fire_detections", "data_quality_flags", "ingestion_runs",
)


class DatabaseError(Exception):
    """A storage failure, with a message that is safe to print."""

    def __init__(self, message: str) -> None:
        super().__init__(settings_mod.redact(message))


def _json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def _text(value: Any) -> Optional[str]:
    return None if value is None else str(value)


# --------------------------------------------------------------------------- #
# In-memory store: same keys, no database
# --------------------------------------------------------------------------- #
class MemoryStore:
    def __init__(self) -> None:
        self.stations: Dict[tuple, Station] = {}
        self.observations: Dict[tuple, AirQualityObservation] = {}
        self.forecasts: Dict[tuple, WeatherForecast] = {}
        self.fires: Dict[tuple, FireDetection] = {}
        self.rejections: Dict[str, RejectedRecord] = {}
        self.flags: List[tuple] = []
        self.runs: List[IngestionRun] = []

    def start_run(self, run: IngestionRun) -> None:
        run.run_id = len(self.runs) + 1
        self.runs.append(run)

    def finish_run(self, run: IngestionRun) -> None:
        pass

    def load_stations(self, source: str) -> List[Station]:
        return [s for s in self.stations.values() if s.source == source]

    def upsert_stations(self, stations: Iterable[Station]) -> int:
        count = 0
        for station in stations:
            self.stations[station.key] = station
            count += 1
        return count

    def _insert(self, table: Dict[Any, Any], records: Iterable[Any], kind: str) -> int:
        inserted = 0
        for record in records:
            if record.unique_key in table:
                continue
            table[record.unique_key] = record
            self.flags.extend((kind, record.unique_key, f.code) for f in record.quality_flags)
            inserted += 1
        return inserted

    def insert_observations(self, records: Iterable[AirQualityObservation], run: IngestionRun) -> int:
        return self._insert(self.observations, records, "air_quality_observation")

    def insert_forecasts(self, records: Iterable[WeatherForecast], run: IngestionRun) -> int:
        return self._insert(self.forecasts, records, "weather_forecast")

    def insert_fires(self, records: Iterable[FireDetection], run: IngestionRun) -> int:
        return self._insert(self.fires, records, "fire_detection")

    def insert_rejections(self, rejected: Iterable[RejectedRecord], run: IngestionRun) -> int:
        inserted = 0
        for item in rejected:
            if item.hash not in self.rejections:
                self.rejections[item.hash] = item
                inserted += 1
        return inserted

    def close(self) -> None:
        pass


# --------------------------------------------------------------------------- #
# PostgreSQL
# --------------------------------------------------------------------------- #
def connect():
    """Open a connection from ``DATABASE_URL``. Never logs the string."""
    status = settings_mod.secret_status().get("DATABASE_URL")
    dsn = settings_mod.secret("DATABASE_URL")
    if not dsn:
        if status == "placeholder":
            raise DatabaseError("DATABASE_URL still contains placeholder text (PROJECT_REF / POOLER_HOST); put the real connection string in .env")
        raise CredentialMissing("DATABASE_URL")
    try:
        import psycopg2

        kwargs: Dict[str, Any] = {"connect_timeout": 20}
        if "sslmode=" not in dsn:
            kwargs["sslmode"] = "require"
        return psycopg2.connect(dsn, **kwargs)
    except Exception as exc:  # noqa: BLE001 - every driver error is reported the same safe way
        raise DatabaseError(f"could not connect to the database ({exc.__class__.__name__}: {exc})") from None


def migrate(connection=None) -> List[str]:
    """Apply every migration that has not been applied yet. Returns their names."""
    own = connection is None
    connection = connection or connect()
    applied: List[str] = []
    try:
        with connection, connection.cursor() as cursor:
            cursor.execute("create schema if not exists airguard")
            cursor.execute(
                "create table if not exists airguard.schema_migrations "
                "(filename text primary key, applied_at timestamptz not null default now())"
            )
            cursor.execute("select filename from airguard.schema_migrations")
            done = {row[0] for row in cursor.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            with connection, connection.cursor() as cursor:
                cursor.execute(path.read_text(encoding="utf-8"))
                cursor.execute("insert into airguard.schema_migrations (filename) values (%s)", (path.name,))
            applied.append(path.name)
    except DatabaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DatabaseError(f"migration failed ({exc.__class__.__name__}: {exc})") from None
    finally:
        if own:
            connection.close()
    return applied


class PostgresStore:
    def __init__(self, connection=None) -> None:
        self.connection = connection or connect()

    # -- runs ----------------------------------------------------------------- #
    def start_run(self, run: IngestionRun) -> None:
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                "insert into airguard.ingestion_runs (source_id, started_at, status) values (%s, %s, 'RUNNING') returning run_id",
                (run.source, run.started_at),
            )
            run.run_id = cursor.fetchone()[0]

    def finish_run(self, run: IngestionRun) -> None:
        if run.run_id is None:
            return
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                "update airguard.ingestion_runs set finished_at=%s, status=%s, retrieved=%s, accepted=%s, flagged=%s, "
                "rejected=%s, duplicates=%s, written=%s, error=%s, notes=%s where run_id=%s",
                (
                    run.finished_at, run.status.value, run.retrieved, run.accepted, run.flagged, run.rejected,
                    run.duplicates, run.written, run.error, _json([settings_mod.redact(n) for n in run.notes]), run.run_id,
                ),
            )

    # -- stations ------------------------------------------------------------- #
    def load_stations(self, source: str) -> List[Station]:
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                "select source_station_id, name, city, state, latitude, longitude from airguard.stations where source_id=%s",
                (source,),
            )
            return [
                Station(source=source, source_station_id=row[0], name=row[1], city=row[2], state=row[3], latitude=row[4], longitude=row[5])
                for row in cursor.fetchall()
            ]

    def upsert_stations(self, stations: Iterable[Station]) -> int:
        from psycopg2.extras import execute_values

        stations = list(stations)
        if not stations:
            return 0
        rows = [
            (
                s.source, s.source_station_id, s.name, s.city, s.state, s.country, s.latitude, s.longitude,
                s.timezone, s.owner, s.upstream_provider, s.match_method, s.match_distance_m, _json(s.metadata),
            )
            for s in stations
        ]
        with self.connection, self.connection.cursor() as cursor:
            execute_values(
                cursor,
                "insert into airguard.stations (source_id, source_station_id, name, city, state, country, latitude, longitude, "
                "timezone, owner, upstream_provider, match_method, match_distance_m, metadata) values %s "
                "on conflict (source_id, source_station_id) do update set "
                "name=excluded.name, city=excluded.city, state=excluded.state, latitude=excluded.latitude, longitude=excluded.longitude, "
                "timezone=excluded.timezone, owner=excluded.owner, upstream_provider=excluded.upstream_provider, "
                "match_method=coalesce(excluded.match_method, airguard.stations.match_method), "
                "match_distance_m=coalesce(excluded.match_distance_m, airguard.stations.match_distance_m), "
                "metadata=excluded.metadata, last_seen_at=now()",
                rows,
                page_size=500,
            )
            # Resolve "same monitor" links to primary keys now that both sides exist.
            links = [(s.same_as[0], s.same_as[1], s.source, s.source_station_id) for s in stations if s.same_as]
            for target_source, target_id, source, station_id in links:
                cursor.execute(
                    "update airguard.stations child set same_as_station_pk = parent.station_pk "
                    "from airguard.stations parent where parent.source_id=%s and parent.source_station_id=%s "
                    "and child.source_id=%s and child.source_station_id=%s",
                    (target_source, target_id, source, station_id),
                )
        return len(rows)

    def _station_pks(self, cursor, source: str) -> Dict[str, int]:
        cursor.execute("select source_station_id, station_pk from airguard.stations where source_id=%s", (source,))
        return dict(cursor.fetchall())

    # -- flags ---------------------------------------------------------------- #
    def _insert_flags(self, cursor, kind: str, column: str, pairs: Sequence[Tuple[int, Any]], run: IngestionRun) -> None:
        from psycopg2.extras import execute_values

        rows = [
            (kind, pk, record.source, flag.code, flag.severity.value, flag.message, flag.field_name or "", run.run_id)
            for pk, record in pairs
            for flag in record.quality_flags
        ]
        if rows:
            execute_values(
                cursor,
                f"insert into airguard.data_quality_flags (record_kind, {column}, source_id, code, severity, message, field_name, ingestion_run_id) "
                "values %s on conflict do nothing",
                rows,
                page_size=1000,
            )

    # -- observations --------------------------------------------------------- #
    def insert_observations(self, records: Iterable[AirQualityObservation], run: IngestionRun) -> int:
        from psycopg2.extras import execute_values

        records = list(records)
        if not records:
            return 0
        with self.connection, self.connection.cursor() as cursor:
            pks = self._station_pks(cursor, records[0].source)
            rows = [
                (
                    o.source, o.source_type.value, pks.get(o.source_station_id), o.source_station_id, o.source_record_id, o.sensor_id,
                    o.pollutant, o.raw_pollutant, o.value_kind.value, o.averaging_period, _text(o.raw_value), _text(o.raw_min),
                    _text(o.raw_max), o.raw_unit, o.normalized_value, o.normalized_unit, o.observed_at, o.local_timezone,
                    o.retrieved_at, o.quality_state.value, o.freshness.value if o.freshness else None, o.use_for_modelling,
                    _json(o.provenance), run.run_id,
                )
                for o in records
            ]
            returned = execute_values(
                cursor,
                "insert into airguard.air_quality_observations (source_id, source_type, station_pk, source_station_id, source_record_id, "
                "sensor_id, pollutant, raw_pollutant, value_kind, averaging_period, raw_value, raw_min, raw_max, raw_unit, normalized_value, "
                "normalized_unit, observed_at, local_timezone, retrieved_at, quality_state, freshness_at_retrieval, use_for_modelling, "
                "provenance, ingestion_run_id) values %s "
                "on conflict (source_id, source_station_id, pollutant, averaging_period, observed_at) do nothing "
                "returning observation_id, source_station_id, pollutant, averaging_period, observed_at",
                rows,
                page_size=1000,
                fetch=True,
            )
            by_key = {(o.source_station_id, o.pollutant, o.averaging_period, o.observed_at): o for o in records}
            pairs = [(row[0], by_key[(row[1], row[2], row[3], row[4])]) for row in returned if (row[1], row[2], row[3], row[4]) in by_key]
            self._insert_flags(cursor, "air_quality_observation", "observation_id", pairs, run)
        return len(returned)

    # -- weather -------------------------------------------------------------- #
    def insert_forecasts(self, records: Iterable[WeatherForecast], run: IngestionRun) -> int:
        from psycopg2.extras import execute_values

        records = list(records)
        if not records:
            return 0
        columns = ", ".join(WEATHER_VARIABLES)
        rows = [
            (
                f.source, f.model, f.location_label, round(f.latitude, 4), round(f.longitude, 4), f.issued_at, f.retrieved_at,
                f.valid_at, f.lead_time_hours, *[f.variables.get(v) for v in WEATHER_VARIABLES], _json(f.units),
                f.quality_state.value, _json(f.provenance), run.run_id,
            )
            for f in records
        ]
        with self.connection, self.connection.cursor() as cursor:
            returned = execute_values(
                cursor,
                "insert into airguard.weather_forecasts (source_id, model, location_label, latitude, longitude, issued_at, retrieved_at, "
                f"valid_at, lead_time_hours, {columns}, units, quality_state, provenance, ingestion_run_id) values %s "
                "on conflict (source_id, model, latitude, longitude, valid_at, retrieved_at) do nothing "
                "returning forecast_id, location_label, valid_at, retrieved_at",
                rows,
                page_size=1000,
                fetch=True,
            )
            by_key = {(f.location_label, f.valid_at, f.retrieved_at): f for f in records}
            pairs = [(row[0], by_key[(row[1], row[2], row[3])]) for row in returned if (row[1], row[2], row[3]) in by_key]
            self._insert_flags(cursor, "weather_forecast", "forecast_id", pairs, run)
        return len(returned)

    # -- fires ---------------------------------------------------------------- #
    def insert_fires(self, records: Iterable[FireDetection], run: IngestionRun) -> int:
        from psycopg2.extras import execute_values

        records = list(records)
        if not records:
            return 0
        rows = [
            (
                f.source, f.source_record_id, f.product, f.satellite, f.instrument, f.latitude, f.longitude, f.acquired_at,
                f.confidence, f.frp_mw, f.brightness_k, f.day_night, f.version, f.retrieved_at, f.quality_state.value,
                _json(f.provenance), run.run_id,
            )
            for f in records
        ]
        with self.connection, self.connection.cursor() as cursor:
            returned = execute_values(
                cursor,
                "insert into airguard.fire_detections (source_id, source_record_id, product, satellite, instrument, latitude, longitude, "
                "acquired_at, confidence, frp_mw, brightness_k, day_night, version, retrieved_at, quality_state, provenance, ingestion_run_id) "
                "values %s on conflict (source_id, source_record_id) do nothing returning detection_id, source_record_id",
                rows,
                page_size=1000,
                fetch=True,
            )
            by_key = {f.source_record_id: f for f in records}
            pairs = [(row[0], by_key[row[1]]) for row in returned if row[1] in by_key]
            self._insert_flags(cursor, "fire_detection", "detection_id", pairs, run)
        return len(returned)

    # -- rejections ----------------------------------------------------------- #
    def insert_rejections(self, rejected: Iterable[RejectedRecord], run: IngestionRun) -> int:
        from psycopg2.extras import execute_values

        rows = [
            ("rejected_record", r.source, r.hash, r.code, "reject", settings_mod.redact(r.message), _json(r.raw_excerpt), run.run_id)
            for r in rejected
        ]
        if not rows:
            return 0
        with self.connection, self.connection.cursor() as cursor:
            returned = execute_values(
                cursor,
                "insert into airguard.data_quality_flags (record_kind, source_id, record_hash, code, severity, message, details, ingestion_run_id) "
                "values %s on conflict do nothing returning flag_id",
                rows,
                page_size=1000,
                fetch=True,
            )
        return len(returned)

    # -- inspection ----------------------------------------------------------- #
    def counts(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        with self.connection, self.connection.cursor() as cursor:
            for table in TABLES:
                cursor.execute(f"select count(*) from airguard.{table}")
                result[table] = cursor.fetchone()[0]
        return result

    def latest_runs(self, limit: int = 8) -> List[tuple]:
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                "select source_id, status, retrieved, accepted, flagged, rejected, written, started_at, finished_at "
                "from airguard.ingestion_runs order by started_at desc limit %s",
                (limit,),
            )
            return cursor.fetchall()

    def query(self, sql: str, params: Sequence[Any] = ()) -> List[tuple]:
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def close(self) -> None:
        self.connection.close()


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "status"
    settings_mod.load_env()
    try:
        if command == "migrate":
            applied = migrate()
            print("applied: " + (", ".join(applied) if applied else "nothing new; schema is up to date"))
            return 0
        if command == "status":
            store = PostgresStore()
            print("rows per table (schema airguard):")
            for table, n in store.counts().items():
                print(f"  {table:28s} {n:>8,}")
            print("latest runs:")
            for row in store.latest_runs():
                started: datetime = row[7]
                print(f"  {row[0]:18s} {row[1]:8s} retrieved={row[2]} accepted={row[3]} flagged={row[4]} rejected={row[5]} written={row[6]} started={started:%Y-%m-%d %H:%M}Z")
            store.close()
            return 0
        print("usage: python -m src.ingestion.db [migrate|status]")
        return 2
    except (DatabaseError, CredentialMissing) as exc:
        print(f"database: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
