from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget,
)

from echo_app.services import excel_export, reports, teams
from echo_app.ui.tasks import error_message, run_async
from echo_app.ui.toast import toast
from echo_app.ui.widgets import Card, ClickableLabel, button, chip, clear_layout, field, label, scroll_page

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
EMPTY_DATE = QDate(2000, 1, 1)


def _optional_date_edit() -> QDateEdit:
    """A date picker that can be left empty (shown blank at its minimum date)."""
    edit = QDateEdit(calendarPopup=True)
    edit.setDisplayFormat("yyyy-MM-dd")
    edit.setMinimumDate(EMPTY_DATE)
    edit.setSpecialValueText("Any")
    edit.setDate(EMPTY_DATE)
    return edit


def _date_value(edit: QDateEdit) -> date | None:
    return None if edit.date() == EMPTY_DATE else edit.date().toPython()


class ReportRow(Card):
    def __init__(self, r: dict, show_author: bool, parent=None):
        super().__init__(parent=parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QWidget()
        head.setCursor(Qt.PointingHandCursor)
        h_lay = QHBoxLayout(head)
        h_lay.setContentsMargins(18, 14, 18, 14)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label(r["report_date"].strftime("%a, %b %d, %Y").replace(" 0", " "), "Small"))
        titles.addWidget(label(r.get("project_name") or "Untitled project", "H3"))
        h_lay.addLayout(titles, 1)
        if show_author:
            h_lay.addWidget(chip(r["username"]))
        self.arrow = label("⌄", "H3")
        h_lay.addWidget(self.arrow)
        lay.addWidget(head)

        self.body = QFrame()
        self.body.setObjectName("ReportBody")
        b_lay = QGridLayout(self.body)
        b_lay.setContentsMargins(18, 12, 18, 16)
        b_lay.setHorizontalSpacing(18)
        b_lay.setVerticalSpacing(10)
        b_lay.setColumnStretch(1, 1)
        rows = [
            ("Leader work", r.get("leader_work")),
            ("Team progress", r.get("team_progress")),
            ("Work done", None if r.get("leader_work") else r.get("work_done")),
            ("Outcome", r.get("outcome")),
            ("Blockers", r.get("blockers")),
            ("Pending", r.get("pending_work")),
            ("Next plan", r.get("next_plan")),
        ]
        line = 0
        for caption, value in rows:
            if not value:
                continue
            cap = label(caption, "FieldLabel")
            cap.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            b_lay.addWidget(cap, line, 0)
            b_lay.addWidget(label(value, wrap=True, selectable=True), line, 1)
            line += 1
        if r.get("chatbot_summary"):
            toggle = ClickableLabel("▸ View narrative summary")
            toggle.setObjectName("Muted")
            toggle.setCursor(Qt.PointingHandCursor)
            narrative = label(r["chatbot_summary"], wrap=True, selectable=True)
            narrative.setStyleSheet("background: #F7F8FA; border-radius: 8px; padding: 12px;")
            narrative.hide()

            def flip():
                narrative.setVisible(not narrative.isVisible())
                toggle.setText(("▾" if narrative.isVisible() else "▸") + " View narrative summary")

            toggle.clicked.connect(flip)
            b_lay.addWidget(toggle, line, 0, 1, 2)
            b_lay.addWidget(narrative, line + 1, 0, 1, 2)
        self.body.hide()
        lay.addWidget(self.body)

        head.mouseReleaseEvent = lambda _e: self.toggle()

    def toggle(self):
        self.body.setVisible(not self.body.isVisible())
        self.arrow.setText("⌃" if self.body.isVisible() else "⌄")


class PastReportsPage(QWidget):
    def __init__(self, team: dict, session, parent=None):
        super().__init__(parent)
        self.team = team
        self.session = session
        self.is_leader = team["role"] == "leader"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        outer.addWidget(scroll_page(body))
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(18)

        # Filters
        card = Card()
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(20, 18, 20, 18)
        c_lay.setSpacing(14)
        self.filter_row = QHBoxLayout()
        self.filter_row.setSpacing(14)

        today = date.today()
        self.period = QComboBox()
        for text, value in (("Month", "month"), ("Year", "year"), ("Single Date", "single"), ("Custom Range", "range")):
            self.period.addItem(text, value)
        self.month = QComboBox()
        for i, m in enumerate(MONTHS, start=1):
            self.month.addItem(m, i)
        self.month.setCurrentIndex(today.month - 1)
        self.year = QComboBox()
        for y in range(today.year, today.year - 8, -1):
            self.year.addItem(str(y), y)
        self.single = QDateEdit(QDate.currentDate(), calendarPopup=True)
        self.single.setDisplayFormat("yyyy-MM-dd")
        self.from_date = _optional_date_edit()
        self.to_date = _optional_date_edit()
        self.member = QComboBox()
        self.member.addItem("All members", None)

        self.period_fields = {
            "month": field("Month", self.month),
            "year": field("Year", self.year),
            "single": field("Date", self.single),
            "from": field("From date", self.from_date),
            "to": field("To date", self.to_date),
        }
        self.filter_row.addWidget(field("Period", self.period), 1)
        for w in self.period_fields.values():
            self.filter_row.addWidget(w, 1)
        if self.is_leader:
            self.filter_row.addWidget(field("Member", self.member), 2)
        else:
            only = label("Only your reports", "Muted")
            only.setStyleSheet("background: #F7F8FA; border: 1px solid #E4E6EE; border-radius: 10px; padding: 9px 12px;")
            self.filter_row.addWidget(field("Member", only), 2)
        c_lay.addLayout(self.filter_row)
        self.period.currentIndexChanged.connect(self._sync_period)
        self._sync_period()

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.apply_btn = button("🔍  Apply filters", "secondary", self.apply_filters)
        self.export_btn = button("📤  Export Excel", "primary", self.export)
        actions.addWidget(self.apply_btn)
        actions.addWidget(self.export_btn)
        c_lay.addLayout(actions)
        lay.addWidget(card)

        # Results
        lay.addWidget(label("MATCHES", "Overline"))
        self.count_label = label("…", "H2")
        lay.addWidget(self.count_label)
        self.results = QVBoxLayout()
        self.results.setSpacing(10)
        lay.addLayout(self.results)
        lay.addStretch(1)

        if self.is_leader:
            run_async(teams.list_members, team["id"], session.user_id, on_done=self._set_members, owner=self)
        self.apply_filters()

    def refresh(self):
        self.apply_filters()

    def _set_members(self, members):
        for m in members:
            self.member.addItem(f"{m['username']} — {'Leader' if m['role'] == 'leader' else 'Member'}", m["id"])

    def _sync_period(self):
        period = self.period.currentData()
        visible = {"month": {"month", "year"}, "year": {"year"}, "single": {"single"}, "range": {"from", "to"}}[period]
        for key, w in self.period_fields.items():
            w.setVisible(key in visible)

    def filters(self) -> dict:
        period = self.period.currentData()
        f = {}
        if period == "month":
            f.update(month=self.month.currentData(), year=self.year.currentData())
        elif period == "year":
            f["year"] = self.year.currentData()
        elif period == "single":
            f["date"] = self.single.date().toPython()
        else:
            if _date_value(self.from_date):
                f["from"] = _date_value(self.from_date)
            if _date_value(self.to_date):
                f["to"] = _date_value(self.to_date)
        if self.is_leader and self.member.currentData():
            f["user_id"] = self.member.currentData()
        return f

    def apply_filters(self):
        self.apply_btn.setEnabled(False)
        self.count_label.setText("…")
        clear_layout(self.results)

        def done(rows):
            self.apply_btn.setEnabled(True)
            self._render(rows)

        def failed(exc):
            self.apply_btn.setEnabled(True)
            toast(error_message(exc), "error")
            self._render([])

        run_async(reports.list_reports, self.team["id"], self.session.user_id, self.filters(),
                  on_done=done, on_error=failed, owner=self)

    def _render(self, rows):
        clear_layout(self.results)
        self.count_label.setText(f"{len(rows)} report{'' if len(rows) == 1 else 's'}")
        if not rows:
            empty = Card()
            e_lay = QVBoxLayout(empty)
            e_lay.setContentsMargins(24, 32, 24, 32)
            icon = label("🗂️")
            icon.setStyleSheet("font-size: 36px;")
            for w in (icon, label("No reports found", "H3"),
                      label("Try adjusting the filters, or submit today's report to get started.", "Muted")):
                e_lay.addWidget(w, 0, Qt.AlignHCenter)
            self.results.addWidget(empty)
            return
        for r in rows:
            self.results.addWidget(ReportRow(r, show_author=self.is_leader))

    def export(self):
        docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or str(Path.home())
        default = str(Path(docs) / excel_export.default_filename(self.team["team_name"]))
        path, _ = QFileDialog.getSaveFileName(self, "Export Excel", default, "Excel workbook (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        self.export_btn.setEnabled(False)
        self.export_btn.setText("Exporting…")

        def finish():
            self.export_btn.setEnabled(True)
            self.export_btn.setText("📤  Export Excel")

        def done(saved_path):
            finish()
            toast(f"Excel saved to {saved_path.name}", "success")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(saved_path.parent)))

        def failed(exc):
            finish()
            toast(error_message(exc), "error")

        run_async(excel_export.export_excel, self.team["id"], self.session.user_id, self.filters(), path,
                  on_done=done, on_error=failed, owner=self)
