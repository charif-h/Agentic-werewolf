"""
Game Master AI Agent - Controls the game flow and narration
"""
from typing import Optional, List, Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
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
1. Announce phase transitions (night/day)
2. Report events factually (deaths, actions, etc.)
3. Moderate discussions and maintain game flow
4. Explain game rules when needed
5. Provide clear information to players

Your announcements should be:
- Factual and informative
- Clear and concise
- Direct and straightforward
- Neutral and objective (don't reveal hidden information)

You are the impartial referee who manages the game flow."""
    
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
            
Announce the start of the game. Be factual and brief. Simply state that the game begins and mention the number of players. Keep it under 30 words.""")
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
            
Announce the night phase. State that it is night and that special roles should act. Keep it under 20 words.""")
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

Announce the day phase and report what happened during the night. 
Be factual and direct. Keep it under 30 words.""")
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

Report this elimination factually. Keep it under 20 words.""")
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

Announce the game result factually. State who won and who survived. Keep it under 30 words.""")
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
    
    def announce_werewolf_awakening(self, werewolf_names: List[str]) -> str:
        """
        Announce werewolves awakening during night phase
        
        Args:
            werewolf_names: List of werewolf player names
            
        Returns:
            Werewolf awakening announcement
        """
        werewolf_list = ", ".join(werewolf_names)
        
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""The werewolves awaken: {werewolf_list}

Announce that the werewolves are now active and choosing their victim. 
Be factual and brief (under 20 words).""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def announce_werewolf_decision(self, victim_name: str) -> str:
        """
        Announce werewolves' decision during night phase
        
        Args:
            victim_name: Name of the chosen victim
            
        Returns:
            Werewolf decision announcement
        """
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""The werewolves have chosen their victim: {victim_name}

Report the werewolves' decision factually and briefly. 
Keep it under 15 words.""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def should_continue_discussion(self, conversation_so_far: str, rounds_completed: int, num_players: int) -> bool:
        """
        Decide whether to continue the discussion or move to voting
        
        Args:
            conversation_so_far: Complete conversation history
            rounds_completed: Number of discussion rounds completed
            num_players: Number of alive players
            
        Returns:
            True if discussion should continue, False to move to voting
        """
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=f"""Current discussion status:
- Rounds completed: {rounds_completed}
- Players alive: {num_players}
- Conversation so far:
{conversation_so_far}

As the Game Master, decide if the discussion should continue or if it's time to vote.

Consider:
- Has enough information been shared?
- Are players still actively engaging?
- Is the discussion becoming repetitive?
- Has sufficient time been given for accusations and defenses?

Generally, 2-3 rounds of meaningful discussion is enough.

Respond with ONLY "CONTINUE" to keep discussing or "VOTE" to move to voting phase.""")
        ]
        
        response = self.llm.invoke(messages)
        return "continue" in response.content.lower()
    
    def announce_discussion_end(self) -> str:
        """
        Announce the end of the discussion phase
        
        Returns:
            Discussion end announcement
        """
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content="""The discussion phase is ending and it's time to vote.

Announce that discussion is over and voting begins. Be brief and factual (under 15 words).""")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
