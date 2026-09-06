from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional, DefaultDict

class MemoryStorage:
    """In-memory storage for reaction and member data."""
    
    def __init__(self):
        # Structure to store reactions: {chat_id: {message_id: {reaction_emoji: count}}}
        self.reactions: DefaultDict[int, DefaultDict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
        
        # Structure to store member join/leave events: {chat_id: [(timestamp, user_id, joined_status)]}
        self.member_events: DefaultDict[int, List[Tuple[datetime, int, bool]]] = defaultdict(list)
        
        # Structure to store current members for each chat: {chat_id: {user_id}}
        self.current_members: DefaultDict[int, Set[int]] = defaultdict(set)

    def add_reaction(self, chat_id: int, message_id: int, reaction_emoji: str, count: int = 1) -> None:
        """Add or update a reaction to a message."""
        self.reactions[chat_id][message_id][reaction_emoji] += count

    def remove_reaction(self, chat_id: int, message_id: int, reaction_emoji: str, count: int = 1) -> None:
        """Remove a reaction from a message."""
        current_count = self.reactions[chat_id][message_id][reaction_emoji]
        if current_count <= count:
            # Remove the reaction entirely if count reaches zero
            del self.reactions[chat_id][message_id][reaction_emoji]
            # Clean up empty dictionaries
            if not self.reactions[chat_id][message_id]:
                del self.reactions[chat_id][message_id]
                if not self.reactions[chat_id]:
                    del self.reactions[chat_id]
        else:
            self.reactions[chat_id][message_id][reaction_emoji] -= count

    def get_message_reactions(self, chat_id: int, message_id: int) -> Dict[str, int]:
        """Get all reactions for a specific message."""
        return dict(self.reactions[chat_id][message_id])

    def get_chat_reactions(self, chat_id: int) -> Dict[int, Dict[str, int]]:
        """Get all reactions for all messages in a chat."""
        return {msg_id: dict(reactions) for msg_id, reactions in self.reactions[chat_id].items()}

    def get_total_reactions_by_emoji(self, chat_id: int) -> Dict[str, int]:
        """Get total count of each reaction type in a chat."""
        totals = Counter()
        for message_reactions in self.reactions[chat_id].values():
            totals.update(message_reactions)
        return dict(totals)

    def add_member_event(self, chat_id: int, user_id: int, joined: bool) -> None:
        """Record member join/leave event."""
        timestamp = datetime.now()
        self.member_events[chat_id].append((timestamp, user_id, joined))
        
        # Update current members
        if joined:
            self.current_members[chat_id].add(user_id)
        elif user_id in self.current_members[chat_id]:
            self.current_members[chat_id].remove(user_id)

    def get_member_events(self, chat_id: int, limit: Optional[int] = None) -> List[Tuple[datetime, int, bool]]:
        """Get member join/leave events for a chat, optionally limited to recent events."""
        events = self.member_events[chat_id]
        if limit:
            return events[-limit:]
        return events

    def get_current_members_count(self, chat_id: int) -> int:
        """Get count of current members in a chat."""
        return len(self.current_members[chat_id])

    def get_join_leave_stats(self, chat_id: int) -> Dict[str, int]:
        """Get statistics about joins and leaves."""
        joins = sum(1 for _, _, joined in self.member_events[chat_id] if joined)
        leaves = len(self.member_events[chat_id]) - joins
        return {
            "joins": joins,
            "leaves": leaves,
            "current_members": len(self.current_members[chat_id])
        }

    def clear_chat_data(self, chat_id: int) -> None:
        """Clear all data for a specific chat."""
        if chat_id in self.reactions:
            del self.reactions[chat_id]
        if chat_id in self.member_events:
            del self.member_events[chat_id]
        if chat_id in self.current_members:
            del self.current_members[chat_id]
