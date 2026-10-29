# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Shared FastAPI dependencies for the API layer."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query

from app.schemas.common import PageParams


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
    q: Annotated[str | None, Query(max_length=128)] = None,
) -> PageParams:
    return PageParams(page=page, page_size=page_size, q=q)


PageDeps = Annotated[PageParams, Depends(page_params)]
