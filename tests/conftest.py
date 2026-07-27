"""Shared fixtures for PersonaCR verification suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.src.core.github_ingestor import CodeChunk


def make_chunk(
    name: str,
    source: str,
    *,
    file_path: str = "sample.py",
    language: str = "python",
    granularity: str = "function",
    start_line: int = 1,
) -> CodeChunk:
    lines = source.splitlines()
    return CodeChunk(
        file_path=file_path,
        language=language,
        function_name=name,
        source=source,
        start_line=start_line,
        end_line=start_line + max(len(lines) - 1, 0),
        granularity=granularity,
    )


# Hand-countable corpus:
#   docstring: 7/10 → 0.7
#   type hints: 5/10 → 0.5
#   error handling: 3/10 → 0.3
#   naming: snake_case
#   nonempty-line lengths: [6,6,6,3,3,3,3,2,3,4] → avg 3.9, max 6
FINGERPRINT_SPECS: list[tuple[str, str]] = [
    (
        "alpha_one",
        'def alpha_one(x: int) -> int:\n    """A."""\n    try:\n        return x\n    except ValueError:\n        return 0',
    ),
    (
        "alpha_two",
        'def alpha_two(x: int) -> int:\n    """B."""\n    try:\n        return x\n    except ValueError:\n        return 0',
    ),
    (
        "alpha_three",
        'def alpha_three(x: int) -> int:\n    """C."""\n    try:\n        return x\n    except ValueError:\n        return 0',
    ),
    (
        "alpha_four",
        'def alpha_four(x: int) -> int:\n    """D."""\n    return x',
    ),
    (
        "alpha_five",
        'def alpha_five(x: int) -> int:\n    """E."""\n    return x',
    ),
    (
        "beta_six",
        'def beta_six(x):\n    """F."""\n    return x',
    ),
    (
        "beta_seven",
        'def beta_seven(x):\n    """G."""\n    return x',
    ),
    (
        "gamma_eight",
        "def gamma_eight(x):\n    return x",
    ),
    (
        "gamma_nine",
        "def gamma_nine(x):\n    y = x + 1\n    return y",
    ),
    (
        "gamma_ten",
        "def gamma_ten(x):\n    y = x + 1\n    z = y + 1\n    return z",
    ),
]


@pytest.fixture
def known_fingerprint_chunks() -> list[CodeChunk]:
    return [
        make_chunk(name, src, start_line=(i * 10) + 1)
        for i, (name, src) in enumerate(FINGERPRINT_SPECS)
    ]


@pytest.fixture
def known_fingerprint_expected() -> dict:
    lengths = [6, 6, 6, 3, 3, 3, 3, 2, 3, 4]
    return {
        "total_functions": 10,
        "docstring_coverage": 0.7,
        "type_hint_usage": 0.5,
        "error_handling_rate": 0.3,
        "naming_convention": "snake_case",
        "avg_function_length": round(sum(lengths) / len(lengths), 1),
        "max_function_length": max(lengths),
    }
