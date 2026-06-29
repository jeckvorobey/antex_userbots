"""Проверки репозиторных security-инвариантов."""

from __future__ import annotations

import subprocess


def test_runtime_profile_artifacts_are_not_tracked():
    """Проверяет, что runtime-артефакты профиля не находятся в git index."""
    runtime_profile_dir = "tg_user" + "_info"
    result = subprocess.run(
        ["git", "ls-files", runtime_profile_dir],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == ""
