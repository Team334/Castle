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

    # TODO: 2026

    return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/list")
@scouting_bp.route("/scouting")
# @limiter.limit("30 per minute")
@login_required
def home():
    # TODO: 2026

@scouting_bp.route("/scouting/edit/<string:id>", methods=["GET", "POST"])
# @limiter.limit("15 per minute")
@login_required
def edit(id):
    # TODO: 2026


@scouting_bp.route("/scouting/delete/<string:id>")
# @limiter.limit("10 per minute")
@login_required
def delete(id):
    # TODO: 2026


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

        # TODO: 2026

    except Exception as e:
        ...

@scouting_bp.route("/leaderboard")
# @limiter.limit("30 per minute")
def leaderboard():
    # TODO: 2026

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
    # TODO: 2026


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
def pit_scouting_add():
    if request.method == "POST":
        try:
            current_app.logger.info(f"Scouting.add Form Details {request.form}")
            # Process form data
            pit_data = {
                "team_number": int(request.form.get("team_number")),
                "scouter_id": current_user.id,
                "drive_type": {
                    "swerve": "swerve" in request.form.getlist("drive_type"),
                    "tank": "tank" in request.form.getlist("drive_type"),
                    "other": request.form.get("drive_type_other", ""),
                },
                "swerve_modules": request.form.get("swerve_modules", ""),
                "motor_details": {
                    "falcons": "falcons" in request.form.getlist("motors"),
                    "neos": "neos" in request.form.getlist("motors"),
                    "krakens": "krakens" in request.form.getlist("motors"),
                    "vortex": "vortex" in request.form.getlist("motors"),
                    "other": request.form.get("motors_other", ""),
                },
                "motor_count": int(
                    request.form.get("motor_count", 0)
                    if request.form.get("motor_count") != ''
                    else 0
                ),
                "dimensions": {
                    "length": float(
                        request.form.get("length", 0)
                        if request.form.get("length") != ''
                        else 0
                    ),
                    "width": float(
                        request.form.get("width", 0)
                        if request.form.get("width") != ''
                        else 0
                    ),
                    "height": float(
                        request.form.get("height", 0)
                        if request.form.get("height") != ''
                        else 0
                    ),
                },
                "mechanisms": {
                    "coral_scoring": {
                        "enabled": request.form.get("coral_scoring_enabled")
                        == "true",
                        "notes": (
                            request.form.get("coral_scoring_notes", "")
                            if request.form.get("coral_scoring_enabled")
                            == "true"
                            else ""
                        ),
                    },
                    "algae_scoring": {
                        "enabled": request.form.get("algae_scoring_enabled")
                        == "true",
                        "notes": (
                            request.form.get("algae_scoring_notes", "")
                            if request.form.get("algae_scoring_enabled")
                            == "true"
                            else ""
                        ),
                    },
                    "climber": {
                        "has_climber": "has_climber" in request.form,
                        "type_climber": request.form.get("climber_type", ""),
                        "notes": request.form.get("climber_notes", ""),
                    },
                },
                "programming_language": request.form.get(
                    "programming_language", ""
                ),
                "autonomous_capabilities": {
                    "has_auto": request.form.get("has_auto") == "true",
                    "num_routes": (
                        int(
                            request.form.get("auto_routes", 0)
                            if request.form.get("auto_routes") != ''
                            else 0
                        )
                        if request.form.get("has_auto") == "true"
                        else 0
                    ),
                    "preferred_start": (
                        request.form.get("auto_preferred_start", "")
                        if request.form.get("has_auto") == "true"
                        else ""
                    ),
                    "notes": (
                        request.form.get("auto_notes", "")
                        if request.form.get("has_auto") == "true"
                        else ""
                    ),
                },
                "driver_experience": {
                    "years": int(
                        request.form.get("years", 0)
                        if request.form.get("years") != ''
                        else 0
                    ),
                    "notes": request.form.get("driver_notes", ""),
                },
                "notes": request.form.get("notes", ""),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
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
