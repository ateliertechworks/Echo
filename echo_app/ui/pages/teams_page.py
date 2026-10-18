from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget,
)

from echo_app.services import teams
from echo_app.ui.tasks import error_message, run_async
from echo_app.ui.toast import toast
from echo_app.ui.widgets import Card, badge, button, clear_layout, field, label, scroll_page

CARD_MIN_WIDTH = 280


class TeamCard(Card):
    def __init__(self, team: dict, parent=None):
        super().__init__(clickable=True, parent=parent)
        self.setMinimumHeight(180)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 18)
        lay.setSpacing(10)

        head = QHBoxLayout()
        avatar = QFrame()
        avatar.setObjectName("TeamAvatar")
        avatar.setFixedSize(46, 46)
        initials = "".join(w[0].upper() for w in (team["team_name"] or "?").split()[:2] if w)
        a_lay = QVBoxLayout(avatar)
        a_lay.setContentsMargins(0, 0, 0, 0)
        a_lay.addWidget(label(initials or "?"), 0, Qt.AlignCenter)
        head.addWidget(avatar)
        head.addStretch(1)
        head.addWidget(badge(team["role"]), 0, Qt.AlignTop)
        lay.addLayout(head)

        lay.addWidget(label(team["team_name"], "H3", wrap=True))
        if team.get("description"):
            desc = label(team["description"], "Muted", wrap=True)
            desc.setMaximumHeight(42)
            lay.addWidget(desc)
        lay.addStretch(1)

        meta = QHBoxLayout()
        meta.setSpacing(28)
        for caption, value in (("CODE", team["team_code"]), ("MEMBERS", str(team.get("member_count") or "—"))):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(label(caption, "Overline"))
            col.addWidget(label(value, "H3"))
            meta.addLayout(col)
        meta.addStretch(1)
        lay.addLayout(meta)


class FormDialog(QDialog):
    def __init__(self, title: str, submit_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(24, 22, 24, 20)
        self.lay.setSpacing(14)
        self.lay.addWidget(label(title, "H3"))
        self.body = QVBoxLayout()
        self.body.setSpacing(12)
        self.lay.addLayout(self.body)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(button("Cancel", "ghost", self.reject))
        self.submit_btn = button(submit_text, "primary")
        self.submit_btn.setDefault(True)
        actions.addWidget(self.submit_btn)
        self.lay.addLayout(actions)


class TeamsPage(QWidget):
    def __init__(self, session, on_open_team, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.session = session
        self.on_open_team = on_open_team
        self.teams: list[dict] | None = None
        self._columns = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        outer.addWidget(scroll_page(body))
        lay = QVBoxLayout(body)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(20)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Your Teams", "H1"))
        titles.addWidget(label("Create a new team or join one with a code.", "Muted"))
        header.addLayout(titles)
        header.addStretch(1)
        header.addWidget(button("Join team", "secondary", self.open_join))
        header.addWidget(button("+ Create team", "primary", self.open_create))
        lay.addLayout(header)

        self.content = QVBoxLayout()
        lay.addLayout(self.content)
        lay.addStretch(1)

    def reload(self):
        self.teams = None
        self._render()
        run_async(teams.list_my_teams, self.session.user_id, on_done=self._loaded, owner=self)

    def _loaded(self, rows):
        self.teams = rows
        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.teams and self._columns != self._column_count():
            self._render()

    def _column_count(self):
        return max(1, (self.width() - 56) // CARD_MIN_WIDTH)

    def _render(self):
        clear_layout(self.content)
        if self.teams is None:
            self.content.addWidget(label("Loading teams…", "Muted"))
            return
        if not self.teams:
            empty = Card()
            e_lay = QVBoxLayout(empty)
            e_lay.setContentsMargins(32, 40, 32, 40)
            e_lay.setSpacing(8)
            rocket = label("🚀")
            rocket.setStyleSheet("font-size: 44px;")
            for w in (rocket, label("No teams yet", "H3"),
                      label("Kick things off by creating a team or joining an existing one.", "Muted")):
                e_lay.addWidget(w, 0, Qt.AlignHCenter)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(button("+ Create team", "primary", self.open_create))
            row.addWidget(button("Join team", "secondary", self.open_join))
            row.addStretch(1)
            e_lay.addSpacing(8)
            e_lay.addLayout(row)
            self.content.addWidget(empty)
            return
        self._columns = self._column_count()
        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(18)
        for i, team in enumerate(self.teams):
            card = TeamCard(team)
            card.clicked.connect(lambda t=team: self.on_open_team(t["id"]))
            grid.addWidget(card, i // self._columns, i % self._columns)
        for c in range(self._columns):
            grid.setColumnStretch(c, 1)
        self.content.addWidget(grid_host)

    # ----- dialogs -----
    def open_create(self):
        dlg = FormDialog("Create a new team", "Create", self)
        name = QLineEdit(placeholderText="e.g. Data Insights")
        desc = QPlainTextEdit(placeholderText="What does this team focus on?")
        desc.setFixedHeight(90)
        dlg.body.addWidget(field("Team name", name))
        dlg.body.addWidget(field("Description (optional)", desc))
        dlg.body.addWidget(label("You'll be added as the Team Leader. A shareable team code will be generated "
                                 "automatically.", "Small", wrap=True))

        def submit():
            dlg.submit_btn.setEnabled(False)

            def done(_team):
                toast("Team created", "success")
                dlg.accept()
                self.reload()

            def failed(exc):
                dlg.submit_btn.setEnabled(True)
                toast(error_message(exc), "error")

            run_async(teams.create_team, self.session.user_id, name.text(), desc.toPlainText(),
                      on_done=done, on_error=failed, owner=dlg)

        dlg.submit_btn.clicked.connect(submit)
        dlg.exec()

    def open_join(self):
        dlg = FormDialog("Join a team", "Join", self)
        code = QLineEdit(placeholderText="e.g. K7P3XM2N")
        code.setStyleSheet("letter-spacing: 3px; font-weight: 600;")
        code.textEdited.connect(lambda t: code.setText(t.upper()))
        dlg.body.addWidget(field("Team code", code))
        dlg.body.addWidget(label("Ask your team leader for the code. You'll join as a Member.", "Small", wrap=True))

        def submit():
            dlg.submit_btn.setEnabled(False)

            def done(_team):
                toast("Joined team", "success")
                dlg.accept()
                self.reload()

            def failed(exc):
                dlg.submit_btn.setEnabled(True)
                toast(error_message(exc), "error")

            run_async(teams.join_team, self.session.user_id, code.text(), on_done=done, on_error=failed, owner=dlg)

        dlg.submit_btn.clicked.connect(submit)
        dlg.exec()
