"""Return cached metric snapshots immediately; schedule missing public data."""
import re
import math

from .TBA import STATBOTICS_URL, TBAInterface, get_team_epa
from .api_cache import public_api_cache

METRICS = ('epa', 'opr', 'dpr', 'ccwm')


def team_stats_snapshot(teams, year):
    tba = TBAInterface()
    needs_names = any(item.get('event_code') not in (None, '', 'all') and
                      not re.fullmatch(r'\d{4}[a-z0-9]+', item['event_code'])
                      for item in teams)
    names = (tba.get_current_events(year, include_test_data=True,
                                   background=True) or {}) if needs_names else {}
    results = {}
    for item in teams:
        number = int(item['team_number'])
        team_key = f'frc{number}'
        event = item.get('event_code')
        key = f'{number}_{event}' if event else str(number)
        if key in results:
            continue
        values = {metric: None for metric in METRICS}
        values['epa'] = get_team_epa(number, year, background=True)
        pending = public_api_cache.pending(
            f'{STATBOTICS_URL}/team_year/{number}/{year}')
        if event in (None, '', 'all'):
            events = tba.get_team_events(team_key, year, background=True)
            pending |= tba.pending(f'/team/{team_key}/events/{year}/simple')
            event_keys = [ev['key'] for ev in events or [] if ev.get('key')]
        else:
            event_key = (names.get(event) or {}).get('key')
            if not event_key and re.fullmatch(r'\d{4}[a-z0-9]+', event):
                event_key = event
            event_keys = [event_key] if event_key else []
            if not event_key:
                pending |= tba.pending(f'/events/{year}/simple')
        collected = {metric: [] for metric in METRICS[1:]}
        for event_key in event_keys:
            stats = tba.get_event_oprs(event_key, background=True)
            pending |= tba.pending(f'/event/{event_key}/oprs')
            for metric in collected:
                metric_values = stats.get(f'{metric}s') if isinstance(stats, dict) else None
                value = metric_values.get(team_key) if isinstance(metric_values, dict) else None
                if isinstance(value, (int, float)) and math.isfinite(value):
                    collected[metric].append(value)
        for metric, samples in collected.items():
            if samples:
                values[metric] = sum(samples) / len(samples)
        values['pending'] = pending
        results[key] = values
    return results
