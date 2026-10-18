"""Runs blocking work (database, model, file export) off the UI thread."""

import logging

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

log = logging.getLogger(__name__)

_live = set()  # keep tasks alive until their result is delivered


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(object)


class _Task(QRunnable):
    def __init__(self, fn, args, kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # noqa: BLE001 — forwarded to the UI
            self.signals.failed.emit(e)
        else:
            self.signals.finished.emit(result)


def error_message(exc: Exception) -> str:
    from psycopg import OperationalError
    from psycopg_pool import PoolTimeout

    from echo_app.services import ServiceError

    if isinstance(exc, ServiceError):
        return str(exc)
    if isinstance(exc, (OperationalError, PoolTimeout)):
        return "Can't reach the database. Check that Postgres is running and DATABASE_URL is correct."
    return str(exc) or exc.__class__.__name__


def _default_error(exc):
    from echo_app.ui.toast import toast

    toast(error_message(exc), "error")


def run_async(fn, *args, on_done=None, on_error=None, owner=None, **kwargs):
    """Calls fn(*args, **kwargs) on the thread pool; callbacks run on the UI thread.

    When `owner` (a widget) has been destroyed by the time the work finishes, the
    callbacks are skipped.
    """
    task = _Task(fn, args, kwargs)
    task.setAutoDelete(False)
    _live.add(task)

    def finished(result):
        _live.discard(task)
        if owner is not None and not shiboken6.isValid(owner):
            return
        if on_done:
            on_done(result)

    def failed(exc):
        _live.discard(task)
        from echo_app.services import ServiceError

        if not isinstance(exc, ServiceError):
            log.error("Background task %s failed", getattr(fn, "__name__", fn), exc_info=exc)
        if owner is not None and not shiboken6.isValid(owner):
            return
        (on_error or _default_error)(exc)

    task.signals.finished.connect(finished)
    task.signals.failed.connect(failed)
    QThreadPool.globalInstance().start(task)
