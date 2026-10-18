"""Shared PostgreSQL access. Each `transaction()` block commits on success and
rolls back on error; rows come back as dicts."""

import logging
import threading
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from echo_app import config

log = logging.getLogger(__name__)

_pool = None
_pool_lock = threading.Lock()


def pool() -> ConnectionPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ConnectionPool(
                config.DATABASE_URL,
                min_size=1,
                max_size=5,
                kwargs={"row_factory": dict_row, "connect_timeout": 5},
                timeout=10,
                open=True,
            )
        return _pool


def close():
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


@contextmanager
def transaction():
    with pool().connection() as conn:
        yield conn


def fetch_all(sql, params=None):
    with transaction() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql, params=None):
    with transaction() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql, params=None):
    with transaction() as conn:
        conn.execute(sql, params)


def run_migrations():
    """Applies every migration in order. They are idempotent, so this runs on each start."""
    with transaction() as conn:
        for path in sorted(config.MIGRATIONS_DIR.glob("*.sql")):
            log.info("[migrate] applying %s", path.name)
            conn.execute(path.read_text(encoding="utf-8"))
    log.info("[migrate] done")
