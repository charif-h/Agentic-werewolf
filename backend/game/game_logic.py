"""
Game orchestration for Werewolves of Millers Hollow

`WerewolfGame` asks the player agents (LLM) for decisions, passes them to the
pure rules in `backend.engine.rules`, and records the narration. It contains no
game rules of its own.
"""
import logging
import random
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from backend.engine import rules
from backend.roles import WEREWOLVES, get_handler, night_handlers
from backend.models.game_models import (
    PlayerProfile, GameState, GamePhase, Role, Discussion, Message
)
from backend.agents.profile_generator import generate_all_players
from backend.agents.player_agent import PlayerAgent
from backend.game.game_master import GameMaster
from backend.game.targets import pick_target


logger = logging.getLogger(__name__)


class WerewolfGame:
    """Runs a game by combining LLM player agents with the rules engine"""

    def __init__(self, num_players: int = 24, ai_provider: Optional[str] = None):
        """
        Initialize the game

        Args:
            num_players: Number of players (default 24)
            ai_provider: AI provider to use for all agents
        """
        self.num_players = num_players
        self.ai_provider = ai_provider
        self.state = GameState()
        self.player_agents: Dict[str, PlayerAgent] = {}
        self.game_master = GameMaster()

    def setup_game(self) -> GameState:
        """
        Set up the game: generate players and assign roles

        Returns:
            Initial game state
        """
        players = generate_all_players(self.num_players)
        rules.assign_roles(players)

        for player in players:
            self.player_agents[player.id] = PlayerAgent(player, self.ai_provider)

        self.state.players = players
        self.state.phase = GamePhase.SETUP

        opening = self.game_master.narrate_game_start(players)
        self.state.game_log.append(f"[GAME MASTER] {opening}")

        return self.state

    def start_night(self) -> str:
        """
        Start the night phase

        Returns:
            Night announcement
        """
        rules.start_night(self.state)

        announcement = self.game_master.announce_night(self.state.day_number)
        self.state.game_log.append(f"[GAME MASTER] {announcement}")

        if any(get_handler(p.role).team == WEREWOLVES for p in rules.alive_players(self.state)):
            werewolf_announcement = self.game_master.announce_werewolf_awakening()
            self.state.game_log.append(f"[GAME MASTER] {werewolf_announcement}")

        return announcement

    def process_night_actions(self) -> Dict[str, any]:
        """
        Ask the night roles for their targets and apply them

        Returns:
            Dictionary of night results (see `rules.resolve_night`)
        """
        alive = rules.alive_players(self.state)
        targets: Dict[Role, Optional[PlayerProfile]] = {}
        for handler in night_handlers():
            # Simplified: the first alive player of the role acts (werewolves would coordinate)
            actor = next((p for p in alive if p.role == handler.role), None)
            targets[handler.role] = self._choose_night_target(actor)
            if targets[handler.role] and handler.announce_night_choice:
                decision = self.game_master.announce_werewolf_decision()
                self.state.game_log.append(f"[GAME MASTER] {decision}")

        return rules.resolve_night(self.state, targets)

    def _choose_night_target(self, actor: Optional[PlayerProfile]) -> Optional[PlayerProfile]:
        """
        Ask a player's agent for a night target and map the answer to a valid player.
        Unclear answers or LLM errors fall back to a random valid target.
        """
        if actor is None:
            return None
        valid_names = rules.valid_night_targets(self.state, actor)
        if not valid_names:
            return None
        game_state = self._get_game_state_dict()
        game_state['valid_targets'] = valid_names
        try:
            answer = self.player_agents[actor.id].night_action(game_state)
        except Exception as e:
            logger.warning("Night action failed for %s: %s", actor.name, e)
            answer = None
        return rules.find_player_by_name(self.state, pick_target(answer, valid_names))

    def start_day(self) -> str:
        """
        Start the day phase and announce night results

        Returns:
            Day announcement
        """
        self.state.phase = GamePhase.DAY

        announcement = self.game_master.announce_day(
            self.state.day_number, rules.describe_night(self.state)
        )
        self.state.game_log.append(f"[GAME MASTER] {announcement}")

        return announcement

    def conduct_discussion(self, max_rounds: int = 5) -> List[str]:
        """
        Conduct dynamic discussion phase where players can respond to each other
        Each time someone speaks, all players get a chance to respond

        Args:
            max_rounds: Maximum number of discussion rounds (default: 5)

        Returns:
            List of discussion messages
        """
        self.state.phase = GamePhase.DISCUSSION
        messages = []

        alive_players = rules.alive_players(self.state)
        alive_names = [p.name for p in alive_players]

        # Create main discussion
        discussion = Discussion(
            round_number=1,
            topic="Dynamic discussion - players can respond to each other",
            messages=[]
        )

        for discussion_round in range(1, max_rounds + 1):
            round_speech_count = 0

            # Shuffle player order each round for fairness
            shuffled_players = alive_players.copy()
            random.shuffle(shuffled_players)

            # Build current conversation context for this round
            current_conversation = ""
            if discussion.messages:
                current_conversation = "\n".join([f"[{msg.sender}] {msg.content}" for msg in discussion.messages])

            for player in shuffled_players:
                try:
                    agent = self.player_agents[player.id]

                    # Give each player the updated conversation to consider responding
                    time.sleep(0.3)  # Shorter delay for more dynamic interaction
                    comment = agent.discuss(current_conversation, alive_names)

                    # Filter out "no comment" responses
                    if comment and comment.strip() and comment.strip().lower() != "no comment":
                        message_text = f"[{player.name}] {comment}"
                        messages.append(message_text)
                        self.state.game_log.append(message_text)
                        round_speech_count += 1

                        # Add to structured discussion
                        message = Message(
                            sender=player.name,
                            content=comment,
                            timestamp=datetime.now().isoformat(),
                            message_type="dynamic_comment"
                        )
                        discussion.messages.append(message)

                        # Update conversation immediately so next players see this comment
                        current_conversation = "\n".join([f"[{msg.sender}] {msg.content}" for msg in discussion.messages])

                        logger.info("Round %s: %s spoke", discussion_round, player.name)

                except Exception as e:
                    error_msg = str(e).lower()
                    if "rate limit" in error_msg or "429" in error_msg:
                        logger.warning("Rate limit hit for %s, they stay silent this round", player.name)
                        time.sleep(0.8)  # Extra delay on rate limit
                    else:
                        logger.warning("Error with player %s: %s", player.name, e)
                    continue

            # Rule-based Game Master decides whether to play another round
            if not self.game_master.should_continue_discussion(
                round_speech_count, discussion_round, len(alive_players), max_rounds
            ):
                end_announcement = self.game_master.announce_discussion_end()
                self.state.game_log.append(f"[GAME MASTER] {end_announcement}")
                break

            # Shorter delay between rounds for more dynamic feel
            time.sleep(0.5)

        # Save discussion to game state
        if discussion.messages:
            self.state.discussions.append(discussion)

        return messages

    def conduct_vote(self) -> Tuple[Optional[PlayerProfile], Dict[str, int]]:
        """
        Collect every player's vote and let the rules engine eliminate someone

        Returns:
            Tuple of (eliminated player, vote counts)
        """
        self.state.phase = GamePhase.VOTING

        alive_players = rules.alive_players(self.state)
        candidate_names = [p.name for p in alive_players]

        # Build complete conversation context for voting
        full_conversation = ""
        if self.state.discussions:
            latest_discussion = self.state.discussions[-1]
            if latest_discussion.messages:
                full_conversation = "\n".join([f"[{msg.sender}] {msg.content}" for msg in latest_discussion.messages])
            else:
                full_conversation = "No one spoke during the discussion - complete silence."
        else:
            full_conversation = "No discussion took place this phase."

        # Shuffle voting order to prevent influence
        shuffled_voters = alive_players.copy()
        random.shuffle(shuffled_voters)

        votes: Dict[str, str] = {}  # voter name -> target name
        for player in shuffled_voters:
            reason = None
            try:
                time.sleep(0.5)  # Rate limit protection

                vote_target = self.player_agents[player.id].vote(full_conversation, candidate_names)
                target = rules.find_player_by_name(self.state, vote_target)
                if target and target.name in candidate_names and target.name != player.name:
                    votes[player.name] = target.name
                    self.state.game_log.append(f"[VOTE] {player.name} votes to eliminate {target.name}")
                else:
                    reason = "invalid target corrected"
            except Exception as e:
                error_msg = str(e).lower()
                if "rate limit" in error_msg or "429" in error_msg:
                    logger.warning("Rate limit hit during voting for %s", player.name)
                    reason = "rate limited"
                    time.sleep(1)  # Extra delay after rate limit
                else:
                    logger.warning("Voting error for %s: %s", player.name, e)
                    reason = "error fallback"

            if reason:
                target_name = rules.fallback_vote_target(player.name, candidate_names)
                if target_name:
                    votes[player.name] = target_name
                    self.state.game_log.append(f"[VOTE] {player.name} votes for {target_name} ({reason})")

        eliminated, vote_counts = rules.resolve_vote(self.state, votes)
        if eliminated:
            announcement = self.game_master.narrate_elimination(
                eliminated.name, eliminated.role.value, by_vote=True
            )
            self.state.game_log.append(f"[GAME MASTER] {announcement}")
        return eliminated, vote_counts

    def check_win_condition(self) -> Optional[str]:
        """
        Check if game has ended

        Returns:
            Winning team ("werewolves" or "villagers") or None if game continues
        """
        return rules.check_win_condition(self.state)

    def end_game(self, winner: str) -> str:
        """
        End the game and announce winner

        Args:
            winner: Winning team

        Returns:
            Victory announcement
        """
        survivors = rules.end_game(self.state)
        announcement = self.game_master.announce_winner(winner, survivors)
        self.state.game_log.append(f"[GAME MASTER] {announcement}")

        return announcement

    def _get_game_state_dict(self) -> Dict[str, any]:
        """Convert game state to dictionary for agents"""
        # Get recent discussion history
        discussion_history = []
        for discussion in self.state.discussions[-3:]:  # Last 3 discussions
            for message in discussion.messages:
                discussion_history.append(f"[{message.sender}] {message.content}")

        return {
            'phase': self.state.phase.value,
            'day_number': self.state.day_number,
            'players': [
                {
                    'id': p.id,
                    'name': p.name,
                    'status': p.status.value
                }
                for p in self.state.players
            ],
            'recent_events': self.state.game_log[-3:] if self.state.game_log else [],
            'discussion_history': discussion_history,
            'all_discussions': [
                {
                    'round': d.round_number,
                    'topic': d.topic,
                    'messages': [{'sender': m.sender, 'content': m.content} for m in d.messages]
                }
                for d in self.state.discussions
            ]
        }
