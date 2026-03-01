from pydantic import BaseModel
from typing import List

class CreateGameRequest(BaseModel):
    host_name: str

class PlayerInfo(BaseModel):
    id: str
    name: str

class CreateGameResponse(BaseModel):
    game_id: str
    players: list[PlayerInfo]
    stage: str

class JoinGameResponse(BaseModel):
    game_id: str
    players: list[PlayerInfo]
    stage: str

class JoinGameRequest(BaseModel):
    game_id: str
    player_name: str


class SubmitAnswerRequest(BaseModel):
    game_id: str
    players: list[PlayerInfo]
    answer: str
    