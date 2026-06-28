from __future__ import annotations

import subprocess


def test_layering_contracts_hold() -> None:
    try:
        result = subprocess.run(
            ["uv", "run", "lint-imports"],
            cwd=".",  # pytest runs from backend/; pyproject.toml is here
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError("lint-imports timed out after 120 seconds") from exc
    assert result.returncode == 0, result.stdout + result.stderr
