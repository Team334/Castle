from __future__ import annotations

import json
from datetime import datetime, timezone

import aiohttp
from bson import ObjectId, json_util
from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

import logging
from app.scout.scouting_utils import ScoutingManager
from app.utils import async_route, handle_route_errors

from .TBA import TBAInterface

scouting_bp = Blueprint("scouting", __name__)
scouting_manager = None
tba = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@scouting_bp.record
def on_blueprint_init(state):
    global scouting_manager, tba
    app = state.app
    
    # Create ScoutingManager with the singleton connection
    scouting_manager = ScoutingManager(app.config["MONGO_URI"])
    
    # Initialize TBA
    tba = TBAInterface(api_key=app.config.get("TBA_KEY", ""))
    
    # Store in app context for proper cleanup
    if not hasattr(app, 'db_managers'):
        app.db_managers = {}
    app.db_managers['scouting'] = scouting_manager


@scouting_bp.route("/scouting/add", methods=["GET", "POST"])
@login_required
# @limiter.limit("15 per minute")
@handle_route_errors
def add():
    if request.method != "POST":
        # Get current events only
        tba = TBAInterface()
        year = datetime.now().year
        events = tba.get_current_events(year) or {}
        
        return render_template("scouting/add.html", 
                            events=events,
                            event_matches={})  # Empty dict

    data = request.get_json() if request.is_json else request.form.to_dict()

    if "auto_path" in data:
        try:
            if isinstance(data["auto_path"], str):
                if data["auto_path"].strip(): 
                    data["auto_path"] = json.loads(data["auto_path"])
                else:
                    data["auto_path"] = [] 
        except json.JSONDecodeError:
            flash("Invalid path coordinates format", "error")
            return redirect(url_for("scouting.home"))

    success, message = scouting_manager.add_scouting_data(data, current_user.get_id())
    current_app.logger.info(f"Tried to add scouting data ({success}) {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} - {message}")
    current_app.logger.info(f"Scouting.add Form Details {request.form} - {message}")

    if success:
        flash("Team data added successfully", "success")
    else:
        flash(f"Error adding data: {message}", "error")

    return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/list")
@scouting_bp.route("/scouting")
# @limiter.limit("30 per minute")
@login_required
def home():
    try:
        team_data = scouting_manager.get_all_scouting_data(
            current_user.teamNumber, 
            current_user.get_id()
        )

        # Get the user's team if they have one
        team = None
        if current_user.teamNumber:
            team_query = {"team_number": current_user.teamNumber}
            if team_doc := scouting_manager.db.teams.find_one(team_query):
                from app.models import Team
                team = Team.create_from_db(team_doc)
        current_app.logger.info(f"Successfully fetched team data {team_data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return render_template("scouting/list.html", team_data=team_data, team=team)
    except Exception as e:
        current_app.logger.error(f"Error fetching scouting data: {str(e)}", exc_info=True)
        flash("Unable to fetch scouting data. Please try again later.", "error")
        return render_template("scouting/list.html", team_data=[])


@scouting_bp.route("/scouting/edit/<string:id>", methods=["GET", "POST"])
# @limiter.limit("15 per minute")
@login_required
def edit(id):
    try:
        team_data = scouting_manager.get_team_data(id, current_user.get_id())

        if not team_data:
            flash("Team data not found", "error")
            return redirect(url_for("scouting.home"))

        # Check if the current user is on the same team as the scouter
        current_team = current_user.teamNumber
        scouter_team = team_data.scouter_team
        
        # Allow access only if user is the original scouter or on the same team
        if current_user.get_id() != team_data.scouter_id and (not current_team or not scouter_team or str(current_team) != str(scouter_team)):
            flash("Access denied: You can only edit scouting data from your own team", "error")
            return redirect(url_for("scouting.home"))

        if request.method == "POST":
            data = request.form.to_dict()
            current_app.logger.info(f"Scouting.edit Form Details {request.form}")
            # Add edit tracking - record who made the edit
            data['last_edited_by'] = current_user.get_id()
            data['last_edited_at'] = datetime.now().isoformat()
            
            # Convert the drawing coordinates from string to JSON if present
            if "auto_path_coords" in data and isinstance(data["auto_path_coords"], str):
                try:
                    json.loads(data["auto_path_coords"])  # Validate JSON
                except json.JSONDecodeError:
                    flash("Invalid path coordinates format", "error")
                    return render_template("scouting/edit.html", team_data=team_data)
            
            if scouting_manager.update_team_data(id, data, current_user.get_id()):
                flash("Data updated successfully", "success")
                current_app.logger.info(f"Successfully updated scouting data {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} - {message}")
                return redirect(url_for("scouting.home"))
            
            current_app.logger.info(f"Failed to update scouting data {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} - {message}")
            flash("Unable to update data", "error")

        return render_template("scouting/edit.html", team_data=team_data)
    except Exception as e:
        current_app.logger.error(f"Error in edit_scouting_data: {str(e)}", exc_info=True)
        flash("An error occurred while processing your request", "error")
        return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/delete/<string:id>")
# @limiter.limit("10 per minute")
@login_required
def delete(id):
    try:
        # Get information about the record before deleting for better error messages
        team_data = scouting_manager.get_team_data(id, current_user.get_id())
        if not team_data:
            flash("Record not found", "error")
            return redirect(url_for("scouting.home"))

        # Attempt to delete
        if scouting_manager.delete_team_data(id, current_user.get_id()):
            current_app.logger.info(f"Successfully deleted scouting data {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            flash("Record deleted successfully", "success")
        elif team_data.scouter_id == current_user.get_id():
            flash("Error deleting your record. Please try again.", "error")
        elif current_user.teamNumber and team_data.scouter_team == current_user.teamNumber:
            # Check if user is team admin using existing database connection
            team_query = {"team_number": current_user.teamNumber}
            if team_doc := scouting_manager.db.teams.find_one(team_query):
                from app.models import Team
                team = Team.create_from_db(team_doc)
                
                if team.is_admin(current_user.get_id()):
                    # Try to delete again with admin override
                    if scouting_manager.delete_team_data(id, current_user.get_id(), admin_override=True):
                        current_app.logger.info(f"Successfully deleted scouting data {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} (admin)")
                        flash("Record deleted successfully (admin)", "success")
                    else:
                        current_app.logger.info(f"Failed to delete scouting data {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} (admin)")
                        flash("Error deleting team member's record. Please try again.", "error")
                else:
                    current_app.logger.info(f"Permission denied: You must be a team admin to delete other members' records {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                    flash("Permission denied: You must be a team admin to delete other members' records", "error")
            else:
                current_app.logger.info(f"Permission denied: Team not found {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                flash("Permission denied: Team not found", "error")
        else:
            current_app.logger.info(f"Permission denied: You can only delete records from your own team {id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            flash("Permission denied: You can only delete records from your own team", "error")
    except Exception as e:
        current_app.logger.error(f"Delete error: {str(e)}", exc_info=True)
        flash("An internal error has occurred.", "error")
    return redirect(url_for("scouting.home"))


@scouting_bp.route("/lighthouse")
# @limiter.limit("30 per minute")
@login_required
def lighthouse():
    current_app.logger.info(f"Successfully fetched lighthouse for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return render_template("lighthouse.html")

@scouting_bp.route("/lighthouse/auton")
# @limiter.limit("30 per minute")
@login_required
def auton():
    current_app.logger.info(f"Successfully fetched lighthouse/auton for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return render_template("lighthouse/auton.html")

def format_team_stats(stats):
    """Format team stats with calculated totals"""
    return {
        "matches_played": stats.get("matches_played", 0),
        "auto_coral_total": sum([
            stats.get("avg_auto_coral_level1", 0),
            stats.get("avg_auto_coral_level2", 0),
            stats.get("avg_auto_coral_level3", 0),
            stats.get("avg_auto_coral_level4", 0)
        ]),
        "teleop_coral_total": sum([
            stats.get("avg_teleop_coral_level1", 0),
            stats.get("avg_teleop_coral_level2", 0),
            stats.get("avg_teleop_coral_level3", 0),
            stats.get("avg_teleop_coral_level4", 0)
        ]),
        "auto_algae_total": sum([
            stats.get("avg_auto_algae_net", 0),
            stats.get("avg_auto_algae_processor", 0)
        ]),
        "teleop_algae_total": sum([
            stats.get("avg_teleop_algae_net", 0),
            stats.get("avg_teleop_algae_processor", 0)
        ]),
        "climb_success_rate": stats.get("climb_success_rate", 0) * 100
    }


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
                    {"$lookup": {
                        "from": "users",
                        "localField": "scouter_id",
                        "foreignField": "_id",
                        "as": "scouter"
                    }},
                    {"$unwind": "$scouter"},
                    {"$match": {
                        "$or": [
                            {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                            {"scouter._id": ObjectId(current_user.get_id())}
                        ]
                    }},
                    {"$group": {
                        "_id": "$team_number",
                        "matches_played": {"$sum": 1},
                        "avg_auto_coral_level1": {"$avg": {"$cond": [{"$gt": ["$auto_coral_level1", 0]}, "$auto_coral_level1", None]}},
                        "avg_auto_coral_level2": {"$avg": {"$cond": [{"$gt": ["$auto_coral_level2", 0]}, "$auto_coral_level2", None]}},
                        "avg_auto_coral_level3": {"$avg": {"$cond": [{"$gt": ["$auto_coral_level3", 0]}, "$auto_coral_level3", None]}},
                        "avg_auto_coral_level4": {"$avg": {"$cond": [{"$gt": ["$auto_coral_level4", 0]}, "$auto_coral_level4", None]}},
                        "avg_auto_algae_net": {"$avg": {"$cond": [{"$gt": ["$auto_algae_net", 0]}, "$auto_algae_net", None]}},
                        "avg_auto_algae_processor": {"$avg": {"$cond": [{"$gt": ["$auto_algae_processor", 0]}, "$auto_algae_processor", None]}},
                        "avg_teleop_coral_level1": {"$avg": {"$cond": [{"$gt": ["$teleop_coral_level1", 0]}, "$teleop_coral_level1", None]}},
                        "avg_teleop_coral_level2": {"$avg": {"$cond": [{"$gt": ["$teleop_coral_level2", 0]}, "$teleop_coral_level2", None]}},
                        "avg_teleop_coral_level3": {"$avg": {"$cond": [{"$gt": ["$teleop_coral_level3", 0]}, "$teleop_coral_level3", None]}},
                        "avg_teleop_coral_level4": {"$avg": {"$cond": [{"$gt": ["$teleop_coral_level4", 0]}, "$teleop_coral_level4", None]}},
                        "avg_teleop_algae_net": {"$avg": {"$cond": [{"$gt": ["$teleop_algae_net", 0]}, "$teleop_algae_net", None]}},
                        "avg_teleop_algae_processor": {"$avg": {"$cond": [{"$gt": ["$teleop_algae_processor", 0]}, "$teleop_algae_processor", None]}},
                        # Only count successful climbs in the rate
                        "climb_success_rate": {"$avg": {"$cond": ["$climb_success", 1, 0]}},
                        "defense_notes": {"$push": "$defense_notes"},
                        "auto_paths": {"$push": {
                            "path": "$auto_path",
                            "notes": "$auto_notes",
                            "match_number": "$match_number"
                        }},
                        "defense_rating": {"$avg": {"$cond": [{"$gt": ["$defense_rating", 0]}, "$defense_rating", None]}},
                        "mobility_rating": {"$avg": {"$cond": [{"$gt": ["$mobility_rating", 0]}, "$mobility_rating", None]}},
                        "mobility_notes": {"$push": "$mobility_notes"},
                        "durability_rating": {"$avg": {"$cond": [{"$gt": ["$durability_rating", 0]}, "$durability_rating", None]}},
                        "durability_notes": {"$push": "$durability_notes"},
                        "preferred_climb_type": {"$last": "$climb_type"},
                        "matches": {"$push": "$$ROOT"}
                    }},
                    {"$match": {"matches_played": {"$gt": 0}}}
                ]

                if stats := list(
                    scouting_manager.db.team_data.aggregate(pipeline)
                ):
                    normalized_stats = {
                        "auto_scoring": (
                            (stats[0]["avg_auto_coral_level1"] or 0) + 
                            (stats[0]["avg_auto_coral_level2"] or 0) * 2 +
                            (stats[0]["avg_auto_coral_level3"] or 0) * 3 +
                            (stats[0]["avg_auto_coral_level4"] or 0) * 4 +
                            (stats[0]["avg_auto_algae_net"] or 0) * 2 +
                            (stats[0]["avg_auto_algae_processor"] or 0) * 3
                        ) / 20,
                        "teleop_scoring": (
                            (stats[0]["avg_teleop_coral_level1"] or 0) + 
                            (stats[0]["avg_teleop_coral_level2"] or 0) * 2 +
                            (stats[0]["avg_teleop_coral_level3"] or 0) * 3 +
                            (stats[0]["avg_teleop_coral_level4"] or 0) * 4 +
                            (stats[0]["avg_teleop_algae_net"] or 0) * 2 +
                            (stats[0]["avg_teleop_algae_processor"] or 0) * 3
                        ) / 20,
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

        current_app.logger.info(f"Successfully fetched team data {teams_data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return json_util.dumps(teams_data)

    except Exception as e:
        current_app.logger.error(f"Error in compare_teams: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred while comparing teams"}), 500

@scouting_bp.route("/api/search")
@login_required
# @limiter.limit("30 per minute")
@async_route
async def search_teams():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    try:
        # Initialize TBA interface
        tba = TBAInterface()
        
        # Handle both numeric and text searches
        if query.isdigit():
            team_key = f"frc{query}"
            url = f"{tba.base_url}/team/{team_key}"
            
            async with aiohttp.ClientSession(headers=tba.headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return jsonify([])
                    team = await response.json()
        else:
            # Search by team name/nickname
            url = f"{tba.base_url}/teams/search/{query}"
            async with aiohttp.ClientSession(headers=tba.headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return jsonify([])
                    teams = await response.json()
                    if not teams:
                        return jsonify([])
                    team = teams[0]  # Take the first match

        # Get team number from the response
        team_number = team.get("team_number")
        
        # Fetch scouting data from our database
        pipeline = [
            {"$match": {"team_number": team_number}},
            {"$lookup": {
                "from": "users",
                "localField": "scouter_id",
                "foreignField": "_id",
                "as": "scouter"
            }},
            {"$unwind": {"path": "$scouter"}},
            # Add team access filter
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }},
            {"$sort": {"event_code": 1, "match_number": 1}},
            {
                "$project": {
                    "_id": {"$toString": "$_id"},  # Convert ObjectId to string
                    "event_code": 1,
                    "match_number": 1,
                    "auto_coral_level1": {"$ifNull": ["$auto_coral_level1", 0]},
                    "auto_coral_level2": {"$ifNull": ["$auto_coral_level2", 0]},
                    "auto_coral_level3": {"$ifNull": ["$auto_coral_level3", 0]},
                    "auto_coral_level4": {"$ifNull": ["$auto_coral_level4", 0]},
                    "teleop_coral_level1": {"$ifNull": ["$teleop_coral_level1", 0]},
                    "teleop_coral_level2": {"$ifNull": ["$teleop_coral_level2", 0]},
                    "teleop_coral_level3": {"$ifNull": ["$teleop_coral_level3", 0]},
                    "teleop_coral_level4": {"$ifNull": ["$teleop_coral_level4", 0]},
                    "auto_algae_net": {"$ifNull": ["$auto_algae_net", 0]},
                    "auto_algae_processor": {"$ifNull": ["$auto_algae_processor", 0]},
                    "teleop_algae_net": {"$ifNull": ["$teleop_algae_net", 0]},
                    "teleop_algae_processor": {"$ifNull": ["$teleop_algae_processor", 0]},
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

        scouting_data = list(scouting_manager.db.team_data.aggregate(pipeline))

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
        current_app.logger.info(f"Successfully fetched team data {response_data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return json_util.dumps(response_data), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        current_app.logger.error(f"Error in search_teams: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch team data due to an internal error."}), 500

@scouting_bp.route("/leaderboard")
# @limiter.limit("30 per minute")
def leaderboard():
    try:
        MIN_MATCHES = 1
        sort_type = request.args.get('sort', 'coral')
        selected_event = request.args.get('event', 'all')
        
        # Get available events from scouting data
        # Filter by team access: only show events from user's team or user himself
        events_pipeline = [
            # Join with users collection to get scouter information
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
            # Filter by team access
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }},
            # Group by event code to get unique events
            {"$group": {
                "_id": "$event_code",
                "event_name": {"$first": "$event_name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        events = list(scouting_manager.db.team_data.aggregate(events_pipeline))
        
        # Main pipeline for team data
        pipeline = [
            # Join with users collection to get scouter information
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
            # Filter by team access
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }}
        ]
        
        # Filter by selected event if not 'all'
        if selected_event != 'all':
            pipeline.append({"$match": {"event_code": selected_event}})
        
        # Continue with the existing aggregation
        pipeline.extend([
            {"$group": {
                "_id": "$team_number",
                "matches_played": {"$sum": 1},
                # Auto Coral
                "auto_coral_level1": {"$avg": {"$ifNull": ["$auto_coral_level1", 0]}},
                "auto_coral_level2": {"$avg": {"$ifNull": ["$auto_coral_level2", 0]}},
                "auto_coral_level3": {"$avg": {"$ifNull": ["$auto_coral_level3", 0]}},
                "auto_coral_level4": {"$avg": {"$ifNull": ["$auto_coral_level4", 0]}},
                # Teleop Coral
                "teleop_coral_level1": {"$avg": {"$ifNull": ["$teleop_coral_level1", 0]}},
                "teleop_coral_level2": {"$avg": {"$ifNull": ["$teleop_coral_level2", 0]}},
                "teleop_coral_level3": {"$avg": {"$ifNull": ["$teleop_coral_level3", 0]}},
                "teleop_coral_level4": {"$avg": {"$ifNull": ["$teleop_coral_level4", 0]}},
                # Auto Algae
                "auto_algae_net": {"$avg": {"$ifNull": ["$auto_algae_net", 0]}},
                "auto_algae_processor": {"$avg": {"$ifNull": ["$auto_algae_processor", 0]}},
                # Teleop Algae
                "teleop_algae_net": {"$avg": {"$ifNull": ["$teleop_algae_net", 0]}},
                "teleop_algae_processor": {"$avg": {"$ifNull": ["$teleop_algae_processor", 0]}},
                
                # Defense Rating
                "defense_rating": {"$avg": {"$ifNull": ["$defense_rating", 0]}},
                # Mobility Rating
                "mobility_rating": {"$avg": {"$ifNull": ["$mobility_rating", 0]}},
                # Durability Rating
                "durability_rating": {"$avg": {"$ifNull": ["$durability_rating", 0]}},

                # Climb stats
                "climb_attempts": {"$sum": 1},
                "climb_successes": {
                    "$sum": {"$cond": [{"$eq": ["$climb_success", True]}, 1, 0]}
                },
                "deep_climb_attempts": {
                    "$sum": {"$cond": [{"$eq": ["$climb_type", "deep"]}, 1, 0]}
                },
                "deep_climb_successes": {
                    "$sum": {
                        "$cond": [
                            {"$and": [
                                {"$eq": ["$climb_type", "deep"]},
                                {"$eq": ["$climb_success", True]}
                            ]},
                            1,
                            0
                        ]
                    }
                }
            }},
            {"$match": {"matches_played": {"$gte": MIN_MATCHES}}},
            {"$project": {
                "team_number": "$_id",
                "matches_played": 1,
                "auto_coral_stats": {
                    "level1": "$auto_coral_level1",
                    "level2": "$auto_coral_level2",
                    "level3": "$auto_coral_level3",
                    "level4": "$auto_coral_level4"
                },
                "teleop_coral_stats": {
                    "level1": "$teleop_coral_level1",
                    "level2": "$teleop_coral_level2",
                    "level3": "$teleop_coral_level3",
                    "level4": "$teleop_coral_level4"
                },
                "auto_algae_stats": {
                    "net": "$auto_algae_net",
                    "processor": "$auto_algae_processor"
                },
                "teleop_algae_stats": {
                    "net": "$teleop_algae_net",
                    "processor": "$teleop_algae_processor"
                },
                # Calculate totals for each category
                "total_coral": {
                    "$add": [
                        "$auto_coral_level1", "$auto_coral_level2", 
                        "$auto_coral_level3", "$auto_coral_level4",
                        "$teleop_coral_level1", "$teleop_coral_level2", 
                        "$teleop_coral_level3", "$teleop_coral_level4"
                    ]
                },
                "total_auto_coral": {
                    "$add": [
                        "$auto_coral_level1", "$auto_coral_level2", 
                        "$auto_coral_level3", "$auto_coral_level4"
                    ]
                },
                "total_teleop_coral": {
                    "$add": [
                        "$teleop_coral_level1", "$teleop_coral_level2", 
                        "$teleop_coral_level3", "$teleop_coral_level4"
                    ]
                },
                "total_algae": {
                    "$add": [
                        "$auto_algae_net", "$auto_algae_processor",
                        "$teleop_algae_net", "$teleop_algae_processor"
                    ]
                },
                "total_auto_algae": {
                    "$add": ["$auto_algae_net", "$auto_algae_processor"]
                },
                "total_teleop_algae": {
                    "$add": ["$teleop_algae_net", "$teleop_algae_processor"]
                },
                "climb_success_rate": {
                    "$multiply": [
                        {"$cond": [
                            {"$gt": ["$climb_attempts", 0]},
                            {"$divide": ["$climb_successes", "$climb_attempts"]},
                            0
                        ]},
                        100
                    ]
                },
                "deep_climb_success_rate": {
                    "$multiply": [
                        {"$cond": [
                            {"$gt": ["$deep_climb_attempts", 0]},
                            {"$divide": ["$deep_climb_successes", "$deep_climb_attempts"]},
                            0
                        ]},
                        100
                    ]
                },
                "defense_rating": {"$round": ["$defense_rating", 1]},
                "mobility_rating": {"$round": ["$mobility_rating", 1]},
                "durability_rating": {"$round": ["$durability_rating", 1]}
            }}
        ])

        # Add sorting based on selected type
        sort_field = {
            'coral': 'total_coral',
            'auto_coral': 'total_auto_coral',
            'teleop_coral': 'total_teleop_coral',
            'algae': 'total_algae',
            'auto_algae': 'total_auto_algae',
            'teleop_algae': 'total_teleop_algae',
            'deep_climb': 'deep_climb_success_rate',
            'defense': 'defense_rating',
            'mobility': 'mobility_rating',
            'durability': 'durability_rating'
        }.get(sort_type, 'total_coral')

        if sort_type == 'deep_climb':
            pipeline.insert(-1, {
                "$match": {
                    "deep_climb_attempts": {"$gt": 0}
                }
            })

        pipeline.append({"$sort": {sort_field: -1}})
        teams = list(scouting_manager.db.team_data.aggregate(pipeline))
        current_app.logger.info(f"Successfully fetched leaderboard {teams} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return render_template("scouting/leaderboard.html", teams=teams, current_sort=sort_type, 
                              events=events, selected_event=selected_event)
    except Exception as e:
        current_app.logger.error(f"Error in leaderboard: {str(e)}", exc_info=True)
        return render_template("scouting/leaderboard.html", teams=[], current_sort='coral', 
                              events=[], selected_event='all')

@scouting_bp.route("/scouter-leaderboard")
# @limiter.limit("30 per minute")
@login_required
def scouter_leaderboard():
    try:
        sort_by = request.args.get('sort', 'match_count')
        selected_event = request.args.get('event', 'all')
        selected_team = request.args.get('team', 'all')
        
        # Get list of events for filtering
        events_pipeline = [
            {"$group": {"_id": "$event_code"}},
            {"$sort": {"_id": 1}}
        ]
        events = [evt["_id"] for evt in scouting_manager.db.team_data.aggregate(events_pipeline)]
        
        # Build pipeline to count scouting entries by user
        pipeline = [
            # Join with users to get scouter information
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
        ]
        
        # Apply event filter if specified
        if selected_event != 'all':
            pipeline.append({"$match": {"event_code": selected_event}})
            
        # Apply team filter if specified
        if selected_team != 'all' and selected_team.isdigit():
            pipeline.append({"$match": {"scouter.teamNumber": int(selected_team)}})
            
        # Group by scouter and count
        pipeline.extend([
            {
                "$group": {
                    "_id": "$scouter._id",
                    "username": {"$first": "$scouter.username"},
                    "teamNumber": {"$first": "$scouter.teamNumber"},
                    "match_count": {"$sum": 1},
                    "unique_teams": {"$addToSet": "$team_number"},
                }
            },
            {
                "$project": {
                    "username": 1,
                    "teamNumber": 1,
                    "match_count": 1,
                    "unique_teams_count": {"$size": "$unique_teams"},
                }
            }
        ])
        
        # Sort by selected field
        sort_field = {
            'match_count': 'match_count',
            'unique_teams': 'unique_teams_count',
        }.get(sort_by, 'match_count')
        
        pipeline.append({"$sort": {sort_field: -1}})
        
        # Execute query
        scouters = list(scouting_manager.db.team_data.aggregate(pipeline))
        
        # Get list of all teams for filtering
        teams_pipeline = [
            {"$lookup": {
                "from": "users",
                "localField": "scouter_id",
                "foreignField": "_id",
                "as": "scouter"
            }},
            {"$unwind": "$scouter"},
            {"$match": {"scouter.teamNumber": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$scouter.teamNumber"}},
            {"$sort": {"_id": 1}}
        ]
        teams = [team["_id"] for team in scouting_manager.db.team_data.aggregate(teams_pipeline)]
        
        current_app.logger.info(f"Successfully fetched scouter leaderboard {scouters} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
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

@scouting_bp.route("/scouting/matches")
# @limiter.limit("30 per minute")
@login_required
def matches():
    try:
        pipeline = [
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
            # Add team access filter
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }},
            {"$group": {
                "_id": {
                    "event": "$event_code",
                    "match": "$match_number"
                },
                "teams": {
                    "$push": {
                        "number": "$team_number",
                        "alliance": "$alliance",
                        # Auto period
                        "auto_coral_level1": {"$ifNull": ["$auto_coral_level1", 0]},
                        "auto_coral_level2": {"$ifNull": ["$auto_coral_level2", 0]},
                        "auto_coral_level3": {"$ifNull": ["$auto_coral_level3", 0]},
                        "auto_coral_level4": {"$ifNull": ["$auto_coral_level4", 0]},
                        "auto_algae_net": {"$ifNull": ["$auto_algae_net", 0]},
                        "auto_algae_processor": {"$ifNull": ["$auto_algae_processor", 0]},
                        # Teleop period
                        "teleop_coral_level1": {"$ifNull": ["$teleop_coral_level1", 0]},
                        "teleop_coral_level2": {"$ifNull": ["$teleop_coral_level2", 0]},
                        "teleop_coral_level3": {"$ifNull": ["$teleop_coral_level3", 0]},
                        "teleop_coral_level4": {"$ifNull": ["$teleop_coral_level4", 0]},
                        "teleop_algae_net": {"$ifNull": ["$teleop_algae_net", 0]},
                        "teleop_algae_processor": {"$ifNull": ["$teleop_algae_processor", 0]},
                        "climb_type": "$climb_type",
                        "climb_success": "$climb_success"
                    }
                },
            }}
        ]
        
        match_data = list(scouting_manager.db.team_data.aggregate(pipeline))
        matches = []
        
        for match in match_data:
            red_teams = [t for t in match["teams"] if t["alliance"] == "red"]
            blue_teams = [t for t in match["teams"] if t["alliance"] == "blue"]
            
            # Calculate alliance totals
            red_coral = {
                "level1": sum(t["auto_coral_level1"] + t["teleop_coral_level1"] for t in red_teams),
                "level2": sum(t["auto_coral_level2"] + t["teleop_coral_level2"] for t in red_teams),
                "level3": sum(t["auto_coral_level3"] + t["teleop_coral_level3"] for t in red_teams),
                "level4": sum(t["auto_coral_level4"] + t["teleop_coral_level4"] for t in red_teams)
            }
            
            red_algae = {
                "net": sum(t["auto_algae_net"] + t["teleop_algae_net"] for t in red_teams),
                "processor": sum(t["auto_algae_processor"] + t["teleop_algae_processor"] for t in red_teams)
            }
            
            blue_coral = {
                "level1": sum(t["auto_coral_level1"] + t["teleop_coral_level1"] for t in blue_teams),
                "level2": sum(t["auto_coral_level2"] + t["teleop_coral_level2"] for t in blue_teams),
                "level3": sum(t["auto_coral_level3"] + t["teleop_coral_level3"] for t in blue_teams),
                "level4": sum(t["auto_coral_level4"] + t["teleop_coral_level4"] for t in blue_teams)
            }
            
            blue_algae = {
                "net": sum(t["auto_algae_net"] + t["teleop_algae_net"] for t in blue_teams),
                "processor": sum(t["auto_algae_processor"] + t["teleop_algae_processor"] for t in blue_teams)
            }
            
            # Prepare team data for template
            red_team_data = [{
                "number": t["number"],
                "coral_level1": t["auto_coral_level1"] + t["teleop_coral_level1"],
                "coral_level2": t["auto_coral_level2"] + t["teleop_coral_level2"],
                "coral_level3": t["auto_coral_level3"] + t["teleop_coral_level3"],
                "coral_level4": t["auto_coral_level4"] + t["teleop_coral_level4"],
                "algae_net": t["auto_algae_net"] + t["teleop_algae_net"],
                "algae_processor": t["auto_algae_processor"] + t["teleop_algae_processor"],
                "climb_type": t["climb_type"],
                "climb_success": t["climb_success"]
            } for t in red_teams]

            blue_team_data = [{
                "number": t["number"],
                "coral_level1": t["auto_coral_level1"] + t["teleop_coral_level1"],
                "coral_level2": t["auto_coral_level2"] + t["teleop_coral_level2"],
                "coral_level3": t["auto_coral_level3"] + t["teleop_coral_level3"],
                "coral_level4": t["auto_coral_level4"] + t["teleop_coral_level4"],
                "algae_net": t["auto_algae_net"] + t["teleop_algae_net"],
                "algae_processor": t["auto_algae_processor"] + t["teleop_algae_processor"],
                "climb_type": t["climb_type"],
                "climb_success": t["climb_success"]
            } for t in blue_teams]

            matches.append({
                "event_code": match["_id"]["event"],
                "match_number": match["_id"]["match"],
                "red_teams": red_team_data,
                "blue_teams": blue_team_data,
                "red_coral": red_coral,
                "red_algae": red_algae,
                "blue_coral": blue_coral,
                "blue_algae": blue_algae
            })
        current_app.logger.info(f"Successfully fetched matches {matches} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return render_template("scouting/matches.html", matches=matches)

    except Exception as e:
        current_app.logger.error(f"Error fetching matches: {str(e)}", exc_info=True)
        flash("An internal error has occurred.", "error")
        return render_template("scouting/matches.html", matches=[])

@scouting_bp.route("/scouting/check_team")
@login_required
def check_team():
    team_number = request.args.get('team')
    event_code = request.args.get('event')
    match_number = request.args.get('match')
    current_id = request.args.get('current_id')
    
    try:
        # Get current user's team number
        current_user_team = current_user.teamNumber

        pipeline = [
            {
                "$match": {
                    "team_number": int(team_number),
                    "event_code": event_code,
                    "match_number": match_number  # Keep as string, don't convert to int
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": "$scouter"},
        ]
        
        if current_id:
            pipeline[0]["$match"]["_id"] = {"$ne": ObjectId(current_id)}
            
        existing = list(scouting_manager.db.team_data.aggregate(pipeline))
        
        # Check if any existing entry is from the same team
        exists = any(entry.get("scouter", {}).get("teamNumber") == current_user_team 
                    for entry in existing)
        
        return jsonify({"exists": exists})
    except Exception as e:
        current_app.logger.error(f"Error checking team data: {str(e)}", exc_info=True)
        return jsonify({"error": "An internal error has occurred."}), 500

@scouting_bp.route("/scouting/pit")
@login_required
# @limiter.limit("50 per minute")
def pit_scouting():
    try:
        # Update to use filtered pit scouting data
        pit_data_list = list(scouting_manager.get_all_pit_scouting(
            current_user.teamNumber,
            current_user.get_id()
        ))
        current_app.logger.info(f"Successfully fetched pit scouting data {pit_data_list} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return render_template("scouting/pit-scouting.html", pit_data=pit_data_list)
    except Exception as e:
        current_app.logger.error(f"Error fetching pit scouting data: {str(e)}", exc_info=True)
        flash("An internal error has occurred.", "error")
        return render_template("scouting/pit-scouting.html", pit_data=[])

@scouting_bp.route("/scouting/pit/add", methods=["GET", "POST"])
@login_required
# @limiter.limit("15 per minute")
def pit_scouting_add():
    if request.method == "POST":
        try:
            current_app.logger.info(f"Scouting.add Form Details {request.form}")
            # Process form data
            pit_data = {
                "team_number": int(request.form.get("team_number")),
                "scouter_id": current_user.id,
                
                # Drive base information
                "drive_type": {
                    "swerve": "swerve" in request.form.getlist("drive_type"),
                    "tank": "tank" in request.form.getlist("drive_type"),
                    "other": request.form.get("drive_type_other", "")
                },
                "swerve_modules": request.form.get("swerve_modules", ""),
                
                # Motor details
                "motor_details": {
                    "falcons": "falcons" in request.form.getlist("motors"),
                    "neos": "neos" in request.form.getlist("motors"),
                    "krakens": "krakens" in request.form.getlist("motors"),
                    "vortex": "vortex" in request.form.getlist("motors"),
                    "other": request.form.get("motors_other", "")
                },
                "motor_count": int(request.form.get("motor_count", 0) if not (request.form.get("motor_count") == '') else 0),
                
                # Dimensions
                "dimensions": {
                    "length": float(request.form.get("length", 0) if not (request.form.get("length") == '') else 0),
                    "width": float(request.form.get("width", 0) if not (request.form.get("width") == '') else 0),
                    "height": float(request.form.get("height", 0) if not (request.form.get("height") == '') else 0)
                },
                
                # Mechanisms
                "mechanisms": {
                    "coral_scoring": {
                        "enabled": request.form.get("coral_scoring_enabled") == "true",
                        "notes": request.form.get("coral_scoring_notes", "") if request.form.get("coral_scoring_enabled") == "true" else ""
                    },
                    "algae_scoring": {
                        "enabled": request.form.get("algae_scoring_enabled") == "true",
                        "notes": request.form.get("algae_scoring_notes", "") if request.form.get("algae_scoring_enabled") == "true" else ""
                    },
                    "climber": {
                        "has_climber": "has_climber" in request.form,
                        "type_climber": request.form.get("climber_type", ""),
                        "notes": request.form.get("climber_notes", "")
                    }
                },
                
                # Programming and Autonomous
                "programming_language": request.form.get("programming_language", ""),
                "autonomous_capabilities": {
                    "has_auto": request.form.get("has_auto") == "true",
                    "num_routes": int(request.form.get("auto_routes", 0) if not (request.form.get("auto_routes") == '') else 0) if request.form.get("has_auto") == "true" else 0,
                    "preferred_start": request.form.get("auto_preferred_start", "") if request.form.get("has_auto") == "true" else "",
                    "notes": request.form.get("auto_notes", "") if request.form.get("has_auto") == "true" else ""
                },
                
                # Driver Experience
                "driver_experience": {
                    "years": int(request.form.get("years", 0) if not (request.form.get("years") == '') else 0),
                    "notes": request.form.get("driver_notes", "")
                },
                
                # General Notes
                "notes": request.form.get("notes", ""),
                
                # Timestamps
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            # Add to database
            if scouting_manager.add_pit_scouting(pit_data):
                current_app.logger.info(f"Successfully added pit scouting data {pit_data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                flash("Pit scouting data added successfully!", "success")
                return redirect(url_for("scouting.pit_scouting"))
            else:
                current_app.logger.info(f"Failed to add pit scouting data {pit_data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                flash("Error adding pit scouting data. Please try again.", "error")
        except Exception as e:
            flash("An error occurred while adding pit scouting data.", "error")
            current_app.logger.error(f"Error adding pit scouting data: {str(e)}", exc_info=True)
            return redirect(url_for("scouting.pit_scouting"))

    return render_template("scouting/pit-scouting-add.html")

@scouting_bp.route("/scouting/pit/edit/<int:team_number>", methods=["GET", "POST"])
@login_required
# @limiter.limit("10 per minute")
def pit_scouting_edit(team_number):
    pit_data = scouting_manager.get_pit_scouting(team_number)
    if not pit_data:
        flash("Pit scouting data not found", "error")
        return redirect(url_for("scouting.pit_scouting"))

    if str(pit_data["scouter_id"]) != current_user.get_id():
        flash("You don't have permission to edit this data", "error")
        return redirect(url_for("scouting.pit_scouting"))
    
    if request.method == "POST":
        try:
            current_app.logger.info(f"Scouting.edit Form Details {request.form}")
            data = {
                "team_number": int(request.form["team_number"]),
                "scouter_id": ObjectId(current_user.get_id()),
                "drive_type": {
                    "swerve": "swerve" in request.form.getlist("drive_type"),
                    "tank": "tank" in request.form.getlist("drive_type"),
                    "other": request.form.get("drive_type_other", "")
                },
                "swerve_modules": request.form.get("swerve_modules", ""),
                "motor_details": {
                    "falcons": "falcons" in request.form.getlist("motors"),
                    "neos": "neos" in request.form.getlist("motors"),
                    "krakens": "krakens" in request.form.getlist("motors"),
                    "vortex": "vortex" in request.form.getlist("motors"),
                    "other": request.form.get("motors_other", "")
                },
                "motor_count": int(request.form.get("motor_count", 0)),
                "dimensions": {
                    "length": float(request.form.get("length", 0)),
                    "width": float(request.form.get("width", 0)),
                    "height": float(request.form.get("height", 0))
                },
                "mechanisms": {
                    "coral_scoring": {
                        "enabled": request.form.get("coral_scoring_enabled") == "true",
                        "notes": request.form.get("coral_scoring_notes", "") if request.form.get("coral_scoring_enabled") == "true" else ""
                    },
                    "algae_scoring": {
                        "enabled": request.form.get("algae_scoring_enabled") == "true",
                        "notes": request.form.get("algae_scoring_notes", "") if request.form.get("algae_scoring_enabled") == "true" else ""
                    },
                    "climber": {
                        "has_climber": "has_climber" in request.form,
                        "type_climber": request.form.get("climber_type", ""),
                        "notes": request.form.get("climber_notes", "")
                    }
                },
                "programming_language": request.form.get("programming_language", ""),
                "autonomous_capabilities": {
                    "has_auto": request.form.get("has_auto") == "true",
                    "num_routes": int(request.form.get("auto_routes", 0)) if request.form.get("has_auto") == "true" else 0,
                    "preferred_start": request.form.get("auto_preferred_start", "") if request.form.get("has_auto") == "true" else "",
                    "notes": request.form.get("auto_notes", "") if request.form.get("has_auto") == "true" else ""
                },
                "driver_experience": {
                    "years": int(request.form.get("driver_years", 0)),
                    "notes": request.form.get("driver_notes", "")
                },
                "notes": request.form.get("notes", ""),
                "updated_at": datetime.now(timezone.utc)
            }
            
            if scouting_manager.update_pit_scouting(team_number, data, current_user.get_id()):
                current_app.logger.info(f"Successfully updated pit scouting data {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                flash("Pit scouting data updated successfully", "success")
                return redirect(url_for("scouting.pit_scouting"))
            else:
                current_app.logger.info(f"Failed to update pit scouting data {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                flash("Error updating pit scouting data", "error")
        except Exception as e:
            current_app.logger.info(f"Error updating pit scouting data {data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'} {str(e)}", exc_info=True)
            flash("An internal error has occurred.", "error")

    return render_template("scouting/pit-scouting-edit.html", pit_data=pit_data)

@scouting_bp.route("/scouting/pit/delete/<int:team_number>")
@login_required
def pit_scouting_delete(team_number):
    if scouting_manager.delete_pit_scouting(team_number, current_user.get_id()):
        current_app.logger.info(f"Successfully deleted pit scouting data {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        flash("Pit scouting data deleted successfully", "success")
    else:
        current_app.logger.info(f"Failed to delete pit scouting data {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        flash("Error deleting pit scouting data", "error")
    return redirect(url_for("scouting.pit_scouting"))

@scouting_bp.route("/api/tba/events")
@login_required
# @limiter.limit("30 per minute")
def get_tba_events():
    try:
        year = datetime.now().year
        tba = TBAInterface()
        events = tba.get_current_events(year)
        current_app.logger.info(f"Successfully fetched TBA events {events} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return jsonify(events)
    except Exception as e:
        current_app.logger.error(f"Error getting TBA events: {e}")
        return jsonify({"error": "Failed to fetch events"}), 500

@scouting_bp.route("/api/tba/matches/<event_key>")
@login_required
# @limiter.limit("30 per minute")
def get_tba_matches(event_key):
    try:
        tba = TBAInterface()
        matches = tba.get_event_matches(event_key)
        current_app.logger.info(f"Successfully fetched TBA matches {matches} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return jsonify(matches)
    except Exception as e:
        current_app.logger.error(f"Error getting TBA matches: {e}")
        return jsonify({"error": "Failed to fetch matches"}), 500

@scouting_bp.route("/scouting/live-match-status", methods=["GET"])
@login_required
# @limiter.limit("30 per minute")
def live_match_status():
    """Route for the live team schedule modal"""
    team_number = request.args.get('team')
    event_code = request.args.get('event')
    
    # Default to empty context data
    context = {
        'team_number': team_number,
        'event_code': event_code
    }
    current_app.logger.info(f"Successfully fetched live match status {context} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return render_template("scouting/live-match-status.html", **context)

@scouting_bp.route("/api/tba/team-status")
@login_required
# @limiter.limit("30 per minute")
def get_team_status():
    """Get team status at an event including ranking and matches"""
    team_number = request.args.get('team')
    event_code = request.args.get('event')
    
    if not team_number:
        return jsonify({"error": "Team number is required"}), 400
    
    try:
        # Format TBA team key
        team_key = f"frc{team_number}"
        
        # Initialize TBA interface
        tba = TBAInterface()
        
        # If event code not provided, find the most recent event
        if not event_code:
            most_recent_event = tba.get_most_recent_active_event(team_key)
            if most_recent_event:
                event_code = most_recent_event.get('key')
                # Also return event details for the UI
                event_name = most_recent_event.get('name', 'Unknown Event')
            else:
                return jsonify({"error": "No events found for this team"}), 404
        
        # Get team status at event (ranking)
        status = tba.get_team_status_at_event(team_key, event_code)
        
        # Get team matches at event
        matches = tba.get_team_matches_at_event(team_key, event_code)
        current_app.logger.info(f"Successfully fetched team status {status} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

        return jsonify({
            "status": status,
            "matches": matches,
            "event": {
                "key": event_code,
                "name": event_name if 'event_name' in locals() else None
            }
        })
    except Exception as e:
        logger.error(f"Error getting team status: {e}")
        return jsonify({"error": "Failed to fetch team status"}), 500

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
            {"$lookup": {
                "from": "users",
                "localField": "scouter_id",
                "foreignField": "_id",
                "as": "scouter"
            }},
            {"$unwind": {"path": "$scouter", "preserveNullAndEmptyArrays": True}},
            # Add team access filter
            {"$match": {
                "$or": [
                    {"scouter.teamNumber": current_user.teamNumber} if current_user.teamNumber else {"scouter._id": ObjectId(current_user.get_id())},
                    {"scouter._id": ObjectId(current_user.get_id())}
                ]
            }},
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
        paths = list(scouting_manager.db.team_data.aggregate(pipeline))
        
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
        
        current_app.logger.info(f"Successfully fetched team paths {response} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return json_util.dumps(response), 200, {'Content-Type': 'application/json'}
        
    except Exception as e:
        current_app.logger.error(f"Error fetching team paths: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch team path data."}), 500
