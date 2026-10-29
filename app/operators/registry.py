# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""In-memory operator registry.

The registry is populated at import time by importing all modules in this
package. The engine uses `get_operator(op_code)` to look up an operator by
its op_code. The DB `operator` row is the metadata view of the same code.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.operators.base import OperatorBase

_REGISTRY: dict[str, type[OperatorBase]] = {}


def register(cls: type[OperatorBase]) -> type[OperatorBase]:
    """Class decorator. Registers a subclass of OperatorBase by its op_code."""
    if not cls.op_code:
        raise ValueError(f"{cls.__name__} is missing op_code")
    if cls.op_code in _REGISTRY:
        existing = _REGISTRY[cls.op_code]
        if existing is not cls:
            raise ValueError(f"duplicate op_code={cls.op_code}: {existing} vs {cls}")
    _REGISTRY[cls.op_code] = cls
    return cls


def get_operator(op_code: str) -> type[OperatorBase] | None:
    return _REGISTRY.get(op_code)


def all_operators() -> Iterator[tuple[str, type[OperatorBase]]]:
    return iter(_REGISTRY.items())


def known_op_codes() -> list[str]:
    return sorted(_REGISTRY.keys())
