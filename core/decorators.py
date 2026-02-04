from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def log_exceptions(
    *,
    default: T | None = None,
    default_factory: Callable[P, T] | None = None,
    message: str | None = None,
    logger_name: str | None = None,
    exception_types: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T | None]]:
    if default_factory is not None and default is not None:
        raise ValueError("default and default_factory cannot be used together.")

    def decorator(func: Callable[P, T]) -> Callable[P, T | None]:
        logger = logging.getLogger(logger_name or func.__module__)

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            try:
                return func(*args, **kwargs)
            except exception_types:
                logger.exception(message or "Unhandled error in %s", func.__name__)
                if default_factory is not None:
                    return default_factory(*args, **kwargs)
                return default

        return wrapper

    return decorator
