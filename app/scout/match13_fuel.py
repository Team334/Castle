"""Event-cached fuel estimates. MongoDB keeps its existing document format.

SQLite stores opt-in record IDs, provenance, ETags and account-wide request
budgets shared by Gunicorn workers on one host. Only newly saved blank forms
are enrolled. All network work runs in a background thread.
"""
import atexit
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
import json
import logging
import math
import re
import sqlite3
import threading
import time
from pathlib import Path

from bson import ObjectId
import requests

logger = logging.getLogger(__name__)
PHASES = {
    "auto_fuel": "autoCount", "transition_fuel": "transitionCount",
    "teleop_shift_1_fuel": "shift1Count", "teleop_shift_2_fuel": "shift2Count",
    "teleop_shift_3_fuel": "shift3Count", "teleop_shift_4_fuel": "shift4Count",
    "endgame_fuel": "endgameCount",
}
FUEL_FIELDS = (*PHASES, "ferried_fuel")
EVENT_PATTERN = re.compile(r"2026[a-z0-9]+\Z")


def blank_fuel(data):
    """An entered zero is an observation, not missing data."""
    return (str(data.get("_fuel_entered", "false")).lower() not in ("true", "1")
            and all(data.get(field) in (None, "") for field in FUEL_FIELDS))


def match_key(event, label):
    if not EVENT_PATTERN.fullmatch(event):
        return None
    if re.fullmatch(re.escape(event) + r"_(?:qm\d+|sf\d+m\d+|f\d+m\d+)", label):
        return label
    for pattern, suffix in [(r"Qual(?:ification)? (\d+)", "qm{}"),
                            (r"(?:Semifinal|Semi-Finals) (\d+)-(\d+)", "sf{}m{}"),
                            (r"Finals? (\d+)", "f1m{}")]:
        found = re.fullmatch(pattern, label, re.I)
        if found:
            return event + "_" + suffix.format(*found.groups())
    return None


def apportioned(total, weights):
    """Largest remainders keep rounded robot counts equal to alliance totals."""
    if not isinstance(total, (int, float)) or not math.isfinite(total) or total < 0 or total != int(total):
        return None
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in weights.values()):
        return None
    weights = {key: max(0, value) for key, value in weights.items()}
    denominator = sum(weights.values())
    if denominator == 0:
        return {key: 0 for key in weights} if total == 0 else None
    exact = {key: total * value / denominator for key, value in weights.items()}
    result = {key: math.floor(value) for key, value in exact.items()}
    order = sorted(exact, key=lambda key: (-(exact[key] - result[key]), int(key)))
    for key in order[:int(total) - sum(result.values())]:
        result[key] += 1
    return result


def estimate_fuel(official_match, ratings, alliance, team):
    """Allocate official phase counts; ratings are weights, not observations."""
    if alliance not in ("red", "blue"):
        return None
    group = official_match.get("alliances", {}).get(alliance, {})
    teams = [key.removeprefix("frc") for key in group.get("team_keys", [])]
    if str(team) not in teams or len(teams) != 3 or len(set(teams)) != 3 or group.get("score", -1) < 0:
        return None
    hub = (official_match.get("score_breakdown") or {}).get(alliance, {}).get("hubScore")
    if not isinstance(hub, dict):
        return None
    dq = set(group.get("dq_team_keys", []))
    result = {}
    for field, source in PHASES.items():
        # Endgame fuel is shooting, so it uses xTele, not the tower/end rating.
        metric = "xAuto" if field == "auto_fuel" else "xTele"
        weights = {number: 0 if "frc" + number in dq else ratings.get(number, {}).get(metric)
                   for number in teams}
        split = apportioned(hub.get(source), weights)
        if split is None:
            return None
        result[field] = split[str(team)]
    return result


class FuelEstimateService:
    REFRESH_SECONDS = 300
    # Leave headroom for other uses of the same Match13 account.
    BUDGETS = ((60, 30), (3600, 600), (604800, 15000))

    def __init__(self, db, path, api_key="", tba_key="", clock=time.time, get=requests.get):
        self.db, self.path, self.api_key, self.tba_key = db, str(path), api_key, tba_key
        self.clock, self.get = clock, get
        self.wake = threading.Event()
        self.stopping = threading.Event()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, event TEXT NOT NULL, match TEXT NOT NULL,
                    identity TEXT NOT NULL, expected TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, applied INTEGER NOT NULL DEFAULT 0,
                    updated REAL NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events (event TEXT PRIMARY KEY, due REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS cache (
                    provider TEXT, path TEXT, body TEXT, etag TEXT, expires REAL,
                    PRIMARY KEY(provider, path));
                CREATE TABLE IF NOT EXISTS controls (name TEXT PRIMARY KEY, value REAL);
                CREATE TABLE IF NOT EXISTS calls (at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS calls_at ON calls(at);
                CREATE INDEX IF NOT EXISTS jobs_event ON jobs(event, active);
            """)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @contextmanager
    def transaction(self):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            yield con

    @staticmethod
    def control(con, name):
        row = con.execute("SELECT value FROM controls WHERE name=?", (name,)).fetchone()
        return row[0] if row else 0

    @staticmethod
    def set_control(con, name, value):
        con.execute("INSERT OR REPLACE INTO controls VALUES (?,?)", (name, value))

    def enroll(self, record_id, data):
        event = str(data.get("_event_key") or data.get("event_code") or "")
        key = match_key(event, str(data.get("match_number", "")))
        if not key or event.endswith(("test1", "test2", "test3")) or not ObjectId.is_valid(record_id):
            return False
        identity = {field: data[field] for field in ("event_code", "match_number", "alliance")}
        identity["team_number"] = int(data["team_number"])
        with self.transaction() as con:
            con.execute("INSERT OR IGNORE INTO jobs(id,event,match,identity,expected) VALUES (?,?,?,?,?)",
                        (record_id, event, key, json.dumps(identity), json.dumps(dict.fromkeys(FUEL_FIELDS, 0))))
            con.execute("INSERT OR REPLACE INTO events VALUES (?,0)", (event,))
        self.wake.set()
        return True

    def manual_update(self, record_id, update):
        # The writer transaction synchronizes with the background Mongo write:
        # a manual save always wins, including a deliberate zero.
        with self.transaction() as con:
            row = con.execute("SELECT active FROM jobs WHERE id=?", (record_id,)).fetchone()
            con.execute("UPDATE jobs SET active=0 WHERE id=?", (record_id,))
            # A failed older edit must not undo a newer successful manual save.
            ticket = self.control(con, "edit:" + record_id) + 1 if row else None
            if row:
                self.set_control(con, "edit:" + record_id, ticket)
        try:
            success = update()
        except Exception:
            self._restore(record_id, row, ticket)
            raise
        if not success:
            self._restore(record_id, row, ticket)
        return success

    def _restore(self, record_id, row, ticket):
        if row and row[0]:
            with self.transaction() as con:
                if self.control(con, "edit:" + record_id) == ticket:
                    con.execute("UPDATE jobs SET active=1 WHERE id=?", (record_id,))

    def statuses(self, ids, include_manual=False):
        ids = list(dict.fromkeys(map(str, ids)))
        if not ids:
            return {}
        rows = []
        with self.connect() as con:
            for offset in range(0, len(ids), 500):
                batch = ids[offset:offset + 500]
                rows.extend(con.execute("SELECT id,active,applied,updated FROM jobs WHERE "
                                        + ("" if include_manual else "active=1 AND ") + "id IN ("
                                        + ",".join("?" for _ in batch) + ")", batch).fetchall())
        return {row["id"]: {"active": bool(row["active"]), "estimated": bool(row["active"] and row["applied"]),
                            "label": "Scouted" if not row["active"] else "Estimated · Match13" if row["applied"] else "Waiting for fuel estimate",
                            "updated": row["updated"]} for row in rows}

    def _request(self, provider, path):
        now = self.clock()
        with self.connect() as con:
            row = con.execute("SELECT * FROM cache WHERE provider=? AND path=?", (provider, path)).fetchone()
        stale = json.loads(row["body"]) if row and row["body"] else None
        if row and row["expires"] > now:
            return stale
        with self.transaction() as con:
            if self.control(con, provider + "-pause") > now:
                return stale
            if provider == "m13":
                con.execute("DELETE FROM calls WHERE at<=?", (now - 604800,))
                for window, budget in self.BUDGETS:
                    count = con.execute("SELECT count(*) FROM calls WHERE at>?", (now - window,)).fetchone()[0]
                    if count >= budget:
                        return stale
                con.execute("INSERT INTO calls VALUES (?)", (now,))
        base = "https://actions.match13.com" if provider == "m13" else "https://www.thebluealliance.com/api/v3"
        headers = ({"Authorization": "Bearer " + self.api_key} if provider == "m13"
                   else {"X-TBA-Auth-Key": self.tba_key})
        headers["Accept"] = "application/json"
        if row and row["etag"]:
            headers["If-None-Match"] = row["etag"]
        body, etag, delay = stale, row["etag"] if row else None, 900
        try:
            with self.get(base + path, headers=headers, timeout=(3, 5), allow_redirects=False) as response:
                if provider == "m13":
                    self._quota_headers(response.headers, now)
                if response.status_code == 429:
                    delay = self._retry_after(response.headers.get("Retry-After"), now)
                    with self.transaction() as con:
                        self.set_control(con, provider + "-pause",
                                         max(now + delay, self.control(con, provider + "-pause")))
                elif response.status_code in (401, 403):
                    delay = 3600
                    with self.transaction() as con:
                        self.set_control(con, provider + "-pause", now + delay)
                elif response.status_code == 304 and stale is not None:
                    delay = self.REFRESH_SECONDS
                elif response.status_code == 200:
                    candidate = response.json()
                    if (provider == "m13" and isinstance(candidate, dict) and isinstance(candidate.get("teams"), list)
                            or provider == "tba" and isinstance(candidate, list)):
                        body, etag, delay = candidate, response.headers.get("ETag"), self.REFRESH_SECONDS
        except (requests.RequestException, ValueError):
            logger.warning("Fuel estimate provider temporarily unavailable: %s", provider)
        with self.transaction() as con:
            con.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?)",
                        (provider, path, json.dumps(body) if body is not None else None, etag, now + delay))
        return body

    @staticmethod
    def _retry_after(value, now):
        try:
            return max(60, int(value))
        except (TypeError, ValueError):
            try:
                return max(60, parsedate_to_datetime(value).timestamp() - now)
            except (TypeError, ValueError, AttributeError):
                return 900

    def _quota_headers(self, headers, now):
        try:
            remaining = [int(n.strip()) for n in headers.get("X-RateLimit-Remaining", "").split(",")]
            resets = [int(n.strip()) for n in headers.get("X-RateLimit-Reset", "").split(",")]
        except ValueError:
            return
        wait = max([reset for left, reset in zip(remaining, resets) if left <= 0] or [0])
        if wait:
            with self.transaction() as con:
                self.set_control(con, "m13-pause", max(now + wait, self.control(con, "m13-pause")))

    def tick(self):
        if not self.api_key or not self.tba_key:
            return
        now = self.clock()
        with self.transaction() as con:
            if self.control(con, "scheduler") > now:
                return
            events = con.execute("SELECT event FROM events WHERE due<=? ORDER BY due LIMIT 4", (now,)).fetchall()
            if not events:
                return
            # One scheduler across workers; ample lease for 4 events / 8 requests.
            self.set_control(con, "scheduler", now + 180)
            for row in events:
                con.execute("UPDATE events SET due=? WHERE event=?", (now + 300, row[0]))
        try:
            for row in events:
                self.refresh_event(row[0])
        finally:
            with self.transaction() as con:
                self.set_control(con, "scheduler", self.clock() + 60)

    def refresh_event(self, event):
        with self.connect() as con:
            jobs = con.execute("SELECT * FROM jobs WHERE event=? AND active=1", (event,)).fetchall()
        if not jobs:
            return
        rating_data = self._request("m13", f"/v1/events/{event}/teams")
        official = self._request("tba", f"/event/{event}/matches")
        if not isinstance(rating_data, dict) or rating_data.get("eventKey") != event or not isinstance(official, list):
            return
        ratings = {str(team.get("teamNumber")): team for team in rating_data.get("teams", [])}
        matches = {match.get("key"): match for match in official}
        for job in jobs:
            identity = json.loads(job["identity"])
            match = matches.get(job["match"])
            fuel = estimate_fuel(match, ratings, identity["alliance"], identity["team_number"]) if match else None
            if fuel is not None:
                self._apply(job["id"], fuel)
        completed = [match.get("actual_time") or 0 for match in official]
        if completed and min(completed) > 0 and max(completed) < self.clock() - 172800:
            # Completed events need only daily correction checks, not live polling.
            with self.transaction() as con:
                # Enrollment during a refresh sets due=0; preserve its prompt follow-up.
                con.execute("UPDATE events SET due=? WHERE event=? AND due>0", (self.clock() + 86400, event))
                for provider, path in [("m13", f"/v1/events/{event}/teams"), ("tba", f"/event/{event}/matches")]:
                    con.execute("UPDATE cache SET expires=? WHERE provider=? AND path=?",
                                (self.clock() + 86400, provider, path))

    def _apply(self, record_id, fuel):
        with self.transaction() as con:
            job = con.execute("SELECT * FROM jobs WHERE id=? AND active=1", (record_id,)).fetchone()
            if not job:
                return
            identity, expected = json.loads(job["identity"]), json.loads(job["expected"])
            query = {"_id": ObjectId(record_id), **identity, **expected}
            # Guard every fuel field, including ferried fuel. No new Mongo fields.
            result = self.db.team_data.update_one(query, {"$set": fuel})
            if not result.matched_count:
                con.execute("UPDATE jobs SET active=0 WHERE id=?", (record_id,))
                return
            expected.update(fuel)
            con.execute("UPDATE jobs SET expected=?,applied=1,updated=? WHERE id=?",
                        (json.dumps(expected), self.clock(), record_id))

    def start(self):
        if not self.api_key or not self.tba_key:
            return
        self.thread = threading.Thread(target=self._run, name="match13-fuel", daemon=True)
        self.thread.start()
        atexit.register(self.close)

    def _run(self):
        while not self.stopping.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("Fuel estimate refresh failed; scouting remains available")
            self.wake.wait(60)
            self.wake.clear()

    def close(self):
        self.stopping.set()
        self.wake.set()
