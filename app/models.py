# app/models.py
from typing import List, Optional
from enum import Enum
from uuid import UUID

class GameStage(str, Enum):
    WAITING = "waiting_for_players"
    QUESTION = 'question_answering'
    REVEAL = 'question_reveal'
    DEFENSE = 'defense'
    VOTING = 'voting'
    REVEAL_IMPOSTER = 'reveal_imposter'
    END = 'game_end'

class Player:
    """
    In-memory representation of a player.
    Used for WebSocket operations and quick access.
    """
    def __init__(self, player_id: str, name: str, is_host: bool = False):
        self.player_id = player_id
        self.name = name
        self.is_host = is_host
        self.score = 0
        self.question: Optional[str] = None
        self.answer: Optional[str] = None
        self.is_imposter: bool = False
        
    def to_dict(self):
        """Convert player to dictionary for API responses"""
        return {
            "player_id": str(self.player_id),
            "name": self.name,
            "is_host": self.is_host,
            "score": self.score,
            "is_imposter": self.is_imposter
        }

class Game:
    """
    In-memory representation of a game.
    Used for WebSocket operations and quick access.
    """
    def __init__(self, game_id: str, host: Player):
        self.game_id = game_id
        self.players: List[Player] = [host]
        self.stage: GameStage = GameStage.WAITING
        self.imposters: List[Player] = []
        self.votes: dict = {}  # {voter_id: voted_id}
        
    def to_dict(self):
        """Convert game to dictionary for API responses"""
        return {
            "game_id": self.game_id,
            "players": [p.to_dict() for p in self.players],
            "stage": self.stage,
            "player_count": len(self.players)
        }