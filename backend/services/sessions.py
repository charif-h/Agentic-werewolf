"""
Game sessions: several independent games can run at the same time.

Each game has a random id. Sessions that are not used for a while are removed,
and when too many exist the least recently used one is dropped.
"""
import threading
import time
import uuid
from typing import Callable, Dict, Optional

from backend.game.game_logic import WerewolfGame


class SessionNotFound(KeyError):
    """No active game has this id"""


class GameSession:
    """A running game plus the bookkeeping the server needs"""

    def __init__(self, game: WerewolfGame, clock: Callable[[], float] = time.monotonic):
        self.id = uuid.uuid4().hex
        self.game = game
        self.lock = threading.Lock()   # held while a phase is being played
        self._clock = clock
        self.last_used = clock()

    def touch(self) -> None:
        self.last_used = self._clock()


class SessionManager:
    """Stores sessions by id with a time-to-live and a maximum count"""

    def __init__(self, ttl_seconds: float = 7200, max_sessions: int = 20,
                 clock: Callable[[], float] = time.monotonic):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._clock = clock
        self._sessions: Dict[str, GameSession] = {}
        self._guard = threading.RLock()

    def create(self, game: WerewolfGame) -> GameSession:
        """Register a game; first drops expired sessions, then the oldest one if full"""
        with self._guard:
            self.cleanup()
            while len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda s: s.last_used)
                del self._sessions[oldest.id]
            session = GameSession(game, self._clock)
            self._sessions[session.id] = session
            return session

    def get(self, session_id: str) -> GameSession:
        """The session with this id (marks it as used); raises SessionNotFound"""
        with self._guard:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFound(session_id)
            session.touch()
            return session

    def find(self, session_id: str) -> Optional[GameSession]:
        """Like `get` but returns None, and does not count as use"""
        with self._guard:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._guard:
            return self._sessions.pop(session_id, None) is not None

    def cleanup(self) -> int:
        """Remove sessions idle for longer than the TTL; returns how many"""
        with self._guard:
            now = self._clock()
            expired = [s.id for s in self._sessions.values()
                       if now - s.last_used > self.ttl_seconds and not s.lock.locked()]
            for session_id in expired:
                del self._sessions[session_id]
            return len(expired)

    def __len__(self) -> int:
        return len(self._sessions)
