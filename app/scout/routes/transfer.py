"""Moving match entries between devices: export a team's data, import entries from phones, QR scans and files."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.utils import limiter

from ..match13_fuel import zero_scored_fuel
from . import common
from .common import actor_name, scouting_bp

ENTRY_FORMAT = "castle-entries"
JSON_MAX_BYTES = 5 * 1024 * 1024
JSON_MAX_ENTRIES = 500  # per list (matches, pits) in a JSON body: phone sync and QR batches
FILE_MAX_ENTRIES = 20000  # matches + pits in one file: a season's export, with headroom


@scouting_bp.route("/scouting/export")
@login_required
def export_entries():
    data = common.scouting_manager.export_data(current_user.get_id(), current_user.teamNumber)
    name = f"castle-{current_user.teamNumber or 'me'}-{datetime.now(timezone.utc):%Y-%m-%d}.json"
    response = jsonify(data)
    response.headers["Content-Disposition"] = f'attachment; filename="{name}"'
    current_app.logger.info(f"Exported {len(data.get('matches', []))} entries for user {actor_name(current_user)}")
    return response


@scouting_bp.route("/scouting/import", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def import_entries():
    if not current_user.teamNumber:
        return jsonify(error="Join a team to import entries."), 403
    upload = request.files.get("file")
    if upload is None and (request.content_length or 0) > JSON_MAX_BYTES:
        return jsonify(error="Too much data in one upload; send fewer entries at a time."), 413
    try:
        payload = json.load(upload) if upload is not None else request.get_json(force=True, silent=True)
    except (ValueError, UnicodeDecodeError):
        return jsonify(error="That file isn't Castle entry data."), 400
    if not (isinstance(payload, dict) and payload.get("format") == ENTRY_FORMAT and payload.get("version") == 1
            and isinstance(payload.get("matches", []), list) and isinstance(payload.get("pits", []), list)):
        return jsonify(error="That file isn't Castle entry data."), 400
    matches, pits = payload.get("matches", []), payload.get("pits", [])
    too_many = (len(matches) + len(pits) > FILE_MAX_ENTRIES if upload is not None
                else max(len(matches), len(pits)) > JSON_MAX_ENTRIES)
    if too_many:
        return jsonify(error="Too many entries in one upload; split it up."), 413

    venue = bool(current_app.config.get("VENUE_MODE"))
    if venue:
        # The lead's laptop: make sure every scout in the file or QR (rookies too) has a name-only stand-in.
        people = [user for user in payload.get("users", []) if isinstance(user, dict)]             if isinstance(payload.get("users"), list) else []
        if isinstance(payload.get("scout"), dict):
            people.append(payload["scout"])
        common.scouting_manager.ensure_stub_users(people, current_user.teamNumber)
    results = common.scouting_manager.import_matches(matches, current_user.get_id(), current_user.teamNumber,
                                                     venue=venue)
    # AI fuel estimates need the internet; venue entries are signed up when they reach castlescouting.com.
    service = None if venue else current_app.extensions.get("match13_fuel")
    for result, entry in zip(results, matches):
        if result["status"] == "saved" and service and isinstance(entry, dict) and zero_scored_fuel(entry):
            try:
                service.enroll(result["id"], {**entry, "_event_key": entry.get("event_key") or entry.get("_event_key")})
            except Exception:
                current_app.logger.exception("Imported scouting record; could not enroll its fuel estimate")
    if venue:
        pit_results = common.scouting_manager.import_pits_venue(pits)
    else:
        visible_pits = common.scouting_manager.visible_pit_ids(current_user.get_id(), current_user.teamNumber) if pits else set()
        pit_results = [_pit_result(index, pit, visible_pits) for index, pit in enumerate(pits)]

    counts = Counter(result["status"] for result in results)
    current_app.logger.info(f"Imported entries for user {actor_name(current_user)}: {dict(counts)}")
    return jsonify(results=results, pit_results=pit_results, counts=counts)


def _pit_result(index: int, pit, visible: set) -> dict:
    """Pit records are only ever copied to a venue laptop, never created here, so the main server just skips them.
    Only pits the uploader can see count as already here; anything else is rejected the same way."""
    try:
        oid = ObjectId(pit.get("_id")) if isinstance(pit, dict) and pit.get("_id") else None
    except (InvalidId, TypeError):
        oid = None
    if oid in visible:
        return {"key": str(oid), "status": "already_have"}
    return {"key": str(oid or index), "status": "rejected", "reason": "pit entries are only accepted in venue mode"}


@scouting_bp.route("/scouting/scan")
@login_required
def scan_entries():
    """The lead's camera page for QR transfers from scouts' phones."""
    return render_template("scouting/scan.html")
