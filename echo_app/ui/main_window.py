from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from echo_app import config, db
from echo_app.services import auth
from echo_app.ui import toast
from echo_app.ui.pages.auth_page import AuthPage
from echo_app.ui.pages.profile_page import ProfileSetupPage
from echo_app.ui.session import Session
from echo_app.ui.shell import ShellPage
from echo_app.ui.tasks import error_message, run_async
from echo_app.ui.widgets import button, label


class StartupPage(QWidget):
    """Shown while connecting to the database, or when that fails."""

    def __init__(self, on_retry, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        logo = label("📊")
        logo.setStyleSheet("font-size: 48px;")
        lay.addWidget(logo, 0, Qt.AlignHCenter)
        self.title = label("Connecting…", "H2")
        lay.addWidget(self.title, 0, Qt.AlignHCenter)
        self.detail = label("", "Muted", wrap=True)
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setMaximumWidth(560)
        lay.addWidget(self.detail, 0, Qt.AlignHCenter)
        self.retry_btn = button("Retry", "primary", on_retry)
        lay.addWidget(self.retry_btn, 0, Qt.AlignHCenter)
        lay.addStretch(1)
        self.connecting()

    def connecting(self):
        self.title.setText("Connecting to the team database…")
        self.detail.setText("")
        self.retry_btn.hide()

    def failed(self, message: str):
        self.title.setText("Can't start Echo")
        self.detail.setText(f"{message}\n\nDatabase: {_redact(config.DATABASE_URL)}\n"
                            "Start it with `docker compose up -d db`, or set DATABASE_URL in .env.")
        self.retry_btn.show()


def _redact(url: str) -> str:
    """Hides the password in a connection URL."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.rsplit("@", 1)
        return f"{scheme}://{creds.split(':', 1)[0]}:***@{host}"
    return url


def _startup(remembered_user_id):
    db.run_migrations()
    return auth.get_user(remembered_user_id) if remembered_user_id else None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Echo · Team Report")
        self.setWindowIcon(QIcon(str(config.ASSETS_DIR / "icon.svg")))
        self.resize(1280, 840)
        self.setMinimumSize(980, 660)
        self.session = Session()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.startup = StartupPage(self.boot)
        self.auth = AuthPage(self.on_signed_in)
        self.profile = ProfileSetupPage(self.session, on_saved=self.after_profile, on_cancel=self.show_shell)
        self.shell = ShellPage(self.session, on_edit_profile=self.show_profile, on_sign_out=self.sign_out)
        for page in (self.startup, self.auth, self.profile, self.shell):
            self.stack.addWidget(page)
        toast.install(self)
        QTimer.singleShot(0, self.boot)

    def boot(self):
        self.startup.connecting()
        self.stack.setCurrentWidget(self.startup)

        def done(user):
            if user:
                self.on_signed_in(user)
            else:
                self.session.sign_out()
                self.show_auth()

        run_async(_startup, self.session.remembered_user_id(), on_done=done,
                  on_error=lambda e: self.startup.failed(error_message(e)))

    # ----- routing -----
    def show_auth(self):
        self.auth.reset()
        self.stack.setCurrentWidget(self.auth)

    def show_profile(self):
        self.profile.load()
        self.stack.setCurrentWidget(self.profile)

    def show_shell(self):
        self.stack.setCurrentWidget(self.shell)
        self.shell.show_teams()

    def on_signed_in(self, user: dict):
        self.session.sign_in(user)
        if user.get("profile_completed"):
            self.show_shell()
        else:
            self.show_profile()

    def after_profile(self):
        self.show_shell()

    def sign_out(self):
        self.session.sign_out()
        self.show_auth()

    def closeEvent(self, event):
        db.close()
        super().closeEvent(event)
