import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
import requests

logger = logging.getLogger(__name__)

class TBAInterface:
    def __init__(self):
        self.base_url = "https://www.thebluealliance.com/api/v3"
        self.api_key = os.getenv('TBA_AUTH_KEY')
        if not self.api_key:
            logger.warning("TBA_AUTH_KEY not found in environment variables")
        
        self.headers = {
            "X-TBA-Auth-Key": self.api_key,
            "accept": "application/json"
        }
        self.timeout = 5  # Reduced timeout

    @lru_cache(maxsize=100)
    def get_team(self, team_key):
        """Get team information from TBA"""
        try:
            response = requests.get(
                f"{self.base_url}/team/{team_key}",
                headers=self.headers,
                timeout=self.timeout
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching team from TBA: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_event_matches(self, event_key):
        """Get matches for an event and format them by match number"""
        try:
            response = requests.get(
                f"{self.base_url}/event/{event_key}/matches",
                headers=self.headers,
                timeout=self.timeout
            )
            if response.status_code != 200:
                return None

            matches = response.json()
            formatted_matches = {}

            for match in matches:
                if match_number := match.get('match_number'):
                    formatted_matches[match_number] = {
                        'red': match['alliances']['red']['team_keys'],
                        'blue': match['alliances']['blue']['team_keys']
                    }

            return formatted_matches
        except Exception as e:
            logger.error(f"Error fetching event matches from TBA: {e}")
            return None

    @lru_cache(maxsize=100)
    def get_current_events(self, year):
        """Get all events for the specified year"""
        try:
            response = requests.get(
                f"{self.base_url}/events/{year}/simple",
                headers=self.headers,
                timeout=self.timeout
            )
            if response.status_code != 200:
                return None

            events = response.json()
            
            # No date filtering - include all events
            # Convert to dictionary, maintaining alphabetical order
            current_events = {}
            
            # Sort events alphabetically by name
            events.sort(key=lambda x: x['name'])
            
            # Add all events
            for event in events:
                display_name = f"{event['name']}"
                current_events[display_name] = {
                    'key': event['key'],
                    'start_date': event['start_date']
                }

            return current_events
        except Exception as e:
            logger.error(f"Error fetching events from TBA: {e}")
            return None