"""Scouting blueprint; importing the view modules registers their routes."""
from . import events, leaderboards, lighthouse, pit, records
from .common import scouting_bp

__all__ = ["scouting_bp", "events", "leaderboards", "lighthouse", "pit", "records"]
