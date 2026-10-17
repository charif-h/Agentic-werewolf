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
from backend.llm.tokens import OMISSION_NOTICE, fit_lines
from backend.llm import schemas
from backend.agents import psytest
from backend.models.diary import DAY_SUMMARY, HEADER_KINDS, DECISION, NIGHT_SUMMARY, PACK, PLAN, REACTION, ROLE_CARD, make_entry
from backend.models.personality import TRAITS, PersonaCheck
from backend.config import get_settings
from backend.llm.metrics import current_metrics
from backend import prompts
from backend.roles import get_handler

logger = logging.getLogger(__name__)

DECISION_TOKENS = 160     # a JSON object holding a reason and a name
DIARY_TOKENS = 600         # a summary and one opinion per other player
PSYTEST_TOKENS = 400      # six statements with their ratings, as JSON
SPEECH_TOKENS = 200       # a JSON object holding a private reason and one or two sentences


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
        self.vote_plan: Optional[Dict[str, Any]] = None   # whom the player planned to vote against today
        self.mates: List[str] = []   # the other werewolves, for a werewolf (set by `set_pack`)
        self._speech_reason = ""   # private reason of the latest discussion answer
        self.last_vote: Optional[str] = None   # whom this player voted for most recently
        self.diary: List[Dict[str, Any]] = []  # Typed entries (see `backend.models.diary`): role card, pack, one summary per night and day

    @property
    def handler(self):
        """Role handler holding this player's role-specific prompts and rules"""
        return get_handler(self.profile.role)

    def _build_system_prompt(self) -> str:
        """Build the system prompt based on player's personality and role"""
        profile = self.profile
        return prompts.player_system_prompt(
            profile.name, profile.age, profile.sex.value, profile.get_personality_description(),
            self.handler.description if profile.role else None,
            self.knowledge,
        )

    def _prepare_messages(self, system_prompt: str, user_message: str, use_memory: bool = True) -> list:
        """
        Prepare messages for LLM ensuring a proper alternating conversation format

        Args:
            system_prompt: System prompt
            user_message: Current user message
            use_memory: False to leave out what was asked before (first message of a day)

        Returns:
            List of messages in proper format
        """
        messages = [Message(SYSTEM, system_prompt)]

        # Add recent memory ensuring alternating User/Assistant pattern
        limit = get_settings().memory_messages
        recent_memory = self.memory[-limit:] if use_memory and limit else []

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
             max_tokens: int, use_memory: bool = True) -> Optional[str]:
        """
        Send a question and ask for JSON matching `schema`

        Returns:
            The raw answer, or None if the model could not be reached
        """
        messages = self._prepare_messages(system_prompt, context, use_memory)
        try:
            return self.llm.generate(messages, json_schema=schema, max_tokens=max_tokens)
        except Exception as e:
            logger.warning("%s: model call failed: %s", self.profile.name, e)
            return None

    def _game_context(self, game_state: Dict[str, Any], action: str) -> str:
        """The game state followed by a question that needs it (night actions, witch, hunter)"""
        alive_names = [p.get('name') for p in game_state.get('players', [])
                       if p.get('status') == 'alive']
        discussion_history = game_state.get('discussion_history', [])
        window = get_settings().discussion_context_messages
        return prompts.game_context(
            game_state.get('phase', 'unknown'), game_state.get('day_number', 0), alive_names,
            game_state.get('recent_events', 'None'), discussion_history[-window:], action,
        )

    @staticmethod
    def _step_of(game_state: Dict[str, Any]) -> str:
        """Diary step of a decision taken in `game_state`: "Night 2", "Day 1" """
        return f"{'Night' if game_state.get('phase') == 'night' else 'Day'} {game_state.get('day_number', 0)}"

    def _ask_decision(self, system_prompt: str, context: str, schema: Dict[str, Any], parse,
                      tokens: int = DECISION_TOKENS, use_memory: bool = True) -> Optional[Dict[str, Any]]:
        """
        Ask for a decision and its reason. `parse(raw)` gives a dict with a "reason", or None when the
        answer is unusable. An unusable answer, or one without a reason, is asked once more; a valid
        decision that still has no reason is kept (and counted) rather than replaced by chance.
        """
        decision = parse(self._ask(system_prompt, context, schema, tokens, use_memory))
        if decision is None or not decision["reason"]:
            again = parse(self._ask(system_prompt, context + prompts.REASON_REMINDER, schema, tokens, use_memory))
            if again is not None and (decision is None or again["reason"]):
                decision = again
        if decision is not None and not decision["reason"]:
            metrics = current_metrics()
            if metrics is not None:
                metrics.add_missing_reason()
        return decision

    def _record_decision(self, step: str, label: str, decision: Dict[str, Any], kind: str,
                         tag: Optional[str] = None) -> None:
        """
        Write the reason of a decision in the diary right away (no model call), e.g.
        "My vote: Bob. Why: he dodges every question. Why not Cy: he helped me."
        """
        if not get_settings().diary_enabled:
            return
        text = f"{label}. Why: {decision['reason'] or 'no reason given'}"
        not_chosen = decision.get("not_chosen")
        if not_chosen:
            text += f" Why not {not_chosen['player']}: {not_chosen['why_not']}"
        data = {key: decision[key] for key in ("target", "reason", "not_chosen") if key in decision}
        data["decision"] = kind
        if tag:
            data["tag"] = tag
        self._add_entry(step, DECISION, text, data)

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

    def _choose_target(self, game_state: Dict[str, Any], action: str, names: List[str],
                       label: str, kind: str) -> Optional[str]:
        """Ask for one of `names` and a reason (written in the diary); None if the model failed or
        answered nonsense"""
        if not names:
            return None
        decision = self._ask_decision(
            self._build_system_prompt(), self._game_context(game_state, action),
            schemas.target_schema(names), lambda raw: schemas.parse_decision(raw, names))
        if decision is None:
            self._note_invalid_answer()
            return None
        target = decision["target"]
        self._remember(action, target)
        self._record_decision(self._step_of(game_state), f"{label}: {target}", decision, kind)
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
        action = prompts.pack_talk_block(game_state.get('wolf_chat', [])) + self.handler.night_prompt(names)
        return self._choose_target(game_state, action, names, "My night choice", "night")

    def wolf_chat(self, talk: List[str], mates: List[str], targets: List[str]) -> str:
        """What a werewolf tells the pack before the victim is chosen ('' when silent or unclear)"""
        context = prompts.wolf_chat_prompt(self.profile.name, mates, targets, talk, self._knowledge_with_notes())
        system_prompt = prompts.short_reply_system_prompt(self.profile.name, self.profile.personality.summary())
        parsed = schemas.parse_discussion(
            self._ask(system_prompt, context, schemas.discussion_schema(), SPEECH_TOKENS))
        if parsed is None:
            self._note_invalid_answer()
            return ""
        return self._clean_reply(parsed[1]) if parsed[0] else ""

    def note_night_plan(self, night: int, victim: str) -> None:
        """Write down the victim the pack agreed on (no model call)"""
        if get_settings().diary_enabled:
            self._add_entry(f"Night {night}", PLAN, f"Tonight the pack kills {victim}.", {"victim": victim})

    def _knowledge_with_notes(self) -> List[str]:
        """
        Secret facts plus the diary, in two tiers: "who I am" (role card and pack, never cut) and
        the latest entries, newest first, within the token budget. The opinions of the latest
        summary are added so that what the player says and votes follows what they wrote down.
        """
        header = [f"Your diary, first page: {e['text']}" for e in self.diary if e["kind"] in HEADER_KINDS]
        recent = [f"{e['step']}: {e['text']}" for e in self.diary if e["kind"] not in HEADER_KINDS]
        recent = recent[-max(get_settings().diary_prompt_entries, 0):]
        lines = [line for line in fit_lines(recent, get_settings().diary_token_budget)
                 if line != OMISSION_NOTICE]
        notes = prompts.diary_notes(self._last_summary())
        if lines:
            lines = ["Your private diary, newest entry first:"] + lines[::-1]
        return self.knowledge + header + lines + (
            ["Your private notes after the last night or day:"] + notes if notes else [])

    def _last_summary(self) -> Optional[Dict[str, Any]]:
        """The latest night or day summary of the diary, if any"""
        return next((e for e in reversed(self.diary) if e["kind"] in (NIGHT_SUMMARY, DAY_SUMMARY)), None)

    def _add_entry(self, step: str, kind: str, text: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Append a typed entry to the diary"""
        entry = make_entry(len(self.diary) + 1, step, kind, text, data)
        self.diary.append(entry)
        return entry

    def write_role_card(self) -> Dict[str, Any]:
        """The first diary entry: the role the player was given (no model call, the role is known)"""
        role = self.profile.role.value
        return self._add_entry("Role card", ROLE_CARD, f"I am a {role}.", {"role": role})

    def set_pack(self, mates: List[str]) -> None:
        """Learn who the other werewolves are: noted in the diary (a `pack` entry), or kept as a
        secret fact when the diary is off. The list never comes from free text."""
        if get_settings().diary_enabled:
            self.write_pack(mates)
        else:
            self.mates = list(mates)
            self.add_knowledge(f"The other werewolves are: {', '.join(mates)}.")

    def write_pack(self, mates: List[str]) -> Dict[str, Any]:
        """Note the other members of the pack (the werewolves) in the diary"""
        self.mates = list(mates)
        return self._add_entry("Pack", PACK, f"My fellow werewolves are {', '.join(mates)}. I must hide it.", {"mates": mates})

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
        def parse(raw):
            found = schemas.parse_witch(raw, poison_targets)
            return None if found is None else {"save": found[0], "poison": found[1],
                                               "reason": schemas.parse_reason(raw)}

        decision = self._ask_decision(self._build_system_prompt(), self._game_context(game_state, action),
                                      schemas.witch_schema(poison_targets), parse)
        if decision is None:
            self._note_invalid_answer()
            return "PASS"
        save, poison = decision["save"], decision["poison"]
        parts = []
        if save and can_save:
            parts.append("SAVE")
        if poison and can_poison:
            parts.append(f"POISON {poison}")
        answer = " and ".join(parts) or "PASS"
        self._remember(action, answer)
        self._record_decision(self._step_of(game_state), f"My potion decision: {answer}", decision, "witch")
        return answer

    def hunter_shot(self, game_state: Dict[str, Any], targets: List[str]) -> Optional[str]:
        """Ask the dying hunter whom to shoot; None if the model gave no valid answer"""
        action = prompts.hunter_prompt(self.handler.death_shot_instruction, targets)
        return self._choose_target(game_state, action, targets, "My last shot", "hunter")

    def write_diary(self, step: str, events: str, others: List[str]) -> Optional[Dict[str, Any]]:
        """
        Write the private diary entry for a step ("Night 1", "Day 2"): a summary and an opinion
        of every player in `others`, in the voice of this player's personality

        Args:
            step: Name of the step that just ended
            events: What happened during it (the game log lines)
            others: Names of the other living players

        Returns:
            The entry (also appended to `self.diary`), or None if the model gave no valid answer
        """
        if not others:
            return None
        profile = self.profile
        mates = [name for name in others if name in self.mates]
        if mates:                                  # a werewolf knows its pack: it only plans for the others
            others = [name for name in others if name not in mates]
            if not others:
                return None
        last = self._last_summary()
        previous = last["text"] if last else None
        context = prompts.diary_prompt(
            profile.name, profile.role.value, profile.personality.summary(), step,
            self._fit_conversation(events), others, previous, self.knowledge,
            self.last_vote if step.startswith("Day") else None, mates or None,
            self.vote_plan if step.startswith("Day") else None,
        )
        system_prompt = prompts.short_reply_system_prompt(profile.name, profile.personality.summary())
        entry = schemas.parse_diary(
            self._ask(system_prompt, context, schemas.diary_schema(others, wolf=bool(mates)), DIARY_TOKENS),
            others, wolf=bool(mates))
        if entry is None:
            self._note_invalid_answer()
            return None
        return self._add_entry(step, NIGHT_SUMMARY if step.startswith("Night") else DAY_SUMMARY,
                               entry["summary"], {"opinions": entry["opinions"]})

    def take_psytest(self) -> PersonaCheck:
        """
        Answer the psychological test in character and compare the result with the
        assigned Big Five levels. A trait that differs is flagged, the player still plays.
        The result is stored in `profile.persona_check`.
        """
        profile = self.profile
        system_prompt = prompts.player_system_prompt(
            profile.name, profile.age, profile.sex.value, profile.get_personality_description())
        answers: Optional[list] = []
        for trait in TRAITS:                      # one call per trait: six statements are easy to keep in line
            statements = psytest.statements_of(trait)
            context = prompts.psytest_prompt(profile.name, statements)
            ratings = schemas.parse_psytest(
                self._ask(system_prompt, context, schemas.psytest_schema(len(statements)), PSYTEST_TOKENS),
                len(statements))
            if ratings is None:
                self._note_invalid_answer()
                answers = None
                break
            answers += ratings
        check = psytest.evaluate(answers, profile.personality)
        profile.persona_check = check
        metrics = current_metrics()
        if metrics is not None and check.completed:
            metrics.add_psytest(bool(check.flagged))
        return check

    def write_reaction(self, step: str, cause: str, new_lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        Note in the diary, in a sentence or two, how the player reacts to a change in the discussion
        (accused, a role claim, a new suspect) and what they will do. One model call, none when the
        diary is off; the note is None if the model gave nothing usable.
        """
        if not get_settings().diary_enabled:
            return None
        context = prompts.reaction_prompt(self.profile.name, cause, new_lines, self._knowledge_with_notes())
        system_prompt = prompts.short_reply_system_prompt(self.profile.name, self.profile.personality.summary())
        note = schemas.parse_reaction(self._ask(system_prompt, context, schemas.reaction_schema(), SPEECH_TOKENS))
        if note is None:
            self._note_invalid_answer()
            return None
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_reaction_entry()
        return self._add_entry(step, REACTION, note, {"cause": cause})

    def discuss(self, conversation_history: str, alive_players: list[str], scene: str = "", step: str = "Day",
                new_lines: Optional[List[str]] = None) -> str:
        """
        Generate a strategic comment based on conversation history and role

        Args:
            conversation_history: Complete conversation so far
            alive_players: List of alive player names
            scene: Where the village is (see `prompts.scene_block`), put on top of the prompt
            step: Diary step ("Day 2") a line that names a player is justified under
            new_lines: What was said since this player's last turn (None before their first turn)

        Returns:
            What the player says, or "no comment" if they stay silent
        """
        conversation_history = self._fit_conversation(conversation_history)
        context = prompts.discussion_prompt(
            self.profile.name, conversation_history, alive_players, self.profile.role.value,
            self.handler.discussion_strategy,
            self._should_respond_to_conversation(conversation_history),
            self._knowledge_with_notes(), scene,
            prompts.updates_block(self.profile.name, new_lines, mentions_only=False) if new_lines is not None else
            prompts.updates_block(self.profile.name,
                                  [line for line in conversation_history.split("\n") if line.strip()][-6:],
                                  mentions_only=True),
        )

        # The first message of a day starts without the player's earlier answers: they feed
        # the feeling of continuing a talk that never happened
        opening = not conversation_history.strip()
        reply = self._speak(context, use_memory=not opening)
        if opening and reply and prompts.refers_to_earlier_talk(reply):
            # Nobody has spoken, yet the line refers to an earlier exchange: ask once more
            self._note_opening_backreference()
            reply = self._speak(context + prompts.BACKREFERENCE_REMINDER, use_memory=False)
        if reply and prompts.leaks_own_role(reply, self.profile.role.value):
            # Ask once more, with a reminder; give up (stay silent) if it happens again
            self._note_role_leak()
            reply = self._speak(context + prompts.LEAK_REMINDER, use_memory=not opening)
            if reply and prompts.leaks_own_role(reply, self.profile.role.value):
                self._note_role_leak()
                reply = ""
        if reply and self._speech_reason and any(
                re.search(rf"(?<!\w){re.escape(other)}(?!\w)", reply) for other in alive_players
                if other != self.profile.name):
            # A line that accuses or defends someone: the private reason goes to the diary
            self._record_decision(step, f'I said: "{reply}"', {"reason": self._speech_reason}, "speech")
        return reply or prompts.NO_COMMENT

    def _speak(self, context: str, use_memory: bool = True) -> str:
        """One attempt at a discussion answer; '' when silent, unclear or unreachable"""
        system_prompt = prompts.short_reply_system_prompt(
            self.profile.name, self.profile.personality.summary()
        )
        raw = self._ask(system_prompt, context, schemas.discussion_schema(), SPEECH_TOKENS, use_memory)
        parsed = schemas.parse_discussion(raw)
        self._speech_reason = schemas.parse_reason(raw)
        if parsed is None:
            self._note_invalid_answer()
            return ""
        if not parsed[0]:
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

    def _guard_mates(self, decision, mates, system_prompt, context, schema, parse):
        """
        A werewolf must not target a mate unless it is a deliberate sacrifice (`sacrifice_mate` and a
        reason). A mistake is counted and asked once more; if it happens again the decision is dropped.

        Returns:
            `(decision or None, tag)`; the tag is "intentional_sacrifice" for a deliberate sacrifice
        """
        if decision is None or not mates or decision["target"] not in mates:
            return decision, None
        if decision["sacrifice_mate"] and decision["reason"]:
            self._note_wolf_sacrifice()
            return decision, "intentional_sacrifice"
        self._note_wolf_voted_mate()
        decision = self._ask_decision(system_prompt, context + prompts.MATE_VOTE_REMINDER, schema, parse)
        if decision is not None and decision["target"] in mates:
            if decision["sacrifice_mate"] and decision["reason"]:
                self._note_wolf_sacrifice()
                return decision, "intentional_sacrifice"
            return None, None
        return decision, None

    def _top_suspect(self) -> Optional[str]:
        """The player the latest diary summary suspects most (None for a werewolf or without suspects)"""
        last = self._last_summary()
        rank = {"low": 1, "medium": 2, "high": 3}
        suspects = [o for o in (last["data"].get("opinions", []) if last else []) if o.get("guess") == "werewolf"]
        return max(suspects, key=lambda o: rank.get(o.get("confidence"), 0))["player"] if suspects else None

    def plan_vote(self, conversation_history: str, alive_players: list[str], scene: str = "",
                  step: str = "Day") -> Optional[Dict[str, Any]]:
        """
        Decide, before the vote, whom to vote against and why, and write it in the diary as a
        `plan` entry. The vote then takes this plan as its main input and is checked against it.
        A villager plans against the top suspect of the diary (or says what changed), a werewolf
        never against a mate (unless as a deliberate sacrifice).

        Returns:
            The plan `{"target", "reason", "step"}`, also kept in `self.vote_plan`; None when
            planning is off or the model gave no usable plan
        """
        self.vote_plan = None
        if not get_settings().vote_plan_enabled:
            return None
        others = [p for p in alive_players if p != self.profile.name]
        if not others:
            return None
        mates = [name for name in others if name in self.mates]
        suspect = None if mates else self._top_suspect()
        context = prompts.vote_plan_prompt(
            self.profile.name, self.profile.role.value, self.handler.voting_strategy,
            self._fit_conversation(conversation_history), others, self._knowledge_with_notes(), scene,
            mates or None, suspect)
        system_prompt = prompts.short_reply_system_prompt(self.profile.name, self.profile.personality.summary())
        schema = schemas.target_schema(others, sacrifice=bool(mates))
        parse = lambda raw: schemas.parse_decision(raw, others)       # noqa: E731
        decision = self._ask_decision(system_prompt, context, schema, parse)
        decision, tag = self._guard_mates(decision, mates, system_prompt, context, schema, parse)
        if decision is not None and suspect and decision["target"] != suspect:
            again = self._ask_decision(system_prompt, context + prompts.suspect_reminder(suspect), schema, parse)
            if again is not None and (again["target"] == suspect or again["reason"]):
                decision = again               # the top suspect, or a change that is explained
            else:
                decision = {**decision, "target": suspect, "reason": decision["reason"] or "my top suspect"}
        if decision is None:
            self._note_invalid_answer()
            return None
        self.vote_plan = {"target": decision["target"], "reason": decision["reason"], "step": step}
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_vote_plan()
        if get_settings().diary_enabled:
            self._add_entry(step, PLAN, f"Today I will vote against {decision['target']} because "
                            f"{decision['reason'].rstrip('.') or 'my notes say so'}.",
                            {"target": decision["target"], "reason": decision["reason"], "vote": True,
                             **({"tag": tag} if tag else {})})
        return self.vote_plan

    def vote(self, conversation_history: str, alive_players: list[str], scene: str = "", step: str = "Day") -> str:
        """
        Make an independent voting decision based on strategic analysis

        With a plan written before the vote (`plan_vote`), the plan is the main input and the vote is
        checked against it: a different target is asked once more ("vote X, or explain the change");
        an explained change is kept (and logged as a decision), an unexplained one gives the plan back.

        Args:
            conversation_history: Complete conversation from discussion phase
            alive_players: List of all alive players who can be voted for
            scene: Where the village is (see `prompts.scene_block`), put on top of the prompt
            step: Diary step ("Day 2") the vote is justified under

        Returns:
            Name of the player to vote for (always one of the other alive players)
        """
        # Remove self from voting options
        other_players = [p for p in alive_players if p != self.profile.name]

        if not other_players:
            return alive_players[0] if alive_players else ""

        mates = [name for name in other_players if name in self.mates]
        plan = self.vote_plan if self.vote_plan and self.vote_plan["step"] == step else None
        context = prompts.vote_prompt(
            self.profile.name, self.profile.role.value, self.handler.voting_strategy,
            self._fit_conversation(conversation_history), other_players, self._knowledge_with_notes(), scene,
            mates or None, plan,
        )
        system_prompt = prompts.short_reply_system_prompt(
            self.profile.name, self.profile.personality.summary()
        )
        schema = schemas.target_schema(other_players, vote=True, sacrifice=bool(mates))
        parse = lambda raw: schemas.parse_decision(raw, other_players)       # noqa: E731
        decision = self._ask_decision(system_prompt, context, schema, parse)
        decision, tag = self._guard_mates(decision, mates, system_prompt, context, schema, parse)
        if decision is not None and plan and decision["target"] != plan["target"]:
            decision, tag = self._reconcile_with_plan(decision, tag, plan, mates, system_prompt, context, schema, parse)
        # No valid answer (model down, nonsense): a random candidate keeps votes independent
        if decision is None:
            self._note_invalid_answer()
        else:
            self._record_decision(step, f"My vote: {decision['target']}", decision, "vote", tag)
        fallback = [name for name in other_players if name not in mates] or other_players
        self.last_vote = decision["target"] if decision else random.choice(fallback)
        return self.last_vote

    def _reconcile_with_plan(self, decision, tag, plan, mates, system_prompt, context, schema, parse):
        """The vote differs from the plan: ask once more. Same target: coherent. Another target with a
        reason: the change is kept (tag "plan_change"). Otherwise the plan wins (an unexplained change)."""
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_diary_vote_mismatch()
        again = self._ask_decision(system_prompt, context + prompts.plan_reminder(plan["target"]), schema, parse)
        again, again_tag = self._guard_mates(again, mates, system_prompt, context, schema, parse)
        if again is not None and again["target"] == plan["target"]:
            return again, again_tag
        if again is not None and again["reason"]:
            return again, again_tag or "plan_change"
        if metrics is not None:
            metrics.add_unexplained_change()
        return {"target": plan["target"], "reason": plan["reason"] or "my plan", "not_chosen": None,
                "sacrifice_mate": False}, "plan_restored"

    @staticmethod
    def _note_invalid_answer() -> None:
        """Count an unusable answer in the metrics of the running game, if it is tracked"""
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_invalid_answer()

    @staticmethod
    def _note_wolf_voted_mate() -> None:
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_wolf_voted_mate_unintended()

    @staticmethod
    def _note_wolf_sacrifice() -> None:
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_wolf_sacrificed_mate()

    @staticmethod
    def _note_opening_backreference() -> None:
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_opening_backreference()

    @staticmethod
    def _note_role_leak() -> None:
        metrics = current_metrics()
        if metrics is not None:
            metrics.add_role_leak()
