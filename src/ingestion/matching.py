"""Recognising the same monitor arriving through two sources.

OpenAQ republishes many government stations. If AirGuard ingests the official
CPCB feed and OpenAQ, the same instrument can appear twice, and a model trained
on both copies would count one station's evidence double.

Two readings are **not** treated as duplicates merely because they come from
the same city. A link is made only between specific stations, on evidence:

* the two stations are within ``station_match_metres`` of each other, or
* they are within two kilometres **and** their names are near-identical.

A link records *how* it was made and the distance involved. Both records are
kept with their own provenance; nothing is merged or deleted. What changes is
which copy may be used for modelling:

* within one run, :func:`resolve_modelling_preference` marks the less useful
  copy ``use_for_modelling = False``;
* across runs, the link is stored on the station, and the database view
  ``airguard.observations_for_modelling`` keeps one reading per physical
  station, pollutant and hour.

This is a preliminary matcher. It has not been validated against a hand-checked
list of station pairs, and that validation is listed as outstanding work.
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Tuple

from src.ingestion.schemas import AirQualityObservation, Severity, Station

NAME_SIMILARITY = 0.82
NAME_MATCH_MAX_METRES = 2000.0
_NOISE = re.compile(r"\b(cpcb|dpcc|imd|iitm|spcb|appcb|tnpcb|uppcb|wbpcb|kspcb|rspcb|hspcb|ppcb|tspcb|station|monitoring|caaqms)\b")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _normalise_name(name: Optional[str]) -> str:
    text = _NOISE.sub(" ", (name or "").lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def name_similarity(a: Optional[str], b: Optional[str]) -> float:
    left, right = _normalise_name(a), _normalise_name(b)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def link_stations(reference: Iterable[Station], candidates: Iterable[Station], max_metres: float) -> int:
    """Point each candidate at the reference station that is the same monitor.

    Returns the number of links made. ``reference`` is the source whose
    identity is kept (the official feed); ``candidates`` is the aggregator.
    """
    located = [s for s in reference if s.latitude is not None and s.longitude is not None]
    links = 0
    for candidate in candidates:
        if candidate.latitude is None or candidate.longitude is None or not located:
            continue
        nearest, distance = min(
            ((ref, haversine_m(candidate.latitude, candidate.longitude, ref.latitude, ref.longitude)) for ref in located),
            key=lambda pair: pair[1],
        )
        if distance <= max_metres:
            method = "distance"
        elif distance <= NAME_MATCH_MAX_METRES and name_similarity(candidate.name, nearest.name) >= NAME_SIMILARITY:
            method = "name_and_distance"
        else:
            continue
        candidate.same_as = nearest.key
        candidate.match_method = method
        candidate.match_distance_m = round(distance, 1)
        links += 1
    return links


def resolve_modelling_preference(
    reference: List[AirQualityObservation],
    candidates: List[AirQualityObservation],
    candidate_stations: Iterable[Station],
) -> int:
    """Where one monitor reported through both sources, keep one copy for modelling.

    The copy with a normalised concentration is preferred, because a value that
    could not be normalised cannot be modelled; if both have one, the official
    source wins. Returns the number of observations marked as superseded.
    """
    links: Dict[str, Tuple[str, str]] = {s.source_station_id: s.same_as for s in candidate_stations if s.same_as}
    by_station: Dict[Tuple[str, Optional[str]], List[AirQualityObservation]] = {}
    for obs in reference:
        by_station.setdefault((obs.source_station_id or "", obs.pollutant), []).append(obs)

    superseded = 0
    for candidate in candidates:
        link = links.get(candidate.source_station_id or "")
        if not link:
            continue
        for official in by_station.get((link[1], candidate.pollutant), []):
            if official.observed_at is None or candidate.observed_at is None:
                continue
            if abs((official.observed_at - candidate.observed_at).total_seconds()) > 3600:
                continue  # different hours are different measurements
            loser, winner = (
                (official, candidate)
                if official.normalized_value is None and candidate.normalized_value is not None
                else (candidate, official)
            )
            if loser.use_for_modelling:
                loser.use_for_modelling = False
                loser.provenance["superseded_by"] = {"source": winner.source, "station": winner.source_station_id}
                loser.add_flag(
                    "SAME_MONITOR_OTHER_SOURCE",
                    Severity.INFO,
                    f"the same monitor and hour is also held from {winner.source}; this copy is kept for provenance and excluded from modelling",
                )
                superseded += 1
    return superseded
