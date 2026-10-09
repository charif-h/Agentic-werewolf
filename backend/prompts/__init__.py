"""Prompt templates sent to the LLM"""
from backend.prompts.player import (
    discussion_prompt, game_context, hunter_prompt, knowledge_block, personality_behavior,
    player_system_prompt, response_factors, short_reply_system_prompt, vote_prompt,
    witch_prompt,
)

__all__ = ["discussion_prompt", "game_context", "hunter_prompt", "knowledge_block",
           "personality_behavior", "player_system_prompt", "response_factors",
           "short_reply_system_prompt", "vote_prompt", "witch_prompt"]
