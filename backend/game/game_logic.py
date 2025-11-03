"""
Game Logic for Werewolves of Millers Hollow
"""
import random
from typing import List, Dict, Optional, Tuple
from backend.models.game_models import (
    PlayerProfile, GameState, GamePhase, Role, PlayerStatus, Discussion, Message
)
from backend.agents.profile_generator import generate_all_players
from backend.agents.player_agent import PlayerAgent
from backend.agents.game_master_agent import GameMasterAgent


class WerewolfGame:
    """Main game logic controller"""
    
    def __init__(self, num_players: int = 24, ai_provider: Optional[str] = None):
        """
        Initialize the game
        
        Args:
            num_players: Number of players (default 24)
            ai_provider: AI provider to use for all agents
        """
        self.num_players = num_players
        self.ai_provider = ai_provider
        self.state = GameState()
        self.player_agents: Dict[str, PlayerAgent] = {}
        self.game_master = GameMasterAgent(ai_provider=ai_provider)
        
    def setup_game(self) -> GameState:
        """
        Set up the game: generate players and assign roles
        
        Returns:
            Initial game state
        """
        # Generate player profiles
        players = generate_all_players(self.num_players)
        
        # Assign roles based on player count
        roles = self._distribute_roles(self.num_players)
        random.shuffle(roles)
        
        for player, role in zip(players, roles):
            player.role = role
            # Create AI agent for each player
            self.player_agents[player.id] = PlayerAgent(player, self.ai_provider)
        
        self.state.players = players
        self.state.phase = GamePhase.SETUP
        
        # Add game start message
        opening = self.game_master.narrate_game_start(players)
        self.state.game_log.append(f"[GAME MASTER] {opening}")
        
        return self.state
    
    def _distribute_roles(self, num_players: int) -> List[Role]:
        """
        Distribute roles based on number of players
        
        Standard distribution for 24 players:
        - 4 Werewolves
        - 1 Seer
        - 1 Witch
        - 1 Hunter
        - 1 Cupid
        - 1 Guard
        - 15 Villagers
        
        Args:
            num_players: Total number of players
            
        Returns:
            List of roles
        """
        # Calculate werewolf count (roughly 1/6 of players)
        werewolf_count = max(2, num_players // 6)
        
        roles = [Role.WEREWOLF] * werewolf_count
        
        # Add special roles if enough players
        if num_players >= 8:
            roles.append(Role.SEER)
        if num_players >= 10:
            roles.append(Role.WITCH)
        if num_players >= 12:
            roles.append(Role.HUNTER)
        if num_players >= 14:
            roles.append(Role.CUPID)
        if num_players >= 16:
            roles.append(Role.GUARD)
        
        # Fill remaining with villagers
        villager_count = num_players - len(roles)
        roles.extend([Role.VILLAGER] * villager_count)
        
        return roles
    
    def start_night(self) -> str:
        """
        Start the night phase
        
        Returns:
            Night announcement
        """
        self.state.day_number += 1
        self.state.phase = GamePhase.NIGHT
        self.state.night_actions = {}
        
        announcement = self.game_master.announce_night(self.state.day_number)
        self.state.game_log.append(f"[GAME MASTER] {announcement}")
        
        # Announce werewolves awakening
        alive_werewolves = [p for p in self.state.players 
                           if p.status == PlayerStatus.ALIVE and p.role == Role.WEREWOLF]
        if alive_werewolves:
            werewolf_names = [w.name for w in alive_werewolves]
            werewolf_announcement = self.game_master.announce_werewolf_awakening(werewolf_names)
            self.state.game_log.append(f"[GAME MASTER] {werewolf_announcement}")
        
        return announcement
    
    def process_night_actions(self) -> Dict[str, any]:
        """
        Process all night actions (werewolf kills, seer checks, etc.)
        
        Returns:
            Dictionary of night results
        """
        results = {
            'killed': None,
            'protected': None,
            'seer_check': None,
            'witch_saved': False,
            'witch_killed': None
        }
        
        alive_players = [p for p in self.state.players if p.status == PlayerStatus.ALIVE]
        
        # Werewolves choose victim
        werewolves = [p for p in alive_players if p.role == Role.WEREWOLF]
        if werewolves:
            # Get non-werewolf targets (werewolves cannot target each other)
            non_werewolf_targets = [p for p in alive_players if p.role != Role.WEREWOLF]
            if non_werewolf_targets:
                # Create modified game state with only valid targets for werewolves
                werewolf_game_state = self._get_game_state_dict()
                werewolf_game_state['valid_targets'] = [p.name for p in non_werewolf_targets]
                
                # Simplified: first werewolf chooses (in full implementation, they'd coordinate)
                victim_name = self.player_agents[werewolves[0].id].night_action(werewolf_game_state)
                victim = self._find_player_by_name(victim_name)
                
                # Ensure the victim is not a werewolf
                if victim and victim.role != Role.WEREWOLF:
                    results['killed'] = victim.id
                    # Announce werewolves' decision
                    werewolf_decision = self.game_master.announce_werewolf_decision(victim.name)
                    self.state.game_log.append(f"[GAME MASTER] {werewolf_decision}")
        
        # Guard protects someone
        guards = [p for p in alive_players if p.role == Role.GUARD]
        if guards:
            protected_name = self.player_agents[guards[0].id].night_action(
                self._get_game_state_dict()
            )
            protected = self._find_player_by_name(protected_name)
            if protected:
                results['protected'] = protected.id
        
        # Seer checks someone
        seers = [p for p in alive_players if p.role == Role.SEER]
        if seers:
            check_name = self.player_agents[seers[0].id].night_action(
                self._get_game_state_dict()
            )
            checked = self._find_player_by_name(check_name)
            if checked:
                results['seer_check'] = {
                    'player': checked.name,
                    'role': checked.role.value
                }
        
        # Apply results
        if results['killed'] and results['killed'] != results['protected']:
            # Player was killed and not protected
            player = self._find_player_by_id(results['killed'])
            if player:
                player.status = PlayerStatus.DEAD
                self.state.eliminated_players.append(player.id)
                
                # Check if in love
                if player.in_love_with:
                    lover = self._find_player_by_id(player.in_love_with)
                    if lover and lover.status == PlayerStatus.ALIVE:
                        lover.status = PlayerStatus.DEAD
                        self.state.eliminated_players.append(lover.id)
                        results['lover_died'] = lover.id
        
        self.state.night_actions = results
        return results
    
    def start_day(self) -> str:
        """
        Start the day phase and announce night results
        
        Returns:
            Day announcement
        """
        self.state.phase = GamePhase.DAY
        
        # Build night events summary
        night_events = []
        if self.state.night_actions.get('killed'):
            player = self._find_player_by_id(self.state.night_actions['killed'])
            if player and player.status == PlayerStatus.DEAD:
                night_events.append(f"{player.name} was killed")
                
                if self.state.night_actions.get('lover_died'):
                    lover = self._find_player_by_id(self.state.night_actions['lover_died'])
                    if lover:
                        night_events.append(f"{lover.name} died of heartbreak")
        else:
            night_events.append("No one was killed")
        
        events_str = ". ".join(night_events) + "."
        announcement = self.game_master.announce_day(self.state.day_number, events_str)
        self.state.game_log.append(f"[GAME MASTER] {announcement}")
        
        return announcement
    
    def conduct_discussion(self, max_rounds: int = 5) -> List[str]:
        """
        Conduct dynamic discussion phase where players can respond to each other
        Each time someone speaks, all players get a chance to respond
        
        Args:
            max_rounds: Maximum number of discussion rounds (default: 5)
            
        Returns:
            List of discussion messages
        """
        self.state.phase = GamePhase.DISCUSSION
        messages = []
        
        alive_players = [p for p in self.state.players if p.status == PlayerStatus.ALIVE]
        alive_names = [p.name for p in alive_players]
        
        # Create main discussion
        discussion = Discussion(
            round_number=1,
            topic="Dynamic discussion - players can respond to each other",
            messages=[]
        )
        
        import time
        import random
        
        for discussion_round in range(1, max_rounds + 1):
            round_had_new_speech = False
            
            # Shuffle player order each round for fairness
            shuffled_players = alive_players.copy()
            random.shuffle(shuffled_players)
            
            # Build current conversation context for this round
            current_conversation = ""
            if discussion.messages:
                current_conversation = "\n".join([f"[{msg.sender}] {msg.content}" for msg in discussion.messages])
            
            for player in shuffled_players:
                try:
                    agent = self.player_agents[player.id]
                    
                    # Give each player the updated conversation to consider responding
                    time.sleep(0.3)  # Shorter delay for more dynamic interaction
                    comment = agent.discuss(current_conversation, alive_names)
                    
                    # Filter out "no comment" responses
                    if comment and comment.strip() and comment.strip().lower() != "no comment":
                        message_text = f"[{player.name}] {comment}"
                        messages.append(message_text)
                        self.state.game_log.append(message_text)
                        round_had_new_speech = True
                        
                        # Add to structured discussion
                        from datetime import datetime
                        message = Message(
                            sender=player.name,
                            content=comment,
                            timestamp=datetime.now().isoformat(),
                            message_type="dynamic_comment"
                        )
                        discussion.messages.append(message)
                        
                        # Update conversation immediately so next players see this comment
                        current_conversation = "\n".join([f"[{msg.sender}] {msg.content}" for msg in discussion.messages])
                        
                        print(f"Round {discussion_round}: {player.name} spoke, conversation updated")
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    if "rate limit" in error_msg or "429" in error_msg:
                        print(f"Rate limit hit for player {player.name}, they stay silent this round")
                        time.sleep(0.8)  # Extra delay on rate limit
                        continue
                    else:
                        print(f"Error with player {player.name}: {e}")
                        continue
            
            # If no one spoke this round, check if we should end
            if not round_had_new_speech:
                if discussion_round >= 2:  # Minimum 2 rounds
                    silence_announcement = "The discussion has concluded. Time to vote."
                    self.state.game_log.append(f"[GAME MASTER] {silence_announcement}")
                    break
                    
            # Check if Game Master wants to continue discussion
            elif discussion_round >= 3:  # After round 3, GM can decide to end
                try:
                    conversation_so_far = "\n".join([f"[{msg.sender}] {msg.content}" for msg in discussion.messages])
                    should_continue = self.game_master.should_continue_discussion(
                        conversation_so_far, 
                        discussion_round,
                        len(alive_players)
                    )
                    
                    if not should_continue:
                        end_announcement = self.game_master.announce_discussion_end()
                        self.state.game_log.append(f"[GAME MASTER] {end_announcement}")
                        break
                        
                except Exception as e:
                    print(f"GM decision failed: {e}")
                    # Continue to next round on GM error
            
            # Shorter delay between rounds for more dynamic feel
            time.sleep(0.5)
        
        # Save discussion to game state
        if discussion.messages:
            self.state.discussions.append(discussion)
        
        return messages
    
    def conduct_vote(self) -> Tuple[Optional[PlayerProfile], Dict[str, int]]:
        """
        Conduct independent voting where each player makes their own strategic decision
        
        Returns:
            Tuple of (eliminated player, vote counts)
        """
        self.state.phase = GamePhase.VOTING
        
        alive_players = [p for p in self.state.players if p.status == PlayerStatus.ALIVE]
        candidate_names = [p.name for p in alive_players]
        
        votes: Dict[str, List[str]] = {name: [] for name in candidate_names}
        
        # Build complete conversation context for voting
        full_conversation = ""
        if self.state.discussions:
            latest_discussion = self.state.discussions[-1]
            if latest_discussion.messages:
                full_conversation = "\n".join([f"[{msg.sender}] {msg.content}" for msg in latest_discussion.messages])
            else:
                full_conversation = "No one spoke during the discussion - complete silence."
        else:
            full_conversation = "No discussion took place this phase."
        
        # Each player makes independent voting decision
        import time
        import random
        
        # Shuffle voting order to prevent influence
        shuffled_voters = alive_players.copy()
        random.shuffle(shuffled_voters)
        
        for player in shuffled_voters:
            try:
                time.sleep(0.5)  # Rate limit protection
                
                agent = self.player_agents[player.id]
                vote_target = agent.vote(full_conversation, candidate_names)
                
                # Validate vote target
                if vote_target in candidate_names:
                    target_player = self._find_player_by_name(vote_target)
                    if target_player and target_player.status == PlayerStatus.ALIVE:
                        votes[vote_target].append(player.name)
                        self.state.game_log.append(f"[VOTE] {player.name} votes to eliminate {vote_target}")
                    else:
                        # Invalid target, use fallback
                        fallback_target = candidate_names[0] if candidate_names else None
                        if fallback_target:
                            votes[fallback_target].append(player.name)
                            self.state.game_log.append(f"[VOTE] {player.name} votes for {fallback_target} (invalid target corrected)")
                else:
                    # Vote parsing failed, use fallback
                    fallback_target = candidate_names[0] if candidate_names else None
                    if fallback_target:
                        votes[fallback_target].append(player.name)
                        self.state.game_log.append(f"[VOTE] {player.name} votes for {fallback_target} (vote parsing failed)")
                        
            except Exception as e:
                error_msg = str(e).lower()
                if "rate limit" in error_msg or "429" in error_msg:
                    print(f"Rate limit hit during voting for {player.name}")
                    # Use strategic fallback vote during rate limits
                    if candidate_names:
                        # Prefer to vote for someone other than self
                        other_candidates = [c for c in candidate_names if c != player.name]
                        fallback_target = random.choice(other_candidates) if other_candidates else candidate_names[0]
                        votes[fallback_target].append(player.name)
                        self.state.game_log.append(f"[VOTE] {player.name} votes for {fallback_target} (rate limited)")
                    time.sleep(1)  # Extra delay after rate limit
                else:
                    print(f"Voting error for {player.name}: {e}")
                    # Error fallback
                    if candidate_names:
                        fallback_target = candidate_names[0]
                        votes[fallback_target].append(player.name)
                        self.state.game_log.append(f"[VOTE] {player.name} votes for {fallback_target} (error fallback)")
        
        # Count votes and determine elimination
        vote_counts = {name: len(voters) for name, voters in votes.items()}
        
        if vote_counts:
            max_votes = max(vote_counts.values())
            top_voted = [name for name, count in vote_counts.items() if count == max_votes]
            
            # Handle ties (random selection)
            eliminated_name = random.choice(top_voted)
            eliminated_player = self._find_player_by_name(eliminated_name)
            
            if eliminated_player:
                eliminated_player.status = PlayerStatus.DEAD
                self.state.eliminated_players.append(eliminated_player.id)
                
                # Announce elimination
                announcement = self.game_master.narrate_elimination(
                    eliminated_player.name, 
                    eliminated_player.role.value,
                    by_vote=True
                )
                self.state.game_log.append(f"[GAME MASTER] {announcement}")
                
                return eliminated_player, vote_counts
        
        return None, vote_counts
    
    def check_win_condition(self) -> Optional[str]:
        """
        Check if game has ended
        
        Returns:
            Winning team ("werewolves" or "villagers") or None if game continues
        """
        alive_players = [p for p in self.state.players if p.status == PlayerStatus.ALIVE]
        
        werewolves_alive = sum(1 for p in alive_players if p.role == Role.WEREWOLF)
        villagers_alive = len(alive_players) - werewolves_alive
        
        if werewolves_alive == 0:
            return "villagers"
        elif werewolves_alive >= villagers_alive:
            return "werewolves"
        
        return None
    
    def end_game(self, winner: str) -> str:
        """
        End the game and announce winner
        
        Args:
            winner: Winning team
            
        Returns:
            Victory announcement
        """
        self.state.phase = GamePhase.ENDED
        
        survivors = [p.name for p in self.state.players if p.status == PlayerStatus.ALIVE]
        announcement = self.game_master.announce_winner(winner, survivors)
        self.state.game_log.append(f"[GAME MASTER] {announcement}")
        
        return announcement
    
    def _get_game_state_dict(self) -> Dict[str, any]:
        """Convert game state to dictionary for agents"""
        # Get recent discussion history
        discussion_history = []
        for discussion in self.state.discussions[-3:]:  # Last 3 discussions
            for message in discussion.messages:
                discussion_history.append(f"[{message.sender}] {message.content}")
        
        return {
            'phase': self.state.phase.value,
            'day_number': self.state.day_number,
            'players': [
                {
                    'id': p.id,
                    'name': p.name,
                    'status': p.status.value
                }
                for p in self.state.players
            ],
            'recent_events': self.state.game_log[-3:] if self.state.game_log else [],
            'discussion_history': discussion_history,
            'all_discussions': [
                {
                    'round': d.round_number,
                    'topic': d.topic,
                    'messages': [{'sender': m.sender, 'content': m.content} for m in d.messages]
                }
                for d in self.state.discussions
            ]
        }
    
    def _find_player_by_name(self, name: str) -> Optional[PlayerProfile]:
        """Find player by name"""
        for player in self.state.players:
            if player.name.lower() == name.lower():
                return player
        return None
    
    def _find_player_by_id(self, player_id: str) -> Optional[PlayerProfile]:
        """Find player by ID"""
        for player in self.state.players:
            if player.id == player_id:
                return player
        return None
