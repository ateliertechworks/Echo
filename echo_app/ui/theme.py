"""Brand palette and the app-wide Qt stylesheet (ported from the web theme)."""

from PySide6.QtGui import QColor, QPalette

PRIMARY = "#360568"
SECONDARY = "#5B2A86"
TERTIARY = "#7785AC"
ACCENT = "#9AC6C5"
ACCENT_LIGHT = "#A5E6BA"
BG = "#F7F8FA"
SURFACE = "#FFFFFF"
TEXT = "#1F2233"
TEXT_2 = "#5C6270"
BORDER = "#E4E6EE"
DANGER = "#C62828"
PRIMARY_SOFT = "#F1EAF8"


def light_palette() -> QPalette:
    """A fixed light palette so a dark desktop theme doesn't bleed into the app."""
    p = QPalette()
    for role, color in {
        QPalette.Window: BG, QPalette.WindowText: TEXT, QPalette.Base: SURFACE, QPalette.AlternateBase: BG,
        QPalette.Text: TEXT, QPalette.Button: SURFACE, QPalette.ButtonText: TEXT, QPalette.Highlight: SECONDARY,
        QPalette.HighlightedText: "#FFFFFF", QPalette.ToolTipBase: TEXT, QPalette.ToolTipText: "#FFFFFF",
        QPalette.PlaceholderText: "#9AA0AE", QPalette.Link: SECONDARY,
    }.items():
        p.setColor(role, QColor(color))
    return p


STYLESHEET = f"""
* {{
  font-family: "Inter", "Segoe UI", "Ubuntu", "Noto Sans", "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  color: {TEXT};
}}
QMainWindow, QWidget#Page, QScrollArea#PageScroll, QWidget#PageBody {{ background: {BG}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #CDD1DC; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {TERTIARY}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #CDD1DC; border-radius: 3px; min-width: 32px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {TEXT}; color: white; border: none; padding: 6px 8px; border-radius: 6px; }}

/* ---------- Cards ---------- */
QFrame#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#Card:hover[clickable="true"] {{ border-color: {TERTIARY}; }}

/* ---------- Typography ---------- */
QLabel#H1 {{ font-size: 24px; font-weight: 700; }}
QLabel#H2 {{ font-size: 20px; font-weight: 700; }}
QLabel#H3 {{ font-size: 16px; font-weight: 700; }}
QLabel#Muted {{ color: {TEXT_2}; }}
QLabel#Small {{ color: {TEXT_2}; font-size: 12px; }}
QLabel#Overline {{ color: {TEXT_2}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#FieldLabel {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}

/* ---------- Buttons ---------- */
QPushButton {{
  border-radius: 10px; padding: 9px 16px; font-weight: 600; border: 1px solid transparent;
}}
QPushButton:disabled {{ color: #A3A8B5; }}
QPushButton[variant="primary"] {{ background: {PRIMARY}; color: white; }}
QPushButton[variant="primary"]:hover {{ background: {SECONDARY}; }}
QPushButton[variant="primary"]:disabled {{ background: #B7A8C9; color: #F3EEF8; }}
QPushButton[variant="secondary"] {{ background: {SURFACE}; color: {PRIMARY}; border: 1px solid {BORDER}; }}
QPushButton[variant="secondary"]:hover {{ border-color: {TERTIARY}; background: {PRIMARY_SOFT}; }}
QPushButton[variant="ghost"] {{ background: transparent; color: {TEXT_2}; padding: 7px 12px; }}
QPushButton[variant="ghost"]:hover {{ background: #EEF0F5; color: {TEXT}; }}
QPushButton[variant="danger"] {{ background: {DANGER}; color: white; }}
QPushButton[variant="danger"]:hover {{ background: #A61F1F; }}
QPushButton[variant="danger-ghost"] {{ background: transparent; color: {DANGER}; padding: 7px 12px; }}
QPushButton[variant="danger-ghost"]:hover {{ background: #FDECEC; }}
QPushButton[variant="link"] {{ background: transparent; color: {SECONDARY}; padding: 0; border: none; }}
QPushButton[variant="link"]:hover {{ text-decoration: underline; }}
QPushButton[variant="chip"] {{
  background: {PRIMARY_SOFT}; color: {PRIMARY}; border: 1px solid #E0D3EE; border-radius: 12px;
  padding: 5px 13px; font-weight: 600;
}}
QPushButton[variant="chip"]:hover {{ background: #E6D9F3; }}

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox {{
  background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 9px 12px;
  selection-background-color: {SECONDARY}; selection-color: white;
}}
QLineEdit, QComboBox, QDateEdit {{ min-height: 22px; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
  border: 1px solid {SECONDARY};
}}
QLineEdit:disabled, QPlainTextEdit:disabled {{ background: #F1F2F6; color: #8A8F9C; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
  background: {SURFACE}; border: 1px solid {BORDER}; selection-background-color: {PRIMARY_SOFT};
  selection-color: {PRIMARY}; outline: none; padding: 4px;
}}

/* ---------- Badges & chips ---------- */
QLabel#Badge {{ border-radius: 9px; padding: 3px 10px; font-size: 12px; font-weight: 700; }}
QLabel#Badge[role="leader"] {{ background: {PRIMARY}; color: white; }}
QLabel#Badge[role="member"] {{ background: #E3F4F3; color: #2C6B69; }}
QLabel#Chip {{
  background: {PRIMARY_SOFT}; color: {PRIMARY}; border-radius: 10px; padding: 4px 10px; font-size: 12px;
  font-weight: 600;
}}
QLabel#ChipGreen {{
  background: #E5F7EC; color: #1E6B3A; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: 700;
}}

/* ---------- Shell ---------- */
QFrame#Sidebar {{ background: {PRIMARY}; }}
QLabel#Brand {{ color: white; font-size: 17px; font-weight: 700; }}
QLabel#BrandLogo {{ background: rgba(255,255,255,0.14); border-radius: 10px; font-size: 18px; }}
QPushButton#NavItem {{
  color: rgba(255,255,255,0.78); background: transparent; text-align: left; padding: 11px 14px;
  border-radius: 10px; font-weight: 600;
}}
QPushButton#NavItem:hover {{ background: rgba(255,255,255,0.08); color: white; }}
QPushButton#NavItem:checked {{ background: rgba(255,255,255,0.16); color: white; }}
QPushButton#SidebarFooter {{
  color: rgba(255,255,255,0.85); background: rgba(255,255,255,0.08); text-align: left; padding: 11px 14px;
  border-radius: 10px; font-weight: 600;
}}
QPushButton#SidebarFooter:hover {{ background: rgba(255,255,255,0.16); color: white; }}
QFrame#Topbar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QLabel#TopbarTitle {{ font-size: 18px; font-weight: 700; }}
QPushButton#AvatarButton {{ background: transparent; border: none; padding: 0; border-radius: 20px; }}

/* ---------- Auth ---------- */
QFrame#AuthFormSide {{ background: {BG}; }}
QLabel#HeroBrand {{ color: {ACCENT_LIGHT}; font-size: 14px; font-weight: 700; letter-spacing: 2px; }}
QLabel#HeroTitle {{ color: white; font-size: 30px; font-weight: 700; }}

/* ---------- Chat ---------- */
QFrame#ChatPanel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 16px; }}
QFrame#ChatHeader {{ border-bottom: 1px solid {BORDER}; }}
QLabel#BotAvatar {{ background: {PRIMARY_SOFT}; border-radius: 20px; font-size: 20px; }}
QLabel#BotAvatar[pulsing="true"] {{ background: #E2D2F2; }}
QLabel#MsgAvatar {{ background: {PRIMARY_SOFT}; border-radius: 15px; font-size: 15px; }}
QLabel#EchoTitle {{ font-size: 16px; font-weight: 700; }}
QLabel#ModelPill {{ border-radius: 9px; padding: 2px 9px; font-size: 12px; font-weight: 600; background: #EEF0F5; color: {TEXT_2}; }}
QLabel#ModelPill[state="on"] {{ background: #E5F7EC; color: #1E6B3A; }}
QLabel#ModelPill[state="off"] {{ background: #FDECEC; color: {DANGER}; }}
QProgressBar {{ background: #EEF0F5; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {SECONDARY}, stop:1 {ACCENT}); }}
QPushButton#Step {{
  background: #F4F5F8; color: {TEXT_2}; border: 1px solid transparent; border-radius: 14px; padding: 5px 11px;
  font-size: 12px; font-weight: 600;
}}
QPushButton#Step[status="filled"] {{ background: #E5F7EC; color: #1E6B3A; }}
QPushButton#Step[status="skipped"] {{ background: #F1F2F6; color: #9AA0AE; }}
QPushButton#Step[status="current"] {{ background: {PRIMARY_SOFT}; color: {PRIMARY}; border: 1px solid {SECONDARY}; }}
QPushButton#Step[flash="true"] {{ background: {ACCENT_LIGHT}; color: #14502A; }}
QPushButton#Step:hover:enabled {{ border: 1px solid {TERTIARY}; }}
QFrame#BubbleBot {{ background: #F4F5F8; border-radius: 14px; border-top-left-radius: 4px; }}
QFrame#BubbleBot[followUp="true"] {{ background: #FFF8E6; border: 1px solid #F5E1A4; }}
QFrame#BubbleBot[error="true"] {{ background: #FDECEC; border: 1px solid #F3C4C4; }}
QFrame#BubbleUser {{ background: {PRIMARY}; border-radius: 14px; border-top-right-radius: 4px; }}
QFrame#BubbleUser[skipped="true"] {{ background: #E9EBF0; }}
QFrame#BubbleUser QLabel {{ color: white; }}
QFrame#BubbleUser[skipped="true"] QLabel {{ color: {TEXT_2}; font-style: italic; }}
QLabel#MsgTag {{ color: #8A6400; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#Thinking {{ color: {TEXT_2}; font-style: italic; }}
QFrame#DraftPanel {{ background: #FAFAFC; border-left: 1px solid {BORDER}; }}
QFrame#DraftItem {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#DraftItem[state="filled"] {{ border-color: #CDEBD8; }}
QFrame#DraftItem[state="current"] {{ border-color: {SECONDARY}; }}
QFrame#DraftItem[flash="true"] {{ background: #EFFBF3; border-color: {ACCENT_LIGHT}; }}
QFrame#ChatInputBar {{ border-top: 1px solid {BORDER}; }}
QFrame#PreviewCard {{ background: {SURFACE}; border: 1px solid #DCCFEA; border-radius: 14px; }}
QFrame#PreviewRow {{ border-bottom: 1px solid #F0F1F5; }}
QFrame#PreviewRow[flash="true"] {{ background: #EFFBF3; }}
QLabel#PreviewValue {{ padding: 6px 8px; border-radius: 8px; }}
QLabel#PreviewValue[editable="true"]:hover {{ background: {PRIMARY_SOFT}; }}
QFrame#Narrative {{ background: {BG}; border-radius: 10px; }}

/* ---------- Reports & roster ---------- */
QFrame#ReportBody {{ border-top: 1px solid {BORDER}; }}
QFrame#Hero {{
  border-radius: 16px;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {PRIMARY}, stop:1 {SECONDARY});
}}
QFrame#Hero QLabel {{ color: white; }}
QFrame#Hero QLabel#Overline {{ color: rgba(255,255,255,0.7); }}
QPushButton#CodeChip {{
  background: rgba(255,255,255,0.14); color: white; border-radius: 12px; padding: 5px 12px;
  font-family: "JetBrains Mono", "Ubuntu Mono", monospace; font-weight: 600;
}}
QPushButton#CodeChip:hover {{ background: rgba(255,255,255,0.24); }}
QFrame#TeamAvatar {{ border-radius: 12px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {SECONDARY}, stop:1 {TERTIARY}); }}
QFrame#TeamAvatar QLabel {{ color: white; font-weight: 700; font-size: 16px; }}

/* ---------- Toasts & popups ---------- */
QLabel#Toast {{ border-radius: 10px; padding: 12px 18px; color: white; font-weight: 600; background: {TEXT}; }}
QLabel#Toast[kind="success"] {{ background: #1E7A46; }}
QLabel#Toast[kind="error"] {{ background: {DANGER}; }}
QFrame#Popup {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QDialog {{ background: {SURFACE}; }}
QMessageBox {{ background: {SURFACE}; }}
"""
