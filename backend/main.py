"""
FastAPI Backend for Werewolves of Millers Hollow
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional
import json
import asyncio
from datetime import datetime

from backend.game.game_logic import WerewolfGame
from backend.models.game_models import GameState, Message, PlayerProfile
from backend.agents.ai_provider import AIProvider

app = FastAPI(title="Werewolves of Millers Hollow API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global game instance
game: Optional[WerewolfGame] = None
active_connections: List[WebSocket] = []


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error broadcasting: {e}")


manager = ConnectionManager()


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Werewolves of Millers Hollow API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/providers")
async def get_providers():
    """Get available AI providers"""
    try:
        providers = AIProvider.get_available_providers()
        return {"providers": providers}
    except Exception as e:
        return {"providers": [], "error": str(e)}


@app.post("/api/game/create")
async def create_game(num_players: int = 24, ai_provider: Optional[str] = None):
    """
    Create a new game
    
    Args:
        num_players: Number of players (default 24)
        ai_provider: AI provider to use (openai, gemini, mistral)
    """
    global game
    
    try:
        game = WerewolfGame(num_players=num_players, ai_provider=ai_provider)
        state = game.setup_game()
        
        # Broadcast game creation
        await manager.broadcast({
            "type": "game_created",
            "data": {
                "players": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "sex": p.sex.value,
                        "age": p.age,
                        "personality": p.personality.value,
                        "status": p.status.value
                    }
                    for p in state.players
                ],
                "phase": state.phase.value,
                "log": state.game_log
            }
        })
        
        return JSONResponse({
            "status": "success",
            "message": "Game created successfully",
            "game_state": {
                "num_players": len(state.players),
                "phase": state.phase.value
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/game/state")
async def get_game_state():
    """Get current game state"""
    if not game:
        raise HTTPException(status_code=404, detail="No active game")
    
    state = game.state
    return {
        "phase": state.phase.value,
        "day_number": state.day_number,
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "sex": p.sex.value,
                "age": p.age,
                "personality": p.personality.value,
                "role": p.role.value if p.role else None,
                "status": p.status.value
            }
            for p in state.players
        ],
        "game_log": state.game_log[-20:]  # Last 20 entries
    }


@app.post("/api/game/start")
async def start_game():
    """Start the game (begin first night)"""
    if not game:
        raise HTTPException(status_code=404, detail="No active game")
    
    try:
        announcement = game.start_night()
        
        await manager.broadcast({
            "type": "phase_change",
            "data": {
                "phase": "night",
                "day_number": game.state.day_number,
                "announcement": announcement
            }
        })
        
        return {"status": "success", "announcement": announcement}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/next-phase")
async def next_phase():
    """Progress to next game phase"""
    if not game:
        raise HTTPException(status_code=404, detail="No active game")
    
    try:
        current_phase = game.state.phase
        result = {}
        
        if current_phase.value == "night":
            # Process night actions and move to day
            night_results = game.process_night_actions()
            announcement = game.start_day()
            result = {
                "phase": "day",
                "announcement": announcement,
                "night_results": night_results
            }
        
        elif current_phase.value == "day":
            # Start discussion
            game.state.phase = "discussion"
            messages = game.conduct_discussion(rounds=2)
            result = {
                "phase": "discussion",
                "messages": messages
            }
        
        elif current_phase.value == "discussion":
            # Conduct vote
            eliminated, votes = game.conduct_vote()
            result = {
                "phase": "voting",
                "eliminated": eliminated.name if eliminated else None,
                "votes": votes
            }
            
            # Check win condition
            winner = game.check_win_condition()
            if winner:
                end_announcement = game.end_game(winner)
                result["game_ended"] = True
                result["winner"] = winner
                result["end_announcement"] = end_announcement
            else:
                # Start next night
                night_announcement = game.start_night()
                result["next_phase"] = "night"
                result["night_announcement"] = night_announcement
        
        await manager.broadcast({
            "type": "phase_change",
            "data": result
        })
        
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/players")
async def get_players():
    """Get all player profiles"""
    if not game:
        raise HTTPException(status_code=404, detail="No active game")
    
    return {
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "sex": p.sex.value,
                "age": p.age,
                "personality": p.personality.value,
                "personality_description": p.get_personality_description(),
                "status": p.status.value
            }
            for p in game.state.players
        ]
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Echo back for now
            await websocket.send_json({
                "type": "echo",
                "data": message
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
