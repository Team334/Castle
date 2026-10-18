"""Team and scouter leaderboards."""
from __future__ import annotations

from datetime import datetime

from flask import current_app, render_template, request
from flask_login import current_user, login_required

from . import common
from .common import SCOUTER_LOOKUP, actor_name, scouting_bp, team_access_match


@scouting_bp.route("/leaderboard")
# @limiter.limit("30 per minute")
def leaderboard():
    try:
        MIN_MATCHES = 1
        sort_type = request.args.get('sort', 'fuel')
        selected_event = request.args.get('event', 'all')

        # Get available events from scouting data
        # Filter by team access: only show events from user's team or user himself
        events_pipeline = [
            SCOUTER_LOOKUP,
            {"$unwind": "$scouter"},
            team_access_match(current_user),
            # Group by event code to get unique events
            {"$group": {
                "_id": "$event_code",
                "event_name": {"$first": "$event_name"},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]

        events = list(common.scouting_manager.db.team_data.aggregate(events_pipeline))

        # Main pipeline for team data
        pipeline = [
            SCOUTER_LOOKUP,
            {"$unwind": "$scouter"},
            team_access_match(current_user)
        ]

        # Filter by selected event if not 'all'
        if selected_event != 'all':
            pipeline.append({"$match": {"event_code": selected_event}})

        # Continue with the existing aggregation
        pipeline.extend([
            {"$group": {
                "_id": "$team_number",
                "matches_played": {"$sum": 1},

                # Auto Fuel
                "auto_fuel": {"$avg": {"$ifNull": ["$auto_fuel", 0]}},
                "transition_fuel": {"$avg": {"$ifNull": ["$transition_fuel", 0]}},
                "ferried_fuel": {"$avg": {"$ifNull": ["$ferried_fuel", 0]}},

                # Teleop Fuel
                "teleop_shift_1_fuel": {"$avg": {"$ifNull": ["$teleop_shift_1_fuel", 0]}},
                "teleop_shift_2_fuel": {"$avg": {"$ifNull": ["$teleop_shift_2_fuel", 0]}},
                "teleop_shift_3_fuel": {"$avg": {"$ifNull": ["$teleop_shift_3_fuel", 0]}},
                "teleop_shift_4_fuel": {"$avg": {"$ifNull": ["$teleop_shift_4_fuel", 0]}},

                # Endgame Fuel
                "endgame_fuel": {"$avg": {"$ifNull": ["$endgame_fuel", 0]}},

                # Climb Level
                "auto_climb_sum": {"$sum": {"$cond": [{"$eq": ["$auto_climb", True]}, 1, 0]}},
                "climb_level": {"$avg": {"$ifNull": ["$climb_level", 0]}},

                # Defense Rating
                "defense_rating": {"$avg": {"$ifNull": ["$defense_rating", 0]}},
                # Robot Disabled
                "robot_disabled_list": {"$push": "$robot_disabled"},

                "herd_rating": {
                    "$avg": {
                        "$cond": [{"$eq": ["$herd_balls", True]}, {"$ifNull": ["$herd_rating", 0]}, None]
                    }
                },
                "herd_count": {"$sum": {"$cond": [{"$eq": ["$herd_balls", True]}, 1, 0]}},

                "ferrying_rating": {
                    "$avg": {
                        "$cond": [{"$eq": ["$ferrying_did", True]}, {"$ifNull": ["$ferrying_rating", 0]}, None]
                    }
                },
                "ferrying_count": {"$sum": {"$cond": [{"$eq": ["$ferrying_did", True]}, 1, 0]}},

                # Climb stats
                "climb_level_1_success": {"$sum": {"$cond": [{"$and": [{"$eq": ["$climb_level", 1]}, {"$eq": ["$climb_success", True]}]}, 1, 0]}},
                "climb_level_2_success": {"$sum": {"$cond": [{"$and": [{"$eq": ["$climb_level", 2]}, {"$eq": ["$climb_success", True]}]}, 1, 0]}},
                "climb_level_3_success": {"$sum": {"$cond": [{"$and": [{"$eq": ["$climb_level", 3]}, {"$eq": ["$climb_success", True]}]}, 1, 0]}},
                "climb_attempts": {"$sum": 1},
                "climb_successes": {
                    "$sum": {"$cond": [{"$eq": ["$climb_success", True]}, 1, 0]}
                },
            }},
            {"$match": {"matches_played": {"$gte": MIN_MATCHES}}},
            {"$project": {
                "team_number": "$_id",
                "matches_played": 1,

                "auto_fuel": {"$round": ["$auto_fuel", 1]},
                "transition_fuel": {"$round": ["$transition_fuel", 1]},
                "ferried_fuel": {"$round": ["$ferried_fuel", 1]},
                "teleop_fuel_total": {
                    "$add": [
                        "$transition_fuel",
                        "$teleop_shift_1_fuel",
                        "$teleop_shift_2_fuel",
                        "$teleop_shift_3_fuel",
                        "$teleop_shift_4_fuel"
                    ]
                },
                "endgame_fuel": {"$round": ["$endgame_fuel", 1]},

                # Calculate totals for each category
                "total_fuel": {
                    "$add": [
                        "$auto_fuel",
                        "$transition_fuel",
                        "$teleop_shift_1_fuel",
                        "$teleop_shift_2_fuel",
                        "$teleop_shift_3_fuel",
                        "$teleop_shift_4_fuel",
                        "$endgame_fuel"
                    ]
                },

                "climb_level_avg": {"$round": ["$climb_level", 1]},

                "auto_climb_pct": {
                    "$multiply": [
                        {"$divide": ["$auto_climb_sum", "$matches_played"]},
                        100
                    ]
                },
                "climb_l1_pct": {
                    "$multiply": [
                        {"$divide": ["$climb_level_1_success", "$matches_played"]},
                        100
                    ]
                },
                "climb_l2_pct": {
                    "$multiply": [
                        {"$divide": ["$climb_level_2_success", "$matches_played"]},
                        100
                    ]
                },
                "climb_l3_pct": {
                    "$multiply": [
                        {"$divide": ["$climb_level_3_success", "$matches_played"]},
                        100
                    ]
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
                "defense_rating": {"$round": ["$defense_rating", 1]},
                "robot_disabled_list": "$robot_disabled_list",
                "herd_rating": {"$round": [{"$ifNull": ["$herd_rating", 0]}, 1]},
                "herd_count": 1,
                "ferrying_rating": {"$round": [{"$ifNull": ["$ferrying_rating", 0]}, 1]},
                "ferrying_count": 1
            }}
        ])

        # We cannot sort purely by TBA-fetched metrics natively in MongoDB aggregation
        # (EPA/OPR/DPR/CCWM require secondary API calls). Let's process those *after*
        # the aggregate completes if one of those sorts is requested.

        tba_metrics = {'epa', 'opr', 'dpr', 'ccwm'}

        if sort_type not in tba_metrics:
            sort_field = {
                'fuel': 'total_fuel',
                'auto_fuel': 'auto_fuel',
                'ferried_fuel': 'ferried_fuel',
                'auto_climb': 'auto_climb_pct',
                'climb': 'climb_success_rate',
                'climb_l1': 'climb_l1_pct',
                'climb_l2': 'climb_l2_pct',
                'climb_l3': 'climb_l3_pct',
                'defense': 'defense_rating',
                'herd_rating': 'herd_rating',
                'ferrying_rating': 'ferrying_rating'
            }.get(sort_type, 'total_fuel')

            pipeline.append({"$sort": {sort_field: -1}})

        teams = list(common.scouting_manager.db.team_data.aggregate(pipeline))
        current_app.logger.info(f"Successfully fetched leaderboard {teams} for user {actor_name(current_user)}")

        if sort_type in tba_metrics:
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

        # Get list of events for filtering
        events_pipeline = [
            {"$group": {"_id": "$event_code"}},
            {"$sort": {"_id": 1}}
        ]
        events = [evt["_id"] for evt in common.scouting_manager.db.team_data.aggregate(events_pipeline)]

        # Build pipeline to count scouting entries by user
        pipeline = [
            SCOUTER_LOOKUP,
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
        scouters = list(common.scouting_manager.db.team_data.aggregate(pipeline))

        # Get list of all teams for filtering
        teams_pipeline = [
            SCOUTER_LOOKUP,
            {"$unwind": "$scouter"},
            {"$match": {"scouter.teamNumber": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$scouter.teamNumber"}},
            {"$sort": {"_id": 1}}
        ]
        teams = [team["_id"] for team in common.scouting_manager.db.team_data.aggregate(teams_pipeline)]

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
