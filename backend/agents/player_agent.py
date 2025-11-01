"""
Player AI Agent - Controls individual player behavior
"""
from typing import Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
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
    
    def _prepare_messages(self, system_prompt: str, user_message: str) -> list:
        """
        Prepare messages for LLM ensuring proper conversation format for Mistral
        
        Args:
            system_prompt: System prompt
            user_message: Current user message
            
        Returns:
            List of messages in proper format
        """
        messages = [SystemMessage(content=system_prompt)]
        
        # Add recent memory ensuring alternating User/Assistant pattern
        recent_memory = self.memory[-4:]  # Last 4 messages (2 complete exchanges)
        
        # Ensure we don't have consecutive messages of the same type
        if recent_memory:
            # Filter to maintain alternating pattern
            filtered_memory = []
            last_type = None
            
            for msg in recent_memory:
                current_type = type(msg).__name__
                if current_type != last_type:
                    filtered_memory.append(msg)
                    last_type = current_type
            
            messages.extend(filtered_memory)
        
        # Always end with user message
        messages.append(HumanMessage(content=user_message))
        
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
        
        # Build context about game state
        alive_players = [p for p in game_state.get('players', []) if p.get('status') == 'alive']
        player_list = ", ".join([p.get('name') for p in alive_players])
        
        # Build discussion history context
        discussion_context = ""
        discussion_history = game_state.get('discussion_history', [])
        if discussion_history:
            discussion_context = f"\nRecent Discussions:\n" + "\n".join(discussion_history[-10:])  # Last 10 messages
        
        # Build comprehensive game context
        game_context = f"""
Current Game State:
- Phase: {game_state.get('phase', 'unknown')}
- Day: {game_state.get('day_number', 0)}
- Alive Players: {player_list}
- Recent Events: {game_state.get('recent_events', 'None')}
{discussion_context}

Current Action: {context}
"""
        
        messages = self._prepare_messages(system_prompt, game_context)
        
        try:
            response = self.llm.invoke(messages)
            
            # Store in memory as a conversation pair
            self.memory.append(HumanMessage(content=game_context))
            self.memory.append(response)
            
            return response.content
        except Exception as e:
            # Handle rate limit and other API errors
            error_msg = str(e).lower()
            if "rate limit" in error_msg or "429" in error_msg:
                # Return a default response based on personality for rate limit errors
                if self.profile.role == Role.WEREWOLF:
                    return "I'll stay quiet for now and observe."
                else:
                    return "I'm still thinking about this situation."
            else:
                # For other errors, re-raise
                raise e
    
    def vote(self, game_state: Dict[str, Any], candidates: list[str]) -> str:
        """
        Make a voting decision
        
        Args:
            game_state: Current game state
            candidates: List of player names that can be voted for
            
        Returns:
            Name of the player to vote for
        """
        # Build voting context with discussion analysis
        discussion_analysis = ""
        all_discussions = game_state.get('all_discussions', [])
        if all_discussions:
            discussion_analysis = "\n\nAnalysis from Recent Discussions:\n"
            for discussion in all_discussions[-2:]:  # Last 2 discussion rounds
                discussion_analysis += f"Round {discussion['round']}: {discussion['topic']}\n"
                for msg in discussion['messages']:
                    discussion_analysis += f"  - {msg['sender']}: {msg['content']}\n"
        
        context = f"""It's time to vote. You must choose one player to eliminate from these candidates:
{', '.join(candidates)}

Based on the discussions, evidence, your role, and what you've observed, who do you vote to eliminate?
{discussion_analysis}

Consider:
- Who seemed most suspicious in discussions?
- Who deflected questions or seemed nervous?
- Who made accusations that didn't make sense?
- Your role's specific knowledge (if any)

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
            # Get valid targets (non-werewolves only)
            valid_targets = game_state.get('valid_targets', [])
            if valid_targets:
                target_list = ', '.join(valid_targets)
                context = f"As a werewolf, choose one villager to eliminate tonight from these targets: {target_list}. You cannot target other werewolves. Respond with ONLY the player's name."
            else:
                context = "As a werewolf, choose a villager to eliminate tonight. You cannot target other werewolves. Respond with ONLY the player's name."
        elif self.profile.role == Role.SEER:
            context = "As the seer, choose a player whose identity you want to reveal. Respond with ONLY the player's name."
        elif self.profile.role == Role.GUARD:
            context = "As the guard, choose a player to protect tonight. Respond with ONLY the player's name."
        else:
            return None
        
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
        # Build strategic context based on role
        role_strategy = self._get_role_strategy()
        
        # Check if player should be more likely to respond
        should_respond_bonus = self._should_respond_to_conversation(conversation_history)
        
        context = f"""You are {self.profile.name} in a Werewolf game discussion.

CURRENT CONVERSATION:
{conversation_history if conversation_history.strip() else "No one has spoken yet."}

ALIVE PLAYERS: {', '.join(alive_players)}

YOUR HIDDEN INFO: You are a {self.profile.role.value}
{role_strategy}

RESPONSE FACTORS:
{should_respond_bonus}

INSTRUCTIONS:
- Keep response SHORT (1-2 sentences max)
- NEVER mention roles directly (werewolf, villager, etc.)
- You can respond to what others said or ask questions
- Be subtle and natural
- If you have nothing to add, say "no comment"

Do you want to respond to the current conversation?"""
        
        try:
            response = self._get_llm_response(context)
            
            # Clean and validate response
            response = response.strip()
            if not response or response.lower() == "no comment":
                return "no comment"
            
            return response
            
        except Exception as e:
            # Fallback based on role if API fails
            if self.profile.role == Role.WEREWOLF:
                return "no comment"  # Werewolves tend to stay quiet
            else:
                return "no comment"  # Safe fallback
    
    def _should_respond_to_conversation(self, conversation_history: str) -> str:
        """
        Check if player has special reasons to respond to current conversation
        
        Args:
            conversation_history: Current conversation
            
        Returns:
            String describing response factors
        """
        factors = []
        
        # Check if player is mentioned by name
        if self.profile.name in conversation_history:
            factors.append("- You have been mentioned or addressed")
        
        # Check if recent activity (last few messages)
        if conversation_history:
            lines = conversation_history.strip().split('\n')
            if len(lines) >= 2:  # There are recent messages
                factors.append("- Recent activity in conversation")
        
        # Role-specific response factors
        if self.profile.role == Role.SEER:
            factors.append("- As someone with special knowledge, consider if you should guide the discussion")
        elif self.profile.role == Role.WEREWOLF:
            factors.append("- Consider if you need to deflect suspicion or redirect attention")
        elif self.profile.role in [Role.VILLAGER, Role.WITCH, Role.GUARD, Role.HUNTER]:
            factors.append("- Consider if you can help identify threats")
        
        if not factors:
            factors.append("- No special pressure to respond")
        
        return '\n'.join(factors)
    
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
        
        role_voting_strategy = self._get_voting_strategy()
        
        context = f"""You are {self.profile.name} voting to eliminate someone.

CONVERSATION RECAP:
{conversation_history if conversation_history.strip() else "No discussion took place."}

VOTING CANDIDATES: {', '.join(other_players)}

INSTRUCTIONS:
- Analyze who acted most suspiciously
- Consider who seemed defensive or evasive
- Think about who tried to redirect blame
- Vote for who you personally find most suspicious
- Respond with ONLY the player's name

Who do you vote to eliminate?"""
        
        try:
            response = self._get_llm_response(context)
            
            # Extract player name from response
            response = response.strip()
            
            # Try to find exact matches first
            for player in other_players:
                if player.lower() == response.lower():
                    return player
            
            # Try partial matches
            for player in other_players:
                if player.lower() in response.lower():
                    return player
            
            # Fallback to first available player
            return other_players[0]
            
        except Exception as e:
            # Random vote as fallback to ensure independence
            import random
            return random.choice(other_players)
    
    def _get_role_strategy(self) -> str:
        """Get strategic guidance based on player's role"""
        strategies = {
            Role.WEREWOLF: """Your goal: eliminate villagers without being discovered.
- Act like a concerned villager
- Subtly redirect suspicion onto others
- Don't defend other werewolves obviously""",

            Role.VILLAGER: """Your goal: find and eliminate werewolves.
- Ask probing questions
- Point out suspicious behavior
- Work with others to find threats""",

            Role.SEER: """You can see true identities at night.
- Use your knowledge subtly
- Don't reveal your role unless necessary
- Guide discussions toward confirmed werewolves""",

            Role.WITCH: """You have healing and poison potions.
- Keep your role secret
- Use night action knowledge carefully
- Observe who might know too much""",

            Role.GUARD: """You can protect players from attacks.
- Keep protection patterns secret
- Use knowledge of night events subtly
- Look for signs of werewolf coordination""",

            Role.HUNTER: """If killed, you can eliminate another player.
- Be moderately active to help the village
- Keep a mental list of suspects
- Don't fear taking reasonable risks""",
        }
        
        return strategies.get(self.profile.role, strategies[Role.VILLAGER])
    
    def _get_voting_strategy(self) -> str:
        """Get voting strategy based on role"""
        if self.profile.role == Role.WEREWOLF:
            return """As a WEREWOLF, vote to eliminate:
1. Confirmed or suspected special roles (seer, witch, etc.)
2. The most active and influential villagers
3. Anyone who has been suspicious of werewolves
4. Avoid voting for fellow werewolves unless absolutely necessary"""
        else:
            return """As a VILLAGE TEAM member, vote to eliminate:
1. The player who acted most suspiciously during discussions
2. Anyone who deflected questions or was overly defensive
3. Players whose behavior doesn't match their claimed actions
4. The person you personally believe is most likely to be a werewolf"""
    
    def _get_personality_behavior(self) -> str:
        """Get brief personality-based behavior description"""
        personality_map = {
            "ENFP": "enthusiastic and curious",
            "ENFJ": "empathetic and diplomatic", 
            "ENTP": "witty and analytical",
            "ENTJ": "direct and strategic",
            "ESFP": "friendly and spontaneous",
            "ESFJ": "caring and cooperative",
            "ESTP": "practical and observant",
            "ESTJ": "organized and decisive",
            "INFP": "thoughtful and idealistic",
            "INFJ": "insightful and reserved",
            "INTP": "logical and skeptical",
            "INTJ": "independent and methodical",
            "ISFP": "gentle and cautious",
            "ISFJ": "supportive and dutiful",
            "ISTP": "calm and pragmatic",
            "ISTJ": "reliable and careful"
        }
        return personality_map.get(self.profile.personality.value, "neutral")
    
    def _get_llm_response(self, context: str) -> str:
        """Get response from LLM with error handling"""
        system_prompt = f"""You are {self.profile.name} playing Werewolf. 

CRITICAL RULES:
- Keep responses SHORT (1-2 sentences maximum)
- NEVER mention roles directly (werewolf, villager, seer, etc.)
- Be subtle and natural
- Don't explain your reasoning or strategy
- Act like a normal person in a tense situation

Personality: {self.profile.personality.value} - be {self._get_personality_behavior()}"""
        
        messages = self._prepare_messages(system_prompt, context)
        response = self.llm.invoke(messages)
        return response.content
