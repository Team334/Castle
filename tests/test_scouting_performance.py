"""Offline regression tests: no database or real API calls are used."""
import threading
import time
import unittest
from unittest.mock import patch

import requests
from flask import Flask

from app.scout import TBA as tba_module
from app.scout import team_stats
from app.scout.api_cache import PublicAPICache
from app.scout.routes import get_team_epa_opr, get_tba_matches


class Response:
    def __init__(self, data=None, status=200):
        self.data = data if data is not None else {}
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self.data


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = PublicAPICache(workers=2, max_pending=3)

    def tearDown(self):
        self.cache.close()

    def drain(self):
        with self.cache.lock:
            futures = [entry.future for entry in self.cache.entries.values() if entry.future]
        for future in futures:
            future.result(timeout=2)

    def test_identical_calls_share_refresh_and_requests_have_timeout(self):
        gate = threading.Event()
        with patch('requests.Session.get', side_effect=lambda *a, **k:
                   (gate.wait(2), Response({'value': 7}))[1]) as get:
            try:
                start = time.monotonic()
                for _ in range(100):
                    self.assertIsNone(self.cache.get('https://api.example/team/334', background=True))
                self.assertLess(time.monotonic() - start, .2)
                self.assertEqual(self.cache.pending_count, 1)
            finally:
                gate.set()
            self.drain()
            self.assertEqual(self.cache.get('https://api.example/team/334'), {'value': 7})
            self.assertEqual(get.call_count, 1)
            self.assertEqual(get.call_args.kwargs['timeout'], (2, 3))

    def test_outage_preserves_stale_data_and_recovers_after_cooldown(self):
        now = [0]
        self.cache.clock = lambda: now[0]
        url = 'https://api.example/team/334'
        with patch('requests.Session.get', side_effect=[
                Response({'value': 7}), Response(status=503), Response({'value': 9})]) as get:
            self.assertEqual(self.cache.get(url, ttl=1), {'value': 7})
            now[0] = 2
            self.assertEqual(self.cache.get(url, ttl=1), {'value': 7})
            self.drain()
            for i in range(20):
                self.cache.get(f'https://api.example/team/{i}', background=True)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(self.cache.get(url), {'value': 7})
            now[0] = 63
            self.cache.get(url, background=True)
            self.drain()
            self.assertEqual(self.cache.get(url), {'value': 9})

    def test_pending_queue_is_bounded_and_later_polls_can_schedule(self):
        gate = threading.Event()
        with patch('requests.Session.get', side_effect=lambda *a, **k:
                   (gate.wait(2), Response())[1]) as get:
            try:
                for i in range(20):
                    self.cache.get(f'https://api.example/{i}', background=True)
                self.assertEqual(self.cache.pending_count, 3)
                self.assertTrue(self.cache.pending('https://api.example/19'))
            finally:
                gate.set()
            self.drain()
            self.cache.get('https://api.example/19')
            self.assertEqual(get.call_count, 4)

    def test_cache_capacity_and_negative_404_cache(self):
        self.cache.capacity = 2
        with patch('requests.Session.get', return_value=Response(status=404)) as get:
            self.cache.get('https://api.example/1')
            self.cache.get('https://api.example/1')
            self.assertEqual(get.call_count, 1)
            self.assertFalse(self.cache.pending('https://api.example/1'))
            self.cache.get('https://api.example/2')
            self.cache.get('https://api.example/3')
            self.assertEqual(len(self.cache.entries), 2)
            self.assertEqual(get.call_count, 3)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.cache = PublicAPICache(workers=2)
        self.patches = [patch.object(tba_module, 'public_api_cache', self.cache),
                        patch.object(team_stats, 'public_api_cache', self.cache),
                        patch.dict('os.environ', {'TBA_AUTH_KEY': 'test-key'})]
        for item in self.patches:
            item.start()
        self.app = Flask(__name__)
        self.app.config['LOGIN_DISABLED'] = True
        self.app.add_url_rule('/api/team_epa_opr', view_func=get_team_epa_opr, methods=['POST'])
        self.app.add_url_rule('/api/tba/matches/<event_key>', view_func=get_tba_matches)
        self.app.add_url_rule('/', view_func=lambda: 'healthy')

    def tearDown(self):
        self.cache.close()
        for item in reversed(self.patches):
            item.stop()

    def drain(self):
        with self.cache.lock:
            futures = [entry.future for entry in self.cache.entries.values() if entry.future]
        for future in futures:
            future.result(timeout=2)

    def test_two_metric_requests_and_navigation_do_not_wait_for_upstream(self):
        gate = threading.Event()
        pairs = [{'team_number': 334, 'event_code': '2026nyny'}] * 602
        with patch('requests.Session.get', side_effect=lambda *a, **k:
                   (gate.wait(2), Response(status=503))[1]):
            try:
                with self.app.test_client() as client:
                    start = time.monotonic()
                    for _ in range(2):
                        result = client.post('/api/team_epa_opr', json={'teams': pairs, 'year': 2026})
                        self.assertEqual(result.status_code, 200)
                        self.assertTrue(result.json['334_2026nyny']['pending'])
                    self.assertEqual(client.get('/').data, b'healthy')
                    self.assertLess(time.monotonic() - start, .5)
                    self.assertEqual(self.cache.pending_count, 2)
            finally:
                gate.set()
            self.drain()
            with self.app.test_client() as client:
                data = client.post('/api/team_epa_opr', json={'teams': pairs, 'year': 2026}).json
                self.assertFalse(data['334_2026nyny']['pending'])
                self.assertIsNone(data['334_2026nyny']['epa'])

    def test_event_names_resolve_and_real_zero_and_negative_values_survive(self):
        def response(url, **kwargs):
            if '/team_year/' in url:
                return Response({'epa': {'total_points': {'mean': 0.0}}})
            if '/events/' in url:
                return Response([{'name': 'NYC Regional', 'key': '2026nyny', 'start_date': '2026-04-01'}])
            return Response({'oprs': {'frc334': 0}, 'dprs': {'frc334': 2}, 'ccwms': {'frc334': -2}})
        pairs = [{'team_number': 334, 'event_code': 'NYC Regional'}]
        with patch('requests.Session.get', side_effect=response) as get:
            team_stats.team_stats_snapshot(pairs, 2026)
            self.drain()
            team_stats.team_stats_snapshot(pairs, 2026)
            self.drain()
            data = team_stats.team_stats_snapshot(pairs * 20, 2026)['334_NYC Regional']
            self.assertEqual(data, {'epa': 0.0, 'opr': 0, 'dpr': 2, 'ccwm': -2, 'pending': False})
            self.assertEqual(get.call_count, 3)
            # A fresh interface must reuse the same events cache.
            self.assertIn('NYC Regional', tba_module.TBAInterface().get_current_events(2026))
            self.assertEqual(get.call_count, 3)

    def test_match_requests_do_not_occupy_request_threads_during_outage(self):
        gate = threading.Event()
        with patch('requests.Session.get', side_effect=lambda *a, **k:
                   (gate.wait(2), Response(status=503))[1]) as get:
            try:
                with self.app.test_client() as client:
                    start = time.monotonic()
                    for _ in range(30):
                        result = client.get('/api/tba/matches/2026nyny')
                        self.assertEqual(result.status_code, 200)
                        self.assertIsNone(result.json)
                        self.assertEqual(result.headers['X-Scouting-Pending'], 'true')
                    self.assertEqual(client.get('/').data, b'healthy')
                    self.assertLess(time.monotonic() - start, .5)
            finally:
                gate.set()
            self.drain()
            self.assertEqual(get.call_count, 1)
            with self.app.test_client() as client:
                result = client.get('/api/tba/matches/2026nyny')
                self.assertEqual(result.headers['X-Scouting-Pending'], 'false')
                self.assertIsNone(result.json)

    def test_all_events_average_excludes_missing_values(self):
        def response(url, **kwargs):
            if '/team_year/' in url:
                return Response({'epa': {'total_points': {'mean': 4}}})
            if '/events/' in url:
                return Response([{'key': '2026one'}, {'key': '2026two'}])
            return Response({'oprs': {'frc334': 0 if 'one' in url else 10},
                             'ccwms': {'frc334': -5}})
        pairs = [{'team_number': 334, 'event_code': 'all'}]
        with patch('requests.Session.get', side_effect=response):
            team_stats.team_stats_snapshot(pairs, 2026)
            self.drain()
            team_stats.team_stats_snapshot(pairs, 2026)
            self.drain()
            result = team_stats.team_stats_snapshot(pairs, 2026)['334_all']
            self.assertEqual(result['opr'], 5)
            self.assertEqual(result['ccwm'], -5)
            self.assertIsNone(result['dpr'])

    def test_testing_events_work_without_api_key(self):
        with patch.dict('os.environ', {'TBA_AUTH_KEY': ''}), patch('requests.Session.get') as get:
            events = tba_module.TBAInterface().get_current_events(2026, include_test_data=True)
            self.assertEqual(len(events), 3)
            self.assertEqual(tba_module.TBAInterface().get_event_oprs('2026test1'),
                             {'oprs': {}, 'dprs': {}, 'ccwms': {}})
            get.assert_not_called()

    def test_malformed_upstream_metrics_are_unavailable_without_crashing(self):
        pairs = [{'team_number': 334, 'event_code': '2026nyny'}]
        with patch('requests.Session.get', return_value=Response(
                {'epa': {'total_points': None}, 'oprs': None, 'dprs': [],
                 'ccwms': {'frc334': float('nan')}})):
            team_stats.team_stats_snapshot(pairs, 2026)
            self.drain()
            result = team_stats.team_stats_snapshot(pairs, 2026)['334_2026nyny']
            self.assertFalse(result['pending'])
            self.assertTrue(all(result[metric] is None for metric in team_stats.METRICS))

    def test_playoff_matches_do_not_overwrite_each_other(self):
        matches = [{'comp_level': level, 'set_number': 1, 'match_number': number,
                    'alliances': {'red': {'team_keys': ['frc334']},
                                  'blue': {'team_keys': ['frc333']}}}
                   for level in ('sf', 'f') for number in (1, 2)]
        with patch('requests.Session.get', return_value=Response(matches)):
            formatted = tba_module.TBAInterface().get_event_matches('2026nyny')
            self.assertEqual(set(formatted), {'Semifinal 1-1', 'Semifinal 1-2',
                                             'Final 1', 'Final 2'})

    def test_invalid_payloads_return_400(self):
        with self.app.test_client() as client:
            for payload in ([], {'teams': 'wrong'}, {'year': 'invalid'},
                            {'teams': [{'team_number': 'bad'}]},
                            {'teams': [{'team_number': 334, 'event_code': {}}]}):
                self.assertEqual(client.post('/api/team_epa_opr', json=payload).status_code, 400)


if __name__ == '__main__':
    unittest.main()
