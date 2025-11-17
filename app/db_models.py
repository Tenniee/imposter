# app/db_models.py
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from app.database import Base

class DBGame(Base):
    """
    Represents a game in the database.
    Maps to the 'games' table.
    """
    __tablename__ = "games"
    
    game_id = Column(String(6), primary_key=True)
    host_name = Column(String(100), nullable=False)
    stage = Column(String(50), default="waiting_for_players", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship: One game has many players
    players = relationship("DBPlayer", back_populates="game", cascade="all, delete-orphan")
    votes = relationship("DBVote", back_populates="game", cascade="all, delete-orphan")


class DBPlayer(Base):
    """
    Represents a player in the database.
    Maps to the 'players' table.
    """
    __tablename__ = "players"
    
    player_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id = Column(String(6), ForeignKey("games.game_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    is_host = Column(Boolean, default=False)
    score = Column(Integer, default=0)
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    is_imposter = Column(Boolean, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship: Player belongs to one game
    game = relationship("DBGame", back_populates="players")
    
    # Unique constraint: No duplicate names in same game
    __table_args__ = (
        UniqueConstraint('game_id', 'name', name='unique_player_name_per_game'),
    )


class DBVote(Base):
    """
    Represents a vote in the database.
    Maps to the 'votes' table.
    """
    __tablename__ = "votes"
    
    vote_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(6), ForeignKey("games.game_id", ondelete="CASCADE"), nullable=False)
    voter_player_id = Column(UUID(as_uuid=True), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False)
    voted_player_id = Column(UUID(as_uuid=True), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship: Vote belongs to one game
    game = relationship("DBGame", back_populates="votes")
    
    # Unique constraint: Each player can only vote once per game
    __table_args__ = (
        UniqueConstraint('game_id', 'voter_player_id', name='unique_vote_per_player'),
    )