from pydantic import BaseModel
from typing import List

class CreateGameRequest(BaseModel):
    host_name: str

class CreateGameResponse(BaseModel):
    game_id: str
    players: List[str]
    stage: str

class JoinGameRequest(BaseModel):
    game_id: str
    player_name: str

class JoinGameResponse(BaseModel):
    game_id: str
    players: List[str]
    stage: str

class SubmitAnswerRequest(BaseModel):
    game_id: str
    player_id: str
    answer: str
    