"""
Player AI Agent - Controls individual player behavior
"""
from typing import Optional, Dict, Any
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from backend.models.game_models import PlayerProfile, GamePhase, Role
from backend.agents.ai_provider import AIProvider


class PlayerAgent:
    """AI Agent that represents a single player in the game"""
    
    def __init__(self, profile: PlayerProfile, ai_provider: Optional[str] = None):
        """
        Initialize a player agent
        
        Args:
            profile: The player's profile with personality and role
            ai_provider: Which AI provider to use (openai, gemini, mistral)
        """
        self.profile = profile
        self.llm = AIProvider.get_llm(provider=ai_provider, temperature=0.8)
        self.memory = []  # Store conversation history
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt based on player's personality and role"""
        base_prompt = f"""You are {self.profile.name}, a {self.profile.age}-year-old {self.profile.sex.value} 
playing The Werewolves of Millers Hollow.

Your Personality: {self.profile.personality.value} - {self.profile.get_personality_description()}

Your personality influences how you:
- Communicate with others (formal/casual, aggressive/gentle, logical/emotional)
- Make decisions and vote
- React to accusations and events
- Build trust or suspicion with other players
"""
        
        if self.profile.role:
            role_descriptions = {
                Role.WEREWOLF: "You are a WEREWOLF. Your goal is to eliminate villagers without being discovered. During the night, you coordinate with other werewolves to choose a victim. During the day, you must blend in and deflect suspicion.",
                Role.VILLAGER: "You are a VILLAGER. Your goal is to identify and eliminate the werewolves. You have no special powers, but you can use logic and observation during discussions.",
                Role.SEER: "You are the SEER. Each night, you can discover the true identity of one player. Use this information wisely during day discussions without revealing your role.",
                Role.WITCH: "You are the WITCH. You have two potions: one to save someone from death, and one to kill someone. You can use each potion only once during the game.",
                Role.HUNTER: "You are the HUNTER. If you are killed, you can immediately shoot and eliminate another player of your choice.",
                Role.CUPID: "You are CUPID. On the first night, you choose two players to fall in love. If one dies, the other dies of heartbreak.",
                Role.LITTLE_GIRL: "You are the LITTLE GIRL. You can peek during the werewolf phase at night, but risk being caught.",
                Role.GUARD: "You are the GUARD. Each night, you can protect one player from werewolf attacks (but not the same player twice in a row)."
            }
            base_prompt += f"\n\nYour Role: {role_descriptions.get(self.profile.role, '')}"
        
        base_prompt += "\n\nPlay authentically according to your personality and role. Stay in character."
        return base_prompt
    
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
        
        # Build context about game state
        alive_players = [p for p in game_state.get('players', []) if p.get('status') == 'alive']
        player_list = ", ".join([p.get('name') for p in alive_players])
        
        game_context = f"""
Current Game State:
- Phase: {game_state.get('phase', 'unknown')}
- Day: {game_state.get('day_number', 0)}
- Alive Players: {player_list}
- Recent Events: {game_state.get('recent_events', 'None')}

{context}
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=game_context)
        ]
        
        # Add recent memory
        for msg in self.memory[-5:]:  # Last 5 messages for context
            messages.append(msg)
        
        response = self.llm.invoke(messages)
        
        # Store in memory
        self.memory.append(HumanMessage(content=game_context))
        self.memory.append(response)
        
        return response.content
    
    def vote(self, game_state: Dict[str, Any], candidates: list[str]) -> str:
        """
        Make a voting decision
        
        Args:
            game_state: Current game state
            candidates: List of player names that can be voted for
            
        Returns:
            Name of the player to vote for
        """
        context = f"""It's time to vote. You must choose one player to eliminate from these candidates:
{', '.join(candidates)}

Based on the discussions, evidence, and your role, who do you vote to eliminate? 
Respond with ONLY the name of the player you're voting for, nothing else."""
        
        response = self.get_action(game_state, context)
        
        # Extract the name from response
        for candidate in candidates:
            if candidate.lower() in response.lower():
                return candidate
        
        # Default to first candidate if unclear
        return candidates[0] if candidates else ""
    
    def night_action(self, game_state: Dict[str, Any]) -> Optional[str]:
        """
        Perform night action based on role
        
        Args:
            game_state: Current game state
            
        Returns:
            Target player name or None
        """
        if self.profile.role == Role.WEREWOLF:
            context = "As a werewolf, choose a villager to eliminate tonight. Respond with ONLY the player's name."
        elif self.profile.role == Role.SEER:
            context = "As the seer, choose a player whose identity you want to reveal. Respond with ONLY the player's name."
        elif self.profile.role == Role.GUARD:
            context = "As the guard, choose a player to protect tonight. Respond with ONLY the player's name."
        else:
            return None
        
        return self.get_action(game_state, context)
    
    def discuss(self, game_state: Dict[str, Any], discussion_topic: str) -> str:
        """
        Participate in discussion
        
        Args:
            game_state: Current game state
            discussion_topic: Current topic of discussion
            
        Returns:
            Player's contribution to discussion
        """
        context = f"""Discussion Topic: {discussion_topic}

Share your thoughts, suspicions, or defend yourself. Keep your response concise (2-3 sentences) and stay in character."""
        
        return self.get_action(game_state, context)
