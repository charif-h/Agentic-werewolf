"""Root, health and provider information"""
from fastapi import APIRouter

import asyncio

from backend.api import state
from backend.llm.factory import create_llm_client

router = APIRouter()


@router.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Werewolves of Millers Hollow API",
        "version": "1.0.0",
        "status": "running"
    }


@router.get("/api/health")
async def health():
    """Liveness check with the number of running games"""
    return {"status": "ok", "games": len(state.sessions)}


@router.get("/api/model")
async def get_model():
    """Local model status: is Ollama reachable and is the model installed?"""
    return await asyncio.to_thread(create_llm_client().status)
