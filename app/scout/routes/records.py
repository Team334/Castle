"""Match scouting records: add, list, edit, delete, and the per-match view."""
from __future__ import annotations

import json
from datetime import datetime

from bson import ObjectId
from flask import (current_app, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from app.utils import handle_route_errors

from ..match13_fuel import FUEL_FIELDS, zero_scored_fuel
from ..TBA import TBAInterface
from . import common
from .common import TELEOP_SHIFT_FIELDS, actor_name, fuel_total, scouting_bp

SCOUTING_PAGE_SIZE = 20


def _user_team():
    """The current user's Team, or None."""
    return common.scouting_manager.get_team(current_user.teamNumber)


@scouting_bp.route("/scouting/add", methods=["GET", "POST"])
@login_required
@handle_route_errors
def add():
    if request.method != "POST":
        # Get current events only
        tba = TBAInterface()
        year = datetime.now().year
        events = tba.get_current_events(year, include_test_data=True, background=True) or {}

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

    use_estimate = zero_scored_fuel(data)
    for field in FUEL_FIELDS:
        if data.get(field) in (None, ""):
            data[field] = 0
    success, message = common.scouting_manager.add_scouting_data(data, current_user.get_id())
    service = current_app.extensions.get("match13_fuel")
    if success and use_estimate and service:
        try:
            service.enroll(message, data)
        except Exception:
            current_app.logger.exception("Saved scouting record; could not enroll its fuel estimate")
    current_app.logger.info(f"Tried to add scouting data ({success}) {data} for user {actor_name(current_user)} - {message}")
    current_app.logger.info(f"Scouting.add Form Details {request.form} - {message}")

    if success:
        flash("Team data added successfully", "success")
    else:
        flash(f"Error adding data: {message}", "error")

    return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/list")
@scouting_bp.route("/scouting")
@login_required
def home():
    try:
        page = max(1, request.args.get("page", 1, type=int)) if request.args.get("partial") == "1" else 1
        result = common.scouting_manager.get_all_scouting_data(
            current_user.teamNumber, current_user.get_id(), page=page,
            page_size=SCOUTING_PAGE_SIZE, search=request.args.get("search", ""),
            filter_type=request.args.get("filter", "team"))
        team_data, total = result["records"], result["total"]
        service = current_app.extensions.get("match13_fuel")
        if service:
            statuses = service.statuses(record["_id"] for record in team_data)
            for record in team_data:
                record["fuel_estimate"] = statuses.get(str(record["_id"]))

        team = _user_team()
        has_more = page * SCOUTING_PAGE_SIZE < total
        if request.args.get("partial") == "1":
            return jsonify(html=render_template("scouting/_match_list.html", team_data=team_data, team=team),
                           total=total, has_more=has_more, next_page=page + 1)
        return render_template("scouting/list.html", team_data=team_data, team=team,
                               total=total, has_more=has_more)
    except Exception as e:
        current_app.logger.error(f"Error fetching scouting data: {str(e)}", exc_info=True)
        flash("Unable to fetch scouting data. Please try again later.", "error")
        if request.args.get("partial") == "1":
            return jsonify(error="Unable to load matches. Please try again."), 503
        return render_template("scouting/list.html", team_data=[], total=0, has_more=False)


@scouting_bp.route("/api/fuel_estimates", methods=["POST"])
@login_required
def fuel_estimates():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") if isinstance(payload, dict) else None
    if not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(id, str) or not ObjectId.is_valid(id) for id in ids):
        return jsonify(error="Provide up to 100 valid record IDs."), 400
    service = current_app.extensions.get("match13_fuel")
    if not service or not ids:
        return jsonify({})
    statuses = service.statuses(ids, include_manual=True)
    if not statuses:
        return jsonify({})
    records = common.scouting_manager.get_visible_fuel(
        statuses, current_user.get_id(), current_user.teamNumber, FUEL_FIELDS)
    return jsonify({str(record["_id"]): {**statuses[str(record["_id"])],
                     "fuel": {field: record.get(field, 0) for field in FUEL_FIELDS}} for record in records})


@scouting_bp.route("/scouting/edit/<string:id>", methods=["GET", "POST"])
@login_required
def edit(id):
    try:
        team_data = common.scouting_manager.get_team_data(id, current_user.get_id())

        if not team_data:
            flash("Team data not found", "error")
            return redirect(url_for("scouting.home"))

        # Check if the current user is on the same team as the scouter
        current_team = current_user.teamNumber
        scouter_team = team_data.scouter_team

        # Allow access only if user is the original scouter or on the same team
        if current_user.get_id() != str(team_data.scouter_id) and (not current_team or not scouter_team or str(current_team) != str(scouter_team)):
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

            service = current_app.extensions.get("match13_fuel")
            save = lambda: common.scouting_manager.update_team_data(id, data, current_user.get_id())
            saved = service.manual_update(id, save, data) if service else save()
            if saved:
                flash("Data updated successfully", "success")
                current_app.logger.info(f"Successfully updated scouting data {data} for user {actor_name(current_user)}")
                return redirect(url_for("scouting.home"))

            current_app.logger.info(f"Failed to update scouting data {data} for user {actor_name(current_user)}")
            flash("Unable to update data", "error")

        service = current_app.extensions.get("match13_fuel")
        if service:
            team_data.fuel_estimate = service.statuses([id]).get(id)
        return render_template("scouting/edit.html", team_data=team_data)
    except Exception as e:
        current_app.logger.error(f"Error in edit_scouting_data: {str(e)}", exc_info=True)
        flash("An error occurred while processing your request", "error")
        return redirect(url_for("scouting.home"))


@scouting_bp.route("/scouting/delete/<string:id>", methods=["POST"])
@login_required
def delete(id):
    try:
        # Get information about the record before deleting for better error messages
        team_data = common.scouting_manager.get_team_data(id, current_user.get_id())
        if not team_data:
            flash("Record not found", "error")
            return redirect(url_for("scouting.home"))

        # Attempt to delete
        if common.scouting_manager.delete_team_data(id, current_user.get_id()):
            current_app.logger.info(f"Successfully deleted scouting data {id} for user {actor_name(current_user)}")
            flash("Record deleted successfully", "success")
        elif team_data.scouter_id == current_user.get_id():
            flash("Error deleting your record. Please try again.", "error")
        elif current_user.teamNumber and team_data.scouter_team == current_user.teamNumber:
            if not (team := _user_team()):
                current_app.logger.info(f"Permission denied: Team not found {id} for user {actor_name(current_user)}")
                flash("Permission denied: Team not found", "error")
            elif not team.is_admin(current_user.get_id()):
                current_app.logger.info(f"Permission denied: You must be a team admin to delete other members' records {id} for user {actor_name(current_user)}")
                flash("Permission denied: You must be a team admin to delete other members' records", "error")
            # Try to delete again with admin override
            elif common.scouting_manager.delete_team_data(id, current_user.get_id(), admin_override=True):
                current_app.logger.info(f"Successfully deleted scouting data {id} for user {actor_name(current_user)} (admin)")
                flash("Record deleted successfully (admin)", "success")
            else:
                current_app.logger.info(f"Failed to delete scouting data {id} for user {actor_name(current_user)} (admin)")
                flash("Error deleting team member's record. Please try again.", "error")
        else:
            current_app.logger.info(f"Permission denied: You can only delete records from your own team {id} for user {actor_name(current_user)}")
            flash("Permission denied: You can only delete records from your own team", "error")
    except Exception as e:
        current_app.logger.error(f"Delete error: {str(e)}", exc_info=True)
        flash("An internal error has occurred.", "error")
    return redirect(url_for("scouting.home"))


def _alliance_fuel(teams: list[dict]) -> dict:
    return {
        "auto": sum(t["auto_fuel"] for t in teams),
        "transition": sum(t["transition_fuel"] for t in teams),
        "teleop": sum(sum(t[field] for field in TELEOP_SHIFT_FIELDS) for t in teams),
        "endgame": sum(t["endgame_fuel"] for t in teams),
        "total": sum(fuel_total(t) for t in teams)
    }


def _match_team_rows(teams: list[dict], statuses: dict) -> list[dict]:
    return [{
        "number": t["number"],
        "fuel_estimate": statuses.get(str(t["id"])),
        "ferried_fuel": t["ferried_fuel"],
        "fuel_total": fuel_total(t),
        "climb_level": t["climb_level"],
        "climb_success": t["climb_success"],
        "auto_climb": t["auto_climb"]
    } for t in teams]


@scouting_bp.route("/scouting/matches")
@login_required
def matches():
    try:
        match_data = common.scouting_manager.get_match_alliances(current_user.get_id(), current_user.teamNumber)
        service = current_app.extensions.get("match13_fuel")
        statuses = service.statuses(t["id"] for match in match_data for t in match["teams"]) if service else {}
        matches = []

        for match in match_data:
            red_teams = [t for t in match["teams"] if t["alliance"] == "red"]
            blue_teams = [t for t in match["teams"] if t["alliance"] == "blue"]
            matches.append({
                "event_code": match["_id"]["event"],
                "match_number": match["_id"]["match"],
                "red_teams": _match_team_rows(red_teams, statuses),
                "blue_teams": _match_team_rows(blue_teams, statuses),
                "red_fuel": _alliance_fuel(red_teams),
                "blue_fuel": _alliance_fuel(blue_teams)
            })
        current_app.logger.info(f"Successfully fetched matches {matches} for user {actor_name(current_user)}")
        return render_template("scouting/matches.html", matches=matches)

    except Exception as e:
        current_app.logger.error(f"Error fetching matches: {str(e)}", exc_info=True)
        flash("An internal error has occurred.", "error")
        return render_template("scouting/matches.html", matches=[])
