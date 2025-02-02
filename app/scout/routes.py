from __future__ import annotations

import json
from datetime import datetime, timezone

import aiohttp
from bson import ObjectId, json_util
from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from app.models import PitScouting
from app.scout.scouting_utils import ScoutingManager
from app.utils import async_route, handle_route_errors, limiter

from .TBA import TBAInterface

scouting_bp = Blueprint("scouting", __name__)
scouting_manager = None


@scouting_bp.record
def on_blueprint_init(state):
    global scouting_manager, limiter
    app = state.app
    scouting_manager = ScoutingManager(app.config["MONGO_URI"])


@scouting_bp.route("/scouting/add", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per minute")
@handle_route_errors
def add():
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form.to_dict()
        success, message = scouting_manager.add_scouting_data(data, current_user.get_id())
        
        if success:
            flash("Team data added successfully", "success")
        else:
            flash(f"Error adding data: {message}", "error")
            
        return redirect(url_for("scouting.home"))
        
    return render_template("scouting/add.html")


@scouting_bp.route("/scouting/list")
@scouting_bp.route("/scouting")
@limiter.limit("30 per minute")
@login_required
def home():
    try:
        team_data = scouting_manager.get_all_scouting_data()
        return render_template("scouting/list.html", team_data=team_data)
    except Exception as e:
        current_app.logger.error(f"Error fetching scouting data: {str(e)}", exc_info=True)
        flash("Unable to fetch scouting data. Please try again later.", "error")
        return render_template("scouting/list.html", team_data=[])


@scouting_bp.route("/scouting/edit/<string:id>", methods=["GET", "POST"])
@limiter.limit("10 per minute")
@login_required
def edit(id):
    try:
        team_data = scouting_manager.get_team_data(id, current_user.get_id())

        if not team_data:
            flash("Team data not found", "error")
            return redirect(url_for("scouting.home"))

        if not team_data.is_owner:
            flash("Access denied", "error")
            return redirect(url_for("scouting.home"))

        if request.method == "POST":
            if scouting_manager.update_team_data(id, request.form, current_user.get_id()):
                flash("Data updated successfully", "success")
                return redirect(url_for("scouting.home"))
            flash("Unable to update data", "error")

        return render_template("scouting/edit.html", team_data=team_data)
    except Exception as e:
        current_app.logger.error(f"Error in edit_scouting_data: {str(e)}", exc_info=True)
        flash("An error occurred while processing your request", "error")
        return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/delete/<string:id>")
@limiter.limit("5 per minute")
@login_required
def delete(id):
    try:
        if scouting_manager.delete_team_data(id, current_user.get_id()):
            flash("Record deleted successfully", "success")
        else:
            flash("Error deleting record or permission denied", "error")
    except Exception as e:
        flash("An internal error has occurred.", "error")
    return redirect(url_for("scouting.home"))


@scouting_bp.route("/compare")
@limiter.limit("30 per minute")
@login_required
def compare():
    return render_template("compare.html")

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
        "human_player": stats.get("avg_human_player", 0),
        "climb_success_rate": stats.get("climb_success_rate", 0) * 100
    }


@scouting_bp.route("/api/compare")
@limiter.limit("30 per minute")
@login_required
def compare_teams():
    try:
        teams = []
        for i in range(1, 4):  # Support up to 3 teams
            if team_num := request.args.get(f'team{i}'):
                teams.append(team_num)

        if len(teams) < 2:
            return jsonify({"error": "At least 2 teams are required"}), 400

        teams_data = {}
        for team_num in teams:
            try:
                # Get team stats from database
                pipeline = [
                    {"$match": {"team_number": int(team_num)}},
                    {"$group": {
                        "_id": "$team_number",
                        "matches_played": {"$sum": 1},
                        "auto_coral_level1": {"$avg": {"$ifNull": ["$auto_coral_level1", 0]}},
                        "auto_coral_level2": {"$avg": {"$ifNull": ["$auto_coral_level2", 0]}},
                        "auto_coral_level3": {"$avg": {"$ifNull": ["$auto_coral_level3", 0]}},
                        "auto_coral_level4": {"$avg": {"$ifNull": ["$auto_coral_level4", 0]}},
                        "auto_algae_net": {"$avg": {"$ifNull": ["$auto_algae_net", 0]}},
                        "auto_algae_processor": {"$avg": {"$ifNull": ["$auto_algae_processor", 0]}},
                        "teleop_coral_level1": {"$avg": {"$ifNull": ["$teleop_coral_level1", 0]}},
                        "teleop_coral_level2": {"$avg": {"$ifNull": ["$teleop_coral_level2", 0]}},
                        "teleop_coral_level3": {"$avg": {"$ifNull": ["$teleop_coral_level3", 0]}},
                        "teleop_coral_level4": {"$avg": {"$ifNull": ["$teleop_coral_level4", 0]}},
                        "teleop_algae_net": {"$avg": {"$ifNull": ["$teleop_algae_net", 0]}},
                        "teleop_algae_processor": {"$avg": {"$ifNull": ["$teleop_algae_processor", 0]}},
                        "auto_path": {"$last": "$auto_path"},
                        "climb_success_rate": {
                            "$avg": {"$cond": [{"$eq": ["$climb_success", True]}, 100, 0]}
                        },
                        "preferred_climb_type": {"$last": "$climb_type"},
                        "total_coral": {"$sum": {
                            "$add": [
                                "$auto_coral_level1", "$auto_coral_level2",
                                "$auto_coral_level3", "$auto_coral_level4",
                                "$teleop_coral_level1", "$teleop_coral_level2",
                                "$teleop_coral_level3", "$teleop_coral_level4"
                            ]
                        }},
                        "total_algae": {"$sum": {
                            "$add": [
                                "$auto_algae_net", "$auto_algae_processor",
                                "$teleop_algae_net", "$teleop_algae_processor"
                            ]
                        }},
                        "human_player": {"$avg": "$human_player"},
                        "defense_rating": {"$avg": "$defense_rating"},
                        "successful_climbs": {
                            "$sum": {"$cond": ["$climb_success", 1, 0]}
                        },
                    }}
                ]

                stats = list(scouting_manager.db.team_data.aggregate(pipeline))

                # Get the 5 most recent matches and convert ObjectId to string
                matches = list(scouting_manager.db.team_data.aggregate([
                    {"$match": {"team_number": int(team_num)}},
                    {
                        "$lookup": {
                            "from": "users",
                            "localField": "scouter_id",
                            "foreignField": "_id",
                            "as": "scouter"
                        }
                    },
                    {"$unwind": {
                        "path": "$scouter",
                        "preserveNullAndEmptyArrays": True
                    }},
                    {"$sort": {"match_number": -1}},
                    {"$limit": 5},
                    {
                        "$project": {
                            "_id": 1,
                            "team_number": 1,
                            "match_number": 1,
                            "event_code": 1,
                            "alliance": 1,
                            "auto_coral_level1": 1,
                            "auto_coral_level2": 1,
                            "auto_coral_level3": 1,
                            "auto_coral_level4": 1,
                            "auto_algae_net": 1,
                            "auto_algae_processor": 1,
                            "teleop_coral_level1": 1,
                            "teleop_coral_level2": 1,
                            "teleop_coral_level3": 1,
                            "teleop_coral_level4": 1,
                            "teleop_algae_net": 1,
                            "teleop_algae_processor": 1,
                            "human_player": 1,
                            "climb_type": 1,
                            "climb_success": 1,
                            "defense_rating": 1,
                            "auto_path": 1,
                            "auto_notes": 1,
                            "notes": 1,
                            "scouter_name": "$scouter.username",
                            "scouter_team": "$scouter.teamNumber",
                            "profile_picture": "$scouter.profile_picture"
                        }
                    }
                ]))

                # Convert ObjectId to string in matches
                for match in matches:
                    match['_id'] = str(match['_id'])

                # Get team info from TBA
                team_key = f"frc{team_num}"
                team_info = TBAInterface().get_team(team_key)

                # Get auto paths
                auto_paths = scouting_manager.get_auto_paths(team_num)

                # Calculate normalized stats for radar chart
                if stats and stats[0]["matches_played"] > 0:
                    matches_played = stats[0]["matches_played"]
                    normalized_stats = {
                        "auto_scoring": (stats[0]["total_coral"] / matches_played) / 20,
                        "teleop_scoring": (stats[0]["total_algae"] / matches_played) / 20,
                        "climb_rating": (stats[0]["successful_climbs"] / matches_played) / 20,
                        "defense_rating": stats[0]["defense_rating"],
                        "human_player": stats[0]["human_player"]
                    }
                else:
                    normalized_stats = {
                        "auto_scoring": 0,
                        "teleop_scoring": 0,
                        "climb_rating": 0,
                        "defense_rating": 0,
                        "human_player": 0
                    }

                # Convert ObjectId in stats
                if stats and '_id' in stats[0]:
                    stats[0]['_id'] = str(stats[0]['_id'])

                teams_data[team_num] = {
                    "team_number": int(team_num),
                    "nickname": team_info.get("nickname", "Unknown"),
                    "school_name": team_info.get("school_name"),
                    "city": team_info.get("city"),
                    "state_prov": team_info.get("state_prov"),
                    "country": team_info.get("country"),
                    "stats": stats[0] if stats else {},
                    "normalized_stats": normalized_stats,
                    "matches": matches,
                    "auto_paths": auto_paths,
                }

            except Exception as team_error:
                # print(f"Error processing team {team_num}: {str(team_error)}")
                teams_data[team_num] = {
                    "team_number": int(team_num),
                    "error": str(team_error)
                }

        return json.loads(json_util.dumps(teams_data))

    except Exception as e:
        # print(f"Error in compare_teams: {str(e)}")
        return jsonify({"error": "An error occurred while comparing teams"}), 500

@scouting_bp.route("/search")
@login_required
@limiter.limit("30 per minute")
def search():
    return render_template("search.html")


@scouting_bp.route("/api/search")
@login_required
@limiter.limit("30 per minute")
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
            {
                "$lookup": {
                    "from": "users",
                    "localField": "scouter_id",
                    "foreignField": "_id",
                    "as": "scouter"
                }
            },
            {"$unwind": {"path": "$scouter", "preserveNullAndEmptyArrays": True}},
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
                    "human_player": {"$ifNull": ["$human_player", 0]},
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
        return json_util.dumps(response_data), 200, {'Content-Type': 'application/json'}

    except Exception as e:
        current_app.logger.error(f"Error in search_teams: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch team data due to an internal error."}), 500

@scouting_bp.route("/leaderboard")
@limiter.limit("30 per minute")
def leaderboard():
    try:
        MIN_MATCHES = 1
        sort_type = request.args.get('sort', 'coral')
        
        pipeline = [
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

                # Human Player
                "human_player": {"$avg": {"$ifNull": ["$human_player", 0]}},
                
                # Defense Rating
                "defense_rating": {"$avg": {"$ifNull": ["$defense_rating", 0]}},

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
                "human_player": {"$round": ["$human_player", 1]},
                "defense_rating": {"$round": ["$defense_rating", 1]}
            }}
        ]

        # Add sorting based on selected type
        sort_field = {
            'coral': 'total_coral',
            'auto_coral': 'total_auto_coral',
            'teleop_coral': 'total_teleop_coral',
            'algae': 'total_algae',
            'auto_algae': 'total_auto_algae',
            'teleop_algae': 'total_teleop_algae',
            'deep_climb': 'deep_climb_success_rate',
            'human_player': 'human_player',
            'defense': 'defense_rating'
        }.get(sort_type, 'total_coral')

        if sort_type == 'deep_climb':
            pipeline.insert(-1, {
                "$match": {
                    "deep_climb_attempts": {"$gt": 0}
                }
            })

        pipeline.append({"$sort": {sort_field: -1}})

        teams = list(scouting_manager.db.team_data.aggregate(pipeline))
        return render_template("scouting/leaderboard.html", teams=teams, current_sort=sort_type)
    except Exception as e:
        # print(f"Error in leaderboard: {str(e)}")
        return render_template("scouting/leaderboard.html", teams=[], current_sort='coral')


@scouting_bp.route("/scouting/matches")
@limiter.limit("30 per minute")
@login_required
def matches():
    try:
        pipeline = [
            {
                "$group": {
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
                            "human_player": {"$ifNull": ["$human_player", 0]},
                            "climb_type": "$climb_type",
                            "climb_success": "$climb_success"
                        }
                    },
                    "red_human_player": {
                        "$avg": {
                            "$cond": [
                                {"$eq": ["$alliance", "red"]},
                                "$human_player",
                                None
                            ]
                        }
                    },
                    "blue_human_player": {
                        "$avg": {
                            "$cond": [
                                {"$eq": ["$alliance", "blue"]},
                                "$human_player",
                                None
                            ]
                        }
                    }
                }
            },
            {"$sort": {"_id.event": 1, "_id.match": 1}}
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
                "human_player": t["human_player"],
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
                "human_player": t["human_player"],
                "climb_type": t["climb_type"],
                "climb_success": t["climb_success"]
            } for t in blue_teams]
            
            # Update alliance data structure
            red_algae["human_player"] = match["red_human_player"] or 0
            blue_algae["human_player"] = match["blue_human_player"] or 0

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
    current_id = request.args.get('current_id')  # ID of the entry being edited
    
    try:
        query = {
            "team_number": int(team_number),
            "event_code": event_code,
            "match_number": int(match_number)
        }
        
        # If editing, exclude the current entry from the check
        if current_id:
            query["_id"] = {"$ne": ObjectId(current_id)}
            
        existing = scouting_manager.db.team_data.find_one(query)
        
        return jsonify({"exists": existing is not None})
    except Exception as e:
        current_app.logger.error(f"Error checking team data: {str(e)}", exc_info=True)
        return jsonify({"error": "An internal error has occurred."}), 500

@scouting_bp.route("/scouting/pit")
@login_required
@limiter.limit("30 per minute")
def pit_scouting():
    try:
        pit_data_list = list(scouting_manager.get_all_pit_scouting())
        return render_template("scouting/pit-scouting.html", pit_data=pit_data_list)
    except Exception as e:
        current_app.logger.error(f"Error fetching pit scouting data: {str(e)}", exc_info=True)
        flash("An internal error has occurred.", "error")
        return render_template("scouting/pit-scouting.html", pit_data=[])

@scouting_bp.route("/scouting/pit/add", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per minute")
def pit_scouting_add():
    if request.method == "POST":
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
            "motor_count": int(request.form.get("motor_count", 0)),
            
            # Dimensions
            "dimensions": {
                "length": float(request.form.get("length", 0)),
                "width": float(request.form.get("width", 0)),
                "height": float(request.form.get("height", 0))
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
                "num_routes": int(request.form.get("auto_routes", 0)) if request.form.get("has_auto") == "true" else 0,
                "preferred_start": request.form.get("auto_preferred_start", "") if request.form.get("has_auto") == "true" else "",
                "notes": request.form.get("auto_notes", "") if request.form.get("has_auto") == "true" else ""
            },
            
            # Driver Experience
            "driver_experience": {
                "years": int(request.form.get("driver_years", 0)),
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
            flash("Pit scouting data added successfully!", "success")
            return redirect(url_for("scouting.pit_scouting"))
        else:
            flash("Error adding pit scouting data. Please try again.", "error")

    return render_template("scouting/pit-scouting-add.html")

@scouting_bp.route("/scouting/pit/edit/<int:team_number>", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per minute")
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
                flash("Pit scouting data updated successfully", "success")
                return redirect(url_for("scouting.pit_scouting"))
            else:
                flash("Error updating pit scouting data", "error")
        except Exception as e:
            flash("An internal error has occurred.", "error")

    return render_template("scouting/pit-scouting-edit.html", pit_data=pit_data)

@scouting_bp.route("/scouting/pit/delete/<int:team_number>")
@limiter.limit("5 per minute")
@login_required
def pit_scouting_delete(team_number):
    if scouting_manager.delete_pit_scouting(team_number, current_user.get_id()):
        flash("Pit scouting data deleted successfully", "success")
    else:
        flash("Error deleting pit scouting data", "error")
    return redirect(url_for("scouting.pit_scouting"))

@scouting_bp.route("/submit_report", methods=["POST"])
@login_required
def submit_report():
    try:
        data = {
            "data_id": request.form.get("data_id"),
            "report_type": request.form.get("report_type"),
            "reason": request.form.get("reason"),
            "details": request.form.get("details"),
            "reporter_id": current_user.get_id()
        }
        
        if not all([data["data_id"], data["report_type"], 
                   data["reason"], data["details"]]):
            return jsonify({
                "success": False,
                "message": "All fields are required"
            }), 400
            
        success, message = scouting_manager.add_report(data)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Report submitted successfully"
            })
        else:
            return jsonify({
                "success": False,
                "message": message
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error submitting report: {str(e)}")
        return jsonify({
            "success": False,
            "message": "An error occurred while submitting the report"
        }), 500
