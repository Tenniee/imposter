from typing import List
from enum import Enum

class GameStage(str, Enum):
    WAITING = "waiting_for_players"
    QUESTION = 'question_answering'
    REVEAL = 'question_reveal'
    DEFENSE = 'defense'
    VOTING = 'voting'
    REVEAL_IMPOSTER = 'reveal_imposter'
    END = 'game_end'

class Player:
    def __init__(self, player_id: str, name: str, is_host: bool = False):
        self.player_id = player_id
        self.name = name
        self.is_host = is_host
        self.score = 0

class Game:
    def __init__(self, game_id:str, host: Player):
        self.game_id = game_id
        self.players: List[Player] = [host]
        self.stage: GameStage = GameStage.WAITING