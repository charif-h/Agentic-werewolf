"""
FastAPI Backend for Werewolves of Millers Hollow
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import games, health, players, websocket
from backend.api.errors import install_exception_handlers
from backend.config import get_settings

logging.basicConfig(level=get_settings().log_level.upper(),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Werewolves of Millers Hollow API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,  # the API uses no cookies
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

install_exception_handlers(app)

app.include_router(health.router)
app.include_router(games.router)
app.include_router(players.router)
app.include_router(websocket.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=get_settings().host, port=get_settings().port)
