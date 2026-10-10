"""
Player AI Agent - Controls individual player behavior

Every decision (vote, night target, witch potions, hunter shot, what to say)
is requested as JSON that matches a schema, so the model can only answer with
valid names and the code never has to guess what a sentence meant.
"""
import logging
import random
import re
from typing import Optional, Dict, Any, List
from backend.models.game_models import PlayerProfile
from backend.llm import ASSISTANT, SYSTEM, USER, LLMClient, Message, fit_text
from backend.llm import schemas
from backend.config import get_settings
from backend import prompts
from backend.roles import get_handler

logger = logging.getLogger(__name__)

DECISION_TOKENS = 60      # a JSON object holding a name
SPEECH_TOKENS = 160       # a JSON object holding one or two sentences


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

    def _ask(self, system_prompt: str, context: str, schema: Dict[str, Any],
             max_tokens: int) -> Optional[str]:
        """
        Send a question and ask for JSON matching `schema`

        Returns:
            The raw answer, or None if the model could not be reached
        """
        messages = self._prepare_messages(system_prompt, context)
        try:
            return self.llm.generate(messages, json_schema=schema, max_tokens=max_tokens)
        except Exception as e:
            logger.warning("%s: model call failed: %s", self.profile.name, e)
            return None

    def _ask_in_game(self, game_state: Dict[str, Any], action: str, schema: Dict[str, Any]) -> Optional[str]:
        """Ask a question that needs the game state (night actions, witch, hunter)"""
        alive_names = [p.get('name') for p in game_state.get('players', [])
                       if p.get('status') == 'alive']
        discussion_history = game_state.get('discussion_history', [])
        window = get_settings().discussion_context_messages
        context = prompts.game_context(
            game_state.get('phase', 'unknown'), game_state.get('day_number', 0), alive_names,
            game_state.get('recent_events', 'None'), discussion_history[-window:], action,
        )
        return self._ask(self._build_system_prompt(), context, schema, DECISION_TOKENS)

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

    def _choose_target(self, game_state: Dict[str, Any], action: str, names: List[str]) -> Optional[str]:
        """Ask for one of `names`; None if the model failed or answered nonsense"""
        raw = self._ask_in_game(game_state, action, schemas.target_schema(names))
        target = schemas.parse_target(raw, names) if names else None
        if target:
            self._remember(action, target)
        return target

    def night_action(self, game_state: Dict[str, Any]) -> Optional[str]:
        """
        Perform night action based on role

        Args:
            game_state: Current game state (`valid_targets` lists the names to choose from)

        Returns:
            The chosen player name, or None if the role has no night action or
            the model gave no valid answer (the game then picks a random target)
        """
        if not self.handler.acts_at_night:
            return None
        names = game_state.get('valid_targets', [])
        return self._choose_target(game_state, self.handler.night_prompt(names), names)

    def add_knowledge(self, fact: str) -> None:
        """Remember a secret fact (e.g. the seer's findings); it appears in later prompts"""
        self.knowledge.append(fact)

    def witch_action(self, game_state: Dict[str, Any], victim: Optional[str], can_save: bool,
                     can_poison: bool, poison_targets: List[str]) -> str:
        """
        Ask the witch what she does tonight

        Returns:
            "SAVE", "POISON <name>", "SAVE and POISON <name>" or "PASS". Potions she
            no longer has, and unclear answers, give "PASS" (a potion is never used at random).
        """
        action = prompts.witch_prompt(victim, can_save, can_poison, poison_targets)
        raw = self._ask_in_game(game_state, action, schemas.witch_schema(poison_targets))
        decision = schemas.parse_witch(raw, poison_targets)
        if decision is None:
            return "PASS"
        save, poison = decision
        parts = []
        if save and can_save:
            parts.append("SAVE")
        if poison and can_poison:
            parts.append(f"POISON {poison}")
        answer = " and ".join(parts) or "PASS"
        self._remember(action, answer)
        return answer

    def hunter_shot(self, game_state: Dict[str, Any], targets: List[str]) -> Optional[str]:
        """Ask the dying hunter whom to shoot; None if the model gave no valid answer"""
        action = prompts.hunter_prompt(self.handler.death_shot_instruction, targets)
        return self._choose_target(game_state, action, targets)

    def discuss(self, conversation_history: str, alive_players: list[str]) -> str:
        """
        Generate a strategic comment based on conversation history and role

        Args:
            conversation_history: Complete conversation so far
            alive_players: List of alive player names

        Returns:
            What the player says, or "no comment" if they stay silent
        """
        conversation_history = self._fit_conversation(conversation_history)
        context = prompts.discussion_prompt(
            self.profile.name, conversation_history, alive_players, self.profile.role.value,
            self.handler.discussion_strategy,
            self._should_respond_to_conversation(conversation_history),
            self.knowledge,
        )

        reply = self._speak(context)
        if reply and prompts.leaks_own_role(reply, self.profile.role.value):
            # Ask once more, with a reminder; give up (stay silent) if it happens again
            reply = self._speak(context + prompts.LEAK_REMINDER)
            if reply and prompts.leaks_own_role(reply, self.profile.role.value):
                reply = ""
        return reply or prompts.NO_COMMENT

    def _speak(self, context: str) -> str:
        """One attempt at a discussion answer; '' when silent, unclear or unreachable"""
        system_prompt = prompts.short_reply_system_prompt(
            self.profile.name, self.profile.personality.value
        )
        parsed = schemas.parse_discussion(
            self._ask(system_prompt, context, schemas.discussion_schema(), SPEECH_TOKENS)
        )
        if parsed is None or not parsed[0]:
            return ""
        return self._clean_reply(parsed[1])

    @staticmethod
    def _clean_reply(text: str) -> str:
        """Trim the answer and the quotes models like to put around speech"""
        reply = text.strip().strip('"“”').strip()
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
            Name of the player to vote for (always one of the other alive players)
        """
        # Remove self from voting options
        other_players = [p for p in alive_players if p != self.profile.name]

        if not other_players:
            return alive_players[0] if alive_players else ""

        context = prompts.vote_prompt(
            self.profile.name, self.profile.role.value, self.handler.voting_strategy,
            self._fit_conversation(conversation_history), other_players, self.knowledge,
        )
        system_prompt = prompts.short_reply_system_prompt(
            self.profile.name, self.profile.personality.value
        )
        raw = self._ask(system_prompt, context, schemas.target_schema(other_players), DECISION_TOKENS)
        # No valid answer (model down, nonsense): a random candidate keeps votes independent
        return schemas.parse_target(raw, other_players) or random.choice(other_players)
