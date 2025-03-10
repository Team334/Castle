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
        """Get events for the current and previous week, sorted by proximity to today"""
        try:
            response = requests.get(
                f"{self.base_url}/events/{year}/simple",
                headers=self.headers,
                timeout=self.timeout
            )
            if response.status_code != 200:
                return None

            events = response.json()
            current_date = datetime.now().date()
            current_week_start = current_date - timedelta(days=current_date.weekday())
            last_week_start = current_week_start - timedelta(days=7)

            # Create separate lists for today, yesterday, and other days
            today_events = []
            yesterday_events = []
            other_events = []

            for event in events:
                event_start = datetime.strptime(event['start_date'], '%Y-%m-%d').date()
                if last_week_start <= event_start <= current_date:
                    days_difference = abs((current_date - event_start).days)
                    if days_difference == 0:
                        today_events.append(event)
                    elif days_difference == 1:
                        yesterday_events.append(event)
                    else:
                        other_events.append((days_difference, event))

            # Sort other events by days difference
            other_events.sort(key=lambda x: x[0])

            # Convert to dictionary with time indicators, maintaining priority order
            current_events = {}
            
            # Add today's events first
            for event in today_events:
                display_name = f"{event['name']} (Today)"
                current_events[display_name] = {
                    'key': event['key'],
                    'start_date': event['start_date']
                }

            # Add yesterday's events second
            for event in yesterday_events:
                display_name = f"{event['name']} (Yesterday)"
                current_events[display_name] = {
                    'key': event['key'],
                    'start_date': event['start_date']
                }

            # Add other events last, sorted by days ago
            for days_diff, event in other_events:
                display_name = f"{event['name']}"
                current_events[display_name] = {
                    'key': event['key'],
                    'start_date': event['start_date']
                }

            return current_events
        except Exception as e:
            logger.error(f"Error fetching events from TBA: {e}")
            return None