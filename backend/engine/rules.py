"""
Pure rules of Werewolves of Millers Hollow.

Everything here works on a `GameState` and plain values. Decisions (who the
werewolves target, who each player votes for) are passed in by the caller, and
randomness comes from an injectable `random.Random`, so a whole game can be
played in a unit test without any LLM.
"""
import random
from typing import Dict, List, Optional, Tuple

from backend.models.game_models import GamePhase, GameState, PlayerProfile, PlayerStatus, Role
from backend.roles import VILLAGERS, WEREWOLVES, get_handler, night_handlers


# --- Setup -----------------------------------------------------------------

def distribute_roles(num_players: int) -> List[Role]:
    """
    List of roles for a game of `num_players` (unshuffled)

    Werewolves are max(2, n // 6). Special roles are added as the player count
    grows: Seer from 8, Witch from 10, Hunter from 12, Cupid from 14, Guard
    from 16. The rest are villagers.
    """
    roles = [Role.WEREWOLF] * max(2, num_players // 6)
    for minimum, role in [(8, Role.SEER), (10, Role.WITCH), (12, Role.HUNTER),
                          (14, Role.CUPID), (16, Role.GUARD)]:
        if num_players >= minimum:
            roles.append(role)
    roles.extend([Role.VILLAGER] * (num_players - len(roles)))
    return roles


def assign_roles(players: List[PlayerProfile], rng: Optional[random.Random] = None) -> None:
    """Shuffle roles and assign one to each player (in place)"""
    rng = rng or random
    roles = distribute_roles(len(players))
    rng.shuffle(roles)
    for player, role in zip(players, roles):
        player.role = role


# --- Lookups ---------------------------------------------------------------

def alive_players(state: GameState) -> List[PlayerProfile]:
    return [p for p in state.players if p.status == PlayerStatus.ALIVE]


def find_player_by_name(state: GameState, name: Optional[str]) -> Optional[PlayerProfile]:
    """Case-insensitive lookup; None for an empty name"""
    if not name:
        return None
    for player in state.players:
        if player.name.lower() == name.lower():
            return player
    return None


def find_player_by_id(state: GameState, player_id: str) -> Optional[PlayerProfile]:
    for player in state.players:
        if player.id == player_id:
            return player
    return None


# --- Night -----------------------------------------------------------------

def start_night(state: GameState) -> None:
    """Move to the next night"""
    state.day_number += 1
    state.phase = GamePhase.NIGHT
    state.night_actions = {}


def valid_night_targets(state: GameState, actor: PlayerProfile) -> List[str]:
    """
    Names `actor` may target tonight, as defined by their role handler

    Werewolves: alive non-werewolves. Guard: any alive player (self included).
    Seer: any alive player except self. Other roles have no night target.
    """
    return get_handler(actor.role).night_targets(state, actor)


def kill_player(state: GameState, player: PlayerProfile) -> List[PlayerProfile]:
    """
    Kill a player; a lover dies of heartbreak with them

    Returns:
        Everyone who died because of this call (empty if already dead)
    """
    if player.status == PlayerStatus.DEAD:
        return []
    player.status = PlayerStatus.DEAD
    state.eliminated_players.append(player.id)
    died = [player]
    if player.in_love_with:
        lover = find_player_by_id(state, player.in_love_with)
        if lover and lover.status == PlayerStatus.ALIVE:
            died += kill_player(state, lover)
    return died


def resolve_night(state: GameState, targets: Dict[Role, Optional[PlayerProfile]]) -> Dict:
    """
    Apply the night's actions and store them in `state.night_actions`

    Args:
        targets: Role -> player chosen by that role tonight (missing or None
            when the role did not act). Each role handler records its own
            choice; the kill is applied unless the victim is protected.

    Returns:
        Dict with 'killed', 'protected' (player ids), 'seer_check'
        ({'player', 'role'}), 'witch_saved', 'witch_killed' and, when a lover
        died with the victim, 'lover_died' (player id)
    """
    results = {
        'killed': None,
        'protected': None,
        'seer_check': None,
        'witch_saved': False,
        'witch_killed': None,
    }
    for handler in night_handlers():
        target = targets.get(handler.role)
        if target:
            handler.record_night(results, target)
    if results['killed'] and results['killed'] != results['protected']:
        died = kill_player(state, find_player_by_id(state, results['killed']))
        if len(died) > 1:
            results['lover_died'] = died[1].id
    state.night_actions = results
    return results


def describe_night(state: GameState) -> str:
    """Public summary of last night's deaths, e.g. 'Bob was killed.'"""
    results = state.night_actions
    events = []
    victim = find_player_by_id(state, results['killed']) if results.get('killed') else None
    if victim and victim.status == PlayerStatus.DEAD:
        events.append(f"{victim.name} was killed")
        lover = (find_player_by_id(state, results['lover_died'])
                 if results.get('lover_died') else None)
        if lover:
            events.append(f"{lover.name} died of heartbreak")
    else:
        events.append("No one was killed")
    return ". ".join(events) + "."


# --- Day: voting -----------------------------------------------------------

def fallback_vote_target(voter: str, candidates: List[str],
                         rng: Optional[random.Random] = None) -> Optional[str]:
    """Random candidate other than the voter, or None if there is none"""
    others = [c for c in candidates if c != voter]
    return (rng or random).choice(others) if others else None


def resolve_vote(state: GameState, votes: Dict[str, str],
                 rng: Optional[random.Random] = None) -> Tuple[Optional[PlayerProfile], Dict[str, int]]:
    """
    Tally votes and eliminate the player with the most (ties broken randomly)

    Args:
        votes: voter name -> target name

    Returns:
        (eliminated player or None, vote count for every alive player)
    """
    rng = rng or random
    counts = {p.name: 0 for p in alive_players(state)}
    for target in votes.values():
        if target in counts:
            counts[target] += 1
    if not counts:
        return None, counts
    top = max(counts.values())
    eliminated = find_player_by_name(
        state, rng.choice([name for name, c in counts.items() if c == top])
    )
    if eliminated:
        kill_player(state, eliminated)
    return eliminated, counts


# --- End of game -----------------------------------------------------------

def check_win_condition(state: GameState) -> Optional[str]:
    """'villagers' if no werewolf is left, 'werewolves' if they are at least half, else None"""
    alive = alive_players(state)
    wolves = sum(1 for p in alive if get_handler(p.role).team == WEREWOLVES)
    if wolves == 0:
        return VILLAGERS
    if wolves >= len(alive) - wolves:
        return WEREWOLVES
    return None


def end_game(state: GameState) -> List[str]:
    """Mark the game as ended; returns the names of the survivors"""
    state.phase = GamePhase.ENDED
    return [p.name for p in alive_players(state)]
