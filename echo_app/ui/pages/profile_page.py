import base64
import mimetypes
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QGridLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget,
)

from echo_app.services import profile
from echo_app.ui.tasks import run_async
from echo_app.ui.toast import toast
from echo_app.ui.widgets import Avatar, Card, FlowLayout, button, clear_layout, field, label, scroll_page

MAX_PHOTO_BYTES = 2 * 1024 * 1024
LINK_FIELDS = [
    ("role_title", "Role / Title", "e.g. Data Engineer"),
    ("linkedin_url", "LinkedIn URL", "https://linkedin.com/in/..."),
    ("github_url", "GitHub URL", "https://github.com/..."),
    ("kaggle_url", "Kaggle URL", "https://kaggle.com/..."),
    ("medium_url", "Medium URL", "https://medium.com/@..."),
]


class ProfileSetupPage(QWidget):
    """First-run profile setup, also used for "Edit profile"."""

    def __init__(self, session, on_saved, on_cancel, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.session = session
        self.on_saved = on_saved
        self.on_cancel = on_cancel
        self.photo = ""
        self.skills: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        outer.addWidget(scroll_page(body))
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 32, 24, 32)

        card = Card()
        card.setMaximumWidth(760)
        card.setMinimumWidth(640)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 30, 32, 30)
        lay.setSpacing(16)
        body_lay.addWidget(card, 0, Qt.AlignHCenter)
        body_lay.addStretch(1)

        lay.addWidget(label("Set up your profile", "H2"))
        lay.addWidget(label("Help teammates get to know you. You can update this anytime.", "Muted", wrap=True))

        # Photo
        photo_row = QHBoxLayout()
        photo_row.setSpacing(16)
        self.avatar = Avatar(None, 72)
        photo_row.addWidget(self.avatar)
        photo_col = QVBoxLayout()
        photo_btns = QHBoxLayout()
        photo_btns.addWidget(button("Upload photo", "secondary", self.pick_photo))
        self.remove_photo_btn = button("Remove", "ghost", self.remove_photo)
        photo_btns.addWidget(self.remove_photo_btn)
        photo_btns.addStretch(1)
        photo_col.addLayout(photo_btns)
        photo_col.addWidget(label("PNG or JPG, max 2MB", "Small"))
        photo_row.addLayout(photo_col, 1)
        lay.addLayout(photo_row)

        # Fields
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        self.inputs: dict[str, QLineEdit] = {
            "username": QLineEdit(),
            "email": QLineEdit(),
        }
        for key, _, placeholder in LINK_FIELDS:
            self.inputs[key] = QLineEdit(placeholderText=placeholder)
        self.inputs["username"].textChanged.connect(self._refresh_avatar)
        captions = [("username", "Username"), ("email", "Email")] + [(k, c) for k, c, _ in LINK_FIELDS]
        for i, (key, caption) in enumerate(captions):
            grid.addWidget(field(caption, self.inputs[key]), i // 2, i % 2)
        lay.addLayout(grid)

        self.bio = QPlainTextEdit(placeholderText="A sentence or two about your focus areas.")
        self.bio.setFixedHeight(90)
        lay.addWidget(field("Short bio (optional)", self.bio))

        # Skills
        skills_box = QWidget()
        skills_lay = QVBoxLayout(skills_box)
        skills_lay.setContentsMargins(0, 0, 0, 0)
        skills_lay.setSpacing(8)
        self.skills_holder = QWidget()
        self.skills_flow = FlowLayout(self.skills_holder, spacing=6)
        skills_lay.addWidget(self.skills_holder)
        self.skill_input = QLineEdit(placeholderText="Add a skill and press Enter")
        self.skill_input.returnPressed.connect(self.add_skill)
        add_row = QHBoxLayout()
        add_row.addWidget(self.skill_input, 1)
        add_row.addWidget(button("Add", "secondary", self.add_skill))
        skills_lay.addLayout(add_row)
        lay.addWidget(field("Skills", skills_box))

        actions = QHBoxLayout()
        self.cancel_btn = button("Cancel", "ghost", lambda: self.on_cancel())
        actions.addWidget(self.cancel_btn)
        actions.addStretch(1)
        self.save_btn = button("Save and continue", "primary", self.save)
        self.save_btn.setMinimumHeight(42)
        self.save_btn.setMinimumWidth(200)
        actions.addWidget(self.save_btn)
        lay.addLayout(actions)

    # ----- data -----
    def load(self):
        user = self.session.user or {}
        self.cancel_btn.setVisible(bool(user.get("profile_completed")))
        self.save_btn.setEnabled(False)
        self._fill({"username": user.get("username"), "email": user.get("email")})

        def done(data):
            self._fill(data)
            self.save_btn.setEnabled(True)

        def failed(_exc):
            self.save_btn.setEnabled(True)

        run_async(profile.get_profile, self.session.user_id, on_done=done, on_error=failed, owner=self)

    def _fill(self, data: dict):
        for key, edit in self.inputs.items():
            edit.setText(data.get(key) or "")
        self.bio.setPlainText(data.get("bio") or "")
        self.photo = data.get("profile_photo") or ""
        self.skills = list(data.get("skills") or [])
        self._render_skills()
        self._refresh_avatar()

    def _refresh_avatar(self):
        self.avatar.set_user({"username": self.inputs["username"].text(), "profile_photo": self.photo})
        self.remove_photo_btn.setVisible(bool(self.photo))

    # ----- photo -----
    def pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a photo", "", "Images (*.png *.jpg *.jpeg *.webp *.gif)")
        if not path:
            return
        data = Path(path).read_bytes()
        if len(data) > MAX_PHOTO_BYTES:
            toast("Photo must be under 2MB", "error")
            return
        mime = mimetypes.guess_type(path)[0] or "image/png"
        self.photo = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        self._refresh_avatar()

    def remove_photo(self):
        self.photo = ""
        self._refresh_avatar()

    # ----- skills -----
    def add_skill(self):
        value = self.skill_input.text().strip()
        if value and value not in self.skills:
            self.skills.append(value)
            self._render_skills()
        self.skill_input.clear()

    def remove_skill(self, skill):
        self.skills = [s for s in self.skills if s != skill]
        self._render_skills()

    def _render_skills(self):
        clear_layout(self.skills_flow)
        for s in self.skills:
            b = button(f"{s}  ×", "chip", lambda _=False, s=s: self.remove_skill(s), tooltip="Remove")
            self.skills_flow.addWidget(b)
        self.skills_holder.setVisible(bool(self.skills))

    # ----- save -----
    def save(self):
        data = {key: edit.text().strip() for key, edit in self.inputs.items()}
        if not data["username"] or not data["email"]:
            toast("Username and email are required", "error")
            return
        data.update(bio=self.bio.toPlainText().strip(), profile_photo=self.photo, skills=self.skills)
        self.save_btn.setEnabled(False)
        self.save_btn.setText("Saving…")

        def finish():
            self.save_btn.setEnabled(True)
            self.save_btn.setText("Save and continue")

        def done(row):
            finish()
            self.session.update({**row, "profile_completed": True})
            toast("Profile saved", "success")
            self.on_saved()

        def failed(exc):
            finish()
            from echo_app.ui.tasks import error_message

            toast(error_message(exc), "error")

        run_async(profile.update_profile, self.session.user_id, data, on_done=done, on_error=failed, owner=self)
