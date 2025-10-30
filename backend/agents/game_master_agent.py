"""
Game Master AI Agent - Controls the game flow and narration
"""
from typing import Optional, List, Dict, Any
from langchain.schema import HumanMessage, SystemMessage
from backend.models.game_models import GamePhase, GameState, PlayerProfile
from backend.agents.ai_provider import AIProvider


class GameMasterAgent:
    """AI Agent that serves as the game master/narrator"""
    
    def __init__(self, ai_provider: Optional[str] = None):
        """
        Initialize the game master agent
        
        Args:
            ai_provider: Which AI provider to use (openai, gemini, mistral)
        """
        self.llm = AIProvider.get_llm(provider=ai_provider, temperature=0.7)
        self.game_state: Optional[GameState] = None
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt for the game master"""
        return """You are the Game Master of "The Werewolves of Millers Hollow."

Your responsibilities:
1. Narrate the story and set the atmosphere
2. Announce phase transitions (night/day)
3. Describe events (deaths, revelations, etc.)
4. Moderate discussions and maintain game flow
5. Explain game rules when needed

Your narration should be:
- Atmospheric and engaging
- Clear and concise
- Dramatic but not overly verbose
- Fair and neutral (don't reveal hidden information)

You are the storyteller who brings the village of Millers Hollow to life."""
    
    def narrate_game_start(self, players: List[PlayerProfile]) -> str:
        """
        Narrate the beginning of the game
        
        Args:
            players: List of all players in the game
            
        Returns:
            Opening narration
        """
        player_names = ", ".join([p.name for p in players])
        
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""The game is beginning with {len(players)} players: {player_names}.
            
Create an atmospheric opening narration for the game. Welcome the players to the village of Millers Hollow 
and set the scene for the werewolf mystery. Keep it under 100 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def announce_night(self, night_number: int) -> str:
        """
        Announce the beginning of night phase
        
        Args:
            night_number: Current night number
            
        Returns:
            Night announcement narration
        """
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""It is now Night {night_number}. 
            
Announce the night phase dramatically. Remind players that the village sleeps and 
those with night powers should act. Keep it under 50 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def announce_day(self, day_number: int, night_events: str) -> str:
        """
        Announce the beginning of day phase and reveal night events
        
        Args:
            day_number: Current day number
            night_events: Summary of what happened during the night
            
        Returns:
            Day announcement with night events
        """
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""It is now Day {day_number}. 

Night Events: {night_events}

Announce the day phase and reveal what happened during the night. 
Be dramatic but clear. Keep it under 75 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def narrate_elimination(self, player_name: str, role: str, by_vote: bool = True) -> str:
        """
        Narrate a player's elimination
        
        Args:
            player_name: Name of eliminated player
            role: The player's role
            by_vote: Whether eliminated by vote (True) or killed at night (False)
            
        Returns:
            Elimination narration
        """
        method = "voted out by the village" if by_vote else "killed during the night"
        
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""{player_name} has been {method}. Their role was: {role}.

Create a dramatic narration of this elimination. Keep it under 50 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def announce_winner(self, winning_team: str, survivors: List[str]) -> str:
        """
        Announce the game winner
        
        Args:
            winning_team: "villagers" or "werewolves"
            survivors: List of surviving player names
            
        Returns:
            Victory announcement
        """
        survivor_list = ", ".join(survivors) if survivors else "none"
        
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""The game has ended. The {winning_team} have won!

Survivors: {survivor_list}

Create a dramatic ending narration announcing the victory. Keep it under 75 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def moderate_discussion(self, context: str) -> str:
        """
        Moderate and guide discussion
        
        Args:
            context: Current discussion context
            
        Returns:
            Moderation message
        """
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""Current situation: {context}

Provide a brief moderation comment to guide the discussion or move it forward. 
Keep it under 40 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def explain_rules(self, question: str) -> str:
        """
        Explain game rules or mechanics
        
        Args:
            question: Question about the rules
            
        Returns:
            Rule explanation
        """
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""A player asks: {question}

Provide a clear, concise explanation of the game rules. Keep it under 60 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
