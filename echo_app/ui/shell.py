"""Signed-in layout: sidebar navigation, top bar with profile menu, and the content pages."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from echo_app.services import profile, teams
from echo_app.ui.pages.chat_panel import ChatPanel
from echo_app.ui.pages.past_reports import PastReportsPage
from echo_app.ui.pages.team_details import TeamDetailsPage, copy_team_code, skills_flow, social_links
from echo_app.ui.pages.teams_page import TeamsPage
from echo_app.ui.tasks import error_message, run_async
from echo_app.ui.widgets import Avatar, avatar_pixmap, badge, button, clear_layout, label


class ProfilePopup(QFrame):
    """Dropdown from the top-bar avatar: who you are, socials, edit profile, sign out."""

    def __init__(self, details: dict, on_edit, on_sign_out, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("Popup")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedWidth(340)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 16)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(Avatar(details, 56))
        info = QVBoxLayout()
        info.setSpacing(2)
        info.addWidget(label(details.get("username") or "", "H3"))
        info.addWidget(label(details.get("email") or "", "Small"))
        if details.get("role_title"):
            info.addWidget(label(details["role_title"], "Muted"))
        head.addLayout(info, 1)
        lay.addLayout(head)

        lay.addWidget(label("CONTACT & SOCIALS", "Overline"))
        lay.addWidget(social_links(details))
        if details.get("skills"):
            lay.addWidget(label("SKILLS", "Overline"))
            lay.addWidget(skills_flow(details["skills"]))

        actions = QHBoxLayout()
        actions.addWidget(button("Edit profile", "primary", lambda: (self.close(), on_edit())), 1)
        actions.addWidget(button("Sign out", "secondary", lambda: (self.close(), on_sign_out())))
        lay.addLayout(actions)


class WorkspacePage(QWidget):
    """One team: header card plus Today's Report / Past Reports / Team Details."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.team = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 24)
        lay.setSpacing(18)

        self.hero = QFrame()
        self.hero.setObjectName("Hero")
        h_lay = QHBoxLayout(self.hero)
        h_lay.setContentsMargins(24, 14, 24, 14)
        h_lay.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("TEAM", "Overline"))
        self.team_name = label("", "H2")
        titles.addWidget(self.team_name)
        h_lay.addLayout(titles)
        h_lay.addStretch(1)
        self.hero_meta = QHBoxLayout()
        self.hero_meta.setSpacing(10)
        h_lay.addLayout(self.hero_meta)
        lay.addWidget(self.hero)

        self.tabs = QStackedWidget()
        lay.addWidget(self.tabs, 1)
        self.message = label("", "Muted")
        self.message.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.message, 1)

    def load(self, team_id, on_loaded, on_failed):
        self.team = None
        self.team_name.setText("Loading…")
        clear_layout(self.hero_meta)
        self._clear_tabs()
        self.message.hide()
        self.tabs.show()

        def done(team):
            self.team = team
            self.team_name.setText(team["team_name"])
            self.hero_meta.addWidget(badge(team["role"], short=False))
            code = QPushButton(f"Code: {team['team_code']}  ⧉")
            code.setObjectName("CodeChip")
            code.setCursor(Qt.PointingHandCursor)
            code.setToolTip("Copy code")
            code.clicked.connect(lambda: copy_team_code(team))
            self.hero_meta.addWidget(code)
            user = self.session.user
            self.tabs.addWidget(ChatPanel(team, user))
            self.tabs.addWidget(PastReportsPage(team, self.session))
            self.tabs.addWidget(TeamDetailsPage(team, self.session))
            on_loaded(team)

        def failed(exc):
            self.team_name.setText("Team")
            self.tabs.hide()
            self.message.setText(f"Team not accessible.\n{error_message(exc)}")
            self.message.show()
            on_failed()

        run_async(teams.get_team, team_id, self.session.user_id, on_done=done, on_error=failed, owner=self)

    def _clear_tabs(self):
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeWidget(w)
            w.deleteLater()

    def show_tab(self, index: int):
        self.tabs.setCurrentIndex(index)
        page = self.tabs.widget(index)
        if hasattr(page, "refresh"):
            page.refresh()


class ShellPage(QWidget):
    def __init__(self, session, on_edit_profile, on_sign_out, parent=None):
        super().__init__(parent)
        self.session = session
        self.on_edit_profile = on_edit_profile
        self.on_sign_out = on_sign_out

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        s_lay = QVBoxLayout(sidebar)
        s_lay.setContentsMargins(14, 18, 14, 18)
        s_lay.setSpacing(6)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = label("📊", "BrandLogo")
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignCenter)
        brand.addWidget(logo)
        brand.addWidget(label("Team Report", "Brand"))
        brand.addStretch(1)
        s_lay.addLayout(brand)
        s_lay.addSpacing(18)
        self.nav_layout = QVBoxLayout()
        self.nav_layout.setSpacing(4)
        s_lay.addLayout(self.nav_layout)
        s_lay.addStretch(1)
        self.back_btn = QPushButton("←  Back to Team Space")
        self.back_btn.setObjectName("SidebarFooter")
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.show_teams)
        s_lay.addWidget(self.back_btn)
        root.addWidget(sidebar)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        # Main column
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        topbar = QFrame()
        topbar.setObjectName("Topbar")
        topbar.setFixedHeight(64)
        t_lay = QHBoxLayout(topbar)
        t_lay.setContentsMargins(28, 0, 20, 0)
        self.title = label("", "TopbarTitle")
        t_lay.addWidget(self.title)
        t_lay.addStretch(1)
        self.avatar_btn = QPushButton()
        self.avatar_btn.setObjectName("AvatarButton")
        self.avatar_btn.setCursor(Qt.PointingHandCursor)
        self.avatar_btn.setFixedSize(40, 40)
        self.avatar_btn.setToolTip("Profile")
        self.avatar_btn.clicked.connect(self.open_profile_menu)
        t_lay.addWidget(self.avatar_btn)
        main.addWidget(topbar)

        self.content = QStackedWidget()
        self.teams_page = TeamsPage(session, self.open_team)
        self.workspace = WorkspacePage(session)
        self.content.addWidget(self.teams_page)
        self.content.addWidget(self.workspace)
        main.addWidget(self.content, 1)
        root.addLayout(main, 1)

    def refresh_user(self):
        from PySide6.QtGui import QIcon

        self.avatar_btn.setIcon(QIcon(avatar_pixmap(self.session.user, 38)))
        self.avatar_btn.setIconSize(self.avatar_btn.size())

    def _set_nav(self, items):
        for b in self.nav_group.buttons():
            self.nav_group.removeButton(b)
        clear_layout(self.nav_layout)
        for i, (text, handler) in enumerate(items):
            b = QPushButton(text)
            b.setObjectName("NavItem")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(handler)
            self.nav_group.addButton(b, i)
            self.nav_layout.addWidget(b)
        if items:
            self.nav_group.button(0).setChecked(True)

    def show_teams(self):
        self.refresh_user()
        self._set_nav([("👥   Teams", self.show_teams)])
        self.back_btn.hide()
        self.title.setText("Your Teams")
        self.content.setCurrentWidget(self.teams_page)
        self.teams_page.reload()

    def open_team(self, team_id):
        self._set_nav([
            ("💬   Today's Report", lambda: self.workspace.show_tab(0)),
            ("🗂️   Past Reports", lambda: self.workspace.show_tab(1)),
            ("👥   Team Details", lambda: self.workspace.show_tab(2)),
        ])
        self.back_btn.show()
        self.title.setText("Team")
        self.content.setCurrentWidget(self.workspace)
        self.workspace.load(team_id, on_loaded=lambda t: self.title.setText(t["team_name"]), on_failed=lambda: None)

    def open_profile_menu(self):
        def show(details):
            popup = ProfilePopup(details, self.on_edit_profile, self.on_sign_out, self)
            popup.adjustSize()
            anchor = self.avatar_btn.mapToGlobal(QPoint(self.avatar_btn.width(), self.avatar_btn.height() + 8))
            popup.move(anchor.x() - popup.width(), anchor.y())
            popup.show()

        run_async(profile.get_profile, self.session.user_id, on_done=show,
                  on_error=lambda _e: show(self.session.user or {}), owner=self)
