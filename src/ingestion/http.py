"""A small HTTP client with bounded retries and no way to leak a credential.

Every connector goes through :class:`HttpClient`. It retries what is worth
retrying (connection failures, timeouts, 429 and 5xx), gives up on what is not
(other 4xx), honours ``Retry-After``, and caps both the number of attempts and
the wait between them.

Two providers put the credential where a careless log line would print it: one
in the query string, one in the URL path. Nothing here logs a URL with its
query, and every error message is passed through :func:`settings.redact`
before it is raised.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional
from urllib.parse import urlsplit

from src import config
from src.ingestion import settings as settings_mod

LOGGER = config.get_logger(__name__)

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class HttpError(Exception):
    """A request that did not produce a usable response. The message is safe to log."""

    def __init__(self, message: str, status: Optional[int] = None, kind: str = "http_error") -> None:
        super().__init__(settings_mod.redact(message))
        self.status = status
        self.kind = kind  # connection | timeout | http_error | rate_limited | malformed


@dataclass
class Response:
    status: int
    headers: Mapping[str, str]
    text: str

    def json(self) -> Any:
        try:
            return json.loads(self.text)
        except (ValueError, TypeError) as exc:
            raise HttpError(f"response was not valid JSON ({exc.__class__.__name__})", self.status, "malformed") from None


#: ``transport(url, params, headers, timeout) -> Response``. Raises
#: ``TimeoutError`` or ``ConnectionError`` for transport-level failure.
Transport = Callable[[str, Optional[Mapping[str, Any]], Optional[Mapping[str, str]], float], Response]


def _requests_transport(url: str, params, headers, timeout: float) -> Response:
    import requests

    try:
        reply = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        raise TimeoutError("request timed out") from None
    except requests.exceptions.RequestException as exc:
        # The exception text can embed the full URL, credentials included.
        raise ConnectionError(f"{exc.__class__.__name__}: could not reach {safe_host(url)}") from None
    return Response(reply.status_code, {k.lower(): v for k, v in reply.headers.items()}, reply.text)


def safe_host(url: str) -> str:
    """Host and port only. Paths and queries can carry credentials."""
    parts = urlsplit(url)
    return parts.netloc or url.split("/")[0]


class HttpClient:
    def __init__(
        self,
        settings: Optional[settings_mod.Settings] = None,
        transport: Optional[Transport] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings or settings_mod.get_settings()
        self.transport = transport or _requests_transport
        self.sleep = sleep
        self.requests_made = 0

    def get(
        self,
        url: str,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
        label: str = "request",
    ) -> Response:
        """GET with bounded exponential back-off. ``label`` is what gets logged."""
        attempts = self.settings.http_max_retries + 1
        last: Optional[HttpError] = None

        for attempt in range(1, attempts + 1):
            wait: Optional[float] = None
            try:
                self.requests_made += 1
                response = self.transport(url, params, headers, self.settings.http_timeout_seconds)
            except TimeoutError:
                last = HttpError(f"{label}: timed out after {self.settings.http_timeout_seconds}s contacting {safe_host(url)}", kind="timeout")
            except ConnectionError as exc:
                last = HttpError(f"{label}: {exc}", kind="connection")
            else:
                if 200 <= response.status < 300:
                    return response
                if response.status == 429:
                    last = HttpError(f"{label}: rate limited by {safe_host(url)} (HTTP 429)", 429, "rate_limited")
                    wait = _retry_after(response.headers)
                elif response.status in RETRYABLE_STATUS:
                    last = HttpError(f"{label}: {safe_host(url)} returned HTTP {response.status}", response.status)
                else:
                    detail = _short_reason(response.text)
                    raise HttpError(f"{label}: {safe_host(url)} returned HTTP {response.status}{detail}", response.status)

            if attempt == attempts:
                break
            if wait is None:
                wait = self.settings.http_backoff_seconds * (2 ** (attempt - 1))
            wait = min(wait, self.settings.http_max_backoff_seconds)
            LOGGER.info("%s: attempt %d of %d failed (%s); retrying in %.1fs", label, attempt, attempts, last.kind, wait)
            self.sleep(wait)

        assert last is not None
        raise last


def _retry_after(headers: Mapping[str, str]) -> Optional[float]:
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def _short_reason(body: str) -> str:
    """A provider's own error text, trimmed and scrubbed, for the failure reason."""
    text = " ".join((body or "").split())[:160]
    return f": {settings_mod.redact(text)}" if text else ""


def header_int(headers: Mapping[str, str], name: str) -> Optional[int]:
    try:
        return int(float(headers.get(name, "")))
    except (TypeError, ValueError):
        return None


def as_dict(payload: Any, label: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise HttpError(f"{label}: expected a JSON object, got {type(payload).__name__}", kind="malformed")
    return payload
