"""
Game Master - deterministic announcements and discussion pacing (no LLM calls)
"""
import random
from typing import List

from backend.models.game_models import PlayerProfile


class GameMaster:
    """Referee that narrates the game with templates and decides when discussion ends"""

    # From round 3 on, at least this share of players (and never fewer than 2)
    # must speak in a round for the discussion to continue
    MIN_SPEAKER_RATIO = 1 / 3

    def narrate_game_start(self, players: List[PlayerProfile]) -> str:
        return random.choice([
            "The game begins with {n} players.",
            "Welcome to Millers Hollow. {n} players take part in this game.",
        ]).format(n=len(players))

    def announce_night(self, night_number: int) -> str:
        return random.choice([
            "Night {n} falls. Special roles, it is time to act.",
            "It is now Night {n}. The village sleeps while special roles act.",
        ]).format(n=night_number)

    def announce_day(self, day_number: int, night_events: str) -> str:
        return random.choice([
            "Day {n} begins. {events}",
            "The sun rises on Day {n}. {events}",
        ]).format(n=day_number, events=night_events)

    def narrate_elimination(self, player_name: str, role: str, by_vote: bool = True) -> str:
        method = "voted out by the village" if by_vote else "killed during the night"
        return f"{player_name} has been {method}. Their role was: {role}."

    def announce_winner(self, winning_team: str, survivors: List[str]) -> str:
        survivor_list = ", ".join(survivors) if survivors else "none"
        return f"The game is over. The {winning_team} win! Survivors: {survivor_list}."

    def announce_werewolf_awakening(self) -> str:
        # Deliberately does not name the werewolves: the game log is visible to everyone
        return "The werewolves awaken and choose their victim."

    def announce_werewolf_decision(self) -> str:
        # Deliberately does not name the victim: the night result is announced at dawn
        return "The werewolves have made their choice and go back to sleep."

    def announce_discussion_end(self) -> str:
        return random.choice([
            "The discussion is over. Time to vote.",
            "Enough talk. The village now votes.",
        ])

    def should_continue_discussion(self, messages_last_round: int, rounds_completed: int,
                                   num_players: int, max_rounds: int) -> bool:
        """
        Decide whether another discussion round should be played

        Args:
            messages_last_round: Number of messages spoken in the round that just ended
            rounds_completed: Number of rounds completed so far
            num_players: Number of alive players
            max_rounds: Maximum number of rounds allowed

        Returns:
            True to keep discussing, False to move to voting
        """
        if rounds_completed >= max_rounds:
            return False
        if messages_last_round == 0:
            # Silence ends the discussion, but only after a second chance
            return rounds_completed < 2
        if rounds_completed >= 3:
            min_speakers = max(2, int(num_players * self.MIN_SPEAKER_RATIO))
            return messages_last_round >= min_speakers
        return True
