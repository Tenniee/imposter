from fastapi import WebSocket
from app.models import Game, Player
import uuid
import random

class GameManager:
    def __init__(self):
        self.games = {}  # game_id -> Game object
        self.connections = {}  # game_id -> list of WebSockets

    # ------------------------------
    # Game Management
    # ------------------------------
    def create_game(self, host_name: str) -> Game:
        game_id = str(uuid.uuid4())[:6]
        host = Player(player_id=str(uuid.uuid4()), name=host_name, is_host=True)
        game = Game(game_id=game_id, host=host)
        self.games[game_id] = game
        self.connections[game_id] = []  # init empty connections list
        return game

    def join_game(self, game_id: str, player_name: str) -> Game:
        if game_id not in self.games:
            raise ValueError("Game not found")

        player = Player(player_id=str(uuid.uuid4()), name=player_name)
        self.games[game_id].players.append(player)
        return self.games[game_id]

    # ------------------------------
    # WebSocket Management
    # ------------------------------
    async def connect(self, websocket: WebSocket, game_id: str):
        """Add a websocket connection to a game."""
        await websocket.accept()
        if game_id not in self.connections:
            self.connections[game_id] = []
        self.connections[game_id].append(websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        """Remove a websocket connection from a game."""
        if game_id in self.connections:
            if websocket in self.connections[game_id]:
                self.connections[game_id].remove(websocket)

    async def broadcast(self, game_id: str, message: dict):
        """Send a message to all connected websockets in the game."""
        if game_id in self.connections:
            to_remove = []
            for ws in self.connections[game_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    # mark broken sockets for removal
                    to_remove.append(ws)

            # cleanup broken connections
            for ws in to_remove:
                self.disconnect(ws, game_id)

    # ------------------------------
    # Game State Updates
    # ------------------------------
    async def send_current_state(self, websocket: WebSocket, game_id: str):
        game = self.games.get(game_id)
        if game:
            await websocket.send_json({
                "event": "current_state",
                "players": [p.name for p in game.players],
                "stage": game.stage
            })

    async def notify_game_update(self, game_id: str):
        """Notify ALL players in the game of the current state."""
        game = self.games.get(game_id)
        if game:
            await self.broadcast(
                game_id,
                {
                    "event": "game_update",
                    "stage": game.stage,
                    "players": [p.dict() for p in game.players],
                }
            )

    # ------------------------------
    # Game Logic
    # ------------------------------
    def generate_questions(self):
        return "What’s your favorite food?", "A chinese cuisine?"

    def start_game(self, game_id: str):
        game = self.games.get(game_id)
        if not game:
            raise ValueError("Game not found")

        players = game.players
        if len(players) < 3:
            raise ValueError("At least 3 players required")

        # Randomly assign imposters
        num_imposters = random.randint(1, len(players) - 1)
        imposters = random.sample(players, num_imposters)
        game.imposters = imposters

        # Generate questions
        q_main, q_imposter = self.generate_questions()

        # Assign questions
        for p in players:
            if p in imposters:
                p.question = q_imposter
            else:
                p.question = q_main

        game.stage = "question_answering"
        return game


    async def reveal_answers(self, game_id: str):
        """
        Reveal everyone's answers once all have been submitted.
        """
        game = self.games.get(game_id)
        if not game:
            raise ValueError("Game not found")

        # Prepare name + answer for everyone
        results = [
            {"player": p.name, "answer": p.answer}
            for p in game.players
        ]

        # Update stage
        game.stage = "reveal_answers"

        # Broadcast results to all connected clients
        await self.broadcast(game_id, {
            "event": "reveal_answers",
            "data": results
        })

    async def reveal_imposter(self, game_id: str):
        """
        Reveals the imposter(s), calculates scores,
        updates game stage, and notifies all players.
        """
        game = self.games.get(game_id)
        if not game:
            return

        # Ensure stage consistency
        game.stage = "reveal_imposter"

        # Count votes per player
        vote_counts = {}
        for voted_id in getattr(game, "votes", {}).values():
            vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

        # Identify the player(s) with the most votes
        max_votes = max(vote_counts.values(), default=0)
        most_voted_ids = [
            pid for pid, count in vote_counts.items() if count == max_votes
        ]

        # Reveal who the imposters were
        imposters = getattr(game, "imposters", [])

        # --- 🏆 SCORING LOGIC ---
        for player in game.players:
            # Initialize points if not already set
            if not hasattr(player, "points"):
                player.points = 0

            # If player is an imposter and was NOT voted — +2 points
            if player in imposters and player.player_id not in most_voted_ids:
                player.points += 2

            # If player is NOT an imposter and an imposter WAS voted — +1 point
            elif player not in imposters and any(
                imp.player_id in most_voted_ids for imp in imposters
            ):
                player.points += 1

        # --- 🎯 Prepare round summary ---
        summary = {
            "event": "reveal_imposter",
            "stage": game.stage,
            "imposters": [p.name for p in imposters],
            "votes": vote_counts,
            "scores": {p.name: getattr(p, "points", 0) for p in game.players},
        }

        # Broadcast the results to all connected players
        await self.broadcast(game_id, summary)

        # Move to END stage after results are shown
        game.stage = "game_end"

