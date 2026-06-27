from __future__ import annotations

import subprocess


def test_import_contracts_hold() -> None:
    result = subprocess.run(
        ["uv", "run", "lint-imports"],
        cwd=".",  # pytest runs from backend/; pyproject.toml is here
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
