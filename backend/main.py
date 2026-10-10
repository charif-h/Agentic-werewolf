"""
FastAPI Backend for Werewolves of Millers Hollow
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import games, health, players, websocket
from backend.api.errors import install_exception_handlers
from backend.config import get_settings
from backend.llm.factory import create_llm_client
from backend.llm.health import check_model

logging.basicConfig(level=get_settings().log_level.upper(),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """At startup, say clearly whether the local model is ready (the server starts either way)"""
    ready, message = await asyncio.to_thread(check_model, create_llm_client())
    (logger.info if ready else logger.error)(message)
    yield


app = FastAPI(title="Werewolves of Millers Hollow API", lifespan=lifespan)

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
