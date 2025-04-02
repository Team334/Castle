import logging
import os
from datetime import datetime
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
                comp_level = match.get('comp_level', 'qm')
                set_number = match.get('set_number', None)
                if match_number := match.get('match_number'):
                    if comp_level == 'qm':
                        match_key = f"Qual {match_number}"
                    elif comp_level == 'sf':
                        match_key = f"Semifinal {set_number}"
                    elif comp_level == 'f':
                        match_key = f"Final {set_number}"
                    else:
                        match_key = f"{comp_level}{match_number}"

                    formatted_matches[match_key] = {
                        'red': match['alliances']['red']['team_keys'],
                        'blue': match['alliances']['blue']['team_keys'],
                        'comp_level': comp_level,
                        'match_number': match_number,
                        'set_number': match.get('set_number', None)
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
            
    @lru_cache(maxsize=100)
    def get_team_status_at_event(self, team_key, event_key):
        """Get team status and ranking at a specific event"""
        try:
            response = requests.get(
                f"{self.base_url}/team/{team_key}/event/{event_key}/status",
                headers=self.headers,
                timeout=self.timeout
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"Error fetching team status from TBA: {e}")
            return None
            
    @lru_cache(maxsize=100)
    def get_team_matches_at_event(self, team_key, event_key):
        """Get a team's matches at a specific event with previous and upcoming separation"""
        try:
            response = requests.get(
                f"{self.base_url}/team/{team_key}/event/{event_key}/matches",
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return None
                
            matches = response.json()
            current_time = datetime.now().timestamp()
            
            previous_matches = []
            upcoming_matches = []
            
            for match in matches:
                # Get match details
                comp_level = match.get('comp_level', 'qm')
                match_number = match.get('match_number')
                set_number = match.get('set_number')
                
                # Format match name
                if comp_level == 'qm':
                    match_name = f"Qualification {match_number}"
                elif comp_level == 'sf':
                    match_name = f"Semifinal {set_number}-{match_number}"
                elif comp_level == 'f':
                    match_name = f"Final {match_number}"
                else:
                    match_name = f"{comp_level.upper()} {match_number}"
                
                # Determine alliance
                alliance = None
                for color in ['red', 'blue']:
                    if team_key in match['alliances'][color]['team_keys']:
                        alliance = color
                        break
                
                match_info = {
                    'match_name': match_name,
                    'time': match.get('predicted_time') or match.get('time', 0) or 0,
                    'alliance': alliance,
                    'score': None if match.get('score_breakdown') is None else {
                        'red': match['alliances']['red']['score'],
                        'blue': match['alliances']['blue']['score']
                    }
                }
                
                # Sort into previous or upcoming
                actual_time = match.get('actual_time')
                if (actual_time is not None and actual_time > 0) or match_info['time'] < current_time:
                    previous_matches.append(match_info)
                else:
                    upcoming_matches.append(match_info)
            
            # Sort matches by time
            previous_matches.sort(key=lambda m: m['time'])
            upcoming_matches.sort(key=lambda m: m['time'])
            
            return {
                'previous': previous_matches,
                'upcoming': upcoming_matches
            }
            
        except Exception as e:
            logger.error(f"Error fetching team matches from TBA: {e}")
            return None
            
    @lru_cache(maxsize=100)
    def get_team_events(self, team_key, year=None):
        """Get all events a team is participating in for the given year"""
        if year is None:
            year = datetime.now().year
            
        try:
            response = requests.get(
                f"{self.base_url}/team/{team_key}/events/{year}/simple",
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return None
                
            events = response.json()
            # Sort by start date, most recent first
            events.sort(key=lambda e: e.get('start_date', ''), reverse=True)
            
            return events
        except Exception as e:
            logger.error(f"Error fetching team events from TBA: {e}")
            return None
            
    def get_most_recent_active_event(self, team_key):
        """Find the most recent event that a team is participating in"""
        year = datetime.now().year
        events = self.get_team_events(team_key, year)
        
        if not events:
            return None
            
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # First try to find events happening now
        for event in events:
            start_date = event.get('start_date')
            end_date = event.get('end_date')
            
            if start_date and end_date and start_date <= current_date <= end_date:
                return event
                
        # If no current events, get the most recent event (events are already sorted by date, most recent first)
        return events[0]