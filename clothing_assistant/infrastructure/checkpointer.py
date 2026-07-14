"""Factories for LangGraph checkpoint runtimes."""

from dataclasses import dataclass
from typing import Any, Callable

from langgraph.checkpoint.memory import InMemorySaver


@dataclass
class CheckpointerRuntime:
    """Own a graph saver and the resource cleanup it needs."""

    saver: Any
    close: Callable[[], None]


def create_checkpointer_runtime(
    backend: str,
    dsn: str | None,
    pool_factory=None,
    saver_factory=None,
) -> CheckpointerRuntime:
    """Create a memory or PostgreSQL saver without exposing the connection."""
    if backend == "memory":
        return CheckpointerRuntime(saver=InMemorySaver(), close=lambda: None)

    if backend != "postgres":
        raise RuntimeError("LANGGRAPH_CHECKPOINTER_BACKEND must be memory or postgres")
    if not dsn or not dsn.strip():
        raise RuntimeError("LANGGRAPH_CHECKPOINTER_DSN is required for postgres")

    dict_row = None
    if pool_factory is None or saver_factory is None:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row as postgres_dict_row
        from psycopg_pool import ConnectionPool

        pool_factory = pool_factory or ConnectionPool
        saver_factory = saver_factory or PostgresSaver
        dict_row = postgres_dict_row

    pool_kwargs = {
        "conninfo": dsn,
        "min_size": 1,
        "max_size": 5,
        "kwargs": {
            "autocommit": True,
            "prepare_threshold": 0,
        },
    }
    if dict_row is not None:
        pool_kwargs["kwargs"]["row_factory"] = dict_row

    pool = pool_factory(**pool_kwargs)
    try:
        saver = saver_factory(pool)
        saver.setup()
    except Exception:
        pool.close()
        raise
    closed = False

    def close() -> None:
        nonlocal closed
        if not closed:
            closed = True
            pool.close()

    return CheckpointerRuntime(saver=saver, close=close)
