"""No real API calls or MongoDB connections; writes use an in-memory fake."""
import copy
from datetime import datetime, timezone
import json
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId
from flask import Flask
import requests

from app.scout.routes import common, records
from app.scout.match13_fuel import (FUEL_FIELDS, PHASES, FuelEstimateService,
                                   apportioned, zero_scored_fuel, estimate_fuel, match_key)


class Response:
    def __init__(self, body=None, status=200, headers=None):
        self.body, self.status_code, self.headers = body, status, headers or {}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def json(self):
        return self.body


class Collection:
    def __init__(self):
        self.records = {}
        self.writes = []
    def find_one(self, query):
        record = self.records.get(str(query['_id']))
        return copy.deepcopy(record) if record else None
    def find(self, query, projection):
        selected = [copy.deepcopy(record) for record in self.records.values()
                    if all(record.get(field) in clause[field]['$in']
                           for clause in query.get('$and', []) for field in clause)
                    and ('_id' not in query or record['_id'] > query['_id']['$gt'])]
        class Cursor:
            def sort(self, field, direction):
                selected.sort(key=lambda item: item[field])
                return self
            def limit(self, count):
                return selected[:count]
        return Cursor()
    def update_one(self, query, update):
        self.writes.append((query, update))
        record = self.records.get(str(query['_id']))
        matched = bool(record and all(record.get(k) == v for k, v in query.items()))
        if matched:
            record.update(update['$set'])
        return SimpleNamespace(matched_count=int(matched))


def fixtures():
    ratings = {'eventKey': '2026nyn2', 'teams': [
        {'teamNumber': n, 'xAuto': w, 'xTele': w} for n, w in [(334, 1), (1880, 2), (8267, 3)]]}
    match = {'key': '2026nyn2_qm4', 'actual_time': 10000,
             'alliances': {'blue': {'team_keys': ['frc334', 'frc1880', 'frc8267'], 'score': 82}},
             'score_breakdown': {'blue': {'hubScore': dict(zip(PHASES.values(), [12, 6, 0, 18, 0, 24, 12]))}}}
    return ratings, match


class EstimatorTests(unittest.TestCase):
    def test_only_nonzero_scored_counts_block_estimates(self):
        self.assertTrue(zero_scored_fuel({}))
        for field in PHASES:
            for value in ('', None, '0', 0, 0.0, '0.0'):
                self.assertTrue(zero_scored_fuel({field: value, 'ferried_fuel': 90}))
            for value in ('1', 1, -1, 'invalid'):
                self.assertFalse(zero_scored_fuel({field: value}))
        self.assertTrue(zero_scored_fuel({'_fuel_entered': 'true', 'ferried_fuel': 12}))

    def test_match_identity_includes_distinct_finals_and_semifinals(self):
        self.assertEqual(match_key('2026nyn2', 'Qual 4'), '2026nyn2_qm4')
        self.assertEqual(match_key('2026nyn2', 'Semifinal 2-1'), '2026nyn2_sf2m1')
        self.assertEqual(match_key('2026nyn2', 'Final 2'), '2026nyn2_f1m2')
        self.assertIsNone(match_key('../bad', 'Qual 4'))

    def test_rounding_preserves_official_totals_and_missing_ratings_are_not_invented(self):
        split = apportioned(11, {'334': 1, '1880': 1, '8267': 1})
        self.assertEqual(sum(split.values()), 11)
        self.assertEqual(split['334'], 4)
        self.assertIsNone(apportioned(11, {'334': None}))
        self.assertIsNone(apportioned(11, {'334': -1}))
        self.assertEqual(apportioned(0, {'334': -1}), {'334': 0})

    def test_phase_allocation_never_copies_end_rating_into_endgame_fuel(self):
        ratings, match = fixtures()
        weights = {str(r['teamNumber']): r for r in ratings['teams']}
        weights['334']['xEnd'] = 9999
        totals = []
        for number in weights:
            fuel = estimate_fuel(match, weights, 'blue', number)
            self.assertEqual(fuel['endgame_fuel'], int(number == '334') * 2 + int(number == '1880') * 4 + int(number == '8267') * 6)
            self.assertNotIn('ferried_fuel', fuel)
            totals.append(fuel)
        for field, source in PHASES.items():
            self.assertEqual(sum(f[field] for f in totals), match['score_breakdown']['blue']['hubScore'][source])
        match['alliances']['blue']['score'] = -1
        self.assertIsNone(estimate_fuel(match, weights, 'blue', '334'))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'state.sqlite'
        self.collection = Collection()
        self.db = SimpleNamespace(team_data=self.collection)
        self.now = [10000.]
        self.ratings, self.match = fixtures()
        self.network = MagicMock(side_effect=lambda url, **kw: Response(
            self.ratings if 'match13' in url else [{'key': '2026nyn2', 'name': 'Gotham Regional'}]
            if '/events/2026/simple' in url else [self.match], headers={'ETag': 'test-etag'}))
        self.service = FuelEstimateService(self.db, self.path, 'test-key', 'test-tba', clock=lambda: self.now[0], get=self.network)
        self.id = str(ObjectId())
        self.data = {'_event_key': '2026nyn2', 'event_code': 'Gotham Regional', 'match_number': 'Qual 4', 'team_number': 334, 'alliance': 'blue'}
        self.collection.records[self.id] = {'_id': ObjectId(self.id), **{k: v for k, v in self.data.items() if not k.startswith('_')}, **dict.fromkeys(FUEL_FIELDS, 0)}

    def tearDown(self):
        self.directory.cleanup()

    def test_existing_zero_records_backfill_and_later_ratings_recalculate(self):
        old_id = str(ObjectId())
        self.collection.records[old_id] = copy.deepcopy(self.collection.records[self.id])
        self.collection.records[old_id]['_id'] = ObjectId(old_id)
        self.collection.records[old_id]['ferried_fuel'] = 37
        protected_id = str(ObjectId())
        protected = {**copy.deepcopy(self.collection.records[old_id]), '_id': ObjectId(protected_id), 'auto_fuel': 9}
        self.collection.records[protected_id] = copy.deepcopy(protected)
        self.service.enroll(self.id, self.data)
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 2)
        self.assertEqual(self.collection.records[old_id]['auto_fuel'], 2)
        self.assertEqual(self.collection.records[old_id]['ferried_fuel'], 37)
        self.assertEqual(self.collection.records[protected_id], protected)
        self.assertTrue(self.service.statuses([self.id])[self.id]['estimated'])
        self.assertEqual(set(self.collection.writes[0][1]['$set']), set(PHASES))
        self.ratings['teams'][0]['xAuto'] = 3
        self.now[0] += 301
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 5)
        self.assertEqual(self.collection.records[old_id]['auto_fuel'], 5)
        self.assertEqual(self.collection.records[protected_id], protected)

    def test_cache_scheduler_and_enrollment_survive_new_worker_and_restart(self):
        self.service.enroll(self.id, self.data)
        self.service.tick()
        other = FuelEstimateService(self.db, self.path, 'test-key', 'test-tba', clock=lambda: self.now[0], get=self.network)
        other.tick()
        self.assertEqual(self.network.call_count, 2)
        self.assertTrue(other.statuses([self.id])[self.id]['estimated'])
        self.now[0] += 60
        other.refresh_event('2026nyn2')
        self.assertEqual(self.network.call_count, 2)

    def test_concurrent_workers_fetch_an_event_only_once(self):
        self.service.enroll(self.id, self.data)
        other = FuelEstimateService(self.db, self.path, 'test-key', 'test-tba', clock=lambda: self.now[0], get=self.network)
        barrier = threading.Barrier(2)
        def run(service):
            barrier.wait(timeout=5)
            service.tick()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(run, self.service), pool.submit(run, other)
            first.result(timeout=5)
            second.result(timeout=5)
        self.assertEqual(self.network.call_count, 2)
        self.assertTrue(self.service.statuses([self.id])[self.id]['estimated'])

    def test_manual_save_wins_when_background_write_is_already_running(self):
        self.service.enroll(self.id, self.data)
        writing, release, manual_started = threading.Event(), threading.Event(), threading.Event()
        original = self.collection.update_one
        def delayed_write(query, update):
            writing.set()
            if not release.wait(timeout=5):
                raise TimeoutError('Test did not release background write')
            return original(query, update)
        self.collection.update_one = delayed_write
        def manual():
            manual_started.set()
            def save():
                self.collection.records[self.id].update(dict.fromkeys(FUEL_FIELDS, 0))
                self.collection.records[self.id]['auto_fuel'] = 9
                return True
            return self.service.manual_update(self.id, save, {'auto_fuel': '9'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            background = pool.submit(self.service.tick)
            try:
                self.assertTrue(writing.wait(timeout=5))
                edited = pool.submit(manual)
                self.assertTrue(manual_started.wait(timeout=5))
            finally:
                release.set()
            background.result(timeout=5)
            self.assertTrue(edited.result(timeout=5))
        self.service.refresh_event('2026nyn2')
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 9)
        self.assertFalse(self.service.statuses([self.id]))

    def test_idle_scheduler_and_finished_event_allow_new_enrollment_without_new_calls(self):
        record = self.collection.records.pop(self.id)
        self.service.tick()
        self.assertEqual(self.network.call_count, 0)
        self.collection.records[self.id] = record
        self.now[0] = 200000
        self.service.enroll(self.id, self.data)
        self.service.tick()
        with self.service.connect() as con:
            self.assertEqual(con.execute('SELECT due FROM events').fetchone()[0], self.now[0] + 86400)
        new_id = str(ObjectId())
        self.collection.records[new_id] = {**self.collection.records[self.id], '_id': ObjectId(new_id), **dict.fromkeys(FUEL_FIELDS, 0)}
        self.service.enroll(new_id, self.data)
        self.now[0] += 60
        self.service.tick()
        self.assertTrue(self.service.statuses([new_id])[new_id]['estimated'])
        self.assertEqual(self.network.call_count, 2)

    def test_manual_nonzero_save_wins_and_failed_save_keeps_automatic_updates(self):
        self.service.enroll(self.id, self.data)
        self.service.tick()
        self.assertFalse(self.service.manual_update(self.id, lambda: False))
        self.assertIn(self.id, self.service.statuses([self.id]))
        def save():
            self.collection.records[self.id].update(dict.fromkeys(FUEL_FIELDS, 0))
            self.collection.records[self.id]['auto_fuel'] = 9
            return True
        self.service.manual_update(self.id, save, {'auto_fuel': '9'})
        self.service.refresh_event('2026nyn2')
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 9)
        self.assertNotIn(self.id, self.service.statuses([self.id]))

    def test_external_ferry_edit_does_not_block_estimates_or_get_overwritten(self):
        self.service.enroll(self.id, self.data)
        self.collection.records[self.id]['ferried_fuel'] = 10
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['ferried_fuel'], 10)
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 2)
        self.assertTrue(self.service.statuses([self.id])[self.id]['estimated'])

    def test_failed_older_edit_cannot_reactivate_after_a_newer_manual_nonzero_save(self):
        self.service.enroll(self.id, self.data)
        def newer_save():
            self.collection.records[self.id].update(dict.fromkeys(FUEL_FIELDS, 0))
            self.collection.records[self.id]['auto_fuel'] = 9
            return True
        def failed_older_save():
            self.service.manual_update(self.id, newer_save, {'auto_fuel': '9'})
            return False
        self.assertFalse(self.service.manual_update(self.id, failed_older_save))
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 9)
        self.assertFalse(self.service.statuses([self.id]))

    def test_ferry_only_edit_keeps_estimate_updates_and_zero_edit_reenrolls(self):
        self.service.enroll(self.id, self.data)
        self.service.tick()
        def ferry_save():
            self.collection.records[self.id]['ferried_fuel'] = 56
            return True
        self.service.manual_update(self.id, ferry_save, {'ferried_fuel': '56'})
        self.ratings['teams'][0]['xAuto'] = 3
        self.now[0] += 301
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 5)
        self.assertEqual(self.collection.records[self.id]['ferried_fuel'], 56)
        def zero_save():
            self.collection.records[self.id].update(dict.fromkeys(PHASES, 0))
            return True
        self.service.manual_update(self.id, zero_save, dict.fromkeys(PHASES, '0'))
        self.service.refresh_event('2026nyn2')
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 5)
        self.assertEqual(self.collection.records[self.id]['ferried_fuel'], 56)

    def test_old_ferry_guards_migrate_without_blocking_estimates(self):
        self.service.enroll(self.id, self.data)
        with self.service.transaction() as con:
            con.execute('UPDATE jobs SET expected=?', (json.dumps(dict.fromkeys(FUEL_FIELDS, 0)),))
        self.collection.records[self.id]['ferried_fuel'] = 14
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 2)
        self.assertEqual(self.collection.records[self.id]['ferried_fuel'], 14)

    def test_external_nonzero_scoring_is_protected(self):
        self.service.enroll(self.id, self.data)
        self.collection.records[self.id]['teleop_shift_2_fuel'] = 7
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 0)
        self.assertEqual(self.collection.records[self.id]['teleop_shift_2_fuel'], 7)
        self.assertFalse(self.service.statuses([self.id]))

    def test_backfill_resumes_on_another_instance_with_no_laptop_state(self):
        self.service.DISCOVERY_BATCH = 1
        second_id = str(ObjectId())
        self.collection.records[second_id] = {**self.collection.records[self.id], '_id': ObjectId(second_id), 'ferried_fuel': 22}
        # No enroll call, event key, or state copied from another installation.
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 2)
        self.assertEqual(self.collection.records[second_id]['auto_fuel'], 0)
        other = FuelEstimateService(self.db, self.path, 'key', 'tba', clock=lambda: self.now[0], get=self.network)
        other.DISCOVERY_BATCH = 1
        self.now[0] += 60
        other.tick()
        self.assertEqual(self.collection.records[second_id]['auto_fuel'], 2)
        self.assertEqual(self.collection.records[second_id]['ferried_fuel'], 22)
        self.assertEqual(self.network.call_count, 3)  # Catalog + one ratings/matches pair.
        self.now[0] += 60
        other.tick()
        self.assertEqual(self.network.call_count, 3)

    def test_legacy_missing_and_string_zero_fields_and_inactive_jobs_backfill(self):
        self.service.enroll(self.id, self.data)
        with self.service.transaction() as con:
            con.execute('UPDATE jobs SET active=0')
        record = self.collection.records[self.id]
        record.pop('endgame_fuel')
        record['auto_fuel'] = '0'
        record['transition_fuel'] = None
        record['ferried_fuel'] = 83
        self.service.tick()
        self.assertEqual(record['auto_fuel'], 2)
        self.assertEqual(record['endgame_fuel'], 2)
        self.assertEqual(record['ferried_fuel'], 83)

    def test_catalog_failure_retries_without_losing_backfill_cursor(self):
        self.network.side_effect = lambda url, **kw: Response(status=503)
        self.service.tick()
        self.assertFalse(self.service.statuses([self.id]))
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 0)
        with self.service.connect() as con:
            row = con.execute('SELECT cursor,due FROM discovery').fetchone()
            self.assertIsNone(row['cursor'])
            self.assertEqual(row['due'], self.now[0] + 900)

    def test_ambiguous_event_names_are_not_guessed(self):
        self.network.side_effect = lambda url, **kw: Response([
            {'key': '2026nyn2', 'name': 'Gotham Regional'},
            {'key': '2026other', 'name': 'Gotham Regional'}])
        self.service.tick()
        self.assertEqual(self.network.call_count, 1)
        self.assertFalse(self.service.statuses([self.id]))

    def test_older_season_display_name_is_not_mapped_to_2026(self):
        self.collection.records[self.id]['created_at'] = datetime(2025, 4, 1, tzinfo=timezone.utc)
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 0)
        self.assertFalse(self.service.statuses([self.id]))

    def test_editing_an_old_zero_record_without_a_job_starts_estimates(self):
        def save():
            self.collection.records[self.id]['ferried_fuel'] = 28
            return True
        self.service.manual_update(self.id, save, {'ferried_fuel': '28'})
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 2)
        self.assertEqual(self.collection.records[self.id]['ferried_fuel'], 28)

    def test_zero_completion_of_an_older_edit_cannot_reenroll_after_newer_nonzero_save(self):
        self.service.enroll(self.id, self.data)
        def newer():
            self.collection.records[self.id]['auto_fuel'] = 9
            return True
        def older():
            self.collection.records[self.id].update(dict.fromkeys(PHASES, 0))
            self.service.manual_update(self.id, newer, {'auto_fuel': '9'})
            return True
        self.service.manual_update(self.id, older, dict.fromkeys(PHASES, '0'))
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 9)
        self.assertFalse(self.service.statuses([self.id]))

    def test_backfill_does_not_reenroll_during_an_inflight_manual_save(self):
        self.service.enroll(self.id, self.data)
        def save():
            self.service.tick()
            self.assertFalse(self.collection.writes)
            self.collection.records[self.id]['auto_fuel'] = 9
            return True
        self.service.manual_update(self.id, save, {'auto_fuel': '9'})
        self.now[0] += 301
        self.service.tick()
        self.assertEqual(self.collection.records[self.id]['auto_fuel'], 9)
        self.assertFalse(self.service.statuses([self.id]))

    def test_unplayed_match_waits_then_fills_after_results_arrive(self):
        self.match['alliances']['blue']['score'] = -1
        self.service.enroll(self.id, self.data)
        self.service.tick()
        self.assertFalse(self.service.statuses([self.id])[self.id]['estimated'])
        self.assertFalse(self.collection.writes)
        self.match['alliances']['blue']['score'] = 82
        self.now[0] += 301
        self.service.tick()
        self.assertTrue(self.service.statuses([self.id])[self.id]['estimated'])

    def test_etag_304_counts_and_429_waits_without_losing_cached_data(self):
        self.service._request('m13', '/v1/events/2026nyn2/teams')
        self.now[0] += 301
        self.network.side_effect = None
        self.network.return_value = Response(status=304)
        self.assertEqual(self.service._request('m13', '/v1/events/2026nyn2/teams'), self.ratings)
        self.assertEqual(self.network.call_args.kwargs['headers']['If-None-Match'], 'test-etag')
        with self.service.connect() as con:
            self.assertEqual(con.execute('SELECT count(*) FROM calls').fetchone()[0], 2)
        self.now[0] += 301
        self.network.return_value = Response(status=429, headers={'Retry-After': '3600'})
        self.assertEqual(self.service._request('m13', '/v1/events/2026nyn2/teams'), self.ratings)
        self.service._request('m13', '/v1/events/other/teams')
        self.assertEqual(self.network.call_count, 3)
        self.now[0] += 3601
        self.network.return_value = Response(self.ratings)
        self.service._request('m13', '/v1/events/2026nyn2/teams')
        self.assertEqual(self.network.call_count, 4)

    def test_all_workers_share_rolling_minute_hour_and_week_budgets(self):
        for window, limit in self.service.BUDGETS:
            with self.service.transaction() as con:
                con.execute('DELETE FROM calls')
                con.executemany('INSERT INTO calls VALUES (?)', [(self.now[0] - window + 1,)] * limit)
            before = self.network.call_count
            other = FuelEstimateService(self.db, self.path, 'same-account', 'test-tba', clock=lambda: self.now[0], get=self.network)
            other._request('m13', f'/v1/events/limit{window}/teams')
            self.assertEqual(self.network.call_count, before)

    def test_quota_headers_auth_failures_and_timeouts_back_off(self):
        self.network.side_effect = None
        self.network.return_value = Response(self.ratings, headers={'X-RateLimit-Remaining': '40,0,30000', 'X-RateLimit-Reset': '50,1800,5000'})
        self.service._request('m13', '/v1/events/2026nyn2/teams')
        self.service._request('m13', '/v1/events/next/teams')
        self.assertEqual(self.network.call_count, 1)
        self.now[0] += 1801
        self.network.return_value = Response(status=401)
        self.service._request('m13', '/v1/events/next/teams')
        self.service._request('m13', '/v1/events/another/teams')
        self.assertEqual(self.network.call_count, 2)
        self.now[0] += 3601
        self.network.side_effect = requests.Timeout()
        self.assertEqual(self.service._request('m13', '/v1/events/2026nyn2/teams'), self.ratings)
        self.assertEqual(self.network.call_args.kwargs['timeout'], (3, 5))


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(LOGIN_DISABLED=True, SECRET_KEY='test-only')
        self.app.add_url_rule('/scouting', endpoint='scouting.home', view_func=lambda: 'ok')
        self.app.add_url_rule('/scouting/add', view_func=records.add, methods=['POST'])
        self.app.add_url_rule('/api/fuel_estimates', view_func=records.fuel_estimates, methods=['POST'])
        self.service = MagicMock()
        self.app.extensions['match13_fuel'] = self.service
        self.user = SimpleNamespace(get_id=lambda: '6ac99468539dec0f82df2c4e', teamNumber=334, is_authenticated=True, username='tester')
        self.manager = MagicMock()
        self.manager.add_scouting_data.return_value = (True, str(ObjectId()))

    def test_zero_submissions_enroll_even_with_ferry_and_nonzero_scoring_stays_manual(self):
        with patch.object(records, 'current_user', self.user), patch.object(common, 'scouting_manager', self.manager):
            response = self.app.test_client().post('/scouting/add', data={'team_number': '334'})
            self.assertEqual(response.status_code, 302)
            self.service.enroll.assert_called_once()
            submitted = self.manager.add_scouting_data.call_args.args[0]
            self.assertTrue(all(submitted[field] == 0 for field in FUEL_FIELDS))
            self.service.enroll.reset_mock()
            for data in [{'auto_fuel': '0'}, {'_fuel_entered': 'true'}, {'ferried_fuel': '2'}]:
                self.app.test_client().post('/scouting/add', data=data)
            self.assertEqual(self.service.enroll.call_count, 3)
            self.assertEqual(self.manager.add_scouting_data.call_args.args[0]['ferried_fuel'], '2')
            self.service.enroll.reset_mock()
            for data in [{'auto_fuel': '1'}, {'teleop_shift_4_fuel': '9'}]:
                self.app.test_client().post('/scouting/add', data=data)
            self.service.enroll.assert_not_called()

    def test_polling_uses_access_filter_and_rejects_invalid_or_unbounded_ids(self):
        own, foreign = str(ObjectId()), str(ObjectId())
        self.service.statuses.return_value = {own: {'estimated': True}, foreign: {'estimated': True}}
        self.manager.db.team_data.aggregate.return_value = [{'_id': ObjectId(own), 'auto_fuel': 2}]
        with patch.object(records, 'current_user', self.user), patch.object(common, 'scouting_manager', self.manager):
            client = self.app.test_client()
            response = client.post('/api/fuel_estimates', json={'ids': [own, foreign]})
            self.assertEqual(list(response.json), [own])
            pipeline = self.manager.db.team_data.aggregate.call_args.args[0]
            self.assertEqual(pipeline[3]['$match']['$or'][1], {'scouter.teamNumber': 334})
            for payload in [{'ids': ['bad']}, {'ids': [own] * 101}, []]:
                self.assertEqual(client.post('/api/fuel_estimates', json=payload).status_code, 400)


if __name__ == '__main__':
    unittest.main()
