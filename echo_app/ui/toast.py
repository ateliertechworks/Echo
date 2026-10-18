"""Small auto-hiding notifications stacked at the bottom of the main window."""

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

_host: QWidget | None = None
_toasts: list[QLabel] = []


class _ResizeWatcher(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            _reposition()
        return False


_watcher = _ResizeWatcher()


def install(host: QWidget):
    global _host
    _host = host
    host.installEventFilter(_watcher)


def _reposition():
    if not _host:
        return
    y = _host.height() - 24
    for label in reversed(_toasts):
        label.adjustSize()
        y -= label.height()
        label.move((_host.width() - label.width()) // 2, y)
        y -= 10


def toast(message: str, kind: str = "info", ms: int = 3500):
    if not _host:
        return
    label = QLabel(message, _host)
    label.setObjectName("Toast")
    label.setProperty("kind", kind)
    if label.fontMetrics().horizontalAdvance(message) > 480:
        label.setWordWrap(True)
        label.setFixedWidth(520)
    label.setAlignment(Qt.AlignCenter)
    label.setAttribute(Qt.WA_TransparentForMouseEvents)
    _toasts.append(label)
    label.show()
    label.raise_()
    _reposition()

    def remove():
        if label in _toasts:
            _toasts.remove(label)
        label.deleteLater()
        _reposition()

    QTimer.singleShot(ms, remove)
