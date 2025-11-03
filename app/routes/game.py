from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from app.schemas import CreateGameRequest, CreateGameResponse, JoinGameRequest, JoinGameResponse, SubmitAnswerRequest
from app.game_manager import GameManager

router = APIRouter()
game_manager = GameManager()


@router.websocket("/ws/games/{game_id}/{player_name}")
async def websocket_endpoint_for_joining_game_updates(websocket: WebSocket, game_id: str, player_name: str):
    """WebSocket endpoint for players to subscribe to game updates."""
    try:
        await websocket.accept()  # Ensure connection is accepted first
        print(f"🔌 Player '{player_name}' connected to game {game_id}")

        await game_manager.connect(websocket, game_id, player_name)
        await game_manager.send_current_state(websocket, game_id)

        while True:
            data = await websocket.receive_text()
            print(f"📨 Message from {player_name}: {data}")

            # You can structure messages more clearly
            await game_manager.broadcast(game_id, {
                "event": "player_message",
                "player": player_name,
                "data": data
            })

    except WebSocketDisconnect:
        print(f"⚠️ Player '{player_name}' disconnected from game {game_id}")
        game_manager.disconnect(websocket, game_id)

    except Exception as e:
        print(f"❌ WebSocket error for player '{player_name}': {e}")
        await websocket.close()




@router.post("/create_game", response_model=CreateGameResponse)
def create_game(req: CreateGameRequest):
    game = game_manager.create_game(req.host_name)
    return CreateGameResponse(
        game_id=game.game_id,
        players=[p.name for p in game.players],
        stage=game.stage
    )


@router.post("/join_game", response_model=JoinGameResponse)
async def join_game(req: JoinGameRequest):
    try:
        game = game_manager.join_game(req.game_id, req.player_name)

        # 🔥 Notify everyone via WebSocket that a new player joined
        await game_manager.broadcast(
            req.game_id,
            {
                "event": "player_joined",
                "player": req.player_name,
                "players": [p.name for p in game.players],
                "stage": game.stage
            }
        )

        return JoinGameResponse(
            game_id=game.game_id,
            players=[p.name for p in game.players],
            stage=game.stage
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/start_game/{game_id}")
async def start_game(game_id: str):
    try:
        # Step 1: Start the game and get the game object
        game = game_manager.start_game(game_id)

        # Step 2: Notify all players that the game has started
        await game_manager.broadcast(
            game_id,
            {
                "event": "game_started",
                "stage": game.stage,
                "player_count": len(game.players),
                "imposter_count": len(game.imposters),
            },
        )

        # Step 3: Send individual questions to each player privately
        for player in game.players:
            message = {
                "event": "your_question",
                "question": player.question,
                'game': game.stage,
                "is_imposter": player in game.imposters
            }

            # Send only to that player's WebSocket connection
            await game_manager.send_to_player(game_id, player.name, message)

        # Step 4: Return a simple confirmation
        return {
            "message": "Game started successfully!",
            "game_id": game.game_id,
            "stage": game.stage,
            "players": [p.name for p in game.players],
            "imposters": [p.name for p in game.imposters],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.post("/games/{game_id}/submit-answer")
async def submit_answer(game_id: str, player_id: str, answer: str):
    """
    Endpoint for players to submit their answers.
    When all players have submitted, automatically trigger reveal phase.
    """
    game = game_manager.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Find player
    player = next((p for p in game.players if p.id == player_id), None)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # Store answer
    player.answer = answer

    # Check if all players have answered
    all_answered = all(p.answer is not None for p in game.players)

    if all_answered:
        # Move to reveal phase
        await game_manager.reveal_answers(game_id)

    return {"status": "success", "message": "Answer submitted successfully"}
    
@router.post("/games/{game_id}/vote/{player_id}/{target_id}")
async def vote(game_id: str, player_id: str, target_id: str):
    """
    A player votes for another player they suspect is the imposter.
    Each player can only vote once, but they can change their vote before time is up.
    """
    # Step 1: Validate that the game exists
    game = game_manager.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Step 2: Validate voter and target
    voter = next((p for p in game.players if p.player_id == player_id), None)
    target = next((p for p in game.players if p.player_id == target_id), None)
    if not voter or not target:
        raise HTTPException(status_code=404, detail="Player not found")

    # Step 3: Initialize votes if not already done
    if not hasattr(game, "votes"):
        game.votes = {}

    # Step 4: Record or update vote
    game.votes[player_id] = target_id

    # Step 5: Count total votes received by each player
    vote_counts = {}
    for voted_id in game.votes.values():
        vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1

    # Step 6: Notify all players via WebSocket
    await game_manager.broadcast(game_id, {
        "event": "vote_update",
        "votes": vote_counts,
    })

    # Step 7: Check if all players have voted
    all_voted = len(game.votes) == len(game.players)
    if all_voted:
        # Move to next stage
        game.stage = "reveal_imposter"
        await game_manager.reveal_imposter(game_id)

    # Step 8: Respond to the current voter
    return {
        "status": "success",
        "message": f"{voter.name} voted for {target.name}",
        "current_votes": vote_counts,
        "all_voted": all_voted,
    }

@router.post("/games/{game_id}/restart")
async def restart_game(game_id: str):
    """
    Restart the game with the same players.
    Keeps scores persistent across rounds.
    Reassigns new imposters, new questions, and resets votes.
    """
    game = game_manager.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Reset only round-specific data (keep total scores)
    for player in game.players:
        player.question = None
        player.is_imposter = False

    # Clear temporary game data
    game.votes = {}
    game.stage = "starting"
    game.imposters = []

    # Randomly reassign imposters
    import random
    num_imposters = random.randint(1, len(game.players) - 1)
    imposters = random.sample(game.players, num_imposters)
    game.imposters = imposters

    for imp in imposters:
        imp.is_imposter = True

    # Generate new questions
    q_main, q_imposter = game_manager.generate_questions()

    for player in game.players:
        player.question = q_imposter if player in imposters else q_main

    # Advance stage to question-answering
    game.stage = "question_answering"

    # Notify all connected players via WebSocket
    await game_manager.broadcast(game_id, {
        "event": "game_restarted",
        "message": "A new round has begun!",
        "stage": game.stage,
        "players": [
            {
                "name": p.name,
                "points": getattr(p, "points", 0),
                "question": p.question,
                "is_imposter": p.is_imposter
            }
            for p in game.players
        ]
    })

    return {
        "status": "success",
        "message": "Game restarted successfully",
        "next_stage": game.stage,
        "total_players": len(game.players),
        "scores": {p.name: getattr(p, "points", 0) for p in game.players}
    }


@router.post("/games/{game_id}/end")
async def end_game(game_id: str):
    """
    Ends the game completely and notifies all connected players.
    """
    game = game_manager.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await game_manager.broadcast(game_id, {
        "event": "game_ended",
        "message": "The game has ended. Thanks for playing!"
    })

    # Close all websocket connections for this game
    for conn in game_manager.active_connections.get(game_id, []):
        await conn.close()

    # Clean up from memory
    del game_manager.games[game_id]
    if game_id in game_manager.active_connections:
        del game_manager.active_connections[game_id]

    return {"status": "success", "message": "Game ended and all connections closed."}
