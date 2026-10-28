"""B1 guardrail: client files and everything derived from them stay out of git (ADR-0008)."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from lumiant.core.config import BASE_DIR

PRIVATE_PATHS = [
    "services/api/var/private/client-sap/warehouse.duckdb",
    "services/api/var/private/client-sap/manifest.json",
    "services/api/var/private/tenants/client-sap.yaml",
    "services/api/var/private/inputs/Warehouse Stocks of Material.XLSX",
    "services/api/var/private/inputs/Material Master.xlsx",
    "services/api/Material Master.XLSX",
    "services/api/data/synthetic/stray-export.xlsx",
]


def _repo_root() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    out = subprocess.run(  # noqa: S603 — fixed arguments, no user input
        [git, "rev-parse", "--show-toplevel"], cwd=BASE_DIR, capture_output=True, text=True, check=False
    )
    return out.stdout.strip() if out.returncode == 0 else None


@pytest.mark.security
@pytest.mark.parametrize("path", PRIVATE_PATHS)
def test_private_paths_are_git_ignored(path: str) -> None:
    root = _repo_root()
    if root is None:
        pytest.skip("not a git checkout (e.g. inside the container image)")
    git = shutil.which("git")
    assert git is not None
    result = subprocess.run(  # noqa: S603
        [git, "check-ignore", "--no-index", "-q", path], cwd=root, capture_output=True, check=False
    )
    assert result.returncode == 0, f"{path} is not ignored by .gitignore"


@pytest.mark.security
def test_nothing_private_is_tracked() -> None:
    root = _repo_root()
    if root is None:
        pytest.skip("not a git checkout")
    git = shutil.which("git")
    assert git is not None
    tracked = subprocess.run(  # noqa: S603
        [git, "ls-files", "services/api/var", "*.xlsx", "*.XLSX"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.split()
    assert tracked == []
