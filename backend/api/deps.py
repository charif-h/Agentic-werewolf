"""Helpers shared by the routers"""
from fastapi import HTTPException

from backend.api import state
from backend.services.sessions import GameSession, SessionNotFound


def get_session(game_id: str) -> GameSession:
    """The session for `game_id`, or a 404"""
    try:
        return state.sessions.get(game_id)
    except SessionNotFound:
        raise HTTPException(status_code=404, detail="Game not found")


def acquire(session: GameSession) -> None:
    """Take the session lock or answer 409 if a phase is already running"""
    if not session.lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="This game is busy playing a phase")
