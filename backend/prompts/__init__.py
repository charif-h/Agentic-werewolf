"""Prompt templates sent to the LLM"""
from backend.prompts.player import (
    BACKREFERENCE_REMINDER, LEAK_REMINDER, MATE_VOTE_REMINDER, reaction_prompt, updates_block, plan_reminder, suspect_reminder, vote_plan_prompt, REASON_REMINDER, NO_COMMENT, TARGET_ANSWER_FORMAT, diary_notes, diary_prompt, discussion_prompt, game_context, hunter_prompt, knowledge_block,
    leaks_own_role, player_system_prompt, psytest_prompt, refers_to_earlier_talk, response_factors,
    pack_talk_block, scene_block, short_reply_system_prompt, vote_prompt, witch_prompt, wolf_chat_prompt,
)

__all__ = ["reaction_prompt", "updates_block", "plan_reminder", "suspect_reminder", "vote_plan_prompt", "MATE_VOTE_REMINDER", "BACKREFERENCE_REMINDER", "REASON_REMINDER", "refers_to_earlier_talk", "scene_block", "pack_talk_block", "wolf_chat_prompt", "LEAK_REMINDER", "NO_COMMENT", "TARGET_ANSWER_FORMAT", "leaks_own_role", "diary_notes", "diary_prompt", "discussion_prompt", "game_context", "hunter_prompt", "knowledge_block",
           "player_system_prompt", "psytest_prompt", "response_factors",
           "short_reply_system_prompt", "vote_prompt", "witch_prompt"]
