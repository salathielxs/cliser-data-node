from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


LOGGER_NAME = "cliser.api"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }

        fields = (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "identity_id",
            "credential_id",
            "namespace",
            "operation",
            "error_code",
        )

        for field in fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    return logger


logger = get_logger()
