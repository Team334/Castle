"""Bounded, process-local cache for public scouting APIs (never MongoDB).

Only the four background threads perform network I/O. Identical requests share
one refresh; failures have a cooldown and never erase a previous good value.
"""
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)


@dataclass
class Entry:
    value: object = None
    expires: float = 0
    retry_at: float = 0
    future: object = None


class PublicAPICache:
    def __init__(self, workers=4, capacity=2048, max_pending=128,
                 cooldown=60, clock=time.monotonic):
        self.executor = ThreadPoolExecutor(max_workers=workers,
                                           thread_name_prefix="scouting-api")
        self.capacity = capacity
        self.max_pending = max_pending
        self.cooldown = cooldown
        self.clock = clock
        self.entries = OrderedDict()
        self.providers = {}
        self.lock = threading.RLock()
        self.local = threading.local()
        self.pending_count = 0

    @staticmethod
    def key(url, headers):
        return url, tuple(sorted((headers or {}).items()))

    def pending(self, url, headers=None):
        with self.lock:
            entry = self.entries.get(self.key(url, headers))
            # A full queue is also pending: a later poll can schedule this key.
            return bool(entry and (entry.future is not None or
                        (entry.value is None and entry.retry_at <= self.clock() and
                         self.providers.get(urlsplit(url).netloc, 0) <= self.clock())))

    def get(self, url, headers=None, ttl=300, background=False):
        key = self.key(url, headers)
        with self.lock:
            now = self.clock()
            entry = self.entries.get(key)
            if entry is None:
                # Never evict in-flight work: that would permit duplicate requests.
                if len(self.entries) >= self.capacity:
                    victim = next((k for k, v in self.entries.items()
                                   if v.future is None), None)
                    if victim is None:
                        return None
                    del self.entries[victim]
                entry = self.entries[key] = Entry()
            self.entries.move_to_end(key)
            if entry.value is not None and entry.expires > now:
                return entry.value
            if entry.future is None and entry.retry_at <= now:
                if self.providers.get(urlsplit(url).netloc, 0) > now:
                    entry.retry_at = self.providers[urlsplit(url).netloc]
                elif self.pending_count < self.max_pending:
                    self.pending_count += 1
                    entry.future = self.executor.submit(self._refresh, key, entry, ttl)
            future = entry.future
            # Stale-while-revalidate also makes ordinary navigation inexpensive.
            if background or entry.value is not None or future is None:
                return entry.value
        try:
            future.result(timeout=6)
        except TimeoutError:
            return None
        with self.lock:
            return entry.value

    def _refresh(self, key, entry, ttl):
        url, headers = key
        host = urlsplit(url).netloc
        failed = False
        provider_failed = False
        value = None
        try:
            with self.lock:
                if self.providers.get(host, 0) > self.clock():
                    failed = True
                    return
            if not hasattr(self.local, "session"):
                self.local.session = requests.Session()
            # Statbotics' SDK has no timeout and retries slow failures. Use the
            # public endpoint directly with an explicit connect/read budget.
            with self.local.session.get(url, headers=dict(headers),
                                        timeout=(2, 3)) as response:
                provider_failed = response.status_code in (401, 403, 429) or response.status_code >= 500
                response.raise_for_status()
                value = response.json()
                if not isinstance(value, (dict, list)):
                    raise ValueError("Expected a JSON object or list")
        except (requests.RequestException, ValueError) as error:
            failed = True
            provider_failed = provider_failed or not isinstance(error, requests.HTTPError)
            logger.warning("Public scouting API unavailable: %s", host)
        finally:
            with self.lock:
                now = self.clock()
                if failed:
                    entry.retry_at = now + self.cooldown
                    if provider_failed:
                        self.providers[host] = now + self.cooldown
                else:
                    entry.value = value
                    entry.expires = now + ttl
                    entry.retry_at = 0
                entry.future = None
                self.pending_count -= 1

    def close(self):
        self.executor.shutdown(wait=True)


public_api_cache = PublicAPICache()
