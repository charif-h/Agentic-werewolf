"""Root, health and provider information"""
from fastapi import APIRouter

from backend.agents.ai_provider import AIProvider
from backend.api import state

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


@router.get("/api/providers")
async def get_providers():
    """Get available AI providers"""
    try:
        providers = AIProvider.get_available_providers()
        return {"providers": providers}
    except Exception:
        # Don't expose internal error details
        return {"providers": [], "error": "Failed to load AI providers"}
