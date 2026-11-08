"""Структурные логи приложения: одна JSON-строка на событие."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

LOGGER_NAME = "lada.analytics"


class JsonFormatter(logging.Formatter):
    """Пишет запись лога одной JSON-строкой без переводов строк."""

    def format(self, record: logging.LogRecord) -> str:
        """Собирает поля записи в компактный JSON."""
        return json.dumps(record_payload(record), ensure_ascii=False)


def record_payload(record: logging.LogRecord) -> dict[str, Any]:
    """Поля записи: время, уровень, логгер, сообщение и контекст."""
    base = {
        "time": round(record.created, 3),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    return {**base, **context_of(record)}


def context_of(record: logging.LogRecord) -> dict[str, Any]:
    """Дополнительные поля, переданные через extra."""
    return dict(getattr(record, "fields", {}) or {})


def with_formatter(handler: logging.Handler) -> logging.Handler:
    """Навешивает JSON-формат на обработчик."""
    handler.setFormatter(JsonFormatter())
    return handler


def json_handler() -> logging.Handler:
    """Обработчик, который печатает одну JSON-строку на событие."""
    return with_formatter(logging.StreamHandler(sys.stdout))


def configure(level: str = "INFO") -> logging.Logger:
    """Настраивает общий логгер приложения и отдаёт его."""
    logging.basicConfig(level=level, handlers=[json_handler()], force=True)
    return logger()


def logger() -> logging.Logger:
    """Логгер приложения."""
    return logging.getLogger(LOGGER_NAME)


def log_event(message: str, **fields: Any) -> None:
    """Пишет событие с произвольным контекстом."""
    logger().info(message, extra={"fields": fields})


def log_request(method: str, path: str, status: int, seconds: float) -> None:
    """Пишет событие о завершённом HTTP-запросе."""
    log_event("request", method=method, path=path, status=status, seconds=round(seconds, 3))
