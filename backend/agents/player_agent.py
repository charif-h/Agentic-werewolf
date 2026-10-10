"""
Player AI Agent - Controls individual player behavior
"""
import random
import re
from typing import Optional, Dict, Any, List
from backend.models.game_models import PlayerProfile
from backend.llm import ASSISTANT, SYSTEM, USER, LLMClient, Message, fit_text
from backend.config import get_settings
from backend.game.targets import pick_target
from backend import prompts
from backend.roles import get_handler


class PlayerAgent:
    """AI Agent that represents a single player in the game"""

    def __init__(self, profile: PlayerProfile, llm: LLMClient):
        """
        Initialize a player agent

        Args:
            profile: The player's profile with personality and role
            llm: The language model this player talks to (shared between players)
        """
        self.profile = profile
        self.llm = llm
        self.memory: List[Message] = []  # Store conversation history
        self.knowledge: List[str] = []  # Secret facts learned during the game

    @property
    def handler(self):
        """Role handler holding this player's role-specific prompts and rules"""
        return get_handler(self.profile.role)

    def _build_system_prompt(self) -> str:
        """Build the system prompt based on player's personality and role"""
        profile = self.profile
        return prompts.player_system_prompt(
            profile.name, profile.age, profile.sex.value, profile.personality.value,
            profile.get_personality_description(),
            self.handler.description if profile.role else None,
            self.knowledge,
        )

    def _prepare_messages(self, system_prompt: str, user_message: str) -> list:
        """
        Prepare messages for LLM ensuring a proper alternating conversation format

        Args:
            system_prompt: System prompt
            user_message: Current user message

        Returns:
            List of messages in proper format
        """
        messages = [Message(SYSTEM, system_prompt)]

        # Add recent memory ensuring alternating User/Assistant pattern
        recent_memory = self.memory[-get_settings().memory_messages:] if get_settings().memory_messages else []

        # Ensure we don't have consecutive messages of the same type
        if recent_memory:
            # Filter to maintain alternating pattern
            filtered_memory = []
            last_type = None

            for msg in recent_memory:
                current_type = msg.role
                if current_type != last_type:
                    filtered_memory.append(msg)
                    last_type = current_type

            messages.extend(filtered_memory)

        # Always end with user message
        messages.append(Message(USER, user_message))

        return messages

    def get_action(self, game_state: Dict[str, Any], context: str) -> str:
        """
        Get the player's action or response based on current game state

        Args:
            game_state: Current state of the game
            context: Specific context or question for the player

        Returns:
            The player's response or action
        """
        system_prompt = self._build_system_prompt()

        alive_names = [p.get('name') for p in game_state.get('players', [])
                       if p.get('status') == 'alive']
        discussion_history = game_state.get('discussion_history', [])
        window = get_settings().discussion_context_messages
        game_context = prompts.game_context(
            game_state.get('phase', 'unknown'), game_state.get('day_number', 0), alive_names,
            game_state.get('recent_events', 'None'), discussion_history[-window:], context,
        )

        messages = self._prepare_messages(system_prompt, game_context)

        response = self.llm.generate(messages)

        self._remember(context, response)
        return response

    def _remember(self, question: str, answer: str) -> None:
        """
        Keep a short record of what was asked and answered (not the whole game
        state, which is sent again in every prompt) and forget the oldest entries
        """
        self.memory.append(Message(USER, question))
        self.memory.append(Message(ASSISTANT, answer))
        limit = get_settings().memory_messages
        self.memory = self.memory[-limit:] if limit else []

    def _fit_conversation(self, conversation: str) -> str:
        """Keep the most recent part of the conversation that fits the token budget"""
        return fit_text(conversation, get_settings().conversation_token_budget)

    def night_action(self, game_state: Dict[str, Any]) -> Optional[str]:
        """
        Perform night action based on role

        Args:
            game_state: Current game state

        Returns:
            Target player name or None
        """
        if not self.handler.acts_at_night:
            return None
        context = self.handler.night_prompt(game_state.get('valid_targets', []))
        return self.get_action(game_state, context)

    def add_knowledge(self, fact: str) -> None:
        """Remember a secret fact (e.g. the seer's findings); it appears in later prompts"""
        self.knowledge.append(fact)

    def witch_action(self, game_state: Dict[str, Any], victim: Optional[str], can_save: bool,
                     can_poison: bool, poison_targets: List[str]) -> str:
        """Ask the witch what she does tonight (raw answer, parsed by the game)"""
        context = prompts.witch_prompt(victim, can_save, can_poison, poison_targets)
        return self.get_action(game_state, context)

    def hunter_shot(self, game_state: Dict[str, Any], targets: List[str]) -> str:
        """Ask the dying hunter whom to shoot (raw answer, parsed by the game)"""
        context = prompts.hunter_prompt(self.handler.death_shot_instruction, targets)
        return self.get_action(game_state, context)

    def discuss(self, conversation_history: str, alive_players: list[str]) -> str:
        """
        Generate a strategic comment based on conversation history and role

        Args:
            conversation_history: Complete conversation so far
            alive_players: List of alive player names

        Returns:
            Strategic comment or "no comment" if player chooses to stay silent
        """
        conversation_history = self._fit_conversation(conversation_history)
        context = prompts.discussion_prompt(
            self.profile.name, conversation_history, alive_players, self.profile.role.value,
            self.handler.discussion_strategy,
            self._should_respond_to_conversation(conversation_history),
            self.knowledge,
        )

        try:
            response = self._clean_reply(self._get_llm_response(context))
            if prompts.leaks_own_role(response, self.profile.role.value):
                # Ask once more, with a reminder; give up (stay silent) if it happens again
                response = self._clean_reply(self._get_llm_response(context + prompts.LEAK_REMINDER))
                if prompts.leaks_own_role(response, self.profile.role.value):
                    return prompts.NO_COMMENT
            return response or prompts.NO_COMMENT

        except Exception:
            # Safe fallback if the API fails
            return prompts.NO_COMMENT

    @staticmethod
    def _clean_reply(text: str) -> str:
        """Trim the answer and the quotes models like to put around speech"""
        reply = text.strip().strip('"\u201c\u201d').strip()
        if reply.lower().strip(". ") == prompts.NO_COMMENT:
            return ""
        # Models like to add "No comment." after a real sentence
        return re.sub(r"(?i)[\s.!]*\bno comment\b[\s.!]*$", "", reply).strip() or ""

    def _should_respond_to_conversation(self, conversation_history: str) -> str:
        """
        Check if player has special reasons to respond to current conversation

        Args:
            conversation_history: Current conversation

        Returns:
            String describing response factors
        """
        return prompts.response_factors(self.profile.name, conversation_history,
                                        self.handler.response_hint)

    def vote(self, conversation_history: str, alive_players: list[str]) -> str:
        """
        Make an independent voting decision based on strategic analysis

        Args:
            conversation_history: Complete conversation from discussion phase
            alive_players: List of all alive players who can be voted for

        Returns:
            Name of the player to vote for (must be from alive_players list)
        """
        # Remove self from voting options
        other_players = [p for p in alive_players if p != self.profile.name]

        if not other_players:
            return alive_players[0] if alive_players else ""

        context = prompts.vote_prompt(
            self.profile.name, self.profile.role.value, self.handler.voting_strategy,
            self._fit_conversation(conversation_history), other_players, self.knowledge,
        )

        try:
            response = self._get_llm_response(context)

            # Extract player name from response
            response = response.strip()

            # Unclear answer: random valid candidate (avoids bias toward the first player)
            return pick_target(response, other_players)

        except Exception:
            # Random vote as fallback to ensure independence
            return random.choice(other_players)

    def _get_llm_response(self, context: str) -> str:
        """Get response from LLM with error handling"""
        system_prompt = prompts.short_reply_system_prompt(
            self.profile.name, self.profile.personality.value
        )

        messages = self._prepare_messages(system_prompt, context)
        return self.llm.generate(messages)
