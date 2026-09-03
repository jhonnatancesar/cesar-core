"""Quota local pré-upstream por aplicação e capacidade."""

from dataclasses import dataclass
from threading import Lock
from time import monotonic

from cesar_core.applications.identity import ApplicationId
from cesar_core.security.errors import QuotaExceededError


@dataclass(slots=True)
class _Window:
    started_at: float
    count: int


class QuotaLimiter:
    """Fixed-window limiter em memória, suficiente para o runtime único atual."""

    def __init__(self, *, window_seconds: int = 60) -> None:
        self._window_seconds = window_seconds
        self._windows: dict[tuple[ApplicationId, str], _Window] = {}
        self._lock = Lock()

    def check(self, application_id: ApplicationId, capability: str, limit: int) -> None:
        now = monotonic()
        key = (application_id, capability)
        with self._lock:
            window = self._windows.get(key)
            if window is None or now - window.started_at >= self._window_seconds:
                self._windows[key] = _Window(started_at=now, count=1)
                return
            if window.count >= limit:
                elapsed = int(now - window.started_at)
                raise QuotaExceededError(max(1, self._window_seconds - elapsed))
            window.count += 1

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()
