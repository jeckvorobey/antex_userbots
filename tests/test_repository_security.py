"""Проверки репозиторных security-инвариантов."""

from __future__ import annotations

import subprocess
import tomllib
import zipfile
from fnmatch import fnmatchcase
from pathlib import Path


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


def test_distribution_package_discovery_includes_storage():
    """Проверяет, что установленный пакет содержит общий SQLite-слой."""
    project_root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    find_config = config["tool"]["setuptools"]["packages"]["find"]

    package_root = project_root / find_config["where"][0]
    discovered = {
        path.parent.relative_to(package_root).as_posix().replace("/", ".")
        for path in package_root.rglob("__init__.py")
    }
    packages = {
        package
        for package in discovered
        if any(fnmatchcase(package, pattern) for pattern in find_config["include"])
    }

    assert "storage" in packages


def test_built_wheel_contains_runtime_entrypoint_and_prompt_assets(tmp_path):
    """Проверяет фактический wheel, а не только setuptools discovery config."""
    project_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel_path = next(tmp_path.glob("*.whl"))

    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())

    assert "run.py" in names
    assert "ai/prompts/system.md" in names
    assert "ai/prompts/important_service.toml" in names
    assert any(name.startswith("ai/prompts/bots/") and name.endswith(".md") for name in names)
