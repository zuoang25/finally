"""Exception handlers mapping domain errors onto CONTRACTS.md section 4 codes."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.db import DbError, DuplicateTickerError
from app.services import InvalidTickerError, NoPriceError, TradeValidationError


def _detail(exc: Exception, code: int) -> JSONResponse:
    return JSONResponse(status_code=code, content={"detail": str(exc)})


async def _duplicate_ticker_handler(_: Request, exc: Exception) -> JSONResponse:
    return _detail(exc, status.HTTP_409_CONFLICT)


async def _db_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return _detail(exc, status.HTTP_400_BAD_REQUEST)


async def _bad_request_handler(_: Request, exc: Exception) -> JSONResponse:
    return _detail(exc, status.HTTP_400_BAD_REQUEST)


async def _no_price_handler(_: Request, exc: Exception) -> JSONResponse:
    return _detail(exc, status.HTTP_503_SERVICE_UNAVAILABLE)


def register_exception_handlers(app: FastAPI) -> None:
    """Wire domain exceptions to their HTTP status codes.

    Starlette resolves handlers along the exception's MRO, so the
    `DuplicateTickerError` entry wins over the broader `DbError` one.
    """
    app.add_exception_handler(DuplicateTickerError, _duplicate_ticker_handler)
    app.add_exception_handler(DbError, _db_error_handler)
    app.add_exception_handler(InvalidTickerError, _bad_request_handler)
    app.add_exception_handler(TradeValidationError, _bad_request_handler)
    app.add_exception_handler(NoPriceError, _no_price_handler)
