"""Venue laptop commands (docs/venue-mode.md). They only run with VENUE_MODE=1 because reset deletes data."""
from __future__ import annotations

import click
from flask import current_app

from app.auth.auth_utils import UserManager


def _venue_only():
    if not current_app.config.get("VENUE_MODE"):
        raise click.ClickException("Venue commands only run with VENUE_MODE=1 (they delete data).")


def register_venue_commands(app):
    @app.cli.command("venue-user")
    @click.option("--username", required=True)
    @click.option("--password", required=True)
    @click.option("--team", required=True, type=int)
    def venue_user(username, password, team):
        """Create the lead's login on this laptop. No password ever leaves castlescouting.com."""
        _venue_only()
        created, message = UserManager(current_app.config.get("MONGO_URI")).create_user(
            f"{username}@venue.local", username, password, team)
        if not created:
            raise click.ClickException(message)
        click.echo(f"Created {username} (team {team}). Log in at http://localhost:5000.")

    @app.cli.command("venue-reset")
    @click.option("--force", is_flag=True, help="Delete even entries scouted here that were never downloaded.")
    def venue_reset(force):
        """Start a new event: delete this laptop's match and pit records (users stay)."""
        _venue_only()
        from app.scout.routes import common
        db = common.scouting_manager.db
        push = db.venue_meta.find_one({"_id": "push"})
        unpushed = db.team_data.count_documents(
            {"origin": "venue", "venue_at": {"$gt": push["at"]}} if push else {"origin": "venue"})
        if unpushed and not force:
            raise click.ClickException(
                f"{unpushed} entries scouted on this laptop haven't been saved with 'Download new entries' yet. "
                "Download them and import them on castlescouting.com first, or run with --force to delete them.")
        counts = {name: getattr(db, name).delete_many({}).deleted_count
                  for name in ("team_data", "pit_scouting", "venue_meta")}
        click.echo(f"Reset: {counts['team_data']} match records and {counts['pit_scouting']} pit records deleted.")
