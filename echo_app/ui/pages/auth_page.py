from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from echo_app import config
from echo_app.services import auth
from echo_app.ui.tasks import run_async
from echo_app.ui.toast import toast
from echo_app.ui.widgets import Card, SvgCover, button, field, label


class AuthPage(QWidget):
    """Split-screen sign in / sign up."""

    def __init__(self, on_authenticated, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.on_authenticated = on_authenticated
        self.mode = "signin"

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Hero
        hero = SvgCover(config.ASSETS_DIR / "team-photo.svg")
        hero.setMinimumWidth(380)
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(48, 48, 48, 56)
        hero_lay.addStretch(1)
        hero_lay.addWidget(label("TEAM REPORT", "HeroBrand"))
        title = label("AI-powered daily reporting for teams.", "HeroTitle", wrap=True)
        hero_lay.addWidget(title)
        root.addWidget(hero, 5)

        # Form
        side = QFrame()
        side.setObjectName("AuthFormSide")
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(40, 40, 40, 40)
        side_lay.addStretch(1)

        card = Card()
        card.setMaximumWidth(420)
        card.setMinimumWidth(340)
        form = QVBoxLayout(card)
        form.setContentsMargins(32, 32, 32, 28)
        form.setSpacing(14)
        self.title = label("", "H2")
        self.subtitle = label("", "Muted", wrap=True)
        form.addWidget(self.title)
        form.addWidget(self.subtitle)
        form.addSpacing(4)

        self.username = QLineEdit(placeholderText="Your name")
        self.email = QLineEdit(placeholderText="you@company.com")
        self.password = QLineEdit(placeholderText="••••••••", echoMode=QLineEdit.Password)
        self.username_field = field("Username", self.username)
        form.addWidget(self.username_field)
        form.addWidget(field("Email", self.email))
        form.addWidget(field("Password", self.password))
        for edit in (self.username, self.email, self.password):
            edit.returnPressed.connect(self.submit)

        self.submit_btn = button("", "primary", self.submit)
        self.submit_btn.setMinimumHeight(42)
        form.addSpacing(4)
        form.addWidget(self.submit_btn)

        toggle_row = QHBoxLayout()
        toggle_row.addStretch(1)
        self.toggle_text = label("", "Muted")
        self.toggle_btn = button("", "link", self.toggle_mode)
        toggle_row.addWidget(self.toggle_text)
        toggle_row.addWidget(self.toggle_btn)
        toggle_row.addStretch(1)
        form.addLayout(toggle_row)

        side_lay.addWidget(card, 0, Qt.AlignHCenter)
        side_lay.addStretch(1)
        root.addWidget(side, 4)

        self._apply_mode()

    def reset(self):
        self.password.clear()
        self.mode = "signin"
        self._apply_mode()

    def toggle_mode(self):
        self.mode = "signup" if self.mode == "signin" else "signin"
        self._apply_mode()

    def _apply_mode(self):
        signup = self.mode == "signup"
        self.title.setText("Create your account" if signup else "Sign in")
        self.subtitle.setText("Get started in under a minute." if signup else "Welcome back — pick up where you left off.")
        self.username_field.setVisible(signup)
        self.submit_btn.setText("Create account" if signup else "Sign in")
        self.toggle_text.setText("Already have an account?" if signup else "Don't have an account?")
        self.toggle_btn.setText("Sign in" if signup else "Sign up")
        (self.username if signup else self.email).setFocus()

    def _set_busy(self, busy):
        self.submit_btn.setEnabled(not busy)
        self.submit_btn.setText("Please wait…" if busy else ("Create account" if self.mode == "signup" else "Sign in"))

    def submit(self):
        if not self.submit_btn.isEnabled():
            return
        email, password = self.email.text().strip(), self.password.text()
        if self.mode == "signup":
            fn, args = auth.signup, (self.username.text().strip(), email, password)
        else:
            fn, args = auth.signin, (email, password)
        self._set_busy(True)

        def done(user):
            self._set_busy(False)
            toast(f"Welcome, {user['username'] or user['email']}", "success")
            self.password.clear()
            self.on_authenticated(user)

        def failed(exc):
            self._set_busy(False)
            from echo_app.ui.tasks import error_message

            toast(error_message(exc), "error")

        run_async(fn, *args, on_done=done, on_error=failed, owner=self)
