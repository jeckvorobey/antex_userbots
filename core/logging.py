"""Централизованная настройка логирования приложения."""

import logging
import logging.handlers
from pathlib import Path


_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(
    level: str = "INFO",
    *,
    log_file: str | None = None,
    file_level: str = "ERROR",
    file_max_bytes: int = 10_485_760,
    file_backup_count: int = 5,
) -> None:
    """Настраивает root logger для консольного и файлового вывода."""
    normalized_level = getattr(logging, level.upper(), logging.INFO)
    normalized_file_level = getattr(logging, file_level.upper(), logging.ERROR)
    root_logger = logging.getLogger()

    if not getattr(setup_logging, "_configured", False):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root_logger.addHandler(handler)
        setup_logging._configured = True

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handlers = [
            existing
            for existing in root_logger.handlers
            if isinstance(existing, logging.handlers.RotatingFileHandler)
            and Path(existing.baseFilename).resolve() == log_path.resolve()
        ]
        if not file_handlers:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=file_max_bytes,
                backupCount=file_backup_count,
            )
            file_handler.setLevel(normalized_file_level)
            file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
            root_logger.addHandler(file_handler)
        else:
            file_handlers[0].setLevel(normalized_file_level)

    root_logger.setLevel(normalized_level)
