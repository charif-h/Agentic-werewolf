"""
Phase state machine: what happens when a game moves on from each phase.

`advance_phase` plays the current phase of a game (this can take minutes
because players are LLMs) and returns a result dict. It is blocking, so web
code must call it from a worker thread.
"""
from typing import Callable, Dict

from backend.game.game_logic import WerewolfGame
from backend.llm.metrics import track
from backend.models.game_models import GamePhase


def _end_or_next_night(game: WerewolfGame, result: Dict) -> Dict:
    """After the vote: announce the winner, or start the next night"""
    winner = game.check_win_condition()
    if winner:
        result["game_ended"] = True
        result["winner"] = winner
        result["end_announcement"] = game.end_game(winner)
    else:
        result["next_phase"] = "night"
        result["night_announcement"] = game.start_night()
    return result


def _from_night(game: WerewolfGame) -> Dict:
    """Night -> day: play the night actions and announce the dawn"""
    night_results = game.process_night_actions()
    return {
        "phase": "day",
        "announcement": game.start_day(),
        "night_results": night_results,
    }


def _from_day(game: WerewolfGame) -> Dict:
    """Day -> discussion: players talk"""
    return {"phase": "discussion", "messages": game.conduct_discussion()}


def _from_discussion(game: WerewolfGame) -> Dict:
    """Discussion -> voting: everyone votes, then the game ends or the night begins"""
    eliminated, votes = game.conduct_vote()
    result = {
        "phase": "voting",
        "eliminated": eliminated.name if eliminated else None,
        "votes": votes,
    }
    return _end_or_next_night(game, result)


def _from_voting(game: WerewolfGame) -> Dict:
    """Voting already done (e.g. interrupted): end the game or start the next night"""
    winner = game.check_win_condition()
    if winner:
        return {
            "phase": "ended",
            "game_ended": True,
            "winner": winner,
            "end_announcement": game.end_game(winner),
        }
    return {"phase": "night", "night_announcement": game.start_night()}


TRANSITIONS: Dict[GamePhase, Callable[[WerewolfGame], Dict]] = {
    GamePhase.NIGHT: _from_night,
    GamePhase.DAY: _from_day,
    GamePhase.DISCUSSION: _from_discussion,
    GamePhase.VOTING: _from_voting,
}


def advance_phase(game: WerewolfGame) -> Dict:
    """Play the current phase of `game` and return what happened"""
    transition = TRANSITIONS.get(game.state.phase)
    if transition is None:
        return {"error": f"Unknown phase: {game.state.phase.value}"}
    with track(game.metrics):             # count this game's model calls
        return transition(game)
