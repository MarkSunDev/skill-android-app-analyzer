"""Workspace management helpers for repeated APK/XAPK analysis runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional


DEFAULT_CACHE_PARENT = ".cache"
DEFAULT_WORKSPACE_NAME = "android-app-analyzer"
SOFT_WORKSPACE_LIMIT = 5
HARD_WORKSPACE_LIMIT = 20
WORKSPACE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class WorkspaceLimitError(RuntimeError):
    """Raised when the managed cache workspace exceeds the hard limit."""


@dataclass(frozen=True)
class PackageWorkspace:
    """Resolved directories for a single package workspace."""

    package_name: str
    package_dir: Path
    downloads_dir: Path
    extracted_dir: Path
    reports_dir: Path
    temp_dir: Path


def sanitize_workspace_name(name: str) -> str:
    """Return a filesystem-safe workspace name."""

    sanitized = WORKSPACE_NAME_PATTERN.sub("_", name.strip())
    sanitized = sanitized.strip("._")
    if not sanitized:
        raise ValueError("Workspace name cannot be empty.")
    return sanitized


def resolve_workspace_root(
    repo_root: Optional[Path] = None,
    output_root: Optional[Path] = None,
) -> Path:
    """Resolve and create the managed workspace root."""

    if output_root is not None:
        workspace_root = Path(output_root).resolve()
    else:
        base_root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parent
        workspace_root = base_root / DEFAULT_CACHE_PARENT / DEFAULT_WORKSPACE_NAME

    workspace_root.mkdir(parents=True, exist_ok=True)
    return workspace_root


def count_package_workspaces(workspace_root: Path) -> int:
    """Count top-level package workspaces under the managed root."""

    if not workspace_root.exists():
        return 0
    return sum(1 for child in workspace_root.iterdir() if child.is_dir())


def ensure_workspace_capacity(
    workspace_root: Path,
    soft_limit: int = SOFT_WORKSPACE_LIMIT,
    hard_limit: int = HARD_WORKSPACE_LIMIT,
) -> Optional[str]:
    """Validate workspace size and return a warning message when appropriate."""

    count = count_package_workspaces(workspace_root)
    if count > hard_limit:
        raise WorkspaceLimitError(
            f"Cache workspace has {count} package workspaces. "
            "Please clear the cache workspace before continuing."
        )
    if count > soft_limit:
        return (
            f"Cache workspace already has {count} package workspaces. "
            "Please clear old package workspaces to keep the cache manageable."
        )
    return None


def create_package_workspace(workspace_root: Path, package_name: str) -> PackageWorkspace:
    """Create and return the managed directory structure for a package."""

    safe_name = sanitize_workspace_name(package_name)
    package_dir = workspace_root / safe_name
    if not package_dir.exists() and count_package_workspaces(workspace_root) >= HARD_WORKSPACE_LIMIT:
        raise WorkspaceLimitError(
            "Cache workspace has reached the maximum of 20 package workspaces. "
            "Please clear the cache workspace before continuing."
        )
    downloads_dir = package_dir / "downloads"
    extracted_dir = package_dir / "extracted"
    reports_dir = package_dir / "reports"
    temp_dir = package_dir / "temp"

    for directory in (package_dir, downloads_dir, extracted_dir, reports_dir, temp_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return PackageWorkspace(
        package_name=safe_name,
        package_dir=package_dir,
        downloads_dir=downloads_dir,
        extracted_dir=extracted_dir,
        reports_dir=reports_dir,
        temp_dir=temp_dir,
    )
