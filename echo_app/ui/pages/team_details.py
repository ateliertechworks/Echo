import html

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from echo_app.services import teams
from echo_app.ui.tasks import error_message, run_async
from echo_app.ui.toast import toast
from echo_app.ui.widgets import Avatar, Card, FlowLayout, badge, button, chip, clear_layout, label, scroll_page

SOCIALS = [("linkedin_url", "LinkedIn"), ("github_url", "GitHub"), ("kaggle_url", "Kaggle"), ("medium_url", "Medium")]


def copy_team_code(team: dict, message: str = "Team code copied"):
    QGuiApplication.clipboard().setText(team["team_code"])
    toast(message, "success")


def social_links(person: dict) -> QWidget:
    holder = QWidget()
    flow = FlowLayout(holder, spacing=8)
    links = [(caption, person.get(key)) for key, caption in SOCIALS if person.get(key)]
    for caption, url in links:
        link = label(f'<a href="{html.escape(url, quote=True)}" style="color:#5B2A86;text-decoration:none;font-weight:600">{caption} ↗</a>')
        link.setOpenExternalLinks(True)
        link.setStyleSheet("border: 1px solid #E4E6EE; border-radius: 10px; padding: 6px 12px;")
        flow.addWidget(link)
    if not links:
        flow.addWidget(label("None added yet.", "Small"))
    return holder


def skills_flow(skills) -> QWidget:
    holder = QWidget()
    flow = FlowLayout(holder, spacing=6)
    for s in skills or []:
        flow.addWidget(chip(s))
    return holder


class ProfileDialog(QDialog):
    """A teammate's full profile."""

    def __init__(self, member: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(member["username"])
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 22)
        lay.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(16)
        head.addWidget(Avatar(member, 72))
        info = QVBoxLayout()
        info.setSpacing(4)
        name_row = QHBoxLayout()
        name_row.addWidget(label(member["username"], "H2"))
        name_row.addWidget(badge(member["role"]))
        name_row.addStretch(1)
        info.addLayout(name_row)
        if member.get("role_title"):
            info.addWidget(label(member["role_title"], "Muted"))
        info.addWidget(label(member["email"], "Small", selectable=True))
        head.addLayout(info, 1)
        lay.addLayout(head)

        if member.get("bio"):
            lay.addWidget(label(member["bio"], wrap=True, selectable=True))
        lay.addWidget(label("CONTACT & SOCIALS", "Overline"))
        lay.addWidget(social_links(member))
        if member.get("skills"):
            lay.addWidget(label("SKILLS", "Overline"))
            lay.addWidget(skills_flow(member["skills"]))
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(button("Close", "secondary", self.accept))
        lay.addLayout(close_row)


class TeamDetailsPage(QWidget):
    def __init__(self, team: dict, session, parent=None):
        super().__init__(parent)
        self.team = team
        self.session = session
        self.is_leader = team["role"] == "leader"
        self.members = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        outer.addWidget(scroll_page(body))
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        # Summary
        summary = Card()
        s_lay = QHBoxLayout(summary)
        s_lay.setContentsMargins(22, 18, 22, 18)
        s_lay.setSpacing(32)
        self.leader_value = label("—", "H3")
        self.count_value = label("—", "H3")
        code_row = QHBoxLayout()
        code_row.setSpacing(4)
        code = label(team["team_code"], "H3", selectable=True)
        code.setStyleSheet("font-family: 'JetBrains Mono', 'Ubuntu Mono', monospace; letter-spacing: 1px;")
        code_row.addWidget(code)
        code_row.addWidget(button("⧉", "ghost", lambda: copy_team_code(team), tooltip="Copy code"))
        for caption, value in (("TEAM NAME", label(team["team_name"], "H3")), ("TEAM CODE", code_row),
                               ("LEADER", self.leader_value), ("MEMBERS", self.count_value)):
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(label(caption, "Overline"))
            col.addLayout(value) if isinstance(value, QHBoxLayout) else col.addWidget(value)
            s_lay.addLayout(col)
        s_lay.addStretch(1)
        s_lay.addWidget(button("⧉  Invite — copy team code", "primary",
                               lambda: copy_team_code(team, "Team code copied — share it with new members")))
        lay.addWidget(summary)

        roster_head = QHBoxLayout()
        roster_head.addWidget(label("Team roster", "H3"))
        roster_head.addStretch(1)
        self.roster_hint = label("", "Small")
        roster_head.addWidget(self.roster_hint)
        lay.addLayout(roster_head)

        self.roster = QVBoxLayout()
        self.roster.setSpacing(10)
        lay.addLayout(self.roster)
        lay.addStretch(1)
        self.reload()

    def refresh(self):
        self.reload()

    def reload(self):
        run_async(teams.list_members, self.team["id"], self.session.user_id, on_done=self._render, owner=self)

    def _render(self, members):
        self.members = members
        leader = next((m for m in members if m["role"] == "leader"), None)
        self.leader_value.setText(leader["username"] if leader else "—")
        self.count_value.setText(str(len(members)))
        self.roster_hint.setText(f"{len(members)} {'person' if len(members) == 1 else 'people'} · "
                                 "click a row to view the full profile")
        clear_layout(self.roster)
        for m in members:
            self.roster.addWidget(self._member_row(m))

    def _member_row(self, m: dict) -> QFrame:
        row = Card(clickable=True)
        row.clicked.connect(lambda: ProfileDialog(m, self).exec())
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(14)
        lay.addWidget(Avatar(m, 44))
        main = QVBoxLayout()
        main.setSpacing(3)
        name = QHBoxLayout()
        name.setSpacing(10)
        name.addWidget(label(m["username"], "H3"))
        name.addWidget(badge(m["role"]))
        name.addStretch(1)
        main.addLayout(name)
        sub = " · ".join(p for p in (m.get("role_title"), m["email"]) if p)
        main.addWidget(label(sub, "Small"))
        lay.addLayout(main, 1)
        lay.addWidget(button("👁  View profile", "ghost", lambda: ProfileDialog(m, self).exec()))
        if self.is_leader and m["role"] != "leader":
            lay.addWidget(button("🗑  Remove", "danger-ghost", lambda: self.confirm_remove(m)))
        return row

    def confirm_remove(self, m: dict):
        box = QMessageBox(self)
        box.setWindowTitle("Remove member?")
        box.setIcon(QMessageBox.Warning)
        box.setText(f"Are you sure you want to remove <b>{html.escape(m['username'])}</b> from the team?")
        box.setInformativeText("Their existing reports will remain in the archive, but they will lose access to "
                               "this workspace.")
        remove = box.addButton("Remove", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is not remove:
            return

        def done(_):
            toast("Member removed", "success")
            self.reload()

        run_async(teams.remove_member, self.team["id"], self.session.user_id, m["id"],
                  on_done=done, on_error=lambda e: toast(error_message(e), "error"), owner=self)
