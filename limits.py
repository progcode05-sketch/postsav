"""In-process abuse controls: per-client rate limits and bounded concurrent downloads."""
import threading
import time


class RateLimiter:
    """Sliding-window limiter keyed by client address."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._hits = {}
        self._lock = threading.Lock()

    def check(self, key, limit, window=60):
        """Record a request. Returns (allowed, seconds_until_retry)."""
        if limit <= 0:
            return True, 0
        now = self._clock()
        with self._lock:
            if len(self._hits) > 5000:
                for stale in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - window]:
                    del self._hits[stale]
            hits = [t for t in self._hits.get(key, ()) if t > now - window]
            if len(hits) >= limit:
                self._hits[key] = hits
                return False, max(1, int(hits[0] + window - now) + 1)
            hits.append(now)
            self._hits[key] = hits
            return True, 0


class DownloadGate:
    """Caps simultaneous download jobs globally and per client."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active = {}

    def acquire(self, client, total, per_client):
        with self._lock:
            if sum(self._active.values()) >= total or self._active.get(client, 0) >= per_client:
                return None
            self._active[client] = self._active.get(client, 0) + 1
        released = threading.Event()

        def release():
            # Safe to call from several cleanup paths; only the first one counts.
            if released.is_set():
                return
            released.set()
            with self._lock:
                remaining = self._active.get(client, 1) - 1
                if remaining > 0:
                    self._active[client] = remaining
                else:
                    self._active.pop(client, None)

        return release

    @property
    def active(self):
        with self._lock:
            return sum(self._active.values())
