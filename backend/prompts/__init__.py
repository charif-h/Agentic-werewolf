"""Prompt templates sent to the LLM"""
from backend.prompts.player import (
    LEAK_REMINDER, NO_COMMENT, TARGET_ANSWER_FORMAT, discussion_prompt, game_context, hunter_prompt, knowledge_block,
    leaks_own_role, personality_behavior, player_system_prompt, response_factors,
    short_reply_system_prompt, vote_prompt, witch_prompt,
)

__all__ = ["LEAK_REMINDER", "NO_COMMENT", "TARGET_ANSWER_FORMAT", "leaks_own_role", "discussion_prompt", "game_context", "hunter_prompt", "knowledge_block",
           "personality_behavior", "player_system_prompt", "response_factors",
           "short_reply_system_prompt", "vote_prompt", "witch_prompt"]
