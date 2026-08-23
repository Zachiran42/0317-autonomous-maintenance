import json
import logging
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("incident-agent")


def log_event(event: str, *, incident_id: str | None = None, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, "incident_id": incident_id, **fields}, default=str))

