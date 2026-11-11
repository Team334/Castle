"""Moving match entries between devices: export a team's data, import entries from phones, QR scans and files."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import current_app, jsonify, request
from flask_login import current_user, login_required

from app.utils import limiter

from ..match13_fuel import zero_scored_fuel
from . import common
from .common import actor_name, scouting_bp

ENTRY_FORMAT = "castle-entries"
JSON_MAX_BYTES = 5 * 1024 * 1024
JSON_MAX_MATCHES = 500


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
    matches = payload.get("matches", [])
    if upload is None and len(matches) > JSON_MAX_MATCHES:
        return jsonify(error=f"At most {JSON_MAX_MATCHES} entries per upload."), 413

    results = common.scouting_manager.import_matches(matches, current_user.get_id(), current_user.teamNumber)
    service = current_app.extensions.get("match13_fuel")
    for result, entry in zip(results, matches):
        if result["status"] == "saved" and service and isinstance(entry, dict) and zero_scored_fuel(entry):
            try:
                service.enroll(result["id"], {**entry, "_event_key": entry.get("event_key") or entry.get("_event_key")})
            except Exception:
                current_app.logger.exception("Imported scouting record; could not enroll its fuel estimate")
    pit_results = [_pit_result(index, pit) for index, pit in enumerate(payload.get("pits", []))]

    counts = Counter(result["status"] for result in results)
    current_app.logger.info(f"Imported entries for user {actor_name(current_user)}: {dict(counts)}")
    return jsonify(results=results, pit_results=pit_results, counts=counts)


def _pit_result(index: int, pit) -> dict:
    """Pit records are only ever copied to a venue laptop, never created here, so the main server just skips them."""
    try:
        oid = ObjectId(pit.get("_id")) if isinstance(pit, dict) and pit.get("_id") else None
    except (InvalidId, TypeError):
        oid = None
    if oid and common.scouting_manager.db.pit_scouting.find_one({"_id": oid}, {"_id": 1}):
        return {"key": str(oid), "status": "already_have"}
    return {"key": str(oid or index), "status": "rejected", "reason": "pit entries are only accepted in venue mode"}
