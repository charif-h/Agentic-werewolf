"""
Game Logic for Werewolves of Millers Hollow
"""
import random
from typing import List, Dict, Optional, Tuple
from backend.models.game_models import (
    PlayerProfile, GameState, GamePhase, Role, PlayerStatus
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
            # Simplified: first werewolf chooses (in full implementation, they'd coordinate)
            victim_name = self.player_agents[werewolves[0].id].night_action(
                self._get_game_state_dict()
            )
            victim = self._find_player_by_name(victim_name)
            if victim:
                results['killed'] = victim.id
        
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
    
    def conduct_discussion(self, rounds: int = 3) -> List[str]:
        """
        Conduct discussion phase where players share thoughts
        
        Args:
            rounds: Number of discussion rounds
            
        Returns:
            List of discussion messages
        """
        self.state.phase = GamePhase.DISCUSSION
        messages = []
        
        alive_players = [p for p in self.state.players if p.status == PlayerStatus.ALIVE]
        
        for round_num in range(rounds):
            topic = f"Round {round_num + 1}: Share your suspicions or defend yourself."
            
            for player in alive_players:
                agent = self.player_agents[player.id]
                response = agent.discuss(self._get_game_state_dict(), topic)
                message = f"[{player.name}] {response}"
                messages.append(message)
                self.state.game_log.append(message)
        
        return messages
    
    def conduct_vote(self) -> Tuple[Optional[PlayerProfile], Dict[str, int]]:
        """
        Conduct voting to eliminate a player
        
        Returns:
            Tuple of (eliminated player, vote counts)
        """
        self.state.phase = GamePhase.VOTING
        
        alive_players = [p for p in self.state.players if p.status == PlayerStatus.ALIVE]
        candidate_names = [p.name for p in alive_players]
        
        votes: Dict[str, List[str]] = {name: [] for name in candidate_names}
        
        # Each player votes
        for player in alive_players:
            agent = self.player_agents[player.id]
            vote_target = agent.vote(self._get_game_state_dict(), candidate_names)
            
            if vote_target in candidate_names:
                votes[vote_target].append(player.name)
                self.state.game_log.append(f"[VOTE] {player.name} votes for {vote_target}")
        
        # Count votes
        vote_counts = {name: len(voters) for name, voters in votes.items()}
        
        # Find player with most votes
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
            'recent_events': self.state.game_log[-3:] if self.state.game_log else []
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
