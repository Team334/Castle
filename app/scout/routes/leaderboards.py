"""Team and scouter leaderboards."""
from __future__ import annotations

from datetime import datetime

from flask import current_app, render_template, request
from flask_login import current_user, login_required

from ..scouting_utils import LEADERBOARD_SORT_FIELDS, SCOUTER_SORT_FIELDS
from . import common
from .common import actor_name, scouting_bp

# EPA/OPR/DPR/CCWM come from TBA/Statbotics, so they are sorted after the aggregate
TBA_METRICS = {'epa', 'opr', 'dpr', 'ccwm'}


@scouting_bp.route("/leaderboard")
# @limiter.limit("30 per minute")
def leaderboard():
    try:
        sort_type = request.args.get('sort', 'fuel')
        selected_event = request.args.get('event', 'all')
        manager = common.scouting_manager

        events = manager.get_leaderboard_events(current_user.get_id(), current_user.teamNumber)
        sort_field = None if sort_type in TBA_METRICS else LEADERBOARD_SORT_FIELDS.get(sort_type, 'total_fuel')
        teams = manager.get_team_leaderboard(current_user.get_id(), current_user.teamNumber,
                                             selected_event, sort_field)
        current_app.logger.info(f"Successfully fetched leaderboard {teams} for user {actor_name(current_user)}")

        if sort_type in TBA_METRICS:
            from app.scout.team_stats import team_stats_snapshot
            snapshots = team_stats_snapshot([
                {"team_number": team["team_number"], "event_code": selected_event}
                for team in teams
            ], datetime.now().year)
            for team in teams:
                snapshot = snapshots.get(f"{team['team_number']}_{selected_event}", {})
                team[sort_type] = snapshot.get(sort_type)
            teams.sort(key=lambda team: (team.get(sort_type) is None,
                                         (team.get(sort_type) or 0) *
                                         (1 if sort_type == 'dpr' else -1)))

        return render_template("scouting/leaderboard.html", teams=teams, current_sort=sort_type,
                              events=events, selected_event=selected_event)
    except Exception as e:
        current_app.logger.error(f"Error in leaderboard: {str(e)}", exc_info=True)
        return render_template("scouting/leaderboard.html", teams=[], current_sort='fuel',
                              events=[], selected_event='all')


@scouting_bp.route("/scouter-leaderboard")
# @limiter.limit("30 per minute")
@login_required
def scouter_leaderboard():
    try:
        sort_by = request.args.get('sort', 'match_count')
        selected_event = request.args.get('event', 'all')
        selected_team = request.args.get('team', 'all')
        manager = common.scouting_manager

        events = manager.get_event_codes()
        scouters = manager.get_scouter_leaderboard(selected_event, selected_team,
                                                   SCOUTER_SORT_FIELDS.get(sort_by, 'match_count'))
        teams = manager.get_scouter_teams()

        current_app.logger.info(f"Successfully fetched scouter leaderboard {scouters} for user {actor_name(current_user)}")
        return render_template(
            "scouting/scouter-leaderboard.html",
            scouters=scouters,
            current_sort=sort_by,
            events=events,
            selected_event=selected_event,
            teams=teams,
            selected_team=selected_team
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching scouter leaderboard: {str(e)}", exc_info=True)
        return render_template(
            "scouting/scouter-leaderboard.html",
            scouters=[],
            current_sort='match_count',
            events=[],
            selected_event='all',
            teams=[],
            selected_team='all'
        )
