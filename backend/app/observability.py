import json
import logging
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("incident-agent")


def log_event(event: str, *, maintenance_id: str | None = None, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, "maintenance_id": maintenance_id, **fields}, default=str))
