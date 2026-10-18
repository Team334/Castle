"""Pit scouting form parsing for add and edit; managers mocked, no database."""
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId
from flask import Flask

from app.scout.routes import common, pit


class PitFormTests(unittest.TestCase):
    def setUp(self):
        self.user_id = str(ObjectId())
        self.app = Flask(__name__)
        self.app.config.update(LOGIN_DISABLED=True, SECRET_KEY='test-only')
        self.app.add_url_rule('/scouting/pit', endpoint='scouting.pit_scouting', view_func=lambda: 'list')
        self.app.add_url_rule('/add', view_func=pit.pit_scouting_add, methods=['POST'])
        self.app.add_url_rule('/edit/<entry_id>', view_func=pit.pit_scouting_edit, methods=['POST'])
        self.user = SimpleNamespace(id=self.user_id, get_id=lambda: self.user_id, is_authenticated=True, username='t')
        self.manager = MagicMock()
        self.manager.get_pit_scouting_by_id.return_value = {"scouter_id": ObjectId(self.user_id)}

    def post(self, url, form):
        with patch.object(pit, 'current_user', self.user), patch.object(common, 'scouting_manager', self.manager), \
                patch.object(pit, 'render_template', return_value='form'):
            return self.app.test_client().post(url, data=form)

    def test_blank_numbers_save_as_zero_on_add_and_edit(self):
        form = {'team_number': '334', 'driver_years': '', 'fuel_count_bps': '', 'has_auto': 'true', 'auto_routes': ''}
        self.post('/add', form)
        self.post(f'/edit/{ObjectId()}', form)
        added = self.manager.add_pit_scouting.call_args.args[0]
        edited = self.manager.update_pit_scouting.call_args.args[1]
        for data in (added, edited):
            self.assertEqual(data['driver_experience']['years'], 0)
            self.assertEqual(data['fuel_count_bps'], 0)
            self.assertEqual(data['autonomous_capabilities']['num_routes'], 0)
            self.assertEqual(data['team_number'], 334)
        self.assertIn('created_at', added)
        self.assertNotIn('created_at', edited)
        self.assertEqual(edited['scouter_id'], ObjectId(self.user_id))

    def test_auto_details_ignored_without_auto(self):
        self.post('/add', {'team_number': '1', 'auto_routes': '3', 'auto_notes': 'x'})
        auto = self.manager.add_pit_scouting.call_args.args[0]['autonomous_capabilities']
        self.assertEqual(auto, {'has_auto': False, 'num_routes': 0, 'preferred_start': '', 'notes': ''})

    def test_missing_team_number_on_edit_is_handled(self):
        self.assertEqual(self.post(f'/edit/{ObjectId()}', {}).status_code, 200)
        self.manager.update_pit_scouting.assert_not_called()


if __name__ == '__main__':
    unittest.main()
