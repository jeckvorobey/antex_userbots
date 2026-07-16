"""Fail-closed проверка Coolify persistent volume перед runtime startup."""

from __future__ import annotations

import hmac
import logging
import os
import stat
from pathlib import Path


logger = logging.getLogger(__name__)


class RuntimeVolumeValidationError(RuntimeError):
    """Production volume не соответствует ожидаемому Coolify resource."""


def _decode_mountinfo_path(value: str) -> str:
    """Декодирует стандартные octal escapes Linux mountinfo path."""
    return (
        value.replace(r"\040", " ")
        .replace(r"\011", "\t")
        .replace(r"\012", "\n")
        .replace(r"\134", "\\")
    )


class RuntimeVolumeGuard:
    """Проверяет mount point и identity marker production SQLite volume."""

    marker_name = ".coolify-resource-uuid"

    def __init__(
        self,
        db_path: str,
        *,
        coolify_resource_uuid: str | None = None,
        expected_mount_path: str | Path = "/app/data",
        mountinfo_path: str | Path = "/proc/self/mountinfo",
    ) -> None:
        self.db_path = db_path
        self.coolify_resource_uuid = (
            coolify_resource_uuid
            if coolify_resource_uuid is not None
            else os.environ.get("COOLIFY_RESOURCE_UUID")
        )
        self.expected_mount_path = Path(expected_mount_path).resolve(strict=False)
        self.mountinfo_path = Path(mountinfo_path)

    def verify(self) -> bool:
        """Возвращает True для проверенного Coolify volume, False для local bypass."""
        if self.db_path == ":memory:":
            return False

        effective_db_path = Path(self.db_path).resolve(strict=False)
        if effective_db_path.parent != self.expected_mount_path:
            if self.coolify_resource_uuid:
                raise RuntimeVolumeValidationError(
                    "Coolify runtime использует неожиданный SQLite path вне production mount"
                )
            return False

        resource_uuid = (self.coolify_resource_uuid or "").strip()
        if not resource_uuid:
            raise RuntimeVolumeValidationError(
                "Coolify runtime volume validation требует непустой COOLIFY_RESOURCE_UUID"
            )
        if not self._is_expected_mount_present():
            raise RuntimeVolumeValidationError(
                "Coolify runtime mount /app/data не найден в Linux mount table"
            )

        marker_value = self._read_marker()
        if not hmac.compare_digest(marker_value, resource_uuid):
            raise RuntimeVolumeValidationError(
                "Coolify runtime volume marker не соответствует текущему resource"
            )

        logger.info(
            "Coolify runtime volume подтверждён: mount_path=%s db_path=%s",
            self.expected_mount_path,
            effective_db_path,
        )
        return True

    def _is_expected_mount_present(self) -> bool:
        """Проверяет mount point по Linux mountinfo, включая bind mounts."""
        try:
            lines = self.mountinfo_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise RuntimeVolumeValidationError(
                "Не удалось прочитать Linux mount table для Coolify runtime mount"
            ) from exc

        for line in lines:
            fields = line.split()
            if len(fields) < 5:
                continue
            mount_point = Path(_decode_mountinfo_path(fields[4])).resolve(strict=False)
            if mount_point == self.expected_mount_path:
                return True
        return False

    def _read_marker(self) -> str:
        """Без перехода по symlink читает небольшой regular identity marker."""
        marker_path = self.expected_mount_path / self.marker_name
        open_flags = os.O_RDONLY
        open_flags |= getattr(os, "O_CLOEXEC", 0)
        open_flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            file_descriptor = os.open(marker_path, open_flags)
        except OSError as exc:
            raise RuntimeVolumeValidationError(
                "Coolify runtime volume marker отсутствует или небезопасен"
            ) from exc

        try:
            if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                raise RuntimeVolumeValidationError(
                    "Coolify runtime volume marker должен быть обычным файлом"
                )
            with os.fdopen(file_descriptor, "r", encoding="utf-8") as marker_file:
                marker_value = marker_file.read(257)
                file_descriptor = -1
        finally:
            if file_descriptor >= 0:
                os.close(file_descriptor)

        marker_value = marker_value.strip()
        if not marker_value or len(marker_value) > 256:
            raise RuntimeVolumeValidationError(
                "Coolify runtime volume marker пуст или имеет недопустимый размер"
            )
        return marker_value
