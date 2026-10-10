"""Is the local model ready? One place for the check and its human-readable message"""
from typing import Any, Tuple


def check_model(client: Any) -> Tuple[bool, str]:
    """
    Ask `client` (an OllamaClient) whether the server is up and the model installed

    Clients without a `status()` method (fakes, other backends) are assumed ready.

    Returns:
        (ready, message). The message says what to do when not ready.
    """
    status_of = getattr(client, "status", None)
    if status_of is None:
        return True, "Language model ready."
    status = status_of()
    if not status["reachable"]:
        return False, (f"Ollama is not running at {status['host']}. "
                       "Start it (https://ollama.com), then try again.")
    if not status["installed"]:
        return False, (f"The model '{status['model']}' is not installed. "
                       f"Run: ollama pull {status['model']}")
    size = status.get("size_bytes")
    detail = f" ({size / 1e9:.1f} GB)" if size else ""
    return True, f"Ollama is running and '{status['model']}' is installed{detail}."
