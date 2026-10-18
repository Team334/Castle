"""Event data from TBA/Statbotics: events, matches, live status, alliance selection, EPA/OPR."""
from __future__ import annotations

from datetime import datetime

from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.utils import limiter

from ..TBA import TBAInterface
from .common import actor_name, logger, scouting_bp


@scouting_bp.route("/api/tba/events")
@login_required
def get_tba_events():
    try:
        year = request.args.get('year', default=datetime.now().year, type=int)
        tba = TBAInterface()
        background = request.args.get('background') == '1'
        events = tba.get_current_events(year, include_test_data=background,
                                        background=background)
        if background:
            response = jsonify(events or {})
            response.headers['X-Scouting-Pending'] = str(
                tba.pending(f'/events/{year}/simple')).lower()
            return response
        event_count = len(events) if events else 0
        current_app.logger.info(f"Successfully fetched {event_count} TBA events for year {year} for user {actor_name(current_user)}")
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Error getting TBA events: {e}")
        return jsonify({"error": "Failed to fetch events"}), 500


@scouting_bp.route("/api/tba/matches/<event_key>")
@login_required
def get_tba_matches(event_key):
    try:
        tba = TBAInterface()
        matches = tba.get_event_matches(event_key, background=True)
        response = jsonify(matches)
        response.headers['X-Scouting-Pending'] = str(
            tba.pending(f'/event/{event_key}/matches')).lower()
        return response
    except Exception as e:
        current_app.logger.error(f"Error getting TBA matches: {e}")
        return jsonify({"error": "Failed to fetch matches"}), 500


@scouting_bp.route("/scouting/live-match-status", methods=["GET"])
@login_required
def live_match_status():
    """Route for the live team schedule modal"""
    context = {
        'team_number': request.args.get('team'),
        'event_code': request.args.get('event')
    }
    current_app.logger.info(f"Successfully fetched live match status {context} for user {actor_name(current_user)}")
    return render_template("scouting/live-match-status.html", **context)


@scouting_bp.route("/api/tba/team-status")
@login_required
def get_team_status():
    """Get team status at an event including ranking and matches"""
    team_number = request.args.get('team')
    event_code = request.args.get('event')

    if not team_number:
        return jsonify({"error": "Team number is required"}), 400

    try:
        team_key = f"frc{team_number}"
        tba = TBAInterface()
        event_name = None

        # If event code not provided, find the most recent event
        if not event_code:
            most_recent_event = tba.get_most_recent_active_event(team_key)
            if not most_recent_event:
                return jsonify({"error": "No events found for this team"}), 404

            event_code = most_recent_event.get('key')
            # Also return event details for the UI
            event_name = most_recent_event.get('name', 'Unknown Event')
        # Get team status at event (ranking)
        status = tba.get_team_status_at_event(team_key, event_code)

        # Get team matches at event
        matches = tba.get_team_matches_at_event(team_key, event_code)
        current_app.logger.info(f"Fetched status for team {team_number} at {event_code} for user {actor_name(current_user)}")

        return jsonify({
            "status": status,
            "matches": matches,
            "event": {
                "key": event_code,
                "name": event_name
            }
        })
    except Exception as e:
        logger.error(f"Error getting team status: {e}")
        return jsonify({"error": "Failed to fetch team status"}), 500


@scouting_bp.route("/scouting/mock-alliance-selection")
@login_required
@limiter.limit("30 per minute")
def mock_alliance_selection():
    """Render the mock alliance selection page."""
    current_app.logger.info(f"Successfully loaded mock alliance selection for user {actor_name(current_user)}")
    return render_template("scouting/mock-alliance-selection.html")


@scouting_bp.route("/api/alliance-selection/rankings/<event_key>")
@login_required
def get_alliance_rankings(event_key):
    """Get team rankings for alliance selection"""
    # basic validation for event_key (year + event code)
    if not event_key or not event_key.isalnum():
         return jsonify({"error": "Invalid event key format"}), 400

    try:
        tba = TBAInterface()
        rankings = tba.get_event_rankings(event_key)

        if not rankings:
            return jsonify({"error": "Failed to fetch rankings"}), 404

        # Fetch all team details in bulk for the event
        teams = tba.get_event_teams(event_key)
        team_info_map = {team['key']: team for team in teams} if teams else {}

        for rank in rankings:
            team_info = team_info_map.get(rank['team_key'])
            if team_info:
                rank['nickname'] = team_info.get('nickname', '')
                rank['city'] = team_info.get('city', '')
                rank['state_prov'] = team_info.get('state_prov', '')

        current_app.logger.info(f"Successfully fetched alliance rankings for event {event_key}")
        return jsonify(rankings)

    except Exception as e:
        current_app.logger.error(f"Error fetching alliance rankings: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch rankings"}), 500


@scouting_bp.route("/api/team_epa_opr", methods=["POST"])
@login_required
def get_team_epa_opr():
    """Public metrics must never occupy web workers waiting on upstream APIs."""
    from app.scout.team_stats import team_stats_snapshot

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400
    teams = data.get("teams", [])
    try:
        year = int(data.get("year", datetime.now().year))
        if not 1992 <= year <= datetime.now().year + 1:
            raise ValueError()
        if not isinstance(teams, list) or len(teams) > 2000:
            raise ValueError()
        normalized = []
        for item in teams:
            if not isinstance(item, dict):
                raise ValueError()
            number = int(item.get("team_number", 0))
            event = item.get("event_code")
            if not 1 <= number <= 999999 or (event is not None and
                    (not isinstance(event, str) or len(event) > 200)):
                raise ValueError()
            normalized.append({"team_number": number, "event_code": event})
    except (ValueError, TypeError, OverflowError):
        return jsonify({"error": "Invalid teams, event codes, or year"}), 400
    return jsonify(team_stats_snapshot(normalized, year))
