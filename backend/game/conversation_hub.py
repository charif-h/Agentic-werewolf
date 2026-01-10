"""
Conversation Hub - Manages message collection and selection based on motivation scores
"""
from typing import List, Optional
from datetime import datetime
from backend.models.game_models import ProposedMessage, Message


class ConversationHub:
    """
    Central hub that receives messages from players with motivation scores
    and selects which messages to publish based on highest scores
    """
    
    def __init__(self):
        """Initialize the conversation hub"""
        self.proposed_messages: List[ProposedMessage] = []
        
    def submit_message(self, sender: str, content: str, motivation_score: int) -> None:
        """
        Submit a proposed message to the hub
        
        Args:
            sender: Name of the player sending the message
            content: Message content
            motivation_score: Motivation score from 1 to 10
        """
        if content and content.strip() and content.strip().lower() != "no comment":
            proposed = ProposedMessage(
                sender=sender,
                content=content.strip(),
                motivation_score=max(1, min(10, motivation_score)),  # Clamp between 1-10
                timestamp=datetime.now().isoformat()
            )
            self.proposed_messages.append(proposed)
    
    def select_messages(self) -> List[Message]:
        """
        Select messages with highest motivation scores to publish
        
        Returns:
            List of messages to publish (those with the highest score)
        """
        if not self.proposed_messages:
            return []
        
        # Find the highest motivation score
        max_score = max(msg.motivation_score for msg in self.proposed_messages)
        
        # Select all messages with the highest score
        selected = [
            msg for msg in self.proposed_messages 
            if msg.motivation_score == max_score
        ]
        
        # Convert to regular Message objects
        published_messages = [
            Message(
                sender=msg.sender,
                content=msg.content,
                timestamp=msg.timestamp,
                message_type="chat"
            )
            for msg in selected
        ]
        
        return published_messages
    
    def clear(self) -> None:
        """Clear all proposed messages for the next round"""
        self.proposed_messages = []
    
    def get_proposed_count(self) -> int:
        """Get the number of proposed messages"""
        return len(self.proposed_messages)
