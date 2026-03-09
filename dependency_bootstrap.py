"""Shared dependency bootstrap helpers for the Android app analyzer skill."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import subprocess
import sys
from typing import Callable, Iterable, List, Sequence


@dataclass(frozen=True)
class DependencySpec:
    """Maps a pip package name to the module imported at runtime."""

    package_name: str
    import_name: str = ""

    @property
    def module_name(self) -> str:
        return self.import_name or self.package_name


class DependencyBootstrapError(RuntimeError):
    """Raised when automatic dependency installation fails."""


def find_missing_dependencies(
    specs: Sequence[DependencySpec],
    importer: Callable[[str], object] = importlib.import_module,
) -> List[DependencySpec]:
    missing: List[DependencySpec] = []
    for spec in specs:
        try:
            importer(spec.module_name)
        except ImportError:
            missing.append(spec)
    return missing


def build_manual_install_command(specs: Iterable[DependencySpec]) -> str:
    packages = " ".join(spec.package_name for spec in specs)
    return f"{sys.executable} -m pip install {packages}"


def _format_failure_message(
    missing: Sequence[DependencySpec],
    stdout: str = "",
    stderr: str = "",
) -> str:
    details = (stderr or stdout).strip()
    lines = [
        "自动安装 Python 依赖失败。",
        f"请手动执行: {build_manual_install_command(missing)}",
        "如果你使用虚拟环境，请先激活虚拟环境后再执行安装命令。",
    ]
    if details:
        lines.extend(["", "pip 输出:", details])
    return "\n".join(lines)


def ensure_dependencies(
    specs: Sequence[DependencySpec],
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    importer: Callable[[str], object] = importlib.import_module,
    printer: Callable[[str], None] = print,
) -> None:
    missing = find_missing_dependencies(specs, importer=importer)
    if not missing:
        return

    packages = ", ".join(spec.package_name for spec in missing)
    printer(f"缺少 Python 依赖，正在尝试自动安装: {packages}")
    result = runner(
        [sys.executable, "-m", "pip", "install", *[spec.package_name for spec in missing]],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise DependencyBootstrapError(
            _format_failure_message(missing, stdout=result.stdout, stderr=result.stderr)
        )

    still_missing = find_missing_dependencies(missing, importer=importer)
    if still_missing:
        raise DependencyBootstrapError(_format_failure_message(still_missing))

    printer("Python 依赖安装完成。")
