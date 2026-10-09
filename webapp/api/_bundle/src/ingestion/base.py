"""Shared types for connectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from src.ingestion.schemas import RejectedRecord, Station


class CredentialMissing(Exception):
    """A connector needs a secret that is not configured. Carries the variable *name* only."""

    def __init__(self, name: str) -> None:
        super().__init__(f"credential {name} is not configured (set it in .env or the environment)")
        self.name = name


class SourceUnavailable(Exception):
    """The provider answered, but not with the data this connector is for."""


@dataclass
class Batch:
    """Everything one connector produced in one run, before validation."""

    source: str
    kind: str  # "air_quality" | "weather" | "fire"
    records: List[Any] = field(default_factory=list)
    stations: List[Station] = field(default_factory=list)
    rejected: List[RejectedRecord] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    retrieved: int = 0
    partial: bool = False  # some of the provider's data could not be fetched
