import builtins
import os
import sys
import types
import unittest
from unittest.mock import patch

from clothing_assistant.config_data import get_checkpointer_backend, get_checkpointer_dsn
from clothing_assistant.infrastructure.checkpointer import create_checkpointer_runtime


class FakePool:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False
        self.close_calls = 0

    def close(self):
        self.closed = True
        self.close_calls += 1


class FakeSaver:
    def __init__(self, pool):
        self.pool = pool
        self.setup_called = False

    def setup(self):
        self.setup_called = True


class CheckpointerTests(unittest.TestCase):
    def test_memory_runtime_does_not_import_postgres_dependencies(self):
        original_import = builtins.__import__

        def import_without_postgres(name, *args, **kwargs):
            if name.startswith(("psycopg", "langgraph.checkpoint.postgres")):
                raise AssertionError(f"memory backend imported {name}")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_postgres):
            runtime = create_checkpointer_runtime("memory", None)

        self.assertEqual(runtime.saver.__class__.__name__, "InMemorySaver")

    def test_postgres_runtime_uses_required_pool_options_and_closes_once(self):
        dict_row = object()
        postgres_module = types.ModuleType("langgraph.checkpoint.postgres")
        postgres_module.PostgresSaver = FakeSaver
        psycopg_module = types.ModuleType("psycopg")
        psycopg_module.__path__ = []
        psycopg_rows_module = types.ModuleType("psycopg.rows")
        psycopg_rows_module.dict_row = dict_row
        psycopg_pool_module = types.ModuleType("psycopg_pool")
        psycopg_pool_module.ConnectionPool = FakePool

        with patch.dict(
            sys.modules,
            {
                "langgraph.checkpoint.postgres": postgres_module,
                "psycopg": psycopg_module,
                "psycopg.rows": psycopg_rows_module,
                "psycopg_pool": psycopg_pool_module,
            },
        ):
            runtime = create_checkpointer_runtime("postgres", "postgresql://langgraph:test@localhost/langgraph")

        self.assertTrue(runtime.saver.setup_called)
        self.assertEqual(
            runtime.saver.pool.kwargs["conninfo"],
            "postgresql://langgraph:test@localhost/langgraph",
        )
        self.assertEqual(runtime.saver.pool.kwargs["min_size"], 1)
        self.assertEqual(runtime.saver.pool.kwargs["max_size"], 5)
        self.assertEqual(
            runtime.saver.pool.kwargs["kwargs"],
            {
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        runtime.close()
        runtime.close()
        self.assertTrue(runtime.saver.pool.closed)
        self.assertEqual(runtime.saver.pool.close_calls, 1)

    def test_postgres_runtime_rejects_missing_dsn(self):
        with self.assertRaisesRegex(RuntimeError, "LANGGRAPH_CHECKPOINTER_DSN"):
            create_checkpointer_runtime("postgres", None)

    def test_postgres_runtime_closes_pool_when_saver_setup_fails(self):
        pool = FakePool()

        class SetupFailingSaver(FakeSaver):
            def setup(self):
                raise RuntimeError("setup failed")

        with self.assertRaisesRegex(RuntimeError, "setup failed"):
            create_checkpointer_runtime(
                "postgres",
                "postgresql://langgraph:test@localhost/langgraph",
                pool_factory=lambda **kwargs: pool,
                saver_factory=SetupFailingSaver,
            )

        self.assertEqual(pool.close_calls, 1)

    def test_postgres_runtime_closes_pool_when_saver_creation_fails(self):
        pool = FakePool()

        def fail_saver_creation(_pool):
            raise RuntimeError("saver creation failed")

        with self.assertRaisesRegex(RuntimeError, "saver creation failed"):
            create_checkpointer_runtime(
                "postgres",
                "postgresql://langgraph:test@localhost/langgraph",
                pool_factory=lambda **kwargs: pool,
                saver_factory=fail_saver_creation,
            )

        self.assertEqual(pool.close_calls, 1)

    def test_production_checkpointer_config_fails_closed(self):
        with patch.dict(os.environ, {"AI_RUNTIME_ENV": "production"}, clear=True):
            self.assertEqual(get_checkpointer_backend(), "postgres")
            with self.assertRaisesRegex(RuntimeError, "LANGGRAPH_CHECKPOINTER_DSN"):
                get_checkpointer_dsn()

        with patch.dict(
            os.environ,
            {
                "AI_RUNTIME_ENV": "production",
                "LANGGRAPH_CHECKPOINTER_BACKEND": "memory",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "production requires"):
                get_checkpointer_backend()


if __name__ == "__main__":
    unittest.main()
