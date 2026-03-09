import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)


class NexusInterface:
    """Interface for the FRC Nexus API (v1.5.0)"""

    BASE_URL = "https://frc.nexus/api/v1"

    # Cache: maps team_number (str) -> event_key (str), refreshed every 5 min
    _team_event_cache: dict[str, str] = {}
    _team_event_cache_built_at: float = 0.0
    _CACHE_TTL: float = 300.0  # seconds
    _events_cache: dict | None = None
    _events_cache_at: float = 0.0

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("NEXUS_API_KEY", "")
        if not self.api_key:
            logger.warning(
                "NEXUS_API_KEY not found in environment variables or provided as parameter"
            )
        else:
            logger.info("Initialized NexusInterface with API key")
        self.headers = {
            "Nexus-Api-Key": self.api_key,
            "Accept": "application/json",
        }
        self.timeout = 8
        

    def get_event_status(self, event_key: str) -> dict | None:
        """
        GET /event/{eventKey} 
            Live event status including matches, announcements, parts requests, and nowQueuing.

        Parameters:
            event_key: str - the event key (e.g. "2025tvr")

        Returns:
            dict with keys:
                - matches: list of match objects
                - announcements: list of announcement objects
                - partsRequests: list of parts request objects
                - nowQueuing: str or None
            or None if there was an error fetching the data. 
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/event/{event_key}",
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning("Nexus get_event_status %s returned %s", event_key, response.status_code)
            return None
        except Exception as e:
            logger.error("Error fetching Nexus event status for %s: %s", event_key, e)
            return None

    def get_pit_addresses(self, event_key: str) -> dict | None:
        """
        GET /event/{eventKey}/pits
            Fetch pit address mapping.
            
        Parameters:
            event_key: str - the event key (e.g. "2025tvr")

        Returns:
            dict mapping team numbers (as strings) to pit addresses, 
            or None if there was an error fetching the data.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/event/{event_key}/pits",
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning("Nexus get_pit_addresses %s returned %s", event_key, response.status_code)
            return None
        except Exception as e:
            logger.error("Error fetching Nexus pit addresses for %s: %s", event_key, e)
            return None

    def get_pit_map(self, event_key: str) -> dict | None:
        """
        GET /event/{eventKey}/map
            Fetch pit map

        Parameters:
            event_key: str - the event key (e.g. "2025tvr")
        
        Returns:
            dict representing the pit map, or None if there was an error fetching the data.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/event/{event_key}/map",
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning("Nexus get_pit_map %s returned %s", event_key, response.status_code)
            return None
        except Exception as e:
            logger.error("Error fetching Nexus pit map for %s: %s", event_key, e)
            return None

    def get_inspection_status(self, event_key: str) -> dict | None:
        """
        GET /event/{eventKey}/inspection
            Fetch the team inspection status

        Parameters:
            event_key: str - the event key (e.g. "2025tvr")

        Returns:
            dict mapping team numbers (as strings) to inspection status, 
            or None if there was an error fetching the data.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/event/{event_key}/inspection",
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning("Nexus get_inspection_status %s returned %s", event_key, response.status_code)
            return None
        except Exception as e:
            logger.error("Error fetching Nexus inspection status for %s: %s", event_key, e)
            return None

    def get_events(self) -> dict | None:
        """
        GET /events
            Fetch all events currently registered on Nexus.

        Returns:
            dict mapping event keys to event info dicts, or None if there was an error fetching the data. 
        """
        # Return cached copy if fresh (reuse same TTL as team cache)
        now = time.monotonic()
        if hasattr(NexusInterface, '_events_cache') and \
                now - NexusInterface._events_cache_at < NexusInterface._CACHE_TTL:
            return NexusInterface._events_cache

        try:
            response = requests.get(
                f"{self.BASE_URL}/events",
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                NexusInterface._events_cache = response.json()
                NexusInterface._events_cache_at = now
                return NexusInterface._events_cache
            logger.warning("Nexus get_events returned %s", response.status_code)
            return None
        except Exception as e:
            logger.error("Error fetching Nexus events: %s", e)
            return None

    def find_team_event(self, team_number: int | str) -> tuple[str, str] | None:
        """Find the current Nexus event key and name for a team.

        Fetches all event statuses in parallel so the scan completes in one
        round-trip worth of latency rather than N serial requests.
        Result is cached for _CACHE_TTL seconds.

        Returns (event_key, event_name) or None if not found.
        """
        team_number = str(team_number)
        now = time.monotonic()

        # Return from cache if still fresh
        if (now - NexusInterface._team_event_cache_built_at <= NexusInterface._CACHE_TTL
                and team_number in NexusInterface._team_event_cache):
            ekey = NexusInterface._team_event_cache[team_number]
            all_events = self.get_events() or {}
            ename = (all_events.get(ekey) or {}).get("name", ekey)
            return ekey, ename

        # Rebuild cache — fetch all event statuses in parallel
        if now - NexusInterface._team_event_cache_built_at > NexusInterface._CACHE_TTL:
            logger.info("Nexus: rebuilding team->event cache (parallel)")
            all_events = self.get_events() or {}
            new_cache: dict[str, str] = {}

            def _fetch(ekey: str):
                return ekey, self.get_event_status(ekey)

            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {pool.submit(_fetch, ekey): ekey for ekey in all_events}
                for fut in as_completed(futures):
                    ekey, ev_status = fut.result()
                    if not ev_status:
                        continue
                    for match in ev_status.get("matches", []):
                        for team in (match.get("redTeams") or []) + (match.get("blueTeams") or []):
                            if team is not None:
                                new_cache.setdefault(str(team), ekey)

            NexusInterface._team_event_cache = new_cache
            NexusInterface._team_event_cache_built_at = time.monotonic()
            logger.info("Nexus: cache built with %d teams", len(new_cache))

        ekey = NexusInterface._team_event_cache.get(team_number)
        if not ekey:
            return None

        all_events = self.get_events() or {}
        ename = (all_events.get(ekey) or {}).get("name", ekey)
        return ekey, ename

    def get_team_nexus_data(self, event_key: str, team_number: int | str) -> dict:
        """Aggregate Nexus data relevant to a specific team at an event.

        Parameters:
            - event_key: str - the event key (e.g. "2025tvr")
            - team_number: int or str - the team number (e.g. 334)

        Returns a dict with keys:
          - now_queuing: str | None
          - team_matches: list
          - announcements: list
          - parts_requests: list
          - pit_address: str | None
          - inspection: dict | None
        """
        team_number = str(team_number)
        result = {
            "now_queuing": None,
            "team_matches": [],
            "announcements": [],
            "parts_requests": [],
            "pit_address": None,
            "inspection": None,
            "nexus_available": False,
        }

        # Event status (matches, queue, announcements, parts requests)
        event_status = self.get_event_status(event_key)
        if event_status:
            result["nexus_available"] = True
            result["now_queuing"] = event_status.get("nowQueuing")
            result["announcements"] = event_status.get("announcements", [])
            result["parts_requests"] = event_status.get("partsRequests", [])

            # Filter matches for the requested team
            for match in event_status.get("matches", []):
                red_teams = [str(t) for t in (match.get("redTeams") or match.get("red", [])) if t is not None]
                blue_teams = [str(t) for t in (match.get("blueTeams") or match.get("blue", [])) if t is not None]
                if team_number in red_teams or team_number in blue_teams:
                    result["team_matches"].append(match)

        # Pit address
        pit_addresses = self.get_pit_addresses(event_key)
        if pit_addresses and team_number in pit_addresses:
            result["pit_address"] = pit_addresses[team_number]

        # Inspection status
        inspection = self.get_inspection_status(event_key)
        if inspection and team_number in inspection:
            result["inspection"] = inspection[team_number]

        return result

    def get_event_nexus_overview(self, event_key: str) -> dict:
        """Get a full Nexus overview for an event (for rendering the page).

        Parameters:
            - event_key: str - the event key (e.g. "2025tvr")

        Returns a dict with keys:
          - event_status: full event status or None
          - pit_addresses: dict or None
          - pit_map: dict or None
          - inspection: dict or None
          - nexus_available: bool
        """
        event_status = self.get_event_status(event_key)
        return {
            "event_status": event_status,
            "pit_addresses": self.get_pit_addresses(event_key),
            "pit_map": self.get_pit_map(event_key),
            "inspection": self.get_inspection_status(event_key),
            "nexus_available": event_status is not None,
        }
