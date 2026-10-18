"""Lighthouse pages and their team compare / search / auto path APIs."""
from __future__ import annotations

import requests
from bson import json_util
from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from ..TBA import TBAInterface
from . import common
from .common import SCOUTER_LOOKUP, actor_name, scouting_bp, team_access_match

SEARCH_TIMEOUT = 10  # seconds; aiohttp's default was 5 minutes


@scouting_bp.route("/lighthouse")
# @limiter.limit("30 per minute")
@login_required
def lighthouse():
    current_app.logger.info(f"Successfully fetched lighthouse for user {actor_name(current_user)}")
    return render_template("lighthouse.html")


@scouting_bp.route("/lighthouse/auton")
# @limiter.limit("30 per minute")
@login_required
def auton():
    current_app.logger.info(f"Successfully fetched lighthouse/auton for user {actor_name(current_user)}")
    return render_template("lighthouse/auton.html")


@scouting_bp.route("/api/compare")
# @limiter.limit("30 per minute")
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
                pipeline = [
                    {"$match": {"team_number": team_num}},
                    SCOUTER_LOOKUP,
                    {"$unwind": "$scouter"},
                    team_access_match(current_user),
                    {"$group": {
                        "_id": "$team_number",
                        "matches_played": {"$sum": 1},

                        # Fuel Stats
                        "avg_auto_fuel": {"$avg": {"$ifNull": ["$auto_fuel", 0]}},
                        "avg_auto_climb": {"$avg": {"$cond": ["$auto_climb", 1, 0]}},
                        "avg_transition_fuel": {"$avg": {"$ifNull": ["$transition_fuel", 0]}},
                        "avg_ferried_fuel": {"$avg": {"$ifNull": ["$ferried_fuel", 0]}},
                        "avg_teleop_shift_1_fuel": {"$avg": {"$ifNull": ["$teleop_shift_1_fuel", 0]}},
                        "avg_teleop_shift_2_fuel": {"$avg": {"$ifNull": ["$teleop_shift_2_fuel", 0]}},
                        "avg_teleop_shift_3_fuel": {"$avg": {"$ifNull": ["$teleop_shift_3_fuel", 0]}},
                        "avg_teleop_shift_4_fuel": {"$avg": {"$ifNull": ["$teleop_shift_4_fuel", 0]}},
                        "avg_endgame_fuel": {"$avg": {"$ifNull": ["$endgame_fuel", 0]}},

                        # Climb Stats
                        "climb_success_rate": {"$avg": {"$cond": ["$climb_success", 1, 0]}},
                        "climb_level_1_count": {"$sum": {"$cond": [{"$eq": ["$climb_level", 1]}, 1, 0]}},
                        "climb_level_2_count": {"$sum": {"$cond": [{"$eq": ["$climb_level", 2]}, 1, 0]}},
                        "climb_level_3_count": {"$sum": {"$cond": [{"$eq": ["$climb_level", 3]}, 1, 0]}},
                        "avg_climb_level": {"$avg": {"$ifNull": ["$climb_level", 0]}},

                        "defense_notes": {"$push": "$defense_notes"},
                        "auto_paths": {"$push": {
                            "path": "$auto_path",
                            "notes": "$auto_notes",
                            "match_number": "$match_number"
                        }},
                        "defense_rating": {"$avg": {"$cond": [{"$gt": ["$defense_rating", 0]}, "$defense_rating", None]}},
                        "robot_disabled_list": {"$push": "$robot_disabled"},
                        "preferred_climb_type": {"$last": "$climb_type"},
                        "matches": {"$push": "$$ROOT"}
                    }},
                    {"$match": {"matches_played": {"$gt": 0}}}
                ]

                if stats := list(
                    common.scouting_manager.db.team_data.aggregate(pipeline)
                ):

                    # Calculate total teleop average
                    avg_teleop_total = (
                        (stats[0].get("avg_transition_fuel") or 0) +
                        (stats[0].get("avg_ferried_fuel") or 0) +
                        (stats[0]["avg_teleop_shift_1_fuel"] or 0) +
                        (stats[0]["avg_teleop_shift_2_fuel"] or 0) +
                        (stats[0]["avg_teleop_shift_3_fuel"] or 0) +
                        (stats[0]["avg_teleop_shift_4_fuel"] or 0)
                    )

                    normalized_stats = {
                        # TODO
                        "auto_scoring": min((stats[0]["avg_auto_fuel"] or 0) / 10, 1), # Assumes ~10 max auto fuel
                        "teleop_scoring": min(avg_teleop_total / 30, 1), # Assumes ~30 max teleop fuel
                        "endgame_scoring": min((stats[0]["avg_endgame_fuel"] or 0) / 10, 1), # Assumes ~10 max endgame fuel
                        "climb_level": min((stats[0]["avg_climb_level"] or 0) / 3, 1), # Max level 3
                        "climb_rating": stats[0]["climb_success_rate"],
                        "defense_rating": (stats[0]["defense_rating"] or 0) / 5 if stats[0].get("defense_rating") is not None else 0
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
                        "stats": stats[0],
                        "normalized_stats": normalized_stats,
                        "matches": stats[0]["matches"]
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
# @limiter.limit("30 per minute")
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

        # Fetch scouting data from our database
        pipeline = [
            {"$match": {"team_number": team_number}},
            SCOUTER_LOOKUP,
            {"$unwind": {"path": "$scouter"}},
            team_access_match(current_user),
            {"$sort": {"event_code": 1, "match_number": 1}},
            {
                "$project": {
                    "_id": {"$toString": "$_id"},  # Convert ObjectId to string
                    "event_code": 1,
                    "match_number": 1,
                    # Fuel Stats
                    "transition_fuel": {"$ifNull": ["$transition_fuel", 0]},
                    "ferried_fuel": {"$ifNull": ["$ferried_fuel", 0]},
                    "auto_fuel": {"$ifNull": ["$auto_fuel", 0]},
                    "teleop_shift_1_fuel": {"$ifNull": ["$teleop_shift_1_fuel", 0]},
                    "teleop_shift_2_fuel": {"$ifNull": ["$teleop_shift_2_fuel", 0]},
                    "teleop_shift_3_fuel": {"$ifNull": ["$teleop_shift_3_fuel", 0]},
                    "teleop_shift_4_fuel": {"$ifNull": ["$teleop_shift_4_fuel", 0]},
                    "endgame_fuel": {"$ifNull": ["$endgame_fuel", 0]},

                    # Climb Stats
                    "auto_climb": 1,
                    "climb_level": {"$ifNull": ["$climb_level", 0]},
                    "climb_type": 1,
                    "climb_success": 1,

                    "auto_path": 1,
                    "auto_notes": 1,
                    "defense_rating": {"$ifNull": ["$defense_rating", 0]},
                    "notes": 1,
                    "scouter_name": "$scouter.username",
                    "scouter_id": {"$toString": "$scouter._id"}
                }
            }
        ]

        scouting_data = list(common.scouting_manager.db.team_data.aggregate(pipeline))

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
# @limiter.limit("30 per minute")
def get_team_paths():
    team_number = request.args.get('team')

    if not team_number:
        return jsonify({"error": "Team number is required"}), 400

    try:
        team_number = int(team_number)

        # Build pipeline to get paths for the team
        pipeline = [
            {"$match": {"team_number": team_number}},
            SCOUTER_LOOKUP,
            {"$unwind": {"path": "$scouter", "preserveNullAndEmptyArrays": True}},
            team_access_match(current_user),
            # Only get matches with auto path data
            {"$match": {"auto_path": {"$exists": True, "$ne": []}}},
            # Sort by most recent matches first
            {"$sort": {"match_number": -1}},
            # Project only the needed fields
            {"$project": {
                "_id": {"$toString": "$_id"},
                "team_number": 1,
                "match_number": 1,
                "event_code": 1,
                "event_name": 1,
                "alliance": 1,
                "auto_path": 1,
                "auto_notes": 1,
                "scouter_name": "$scouter.username",
                "scouter_id": {"$toString": "$scouter._id"}
            }}
        ]

        # Get team info from TBA
        tba = TBAInterface()
        team_key = f"frc{team_number}"
        team_info = tba.get_team(team_key) or {}

        # Get paths from database
        paths = list(common.scouting_manager.db.team_data.aggregate(pipeline))

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
