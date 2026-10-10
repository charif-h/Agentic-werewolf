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
    client = create_llm_client()
    ready, message = await asyncio.to_thread(check_model, client)
    (logger.info if ready else logger.error)(message)
    warm_up = getattr(client, "warm_up", None)
    if ready and warm_up and get_settings().llm_warmup:
        asyncio.create_task(_warm_up(warm_up))      # in the background: the server is usable at once
    yield


async def _warm_up(warm_up) -> None:
    """Load the model into memory so that the first game does not wait for it"""
    try:
        seconds = await asyncio.to_thread(warm_up)
        logger.info("Model loaded in memory (%.1f s)", seconds)
    except Exception as e:
        logger.warning("Model warm-up failed: %s", e)


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
