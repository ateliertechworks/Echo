"""Reusable building blocks shared by the pages."""

import base64
import re

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from echo_app.ui import theme


def repolish(widget: QWidget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_prop(widget: QWidget, name: str, value):
    if widget.property(name) != value:
        widget.setProperty(name, value)
        repolish(widget)


def button(text: str, variant: str = "primary", on_click=None, tooltip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setProperty("variant", variant)
    b.setCursor(Qt.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    if on_click:
        b.clicked.connect(on_click)
    return b


def label(text: str = "", name: str = "", wrap: bool = False, selectable: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    if selectable:
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


def badge(role: str, short: bool = True) -> QLabel:
    text = ("Leader" if short else "Team Leader") if role == "leader" else "Member"
    b = label(text, "Badge")
    b.setProperty("role", role)
    b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return b


def chip(text: str, name: str = "Chip") -> QLabel:
    c = label(text, name)
    c.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return c


def field(caption: str, widget: QWidget) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(label(caption, "FieldLabel"))
    lay.addWidget(widget)
    return box


def clear_layout(layout: QLayout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def scroll_page(body: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setObjectName("PageScroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    body.setObjectName("PageBody")
    area.setWidget(body)
    return area


class Card(QFrame):
    clicked = Signal()

    def __init__(self, clickable: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setProperty("clickable", clickable)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if self.property("clickable") and event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def pixmap_from_data_url(data_url: str | None) -> QPixmap | None:
    if not data_url:
        return None
    m = re.match(r"data:image/[\w.+-]+;base64,(.*)", data_url, re.S)
    if not m:
        return None
    pm = QPixmap()
    try:
        ok = pm.loadFromData(base64.b64decode(m.group(1)))
    except ValueError:
        return None
    return pm if ok and not pm.isNull() else None


def avatar_pixmap(user: dict | None, size: int) -> QPixmap:
    """Circular profile photo, or the first initial on a brand gradient."""
    user = user or {}
    dpr = 2
    out = QPixmap(size * dpr, size * dpr)
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addEllipse(QRectF(0, 0, size, size))
    p.setClipPath(path)
    photo = pixmap_from_data_url(user.get("profile_photo"))
    if photo:
        scaled = photo.scaled(size * dpr, size * dpr, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        x = (scaled.width() / dpr - size) / 2
        y = (scaled.height() / dpr - size) / 2
        p.drawPixmap(QPoint(int(-x), int(-y)), scaled)
    else:
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0, QColor(theme.SECONDARY))
        grad.setColorAt(1, QColor(theme.TERTIARY))
        p.fillRect(QRect(0, 0, size, size), grad)
        p.setPen(QColor("white"))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(size * 0.42))
        p.setFont(font)
        initial = (user.get("username") or "?").strip()[:1].upper() or "?"
        p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, initial)
    p.end()
    return out


class Avatar(QLabel):
    def __init__(self, user: dict | None = None, size: int = 40, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.set_user(user)

    def set_user(self, user: dict | None):
        self.setPixmap(avatar_pixmap(user, self._size))


class SvgCover(QWidget):
    """Paints an SVG scaled to cover the widget (like CSS object-fit: cover)."""

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.renderer = QSvgRenderer(str(path), self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _event):
        view = self.renderer.viewBoxF()
        if view.isEmpty():
            return
        scale = max(self.width() / view.width(), self.height() / view.height())
        w, h = view.width() * scale, view.height() * scale
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.renderer.render(p, QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h))
        p.end()


class FlowLayout(QLayout):
    """Lays children out left-to-right, wrapping onto new lines (chips, steps, suggestions)."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, dry_run=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, dry_run):
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_height = area.x(), area.y(), 0
        for item in self._items:
            if item.widget() and item.widget().isHidden():
                continue
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > area.right() + 1 and line_height > 0:
                x = area.x()
                y += line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not dry_run:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + m.bottom()


def hbox(*widgets, spacing: int = 8, margins=(0, 0, 0, 0)) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, QLayout):
            lay.addLayout(w)
        else:
            lay.addWidget(w)
    return lay
