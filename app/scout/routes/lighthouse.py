"""Lighthouse pages and their team compare / search / auto path APIs."""
from __future__ import annotations

import requests
from bson import json_util
from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from ..TBA import TBAInterface
from . import common
from .common import actor_name, scouting_bp

SEARCH_TIMEOUT = 10  # seconds; aiohttp's default was 5 minutes


@scouting_bp.route("/lighthouse")
@login_required
def lighthouse():
    current_app.logger.info(f"Successfully fetched lighthouse for user {actor_name(current_user)}")
    return render_template("lighthouse.html")


@scouting_bp.route("/lighthouse/auton")
@login_required
def auton():
    current_app.logger.info(f"Successfully fetched lighthouse/auton for user {actor_name(current_user)}")
    return render_template("lighthouse/auton.html")


@scouting_bp.route("/api/compare")
@login_required
def compare_teams():
    try:
        teams = []
        for i in range(1, 4):
            if team_num := request.args.get(f'team{i}'):
                teams.append(int(team_num))

        if len(teams) < 2:
            return jsonify({"error": "At least 2 teams are required"}), 400

        teams_data = {}
        for team_num in teams:
            try:
                if stats := common.scouting_manager.get_compare_stats(
                        team_num, current_user.get_id(), current_user.teamNumber):

                    # Calculate total teleop average
                    avg_teleop_total = (
                        (stats.get("avg_transition_fuel") or 0) +
                        (stats.get("avg_ferried_fuel") or 0) +
                        (stats["avg_teleop_shift_1_fuel"] or 0) +
                        (stats["avg_teleop_shift_2_fuel"] or 0) +
                        (stats["avg_teleop_shift_3_fuel"] or 0) +
                        (stats["avg_teleop_shift_4_fuel"] or 0)
                    )

                    normalized_stats = {
                        # TODO
                        "auto_scoring": min((stats["avg_auto_fuel"] or 0) / 10, 1), # Assumes ~10 max auto fuel
                        "teleop_scoring": min(avg_teleop_total / 30, 1), # Assumes ~30 max teleop fuel
                        "endgame_scoring": min((stats["avg_endgame_fuel"] or 0) / 10, 1), # Assumes ~10 max endgame fuel
                        "climb_level": min((stats["avg_climb_level"] or 0) / 3, 1), # Max level 3
                        "climb_rating": stats["climb_success_rate"],
                        "defense_rating": (stats["defense_rating"] or 0) / 5 if stats.get("defense_rating") is not None else 0
                    }

                    # Get team info from TBA
                    team_key = f"frc{team_num}"
                    team_info = TBAInterface().get_team(team_key)

                    teams_data[str(team_num)] = {
                        "team_number": team_num,
                        "nickname": team_info.get("nickname", "Unknown"),
                        "city": team_info.get("city"),
                        "state_prov": team_info.get("state_prov"),
                        "country": team_info.get("country"),
                        "stats": stats,
                        "normalized_stats": normalized_stats,
                        "matches": stats["matches"]
                    }

            except Exception as team_error:
                current_app.logger.error(f"Error processing team {team_num}: {str(team_error)}", exc_info=True)

        if not teams_data:
            return jsonify({"error": "No data available for the selected teams"}), 404

        current_app.logger.info(f"Successfully fetched team data {teams_data} for user {actor_name(current_user)}")
        return json_util.dumps(teams_data)

    except Exception as e:
        current_app.logger.error(f"Error in compare_teams: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred while comparing teams"}), 500


@scouting_bp.route("/api/search")
@login_required
def search_teams():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    try:
        # Initialize TBA interface
        tba = TBAInterface()

        # Handle both numeric and text searches
        if query.isdigit():
            url = f"{tba.base_url}/team/frc{query}"
        else:
            # Search by team name/nickname
            url = f"{tba.base_url}/teams/search/{query}"
        response = requests.get(url, headers=tba.headers, timeout=SEARCH_TIMEOUT)
        if response.status_code != 200:
            return jsonify([])
        team = response.json()
        if not query.isdigit():
            if not team:
                return jsonify([])
            team = team[0]  # Take the first match

        # Get team number from the response
        team_number = team.get("team_number")

        scouting_data = common.scouting_manager.get_team_records(
            team_number, current_user.get_id(), current_user.teamNumber)

        # Format response
        response_data = [{
            "team_number": team_number,
            "nickname": team.get("nickname"),
            "school_name": team.get("school_name"),
            "city": team.get("city"),
            "state_prov": team.get("state_prov"),
            "country": team.get("country"),
            "scouting_data": scouting_data,
            "has_team_page": bool(scouting_data)  # True if we have any scouting data
        }]

        # Use json_util.dumps to handle MongoDB types
        current_app.logger.info(f"Successfully fetched team data {response_data} for user {actor_name(current_user)}")
        return json_util.dumps(response_data), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        current_app.logger.error(f"Error in search_teams: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch team data due to an internal error."}), 500


@scouting_bp.route("/api/team_paths")
@login_required
def get_team_paths():
    team_number = request.args.get('team')

    if not team_number:
        return jsonify({"error": "Team number is required"}), 400

    try:
        team_number = int(team_number)

        # Get team info from TBA
        tba = TBAInterface()
        team_key = f"frc{team_number}"
        team_info = tba.get_team(team_key) or {}

        paths = common.scouting_manager.get_auto_paths(team_number, current_user.get_id(), current_user.teamNumber)

        # Format response
        response = {
            "team_number": team_number,
            "team_info": {
                "nickname": team_info.get("nickname", "Unknown"),
                "city": team_info.get("city", ""),
                "state_prov": team_info.get("state_prov", ""),
                "country": team_info.get("country", "")
            },
            "paths": paths
        }

        current_app.logger.info(f"Successfully fetched team paths {response} for user {actor_name(current_user)}")
        return json_util.dumps(response), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        current_app.logger.error(f"Error fetching team paths: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch team path data."}), 500
