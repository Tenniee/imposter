# app/game_manager.py
from fastapi import WebSocket
from sqlalchemy.orm import Session
from app.models import Game, Player
from app.db_models import DBGame, DBPlayer, DBVote
from app.database import SessionLocal
import uuid
import random
from typing import Optional

class GameManager:
    def __init__(self):
        # WebSocket connections stay in memory (can't be stored in DB!)
        self.connections = {}  # game_id -> {player_name: WebSocket}

    def _get_db(self) -> Session:
        """Get a new database session"""
        return SessionLocal()

    # ------------------------------
    # Game Management (WITH DATABASE)
    # ------------------------------
    def create_game(self, host_name: str) -> Game:
        """
        Create a new game and save it to the database.
        Returns an in-memory Game object for immediate use.
        """
        db = self._get_db()
        try:
            # Generate unique game ID
            game_id = str(uuid.uuid4())[:6]
            
            # Create database game
            db_game = DBGame(
                game_id=game_id,
                host_name=host_name,
                stage="waiting_for_players"
            )
            db.add(db_game)
            
            # Create database player (host)
            player_id = str(uuid.uuid4())
            db_player = DBPlayer(
                player_id=player_id,
                game_id=game_id,
                name=host_name,
                is_host=True
            )
            db.add(db_player)
            
            # Commit to database
            db.commit()
            db.refresh(db_game)
            db.refresh(db_player)
            
            # Create in-memory objects for return
            host = Player(player_id=player_id, name=host_name, is_host=True)
            game = Game(game_id=game_id, host=host)
            
            # Initialize WebSocket connections for this game
            self.connections[game_id] = {}
            
            print(f"✅ Game {game_id} created")
            print(f"📋 self.connections = {self.connections}")  # Print entire dict
            print(f"📍 GameManager instance ID: {id(self)}")  # Print instance memory address    
            return game
            
        finally:
            db.close()

    def join_game(self, game_id: str, player_name: str) -> Game:
        """
        Add a player to an existing game in the database.
        Returns updated in-memory Game object.
        """
        db = self._get_db()
        try:
            # Check if game exists
            db_game = db.query(DBGame).filter(DBGame.game_id == game_id).first()
            if not db_game:
                raise ValueError("Game not found")
            
            # Check if player name already exists in this game
            existing_player = db.query(DBPlayer).filter(
                DBPlayer.game_id == game_id,
                DBPlayer.name == player_name
            ).first()
            if existing_player:
                raise ValueError(f"Player name '{player_name}' already taken in this game")
            
            # Create new player in database
            player_id = str(uuid.uuid4())
            db_player = DBPlayer(
                player_id=player_id,
                game_id=game_id,
                name=player_name,
                is_host=False
            )
            db.add(db_player)
            db.commit()
            db.refresh(db_player)
            
            # Load all players for this game
            db_players = db.query(DBPlayer).filter(DBPlayer.game_id == game_id).all()
            
            # Convert to in-memory Game object
            game = self._db_game_to_memory(db_game, db_players)
            
            print(f"✅ Player {player_name} joined game {game_id}")
            return game
            
        finally:
            db.close()

    def get_game(self, game_id: str) -> Optional[Game]:
        """
        Load a game from the database and return as in-memory object.
        """
        db = self._get_db()
        try:
            db_game = db.query(DBGame).filter(DBGame.game_id == game_id).first()
            if not db_game:
                return None
            
            db_players = db.query(DBPlayer).filter(DBPlayer.game_id == game_id).all()
            return self._db_game_to_memory(db_game, db_players)
            
        finally:
            db.close()

    def _db_game_to_memory(self, db_game: DBGame, db_players: list) -> Game:
        """
        Helper: Convert database models to in-memory Game object.
        """
        # Find host
        host_player = next((p for p in db_players if p.is_host), db_players[0])
        host = Player(
            player_id=str(host_player.player_id),
            name=host_player.name,
            is_host=True
        )
        host.score = host_player.score
        host.question = host_player.question
        host.answer = host_player.answer
        host.is_imposter = host_player.is_imposter
        
        # Create game
        game = Game(game_id=db_game.game_id, host=host)
        game.stage = db_game.stage
        
        # Add all other players
        for db_player in db_players:
            if not db_player.is_host:
                player = Player(
                    player_id=str(db_player.player_id),
                    name=db_player.name,
                    is_host=False
                )
                player.score = db_player.score
                player.question = db_player.question
                player.answer = db_player.answer
                player.is_imposter = db_player.is_imposter
                game.players.append(player)
        
        return game

    # ------------------------------
    # WebSocket Management (STAYS IN MEMORY)
    # ------------------------------
    async def connect(self, websocket: WebSocket, game_id: str, player_name: str):
        """Add a websocket connection to a specific player within a game."""
        await websocket.accept()

        if game_id not in self.connections:
            self.connections[game_id] = {}

        self.connections[game_id][player_name] = websocket
        print(f"🟢 {player_name} connected to game {game_id}")
        print(f"   Total connected players: {list(self.connections[game_id].keys())}")

    def disconnect(self, websocket: WebSocket, game_id: str, player_name: str):
        """Remove a player's websocket connection."""
        if game_id in self.connections and player_name in self.connections[game_id]:
            del self.connections[game_id][player_name]
            print(f"🔴 {player_name} disconnected from {game_id}")

    async def send_to_player(self, game_id: str, player_name: str, message: dict):
        """Send a message to a specific player"""
        if game_id not in self.connections:
            print(f"⚠️ No connections for game {game_id}")
            return
        
        if player_name not in self.connections[game_id]:
            print(f"⚠️ Player {player_name} not connected to game {game_id}")
            print(f"   Available players: {list(self.connections[game_id].keys())}")
            return
        
        websocket = self.connections[game_id][player_name]
        
        try:
            await websocket.send_json(message)
            print(f"✅ Sent to {player_name}: {message.get('event', 'unknown')}")
        except Exception as e:
            print(f"❌ Failed to send to {player_name}: {e}")
            del self.connections[game_id][player_name]
    
    async def broadcast(self, game_id: str, message: dict):
        """Send a message to all players in a game"""
        if game_id not in self.connections:
            print(f"⚠️ No connections for game {game_id}")
            return
        
        if not self.connections[game_id]:
            print(f"⚠️ No players connected to game {game_id}")
            return
        
        dead_connections = []
        
        for player_name, websocket in self.connections[game_id].items():
            try:
                await websocket.send_json(message)
                print(f"✅ Broadcast to {player_name}: {message.get('event', 'unknown')}")
            except Exception as e:
                print(f"❌ Failed to broadcast to {player_name}: {e}")
                dead_connections.append(player_name)
        
        for player_name in dead_connections:
            del self.connections[game_id][player_name]

    # ------------------------------
    # Game State Updates
    # ------------------------------
    async def send_current_state(self, websocket: WebSocket, game_id: str):
        """Send current game state from database"""
        game = self.get_game(game_id)
        if game:
            await websocket.send_json({
                "event": "current_state",
                "players": [p.name for p in game.players],
                "stage": game.stage
            })

    # ------------------------------
    # Game Logic (WITH DATABASE)
    # ------------------------------
    def generate_questions(self):
        return "What's your favorite food?", "A chinese cuisine?"

    def start_game(self, game_id: str):
        """Start the game and update database"""
        db = self._get_db()
        try:
            game = self.get_game(game_id)
            if not game:
                raise ValueError("Game not found")

            if len(game.players) < 3:
                raise ValueError("At least 3 players required")

            # Randomly assign imposters
            num_imposters = random.randint(1, len(game.players) - 1)
            imposters = random.sample(game.players, num_imposters)
            game.imposters = imposters

            # Generate questions
            q_main, q_imposter = self.generate_questions()

            # Assign questions and update database
            for player in game.players:
                is_imposter = player in imposters
                question = q_imposter if is_imposter else q_main
                
                # Update in-memory
                player.question = question
                player.is_imposter = is_imposter
                
                # Update database
                db.query(DBPlayer).filter(DBPlayer.player_id == player.player_id).update({
                    "question": question,
                    "is_imposter": is_imposter
                })

            # Update game stage in database
            db.query(DBGame).filter(DBGame.game_id == game_id).update({
                "stage": "question_answering"
            })
            db.commit()

            game.stage = "question_answering"
            print(f"✅ Game {game_id} started")
            return game
            
        finally:
            db.close()

    async def reveal_answers(self, game_id: str):
        """Reveal everyone's answers"""
        game = self.get_game(game_id)
        if not game:
            raise ValueError("Game not found")

        results = [
            {"player": p.name, "answer": p.answer}
            for p in game.players
        ]

        # Update stage in database
        db = self._get_db()
        try:
            db.query(DBGame).filter(DBGame.game_id == game_id).update({
                "stage": "reveal_answers"
            })
            db.commit()
        finally:
            db.close()

        await self.broadcast(game_id, {
            "event": "reveal_answers",
            "data": results
        })

    async def reveal_imposter(self, game_id: str):
        """Reveal imposter and calculate scores"""
        db = self._get_db()
        try:
            game = self.get_game(game_id)
            if not game:
                return

            # Get votes from database
            votes = db.query(DBVote).filter(DBVote.game_id == game_id).all()
            vote_counts = {}
            for vote in votes:
                voted_id = str(vote.voted_player_id)
                vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

            max_votes = max(vote_counts.values(), default=0)
            most_voted_ids = [pid for pid, count in vote_counts.items() if count == max_votes]

            # Calculate scores
            for player in game.players:
                if player in game.imposters and player.player_id not in most_voted_ids:
                    player.score += 2
                elif player not in game.imposters and any(
                    imp.player_id in most_voted_ids for imp in game.imposters
                ):
                    player.score += 1

                # Update score in database
                db.query(DBPlayer).filter(DBPlayer.player_id == player.player_id).update({
                    "score": player.score
                })

            # Update game stage
            db.query(DBGame).filter(DBGame.game_id == game_id).update({
                "stage": "game_end"
            })
            db.commit()

            # Broadcast results
            summary = {
                "event": "reveal_imposter",
                "stage": "game_end",
                "imposters": [p.name for p in game.imposters],
                "votes": vote_counts,
                "scores": {p.name: p.score for p in game.players},
            }

            await self.broadcast(game_id, summary)
            
        finally:
            db.close()