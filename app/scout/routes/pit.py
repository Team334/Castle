"""Pit scouting: list, add, edit, delete."""
from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import common
from .common import actor_name, scouting_bp


def _form_int(name: str) -> int:
    """Integer form field; blank or missing is 0."""
    return int(request.form.get(name) or 0)


def _pit_form() -> dict:
    """Pit scouting fields from the add/edit form."""
    form = request.form
    has_auto = form.get("has_auto") == "true"
    return {
        "team_number": int(form["team_number"]),

        # Drive base information
        "drive_type": {
            "swerve": "swerve" in form.getlist("drive_type"),
            "tank": "tank" in form.getlist("drive_type"),
            "other": form.get("drive_type_other", "")
        },
        "swerve_modules": form.get("swerve_modules", ""),

        # Mechanisms
        "fuel_count_bps": _form_int("fuel_count_bps"),
        "shooter_type": form.get("shooter_type", ""),
        "shooter_notes": form.get("shooter_notes", ""),
        "hopper_notes": form.get("hopper_notes", ""),
        "intake_notes": form.get("intake_notes", ""),

        # Autonomous
        "autonomous_capabilities": {
            "has_auto": has_auto,
            "num_routes": _form_int("auto_routes") if has_auto else 0,
            "preferred_start": form.get("auto_preferred_start", "") if has_auto else "",
            "notes": form.get("auto_notes", "") if has_auto else ""
        },

        # Driver Experience
        "driver_experience": {
            "years": _form_int("driver_years"),
            "notes": form.get("driver_notes", "")
        },

        # General Notes
        "notes": form.get("notes", ""),
    }


@scouting_bp.route("/scouting/pit")
@login_required
def pit_scouting():
    try:
        # Update to use filtered pit scouting data
        pit_data_list = list(common.scouting_manager.get_all_pit_scouting(
            current_user.teamNumber,
            current_user.get_id()
        ))
        current_app.logger.info(f"Fetched {len(pit_data_list)} pit scouting records for user {actor_name(current_user)}")
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
            now = datetime.now(timezone.utc)
            pit_data = {**_pit_form(), "scouter_id": current_user.id, "created_at": now, "updated_at": now}

            # Add to database
            if common.scouting_manager.add_pit_scouting(pit_data):
                current_app.logger.info(f"Added pit scouting for team {pit_data['team_number']} for user {actor_name(current_user)}")
                flash("Pit scouting data added successfully!", "success")
                return redirect(url_for("scouting.pit_scouting"))
            else:
                current_app.logger.info(f"Failed to add pit scouting for team {pit_data['team_number']} for user {actor_name(current_user)}")
                flash("Error adding pit scouting data. Please try again.", "error")
        except Exception as e:
            flash("An error occurred while adding pit scouting data.", "error")
            current_app.logger.error(f"Error adding pit scouting data: {str(e)}", exc_info=True)
            return redirect(url_for("scouting.pit_scouting"))

    return render_template("scouting/pit-scouting-add.html")


@scouting_bp.route("/scouting/pit/edit/<entry_id>", methods=["GET", "POST"])
@login_required
def pit_scouting_edit(entry_id):
    pit_data = common.scouting_manager.get_pit_scouting_by_id(entry_id)
    if not pit_data:
        flash("Pit scouting data not found", "error")
        return redirect(url_for("scouting.pit_scouting"))

    if str(pit_data["scouter_id"]) != current_user.get_id():
        flash("You don't have permission to edit this data", "error")
        return redirect(url_for("scouting.pit_scouting"))

    if request.method == "POST":
        try:
            data = {**_pit_form(), "scouter_id": ObjectId(current_user.get_id()),
                    "updated_at": datetime.now(timezone.utc)}

            if common.scouting_manager.update_pit_scouting(entry_id, data, current_user.get_id()):
                current_app.logger.info(f"Updated pit scouting entry {entry_id} for user {actor_name(current_user)}")
                flash("Pit scouting data updated successfully", "success")
                return redirect(url_for("scouting.pit_scouting"))
            else:
                current_app.logger.info(f"Failed to update pit scouting entry {entry_id} for user {actor_name(current_user)}")
                flash("Error updating pit scouting data", "error")
        except Exception as e:
            current_app.logger.info(f"Error updating pit scouting entry {entry_id} for user {actor_name(current_user)} {str(e)}", exc_info=True)
            flash("An internal error has occurred.", "error")

    return render_template("scouting/pit-scouting-edit.html", entry=pit_data)


@scouting_bp.route("/scouting/pit/delete/<entry_id>", methods=["POST"])
@login_required
def pit_scouting_delete(entry_id):
    if common.scouting_manager.delete_pit_scouting(entry_id, current_user.get_id()):
        current_app.logger.info(f"Successfully deleted pit scouting entry {entry_id} for user {actor_name(current_user)}")
        flash("Pit scouting data deleted successfully", "success")
    else:
        current_app.logger.info(f"Failed to delete pit scouting entry {entry_id} for user {actor_name(current_user)}")
        flash("Error deleting pit scouting data", "error")
    return redirect(url_for("scouting.pit_scouting"))
