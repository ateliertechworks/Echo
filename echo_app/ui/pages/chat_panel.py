"""Today's Report — the Echo chatbot conversation, live draft and report preview."""

import random
import time
import uuid
from datetime import date, datetime

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from echo_app.services import model, reports
from echo_app.services.chat_flow import READY_TO_SUMMARIZE, chat_turn
from echo_app.services.questions import FIELD_ICONS, FIELD_LABELS, QUESTIONS, fields_for_role
from echo_app.ui import session as store
from echo_app.ui.tasks import error_message, run_async
from echo_app.ui.toast import toast
from echo_app.ui.widgets import (
    ClickableLabel, FlowLayout, button, chip, clear_layout, hbox, label, set_prop,
)

BUBBLE_MAX_WIDTH = 560
READY_LINES = [
    "That's everything! ✨ Here's your report preview — tweak anything you like, then hit Save Report.",
    "All set! 🎉 Review the draft below. You can click any field to edit it, or just tell me what to change.",
]


def greeting(name: str) -> str:
    h = datetime.now().hour
    part = "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"
    return (f"{part}{f', {name}' if name else ''}! 👋 I'm Echo. I'll ask a few quick questions and turn your answers "
            "into a clean report. Answer in your own words — typos are fine, I'll tidy them up.")


class Bubble(QWidget):
    """One chat message row (avatar + bubble)."""

    def __init__(self, msg: dict, on_retry=None, parent=None):
        super().__init__(parent)
        self.msg = msg
        is_bot = msg["from"] == "bot"
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        frame = QFrame()
        frame.setObjectName("BubbleBot" if is_bot else "BubbleUser")
        frame.setMaximumWidth(BUBBLE_MAX_WIDTH)
        frame.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        for prop in ("followUp", "error", "skipped"):
            frame.setProperty(prop, bool(msg.get(prop)))
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 10, 14, 11)
        lay.setSpacing(6)

        if is_bot and msg.get("followUp"):
            lay.addWidget(label("QUICK FOLLOW-UP", "MsgTag"))
        if msg.get("captured"):
            chips = QWidget()
            flow = FlowLayout(chips, spacing=5)
            for c in msg["captured"]:
                ch = chip(f"✓ {c['label']}", "ChipGreen")
                ch.setToolTip(c.get("value", ""))
                flow.addWidget(ch)
            lay.addWidget(chips)
        self.text = label(msg["content"], wrap=True, selectable=True)
        self.text.setTextFormat(Qt.PlainText)
        lay.addWidget(self.text)
        self._is_bot = is_bot
        if msg.get("retry") and on_retry:
            self.retry_btn = button("↻ Retry", "chip", on_retry)
            lay.addWidget(self.retry_btn, 0, Qt.AlignLeft)

        if is_bot:
            avatar = label("🤖", "MsgAvatar")
            avatar.setFixedSize(30, 30)
            avatar.setAlignment(Qt.AlignCenter)
            row.addWidget(avatar, 0, Qt.AlignTop)
            row.addWidget(frame)
            row.addStretch(1)
        else:
            row.addStretch(1)
            row.addWidget(frame)

        self._timer = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_text()

    def _fit_text(self):
        """Short messages hug their text; long ones wrap at the bubble's max width."""
        fm = self.text.fontMetrics()
        natural = max((fm.horizontalAdvance(line) for line in self.msg["content"].splitlines()), default=0) + 6
        reserved = 28 + 48 + (40 if self._is_bot else 0)  # bubble padding, gap to the edge, avatar
        width = max(80, min(natural, BUBBLE_MAX_WIDTH - 28, self.width() - reserved))
        if self.text.width() != width:
            self.text.setFixedWidth(width)

    def typewrite(self, on_tick=None):
        full = self.msg["content"]
        step = max(1, round(len(full) / 60))
        self._shown = 0
        self.text.setText("")
        self._timer = QTimer(self)

        def tick():
            self._shown = min(len(full), self._shown + step)
            self.text.setText(full[:self._shown] + ("▍" if self._shown < len(full) else ""))
            if self._shown >= len(full):
                self._timer.stop()
            if on_tick:
                on_tick()

        self._timer.timeout.connect(tick)
        self._timer.start(16)


class ThinkingRow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        avatar = label("🤖", "MsgAvatar")
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignCenter)
        frame = QFrame()
        frame.setObjectName("BubbleBot")
        f_lay = QHBoxLayout(frame)
        f_lay.setContentsMargins(14, 10, 14, 10)
        self.text = label("•  •  •", "Thinking")
        f_lay.addWidget(self.text)
        row.addWidget(avatar, 0, Qt.AlignTop)
        row.addWidget(frame)
        row.addStretch(1)
        self._started = 0.0
        self._frame = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._started = time.monotonic()
        self._frame = 0
        self._tick()
        self.show()
        self._timer.start(400)

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._frame = (self._frame + 1) % 3
        dots = ["•  ·  ·", "·  •  ·", "·  ·  •"][self._frame]
        secs = int(time.monotonic() - self._started)
        self.text.setText(f"{dots}    Echo is thinking… {secs}s" if secs >= 2 else dots)


class PreviewRow(QFrame):
    def __init__(self, f: dict, saved: bool, on_commit, parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewRow")
        self.f = f
        self.saved = saved
        self.on_commit = on_commit
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 10, 4, 10)
        lay.setSpacing(4)
        lay.addWidget(label(f"{FIELD_ICONS[f['field']]}  {f['label']}", "FieldLabel"))

        self.value = ClickableLabel()
        self.value.setObjectName("PreviewValue")
        self.value.setWordWrap(True)
        self.value.setTextFormat(Qt.PlainText)
        self.value.setProperty("editable", not saved)
        if f["value"]:
            self.value.setText(f["value"] + ("" if saved else "   ✏️"))
        else:
            self.value.setText("(skipped)" if saved else "(skipped — click to add)")
            self.value.setStyleSheet("color: #9AA0AE;")
        if not saved:
            self.value.setCursor(Qt.PointingHandCursor)
            self.value.setToolTip("Click to edit")
            self.value.clicked.connect(self.begin_edit)
        lay.addWidget(self.value)

        self.editor_box = QWidget()
        e_lay = QVBoxLayout(self.editor_box)
        e_lay.setContentsMargins(0, 0, 0, 0)
        self.editor = QPlainTextEdit()
        self.editor.setFixedHeight(76)
        self.editor.installEventFilter(self)
        e_lay.addWidget(self.editor)
        e_lay.addLayout(hbox(None, button("Cancel", "ghost", self.cancel_edit), button("Save", "primary", self.commit)))
        self.editor_box.hide()
        lay.addWidget(self.editor_box)

    def begin_edit(self):
        self.value.hide()
        self.editor.setPlainText(self.f["value"])
        self.editor_box.show()
        self.editor.setFocus()
        self.editor.moveCursor(QTextCursor.End)

    def cancel_edit(self):
        self.editor_box.hide()
        self.value.show()

    def commit(self):
        self.editor_box.hide()
        self.value.show()
        self.on_commit(self.f["field"], self.editor.toPlainText())

    def eventFilter(self, obj, event):
        if obj is self.editor and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
                self.commit()
                return True
            if event.key() == Qt.Key_Escape:
                self.cancel_edit()
                return True
        return super().eventFilter(obj, event)


class PreviewCard(QFrame):
    def __init__(self, preview: dict, saved: bool, busy: bool, flash: list, on_edit, on_save, on_edit_after_save,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("PreviewCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(4)
        lay.addLayout(hbox(label("📋  Report preview", "H3"), None,
                           label("Saved" if saved else "Click any field to edit", "Small")))
        self.rows = {}
        for f in preview["fields"]:
            row = PreviewRow(f, saved, on_edit)
            row.setProperty("flash", f["field"] in flash)
            self.rows[f["field"]] = row
            lay.addWidget(row)

        narrative = QFrame()
        narrative.setObjectName("Narrative")
        n_lay = QVBoxLayout(narrative)
        n_lay.setContentsMargins(14, 12, 14, 12)
        n_lay.addWidget(label("SUMMARY", "Overline"))
        n_lay.addWidget(label(preview.get("narrative") or "—", wrap=True, selectable=True))
        lay.addSpacing(8)
        lay.addWidget(narrative)

        lay.addSpacing(8)
        if saved:
            action = button("✏️  Make changes", "secondary", on_edit_after_save)
        else:
            action = button("💾  Save Report", "primary", on_save)
            action.setEnabled(not busy)
            action.setMinimumHeight(40)
        lay.addLayout(hbox(None, action))


class ChatPanel(QFrame):
    def __init__(self, team: dict, user: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("ChatPanel")
        self.team, self.user = team, user
        self.report_date = date.today()
        self.state_path = store.chat_state_path(user["id"], team["id"], self.report_date)

        self.messages: list[dict] = []
        self.bubbles: list[Bubble] = []
        self.draft: dict = {}
        self.current_field = None
        self.role = team.get("role") or "member"
        self.done = False
        self.preview = None
        self.suggestions: list[dict] = []
        self.phase = "loading"  # loading | chat | saved | error
        self.busy = False
        self.flash: list[str] = []
        self.model = None

        self._flash_timer = QTimer(self, singleShot=True, interval=1800)
        self._flash_timer.timeout.connect(self._clear_flash)

        self._build()
        run_async(model.model_status, on_done=self._set_model, on_error=lambda _e: self._set_model(None), owner=self)
        saved = store.load_chat_state(self.state_path)
        if saved and saved.get("messages"):
            self._restore(saved)
        else:
            self.start()

    # ------------------------------------------------------------------ layout
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("ChatHeader")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(18, 14, 18, 14)
        h_lay.setSpacing(12)
        self.bot_avatar = label("🤖", "BotAvatar")
        self.bot_avatar.setFixedSize(40, 40)
        self.bot_avatar.setAlignment(Qt.AlignCenter)
        h_lay.addWidget(self.bot_avatar)
        info = QVBoxLayout()
        info.setSpacing(3)
        title = label("Echo  <span style='color:#5C6270;font-weight:500;font-size:13px'>· Today's Report</span>",
                      "EchoTitle")
        info.addWidget(title)
        self.model_pill = label("checking…", "ModelPill")
        self.flow_label = label("", "Small")
        info.addLayout(hbox(self.model_pill, self.flow_label,
                            label(self.report_date.strftime("%a, %b %d").replace(" 0", " "), "Small"), None,
                            spacing=10))
        h_lay.addLayout(info, 1)
        self.draft_btn = button("📝 0/0", "ghost", self._toggle_draft, tooltip="Show or hide the live draft")
        self.restart_btn = button("Start over", "ghost", self.clear_chat)
        h_lay.addWidget(self.draft_btn)
        h_lay.addWidget(self.restart_btn)
        root.addWidget(header)

        # Progress
        prog = QWidget()
        p_lay = QVBoxLayout(prog)
        p_lay.setContentsMargins(18, 12, 18, 10)
        p_lay.setSpacing(10)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        p_lay.addWidget(self.progress)
        self.steps_holder = QWidget()
        self.steps_flow = FlowLayout(self.steps_holder, spacing=6)
        p_lay.addWidget(self.steps_holder)
        root.addWidget(prog)

        # Body: messages + live draft
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        self.msg_column = QVBoxLayout(content)
        self.msg_column.setContentsMargins(18, 14, 18, 18)
        self.msg_column.setSpacing(12)
        self.msg_layout = QVBoxLayout()
        self.msg_layout.setSpacing(12)
        self.msg_column.addLayout(self.msg_layout)
        self.thinking = ThinkingRow()
        self.thinking.hide()
        self.msg_column.addWidget(self.thinking)
        self.preview_slot = QVBoxLayout()
        self.msg_column.addLayout(self.preview_slot)
        self.msg_column.addStretch(1)
        self.scroll.setWidget(content)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._scroll_to_bottom)
        body.addWidget(self.scroll, 1)

        self.draft_panel = QFrame()
        self.draft_panel.setObjectName("DraftPanel")
        self.draft_panel.setFixedWidth(270)
        d_lay = QVBoxLayout(self.draft_panel)
        d_lay.setContentsMargins(14, 14, 14, 14)
        d_lay.setSpacing(8)
        d_lay.addLayout(hbox(label("LIVE DRAFT", "Overline"), None,
                             button("✕", "ghost", self._toggle_draft, tooltip="Hide draft")))
        self.draft_items_layout = QVBoxLayout()
        self.draft_items_layout.setSpacing(8)
        d_lay.addLayout(self.draft_items_layout)
        d_lay.addStretch(1)
        draft_scroll = QScrollArea()
        draft_scroll.setWidgetResizable(True)
        draft_scroll.setFrameShape(QFrame.NoFrame)
        draft_scroll.setWidget(self.draft_panel)
        draft_scroll.setFixedWidth(272)
        draft_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.draft_scroll = draft_scroll
        body.addWidget(draft_scroll)
        body_host = QWidget()
        body_host.setLayout(body)
        root.addWidget(body_host, 1)

        # Suggestions
        self.suggest_holder = QWidget()
        s_lay = QVBoxLayout(self.suggest_holder)
        s_lay.setContentsMargins(18, 0, 18, 8)
        self.suggest_inner = QWidget()
        self.suggest_flow = FlowLayout(self.suggest_inner, spacing=8)
        s_lay.addWidget(self.suggest_inner)
        root.addWidget(self.suggest_holder)

        # Input bar
        bar = QFrame()
        bar.setObjectName("ChatInputBar")
        b_lay = QHBoxLayout(bar)
        b_lay.setContentsMargins(14, 12, 14, 12)
        b_lay.setSpacing(8)
        self.input = QLineEdit()
        self.input.setMinimumHeight(40)
        self.input.returnPressed.connect(lambda: self.send())
        self.input.textChanged.connect(lambda _t: self._refresh_controls())
        self.skip_btn = button("Skip", "secondary", self.skip, tooltip="Skip this question")
        self.send_btn = button("Send", "primary", lambda: self.send())
        self.send_btn.setMinimumWidth(84)
        for w in (self.skip_btn, self.send_btn):
            w.setMinimumHeight(40)
        b_lay.addWidget(self.input, 1)
        b_lay.addWidget(self.skip_btn)
        b_lay.addWidget(self.send_btn)
        root.addWidget(bar)

        # Error view (replaces the body when the first turn can't start)
        self.error_view = QWidget()
        e_lay = QVBoxLayout(self.error_view)
        e_lay.setContentsMargins(24, 40, 24, 40)
        e_lay.addStretch(1)
        warn = label("⚠️")
        warn.setStyleSheet("font-size: 40px;")
        e_lay.addWidget(warn, 0, Qt.AlignHCenter)
        e_lay.addWidget(label("Couldn't start Echo", "H3"), 0, Qt.AlignHCenter)
        self.error_text = label("", "Muted", wrap=True)
        self.error_text.setAlignment(Qt.AlignCenter)
        self.error_text.setMaximumWidth(460)
        e_lay.addWidget(self.error_text, 0, Qt.AlignHCenter)
        e_lay.addWidget(button("Retry", "secondary", self.start), 0, Qt.AlignHCenter)
        e_lay.addStretch(1)
        self.error_view.hide()
        root.insertWidget(2, self.error_view, 1)
        self._body_widgets = [prog, body_host, self.suggest_holder, bar]

    # ------------------------------------------------------------------ state
    @property
    def fields(self):
        return fields_for_role(self.role)

    def _persist(self):
        if self.phase in ("loading", "error"):
            return
        store.store_chat_state(self.state_path, {
            "messages": self.messages, "draft": self.draft, "currentField": self.current_field, "role": self.role,
            "done": self.done, "preview": self.preview, "suggestions": self.suggestions, "phase": self.phase,
        })

    def _restore(self, saved: dict):
        self.messages = saved.get("messages") or []
        self.draft = saved.get("draft") or {}
        self.current_field = saved.get("currentField")
        self.role = saved.get("role") or self.role
        self.done = bool(saved.get("done"))
        self.preview = saved.get("preview")
        self.suggestions = saved.get("suggestions") or []
        self.phase = "saved" if saved.get("phase") == "saved" else "chat"
        for msg in self.messages:
            self._add_bubble(msg, animate=False)
        self._refresh()

    def _set_model(self, status):
        self.model = status
        self._refresh_header()

    # ------------------------------------------------------------------ messages
    def _push(self, from_: str, content: str, **extra):
        msg = {"id": uuid.uuid4().hex, "from": from_, "content": content}
        msg.update({k: v for k, v in extra.items() if v})
        self.messages.append(msg)
        self._add_bubble(msg, animate=from_ == "bot")
        return msg

    def _add_bubble(self, msg, animate):
        bubble = Bubble(msg, on_retry=(lambda _=False, m=msg: self.retry(m)) if msg.get("retry") else None)
        self.msg_layout.addWidget(bubble)
        self.bubbles.append(bubble)
        if animate:
            bubble.typewrite()

    def _truncate(self, count: int):
        """Drops messages (and their bubbles) after the first `count`."""
        for bubble in self.bubbles[count:]:
            bubble.deleteLater()
        self.bubbles = self.bubbles[:count]
        self.messages = self.messages[:count]

    def _scroll_to_bottom(self, *_):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ------------------------------------------------------------------ rendering
    def _refresh(self):
        self._refresh_header()
        self._refresh_steps()
        self._refresh_draft()
        self._refresh_preview()
        self._refresh_suggestions()
        self._refresh_controls()
        self._persist()

    def _refresh_header(self):
        if self.model is None:
            text, state = ("checking…", "") if self.phase == "loading" else ("model unknown", "")
        elif self.model.get("online"):
            text, state = f"● {self.model['model']}", "on"
        else:
            text, state = "● model offline", "off"
        self.model_pill.setText(text)
        set_prop(self.model_pill, "state", state)
        self.model_pill.setToolTip(
            "" if state != "off" else "Echo still works: answers are stored as typed (lightly cleaned).")
        self.flow_label.setText("Leader flow" if self.role == "leader" else "Member flow")
        filled = sum(1 for f in self.fields if self.draft.get(f))
        self.draft_btn.setText(f"📝 {filled}/{len(self.fields)}")
        set_prop(self.bot_avatar, "pulsing", self.busy)

    def _status(self, f):
        if self.draft.get(f):
            return "filled"
        if f in (self.draft.get("_skipped") or []):
            return "skipped"
        return "current" if f == self.current_field and not self.done else "pending"

    def _refresh_steps(self):
        clear_layout(self.steps_flow)
        answered = 0
        for f in self.fields:
            status = self._status(f)
            answered += status in ("filled", "skipped")
            icon = "✓" if status == "filled" else "–" if status == "skipped" else FIELD_ICONS[f]
            b = QPushButton(f"{icon}  {FIELD_LABELS[f]}")
            b.setObjectName("Step")
            b.setProperty("status", status)
            b.setProperty("flash", f in self.flash)
            b.setCursor(Qt.PointingHandCursor)
            b.setEnabled(not self.busy and self.phase == "chat" and status != "pending")
            b.setToolTip(self.draft.get(f) or ("Skipped — click to answer" if status == "skipped" else QUESTIONS[f]))
            b.clicked.connect(lambda _=False, f=f: self.revisit(f))
            self.steps_flow.addWidget(b)
        self.progress.setValue(round(answered / len(self.fields) * 100))

    def _refresh_draft(self):
        clear_layout(self.draft_items_layout)
        for f in self.fields:
            item = QFrame()
            item.setObjectName("DraftItem")
            status = self._status(f)
            item.setProperty("state", status if status in ("filled", "current") else "")
            item.setProperty("flash", f in self.flash)
            lay = QVBoxLayout(item)
            lay.setContentsMargins(10, 8, 10, 9)
            lay.setSpacing(3)
            lay.addWidget(label(f"{FIELD_ICONS[f]}  {FIELD_LABELS[f]}", "FieldLabel"))
            if self.draft.get(f):
                value = label(self.draft[f], wrap=True, selectable=True)
                value.setTextFormat(Qt.PlainText)
            else:
                value = label("Skipped" if status == "skipped" else
                              "Answering now…" if status == "current" else "Waiting…", "Small")
            lay.addWidget(value)
            self.draft_items_layout.addWidget(item)

    def _refresh_preview(self):
        clear_layout(self.preview_slot)
        if self.done and self.preview:
            self.preview_slot.addWidget(PreviewCard(
                self.preview, saved=self.phase == "saved", busy=self.busy, flash=self.flash,
                on_edit=self.save_inline_edit, on_save=self.save_report, on_edit_after_save=self.edit_after_save,
            ))

    def _refresh_suggestions(self):
        clear_layout(self.suggest_flow)
        show = self.phase == "chat" and not self.busy and bool(self.suggestions)
        for s in self.suggestions if show else []:
            display = "Same project" if s["label"].startswith("Same project · ") else s["label"]
            self.suggest_flow.addWidget(
                button(s["label"], "chip", lambda _=False, s=s, d=display: self.send(s["value"], display=d)))
        self.suggest_holder.setVisible(show)

    def _refresh_controls(self):
        chatting = self.phase == "chat"
        self.input.setEnabled(chatting and not self.busy)
        if self.phase == "saved":
            placeholder = "Report saved for today."
        elif self.done:
            placeholder = 'Tell me what to change, e.g. "blockers: waiting on API keys"'
        elif self.current_field:
            placeholder = f"{FIELD_LABELS[self.current_field]} — type your answer…"
        else:
            placeholder = "Type your reply…"
        self.input.setPlaceholderText(placeholder)
        self.skip_btn.setVisible(chatting and not self.done)
        self.skip_btn.setEnabled(not self.busy)
        self.send_btn.setEnabled(chatting and not self.busy and bool(self.input.text().strip()))
        self.send_btn.setText("…" if self.busy else "Send")
        self.restart_btn.setEnabled(not self.busy)

    def _set_busy(self, busy: bool):
        self.busy = busy
        if busy and (self.phase != "loading" or not self.messages):
            self.thinking.start()
        else:
            self.thinking.stop()
        self._refresh_header()
        self._refresh_steps()
        self._refresh_suggestions()
        self._refresh_controls()
        if self.done and self.preview:
            self._refresh_preview()
        if not busy and self.phase == "chat":
            QTimer.singleShot(0, self.input.setFocus)

    def _set_flash(self, fields):
        self.flash = list(fields)
        if self.flash:
            self._flash_timer.start()

    def _clear_flash(self):
        self.flash = []
        self._refresh_steps()
        self._refresh_draft()
        if self.done and self.preview:
            self._refresh_preview()

    def _toggle_draft(self):
        self.draft_scroll.setVisible(not self.draft_scroll.isVisible())

    def _show_error(self, message: str):
        self.phase = "error"
        self.error_text.setText(f"{message}\n\nCheck that the database is reachable, then retry.")
        for w in self._body_widgets:
            w.hide()
        self.error_view.show()

    def _hide_error(self):
        self.error_view.hide()
        for w in self._body_widgets:
            w.show()

    # ------------------------------------------------------------------ conversation
    def _apply_response(self, data: dict, quiet: bool = False):
        was_done = self.done
        if data.get("role"):
            self.role = data["role"]
        self.draft = data.get("draft") or {}
        self.current_field = data.get("current_field")
        self.suggestions = data.get("suggestions") or []
        if isinstance(data.get("model_online"), bool) and self.model:
            self.model = {**self.model, "online": data["model_online"]}
        captured = data.get("captured") or []
        if captured:
            self._set_flash(c["field"] for c in captured)

        if data.get("done"):
            self.done = True
            self.preview = data.get("preview")
            if data["bot_message"] == READY_TO_SUMMARIZE:
                if not quiet:
                    if captured and was_done:
                        content = f"Updated {', '.join(c['label'] for c in captured)}. ✅ The preview below is refreshed."
                    else:
                        content = random.choice(READY_LINES)
                    self._push("bot", content, captured=[] if was_done else captured)
            else:
                self._push("bot", data["bot_message"], followUp=True)
        else:
            self.done = False
            self.preview = None
            self._push("bot", data["bot_message"], captured=captured, followUp=data.get("needs_follow_up"))
        self._refresh()

    def _call(self, on_done, on_error, message="", draft=None, current_field=None):
        run_async(chat_turn, self.user["id"], self.team["id"], message, current_field, draft,
                  on_done=on_done, on_error=on_error, owner=self)

    def start(self):
        self._hide_error()
        self.phase = "loading"
        self._set_busy(True)

        def done(data):
            self._truncate(0)
            first_name = (self.user.get("username") or "").split(" ")[0]
            self.phase = "chat"
            self._push("bot", greeting(first_name))
            self._set_busy(False)
            self._apply_response(data)

        def failed(exc):
            self._set_busy(False)
            self._show_error(error_message(exc))

        self._call(done, failed, draft={})

    def send(self, text: str | None = None, display: str | None = None):
        message = (text if text is not None else self.input.text()).strip()
        if not message or self.busy or self.phase != "chat":
            return
        self.input.clear()
        self._push("user", display or message, skipped=message.lower() == "skip")
        self._set_busy(True)
        self._persist()

        def done(data):
            self._set_busy(False)
            self._apply_response(data)

        def failed(exc):
            self._set_busy(False)
            self._push("bot", f"⚠️ {error_message(exc)}", error=True, retry=message)
            self._persist()

        self._call(done, failed, message=message, draft=self.draft,
                   current_field=None if self.done else self.current_field)

    def skip(self):
        self.send("skip", display="Skipped")

    def retry(self, error_msg: dict):
        """Drops the failed exchange (user message + error) and sends it again."""
        if self.busy:
            return
        idx = next((i for i, m in enumerate(self.messages) if m["id"] == error_msg["id"]), -1)
        if idx > 0:
            self._truncate(idx - 1)
        self.send(error_msg["retry"])

    def revisit(self, field: str):
        """Jumps back to any question from the progress steps."""
        if self.busy or self.phase != "chat":
            return
        self.current_field = field
        self.done = False
        self.preview = None
        self.suggestions = []
        if self.draft.get(field):
            content = (f"Sure, let's redo {FIELD_LABELS[field].lower()}. Right now it says: "
                       f"“{self.draft[field]}”\n\n{QUESTIONS[field]}")
        else:
            content = QUESTIONS[field]
        self._push("bot", content)
        self._refresh()
        self.input.setFocus()

    def save_inline_edit(self, field: str, value: str):
        value = value.strip()
        skipped = [f for f in (self.draft.get("_skipped") or []) if f != field or not value]
        if not value and field not in skipped:
            skipped.append(field)
        nxt = {**self.draft, field: value, "_skipped": skipped}
        self._set_busy(True)

        def done(data):
            self._set_busy(False)
            self._apply_response(data, quiet=True)
            self._set_flash([field])
            self._refresh()

        def failed(exc):
            self._set_busy(False)
            toast(error_message(exc), "error")

        self._call(done, failed, draft=nxt)

    def save_report(self):
        if not (self.preview and self.preview.get("structured")):
            return
        self._set_busy(True)

        def done(result):
            self._set_busy(False)
            toast("Today's report updated" if result["updated"] else "Report saved", "success")
            self.phase = "saved"
            self._push("bot", "Saved! 🙌 Your report is now with the team. Have a great rest of your day.")
            self._refresh()

        def failed(exc):
            self._set_busy(False)
            toast(error_message(exc), "error")

        run_async(reports.save_report, self.user["id"], self.team["id"], self.preview["structured"], self.report_date,
                  on_done=done, on_error=failed, owner=self)

    def clear_chat(self):
        answer = QMessageBox.question(
            self, "Start over?",
            "Clear today's conversation and start over? Your saved report stays unchanged until you click "
            "Save Report again.",
        )
        if answer != QMessageBox.Yes:
            return
        store.drop_chat_state(self.state_path)
        self._truncate(0)
        self.draft, self.current_field, self.done, self.preview, self.suggestions = {}, None, False, None, []
        run_async(reports.reset_today, self.user["id"], self.team["id"], self.report_date,
                  on_error=lambda _e: None, owner=self)
        self._refresh_preview()
        self.start()

    def edit_after_save(self):
        self.phase = "chat"
        self._push("bot", "No problem — edit the preview or tell me what to change, then save again.")
        self._refresh()
