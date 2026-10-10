"""Pagination regressions use mocked reads; no database writes or connections."""
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId
from flask import Flask
from app.scout.scouting_utils import ScoutingManager
from app.scout import routes


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.manager = object.__new__(ScoutingManager)
        self.manager.db = MagicMock()
        self.user_id = '6ac99468539dec0f82df2c4e'

    def read(self, **kwargs):
        return self.manager.get_all_scouting_data(None, self.user_id, **kwargs)

    def test_database_returns_one_page_and_total_and_keeps_access_filter(self):
        records = [{'_id': ObjectId(), 'team_number': 334}]
        self.manager.db.team_data.aggregate.return_value = iter([{'records': records, 'count': [{'total': 45}]}])
        self.assertEqual(self.read(page=2), {'records': records, 'total': 45})
        pipeline = self.manager.db.team_data.aggregate.call_args.args[0]
        self.assertEqual(pipeline[2], {'$match': {'scouter._id': ObjectId(self.user_id)}})
        self.assertEqual(pipeline[-1]['$facet']['records'], [
            {'$sort': {'_id': -1}}, {'$skip': 20}, {'$limit': 20}])

    def test_team_visibility_still_includes_team_and_own_records(self):
        self.manager.db.team_data.aggregate.return_value = iter([{'records': [], 'count': []}])
        self.manager.get_all_scouting_data(334, self.user_id, page=1)
        pipeline = self.manager.db.team_data.aggregate.call_args.args[0]
        self.assertEqual(pipeline[2]['$match']['$or'], [
            {'scouter.teamNumber': 334}, {'scouter._id': ObjectId(self.user_id)}])

    def test_search_is_literal_and_runs_before_pagination(self):
        self.manager.db.team_data.aggregate.return_value = iter([{'records': [], 'count': []}])
        self.assertEqual(self.read(page=1, search='.*', filter_type='match'), {'records': [], 'total': 0})
        pipeline = self.manager.db.team_data.aggregate.call_args.args[0]
        search = pipeline[-2]['$match']['$expr']['$regexMatch']
        self.assertEqual(search['regex'], r'\.\*')
        self.assertEqual(search['input']['$convert']['input'], '$match_number')
        self.assertEqual(search['input']['$convert']['onNull'], '')

    def test_existing_callers_still_receive_full_list(self):
        records = [{'_id': ObjectId()}]
        self.manager.db.team_data.aggregate.return_value = iter(records)
        self.assertEqual(self.read(), records)
        self.assertNotIn('$facet', self.manager.db.team_data.aggregate.call_args.args[0][-1])

    def test_route_page_boundaries_and_failed_page_retry(self):
        app = Flask(__name__)
        app.config.update(LOGIN_DISABLED=True, SECRET_KEY='test-only')
        app.add_url_rule('/scouting', view_func=routes.home)
        user = SimpleNamespace(teamNumber=None, get_id=lambda: self.user_id)
        with patch.object(routes, 'current_user', user), patch.object(routes, 'scouting_manager', self.manager), \
                patch.object(routes, 'render_template', return_value='<div id="teamDataContainer"></div>'):
            for page, size, more in [(1, 20, True), (2, 20, True), (3, 5, False), (4, 0, False)]:
                self.manager.get_all_scouting_data = MagicMock(return_value={'records': [{}] * size, 'total': 45})
                response = app.test_client().get(f'/scouting?partial=1&page={page}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['has_more'], more)
                self.assertEqual(response.json['next_page'], page + 1)
                self.assertEqual(self.manager.get_all_scouting_data.call_args.kwargs['page_size'], 20)
            self.manager.get_all_scouting_data.side_effect = RuntimeError('temporary read failure')
            self.assertEqual(app.test_client().get('/scouting?partial=1').status_code, 503)


if __name__ == '__main__':
    unittest.main()
