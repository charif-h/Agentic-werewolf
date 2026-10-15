"""Prompt templates sent to the LLM"""
from backend.prompts.player import (
    LEAK_REMINDER, NO_COMMENT, TARGET_ANSWER_FORMAT, diary_notes, diary_prompt, discussion_prompt, game_context, hunter_prompt, knowledge_block,
    leaks_own_role, player_system_prompt, psytest_prompt, response_factors,
    short_reply_system_prompt, vote_prompt, witch_prompt,
)

__all__ = ["LEAK_REMINDER", "NO_COMMENT", "TARGET_ANSWER_FORMAT", "leaks_own_role", "diary_notes", "diary_prompt", "discussion_prompt", "game_context", "hunter_prompt", "knowledge_block",
           "player_system_prompt", "psytest_prompt", "response_factors",
           "short_reply_system_prompt", "vote_prompt", "witch_prompt"]
