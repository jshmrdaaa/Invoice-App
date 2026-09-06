import base64
import html
import json
import mimetypes
import os
import re
import shutil
import ssl
import subprocess
import sys
import traceback
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

import certifi
import pdfkit
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
LOGO_FILENAME = "logo_grayblue_transparent.png"
LOGO_PATH = os.path.join(BASE_DIR, LOGO_FILENAME)
WRITABLE_LOGO_PATH = os.path.join(APP_DIR, LOGO_FILENAME)
INVOICE_COUNTER_FILE = os.path.join(APP_DIR, "invoice_counter.txt")
ESTIMATE_COUNTER_FILE = os.path.join(APP_DIR, "estimate_counter.txt")
PAST_INVOICE_COUNTER_FILE = os.path.join(APP_DIR, "past_invoice_counter.txt")
DRAFTS_FILE = os.path.join(APP_DIR, "drafts.json")
CUSTOMERS_FILE = os.path.join(APP_DIR, "customers.json")
INVOICE_HISTORY_FILE = os.path.join(APP_DIR, "invoice_history.json")
ESTIMATE_HISTORY_FILE = os.path.join(APP_DIR, "estimate_history.json")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
BACKUP_DIR = os.path.join(APP_DIR, "backups")
UPDATE_LOG_FILE = os.path.join(APP_DIR, "update_log.txt")

# ============================================================
# AUTO-UPDATE
# ============================================================
# Bump this number every time you build and release a new version.
CURRENT_VERSION = "1.0.14"

# Replace YOUR-GITHUB-USERNAME / YOUR-REPO-NAME with your own once you've
# created the GitHub repo (see the auto-update setup instructions).
UPDATE_FEED_URL = "https://api.github.com/repos/jshmrdaaa/Invoice-App/releases/latest"
PREVIEW_DIR = os.path.join(APP_DIR, "previews")
BRAND_BLUE = "#4b7391"
DEFAULT_SETTINGS = {
    "company_name": "Adael Construction LLC",
    "owner_name": "Angel Chabla",
    "phone": "(203)-942-6042",
    "email": "acchabla@yahoo.com",
    "address": "",
    "default_notes": "Thank you for your business!",
}
COMMON_TEXT_FIXES = {
    "teh": "the",
    "recieve": "receive",
    "recieved": "received",
    "adress": "address",
    "quanity": "quantity",
    "quanitity": "quantity",
    "materail": "material",
    "materails": "materials",
    "matrial": "material",
    "installtion": "installation",
    "reapir": "repair",
    "reapirs": "repairs",
    "paintng": "painting",
    "costumer": "customer",
    "costumers": "customers",
    "estiamte": "estimate",
    "invocie": "invoice",
    "remvoe": "remove",
    "removeing": "removing",
    "w/": "with",
}


def read_json(path, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, ValueError):
        return fallback


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as file:
        json.dump(data, file, indent=4)


def backup_file_list():
    return [
        DRAFTS_FILE,
        CUSTOMERS_FILE,
        INVOICE_HISTORY_FILE,
        ESTIMATE_HISTORY_FILE,
        SETTINGS_FILE,
        INVOICE_COUNTER_FILE,
        ESTIMATE_COUNTER_FILE,
        PAST_INVOICE_COUNTER_FILE,
        WRITABLE_LOGO_PATH,
    ]


def write_backup_zip(backup_path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as backup:
        for path in backup_file_list():
            if os.path.exists(path):
                backup.write(path, os.path.basename(path))
        for folder in ["invoices", "estimates"]:
            folder_path = os.path.join(APP_DIR, folder)
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    full_path = os.path.join(folder_path, filename)
                    if os.path.isfile(full_path):
                        backup.write(full_path, os.path.join(folder, filename))


def prune_old_auto_backups(keep=30):
    if not os.path.exists(BACKUP_DIR):
        return
    autos = sorted(
        filename for filename in os.listdir(BACKUP_DIR)
        if filename.startswith("adael_autobackup_") and filename.endswith(".zip")
    )
    for filename in autos[:-keep]:
        try:
            os.remove(os.path.join(BACKUP_DIR, filename))
        except OSError:
            pass


def auto_backup_if_needed():
    """Silently makes one dated backup per day the app is opened, and prunes
    old ones so the backups folder doesn't grow forever. Never raises - a
    backup problem should never stop the app from opening normally."""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        today_stamp = datetime.today().strftime("%Y%m%d")
        backup_path = os.path.join(BACKUP_DIR, f"adael_autobackup_{today_stamp}.zip")
        if os.path.exists(backup_path):
            return
        write_backup_zip(backup_path)
        prune_old_auto_backups()
    except Exception:
        pass


def get_settings():
    settings = DEFAULT_SETTINGS.copy()
    settings.update(read_json(SETTINGS_FILE, {}))
    return settings


def read_counter(path, start):
    if not os.path.exists(path):
        with open(path, "w") as file:
            file.write(str(start))
    with open(path, "r") as file:
        value = file.read().strip()
    if not value.isdigit():
        with open(path, "w") as file:
            file.write(str(start))
        return str(start)
    return value


def increase_counter(path, start):
    try:
        current = int(read_counter(path, start))
    except ValueError:
        current = start
    with open(path, "w") as file:
        file.write(str(current + 1))


def get_next_number(document_type):
    if document_type == "estimate":
        return read_counter(ESTIMATE_COUNTER_FILE, 2002)
    return read_counter(INVOICE_COUNTER_FILE, 1001)


def increase_number(document_type):
    if document_type == "estimate":
        increase_counter(ESTIMATE_COUNTER_FILE, 2002)
    else:
        increase_counter(INVOICE_COUNTER_FILE, 1001)


def get_next_past_invoice_number():
    return f"P{read_counter(PAST_INVOICE_COUNTER_FILE, 1001)}"


def increase_past_invoice_number():
    increase_counter(PAST_INVOICE_COUNTER_FILE, 1001)


def document_sort_key(record):
    number = str(record.get("invoice_number", ""))
    digits = re.sub(r"\D", "", number)
    prefix_rank = 0 if number.startswith("P") else 1
    return (prefix_rank, int(digits or 0))


def matching_customer_key(customers, name):
    wanted = name.strip().lower()
    for saved_name in customers:
        if saved_name.strip().lower() == wanted:
            return saved_name
    return name


def clean_float(value):
    try:
        return float(str(value or "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def clean_int(value):
    try:
        return int(float(str(value or "").replace(",", "")))
    except (TypeError, ValueError):
        return 0


def money(value):
    return f"${clean_float(value):,.2f}"


def format_qty(value):
    value = clean_float(value)
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def resolve_discount(discount_text, subtotal):
    """The Discount box accepts either a flat dollar amount ("50") or a
    percentage ("10%") - this figures out which one was typed and returns
    the actual dollar amount to subtract, so nobody has to do the math."""
    text = str(discount_text or "").strip()
    if not text:
        return 0.0
    if text.endswith("%"):
        percent = clean_float(text[:-1])
        return round(clean_float(subtotal) * percent / 100, 2)
    return round(clean_float(text), 2)


def today_text():
    return datetime.today().strftime("%Y/%m/%d")


def friendly_date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%b %d, %Y")
        except ValueError:
            continue
    return text


def image_to_data_uri(path):
    if not os.path.exists(path) and os.path.exists(WRITABLE_LOGO_PATH):
        path = WRITABLE_LOGO_PATH
    mime_type = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def logo_path():
    if os.path.exists(WRITABLE_LOGO_PATH):
        return WRITABLE_LOGO_PATH
    if os.path.exists(LOGO_PATH):
        return LOGO_PATH
    return ""


def pdfkit_config():
    for path in [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ]:
        if os.path.exists(path):
            return pdfkit.configuration(wkhtmltopdf=path)
    return None


def payment_status(total, amount_paid):
    # Round to the cent before comparing - summing several partial payments
    # in binary floating point can land a fraction of a cent short of the
    # total (e.g. three $416.65 payments on a $1,249.95 invoice), which
    # would otherwise leave a fully-paid invoice stuck showing "PARTIAL".
    total = round(clean_float(total), 2)
    paid = round(clean_float(amount_paid), 2)
    if total <= 0:
        return "SAVED"
    if paid >= total:
        return "PAID"
    if paid > 0:
        return "PARTIAL"
    return "UNPAID"


def friendly_payment_status(status):
    """Turns the internal status code into the plain phrase dad sees in
    confirmation popups, so it's immediately obvious whether an invoice is
    settled or still owes money."""
    return {
        "PAID": "Paid in full",
        "PARTIAL": "Partially paid - balance still due",
        "UNPAID": "Unpaid",
        "SAVED": "No amount due",
        "VOID": "Void",
    }.get(status, status)


def invoice_paid_total(record):
    payments = record.get("payments") or []
    if payments:
        return round(sum(clean_float(payment.get("amount")) for payment in payments), 2)
    return round(clean_float(record.get("amount_paid", 0)), 2)


def invoice_balance(record):
    return round(max(clean_float(record.get("total", 0)) - invoice_paid_total(record), 0), 2)


def apply_invoice_payment(invoice_number, amount_text):
    """Adds a dated payment to the saved invoice history record matching
    invoice_number. Shared by the Home screen's Record Payment flow and the
    "+ Add Payment" button inside the invoice editor, so both go through the
    exact same math and never drift out of sync.
    Returns (ok, applied_amount_or_error_message, updated_record_or_None)."""
    payment = round(clean_float(amount_text), 2)
    if payment <= 0:
        return False, "Enter a payment amount greater than $0.00.", None

    history = read_json(INVOICE_HISTORY_FILE, [])
    for saved in history:
        if str(saved.get("invoice_number")) == str(invoice_number):
            if saved.get("status") == "VOID":
                return False, "This invoice is void, so a payment cannot be added.", None
            current_balance = invoice_balance(saved)
            if current_balance <= 0:
                return False, "This invoice is already fully paid.", None
            applied = min(payment, current_balance)
            payments = saved.get("payments") or []
            payments.append({
                "amount": applied,
                "date": today_text(),
                "saved_at": datetime.today().strftime("%Y/%m/%d %H:%M:%S"),
            })
            paid = round(sum(clean_float(item.get("amount")) for item in payments), 2)
            saved["payments"] = payments
            saved["amount_paid"] = str(paid)
            saved["balance_due"] = invoice_balance(saved)
            saved["status"] = payment_status(saved.get("total", 0), paid)
            write_json(INVOICE_HISTORY_FILE, history)
            return True, applied, saved

    return False, "That invoice could not be found in saved history.", None


def edit_invoice_payment(invoice_number, payment_index, new_amount_text):
    """Corrects the amount of one specific payment already recorded on a
    saved invoice (e.g. dad typed $10,000 instead of $1,000). Keeps the
    original date, just fixes the number, and recalculates paid/balance/status
    the same way apply_invoice_payment does so everything stays in sync.
    Returns (ok, applied_amount_or_error_message, updated_record_or_None)."""
    new_amount = round(clean_float(new_amount_text), 2)
    if new_amount <= 0:
        return False, "Enter an amount greater than $0.00.", None

    history = read_json(INVOICE_HISTORY_FILE, [])
    for saved in history:
        if str(saved.get("invoice_number")) == str(invoice_number):
            payments = saved.get("payments") or []
            if not (0 <= payment_index < len(payments)):
                return False, "That payment could not be found.", None
            other_total = round(
                sum(clean_float(p.get("amount")) for i, p in enumerate(payments) if i != payment_index), 2
            )
            total = clean_float(saved.get("total", 0))
            max_allowed = round(max(total - other_total, 0), 2)
            if max_allowed <= 0:
                return False, "The other payments already cover the full total, so this one can't be increased.", None
            applied = min(new_amount, max_allowed)
            payments[payment_index]["amount"] = applied
            paid = round(sum(clean_float(p.get("amount")) for p in payments), 2)
            saved["payments"] = payments
            saved["amount_paid"] = str(paid)
            saved["balance_due"] = invoice_balance(saved)
            saved["status"] = payment_status(saved.get("total", 0), paid)
            write_json(INVOICE_HISTORY_FILE, history)
            return True, applied, saved

    return False, "That invoice could not be found in saved history.", None


def delete_invoice_payment(invoice_number, payment_index):
    """Removes one payment entry entirely from a saved invoice (e.g. it got
    logged twice by mistake) and recalculates paid/balance/status.
    Returns (ok, message_or_None, updated_record_or_None)."""
    history = read_json(INVOICE_HISTORY_FILE, [])
    for saved in history:
        if str(saved.get("invoice_number")) == str(invoice_number):
            payments = saved.get("payments") or []
            if not (0 <= payment_index < len(payments)):
                return False, "That payment could not be found.", None
            payments.pop(payment_index)
            paid = round(sum(clean_float(p.get("amount")) for p in payments), 2)
            saved["payments"] = payments
            saved["amount_paid"] = str(paid)
            saved["balance_due"] = invoice_balance(saved)
            saved["status"] = payment_status(saved.get("total", 0), paid)
            write_json(INVOICE_HISTORY_FILE, history)
            return True, None, saved

    return False, "That invoice could not be found in saved history.", None


def extract_customer_from_pdf_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    phone_match = re.search(r"(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})", text)
    email = email_match.group(0) if email_match else ""
    phone = phone_match.group(1) if phone_match else ""
    skip_name_pattern = r"bill to|ship to|invoice|estimate|date|number|phone|email|from|to:|@|\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
    street_words = r"street|st\.?|road|rd\.?|lane|ln\.?|drive|dr\.?|avenue|ave\.?|terrace|ter\.?|court|ct\.?|way|place|pl\.?"
    street_index = None
    for index, line in enumerate(lines):
        if re.search(rf"\d+.*\b({street_words})\b", line, re.IGNORECASE):
            street_index = index
            break

    name = ""
    address = ""
    city_state_zip = ""
    if street_index is not None:
        address = lines[street_index]
        if street_index + 1 < len(lines):
            next_line = lines[street_index + 1]
            if re.search(r"\b[A-Z]{2}\b|\d{5}", next_line):
                city_state_zip = next_line
        for index in range(street_index - 1, -1, -1):
            candidate = lines[index]
            if not re.search(skip_name_pattern, candidate, re.IGNORECASE):
                name = candidate
                break

    for index, line in enumerate(lines):
        if re.search(r"bill to|invoice to|estimate for|customer|client", line, re.IGNORECASE):
            for candidate in lines[index + 1:index + 5]:
                if candidate != address and not re.search(skip_name_pattern + r"|address", candidate, re.IGNORECASE):
                    name = name or candidate
                    break
            break

    return {
        "name": name,
        "phone": phone,
        "email": email,
        "address": address,
        "city_state_zip": city_state_zip,
    }


def extract_total_from_pdf_text(text):
    total_lines = [line for line in text.splitlines() if re.search(r"\b(total|amount due|balance due)\b", line, re.IGNORECASE)]
    candidates = total_lines or text.splitlines()
    amounts = []
    for line in candidates:
        for match in re.findall(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})|[0-9]+(?:\.\d{2}))", line):
            amounts.append(clean_float(match))
    return max(amounts) if amounts else 0


def text_issues(value):
    text = str(value or "")
    issues = []
    for wrong, right in COMMON_TEXT_FIXES.items():
        pattern = rf"(?<!\w){re.escape(wrong)}(?!\w)"
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            issues.append({
                "start": match.start(),
                "end": match.end(),
                "wrong": match.group(0),
                "right": right,
            })
    return sorted(issues, key=lambda issue: issue["start"])


def autocorrected_text(value):
    """Applies the same typo list used for spell-check underlining and returns
    the corrected string outright, preserving the capitalization of whatever
    was typed. Used to auto-fix a whole field's text at once (e.g. when a
    table cell or line edit loses focus)."""
    text = str(value or "")
    issues = text_issues(text)
    if not issues:
        return text
    pieces = []
    cursor = 0
    for issue in issues:
        pieces.append(text[cursor:issue["start"]])
        fixed = issue["right"]
        if issue["wrong"][:1].isupper():
            fixed = fixed[:1].upper() + fixed[1:]
        pieces.append(fixed)
        cursor = issue["end"]
    pieces.append(text[cursor:])
    return "".join(pieces)


def _autocorrect_last_word(text, cursor_pos, boundary_chars=" \t\n"):
    """If the character right before cursor_pos is a boundary (space/newline)
    and the word just before that boundary is a known typo, returns
    (corrected_text, new_cursor_pos). Otherwise returns None. This is what
    powers "as you type" autocorrect: it only fires the instant a word is
    finished, the same way autocorrect works on a phone."""
    if not (0 < cursor_pos <= len(text)):
        return None
    if text[cursor_pos - 1] not in boundary_chars:
        return None
    start = cursor_pos - 1
    while start > 0 and text[start - 1] not in boundary_chars:
        start -= 1
    word = text[start:cursor_pos - 1]
    if not word:
        return None
    fixed = COMMON_TEXT_FIXES.get(word.lower())
    if not fixed or fixed.lower() == word.lower():
        return None
    if word[:1].isupper():
        fixed = fixed[:1].upper() + fixed[1:]
    new_text = text[:start] + fixed + text[cursor_pos - 1:]
    new_cursor = start + len(fixed) + 1
    return new_text, new_cursor


def autocorrect_line_edit(field):
    """Wire this to a QLineEdit's textChanged signal to autocorrect the word
    the user just finished typing (as soon as they hit space)."""
    text = field.text()
    result = _autocorrect_last_word(text, field.cursorPosition())
    if not result:
        return
    new_text, new_pos = result
    field.blockSignals(True)
    field.setText(new_text)
    field.setCursorPosition(new_pos)
    field.blockSignals(False)


def autocorrect_line_edit_on_finish(field):
    """Wire this to a QLineEdit's editingFinished signal as a safety net that
    catches the last word of a field even if the user never typed a trailing
    space (e.g. they tabbed away immediately)."""
    text = field.text()
    fixed = autocorrected_text(text)
    if fixed != text:
        field.blockSignals(True)
        field.setText(fixed)
        field.blockSignals(False)


def autocorrect_text_edit(field):
    """Wire this to a QTextEdit's textChanged signal for the same as-you-type
    behavior as autocorrect_line_edit."""
    text = field.toPlainText()
    result = _autocorrect_last_word(text, field.textCursor().position())
    if not result:
        return
    new_text, new_pos = result
    field.blockSignals(True)
    field.setPlainText(new_text)
    cursor = field.textCursor()
    cursor.setPosition(new_pos)
    field.setTextCursor(cursor)
    field.blockSignals(False)


class HomePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 18, 26, 18)
        layout.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(28)
        self.logo_label = QLabel()
        self.refresh_logo()
        top.addWidget(self.logo_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(8)
        title = QLabel("Adael Construction")
        title.setObjectName("homeTitle")
        subtitle = QLabel(f"Invoices & Estimates  ·  v{CURRENT_VERSION}")
        subtitle.setObjectName("mutedText")
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        new_invoice = QPushButton("+ New Invoice")
        new_estimate = QPushButton("+ New Estimate")
        new_invoice.setObjectName("primaryButton")
        new_estimate.setObjectName("primaryButton")
        new_invoice.setMinimumHeight(52)
        new_estimate.setMinimumHeight(52)
        big_button_font = new_invoice.font()
        big_button_font.setPointSize(big_button_font.pointSize() + 2)
        big_button_font.setBold(True)
        new_invoice.setFont(big_button_font)
        new_estimate.setFont(big_button_font)
        new_invoice.clicked.connect(lambda: self.window.open_editor("invoice"))
        new_estimate.clicked.connect(lambda: self.window.open_editor("estimate"))
        buttons.addWidget(new_invoice)
        buttons.addWidget(new_estimate)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        title_box.addLayout(buttons)
        top.addLayout(title_box, 1)
        layout.addLayout(top)

        self.drafts = QListWidget()
        self.customers = QComboBox()
        self.invoice_history = QTableWidget(0, 6)
        self.invoice_history.setHorizontalHeaderLabels(["#", "Customer", "Total", "Balance", "Status", "Date"])
        self.estimate_history = QTableWidget(0, 5)
        self.estimate_history.setHorizontalHeaderLabels(["#", "Customer", "Total", "Status", "Date"])
        self.selected_history_type = None
        self.all_drafts = []
        self.all_customers = {}
        self.all_invoice_history = []
        self.all_estimate_history = []
        self.drafts.setObjectName("panelList")
        self.drafts.setMinimumHeight(160)
        self.drafts.setMaximumHeight(280)
        self.drafts.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.drafts.setAlternatingRowColors(True)
        for table in [self.invoice_history, self.estimate_history]:
            table.setObjectName("panelList")
            table.setMinimumHeight(180)
            table.setMaximumHeight(300)
            table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(34)
            table.horizontalHeader().setMinimumHeight(34)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for column in [0, 2, 3, 4, 5]:
            self.invoice_history.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        for column in [0, 2, 3, 4]:
            self.estimate_history.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.invoice_history.itemClicked.connect(self.select_invoice_history)
        self.estimate_history.itemClicked.connect(lambda _item: self.mark_history_selection("estimate"))

        self.content_stack = QStackedWidget()
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("sidebarNav")
        self.nav_list.addItems(["Drafts", "Customers", "Invoices", "Estimates", "Settings"])
        self.nav_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)

        drafts_tab = QWidget()
        drafts_layout = QVBoxLayout(drafts_tab)
        drafts_layout.setSpacing(12)
        drafts_layout.addWidget(self.section_title("Unfinished Work"))
        self.draft_search = QLineEdit()
        self.draft_search.setPlaceholderText("Search drafts")
        self.draft_search.textChanged.connect(self.populate_drafts)
        drafts_layout.addWidget(self.draft_search)
        drafts_layout.addWidget(self.drafts)
        draft_actions = QHBoxLayout()
        draft_actions.setSpacing(10)
        open_draft = QPushButton("Open Draft")
        delete_draft = QPushButton("Delete Draft")
        delete_draft.setObjectName("dangerButton")
        open_draft.clicked.connect(self.open_selected_draft)
        delete_draft.clicked.connect(self.delete_selected_draft)
        draft_actions.addWidget(open_draft)
        draft_actions.addWidget(delete_draft)
        draft_actions.addStretch(1)
        drafts_layout.addLayout(draft_actions)

        customers_tab = QWidget()
        customer_box = QVBoxLayout(customers_tab)
        customer_box.setSpacing(12)
        customer_box.addWidget(self.section_title("Saved Customers"))
        self.customer_search = QLineEdit()
        self.customer_search.setPlaceholderText("Search customers")
        self.customer_search.textChanged.connect(self.populate_customers)
        self.customers.currentIndexChanged.connect(self.load_customer_editor)
        customer_box.addWidget(self.customer_search)
        customer_box.addWidget(self.customers)
        customer_edit_form = QFormLayout()
        customer_edit_form.setSpacing(8)
        self.edit_customer_name = QLineEdit()
        self.edit_customer_phone = QLineEdit()
        self.edit_customer_email = QLineEdit()
        self.edit_customer_address = QLineEdit()
        self.edit_customer_city_state_zip = QLineEdit()
        self.edit_customer_name.setPlaceholderText("Customer Name")
        self.edit_customer_phone.setPlaceholderText("Phone Number")
        self.edit_customer_email.setPlaceholderText("Email")
        self.edit_customer_address.setPlaceholderText("Street Address")
        self.edit_customer_city_state_zip.setPlaceholderText("City, State ZIP")
        customer_edit_form.addRow("Name", self.edit_customer_name)
        customer_edit_form.addRow("Phone", self.edit_customer_phone)
        customer_edit_form.addRow("Email", self.edit_customer_email)
        customer_edit_form.addRow("Address", self.edit_customer_address)
        customer_edit_form.addRow("City / State / ZIP", self.edit_customer_city_state_zip)
        for field in (self.edit_customer_name, self.edit_customer_address, self.edit_customer_city_state_zip):
            field.textChanged.connect(lambda _, f=field: autocorrect_line_edit(f))
            field.editingFinished.connect(lambda f=field: autocorrect_line_edit_on_finish(f))
        customer_box.addLayout(customer_edit_form)
        customer_actions = QHBoxLayout()
        customer_actions.setSpacing(10)
        customer_invoice = QPushButton("New Invoice")
        customer_estimate = QPushButton("New Estimate")
        import_customers = QPushButton("Import From PDFs")
        customer_save = QPushButton("Save Customer Changes")
        customer_delete = QPushButton("Delete Customer")
        customer_save.setObjectName("primaryButton")
        customer_delete.setObjectName("dangerButton")
        customer_invoice.clicked.connect(lambda: self.new_for_customer("invoice"))
        customer_estimate.clicked.connect(lambda: self.new_for_customer("estimate"))
        import_customers.clicked.connect(self.import_customers_from_pdfs)
        customer_save.clicked.connect(self.save_customer_changes)
        customer_delete.clicked.connect(self.delete_customer)
        customer_actions.addWidget(customer_invoice)
        customer_actions.addWidget(customer_estimate)
        customer_actions.addWidget(import_customers)
        customer_actions.addWidget(customer_save)
        customer_actions.addWidget(customer_delete)
        customer_actions.addStretch(1)
        customer_box.addLayout(customer_actions)
        customer_box.addStretch(1)

        invoices_tab = QWidget()
        invoices_layout = QVBoxLayout(invoices_tab)
        invoices_layout.setSpacing(14)
        invoices_layout.addWidget(self.section_title("Saved Invoices"))
        self.invoice_stats_label = QLabel("")
        self.invoice_stats_label.setObjectName("mutedText")
        invoices_layout.addWidget(self.invoice_stats_label)
        invoice_filter_row = QHBoxLayout()
        invoice_filter_row.setSpacing(10)
        self.invoice_search = QLineEdit()
        self.invoice_search.setPlaceholderText("Search invoices")
        self.invoice_search.textChanged.connect(self.populate_invoice_history)
        self.invoice_sort = QComboBox()
        self.invoice_sort.addItems([
            "Newest / Number",
            "Customer Name",
            "Date",
            "Total",
            "Balance",
            "Status",
        ])
        self.invoice_sort.currentIndexChanged.connect(self.populate_invoice_history)
        invoice_filter_row.addWidget(self.invoice_search, 2)
        invoice_filter_row.addWidget(QLabel("Sort by"))
        invoice_filter_row.addWidget(self.invoice_sort, 1)
        invoices_layout.addLayout(invoice_filter_row)
        invoices_layout.addWidget(self.invoice_history)
        self.payment_history = QTextEdit()
        self.payment_history.setReadOnly(True)
        self.payment_history.setMinimumHeight(90)
        self.payment_history.setMaximumHeight(150)
        self.payment_history.setPlaceholderText("Select an invoice to see payment history.")
        invoices_layout.addWidget(self.payment_history)

        payment_fix_row = QHBoxLayout()
        payment_fix_row.setSpacing(10)
        self.payment_select = QComboBox()
        self.payment_select.addItem("Fix a past payment...", None)
        edit_payment = QPushButton("Edit Selected Payment")
        delete_payment = QPushButton("Delete Selected Payment")
        delete_payment.setObjectName("dangerButton")
        edit_payment.clicked.connect(self.edit_selected_payment)
        delete_payment.clicked.connect(self.delete_selected_payment)
        payment_fix_row.addWidget(self.payment_select, 2)
        payment_fix_row.addWidget(edit_payment)
        payment_fix_row.addWidget(delete_payment)
        invoices_layout.addLayout(payment_fix_row)

        payment_row = QHBoxLayout()
        payment_row.setSpacing(10)
        self.payment_amount = QLineEdit()
        self.payment_amount.setPlaceholderText("New payment amount")
        record_payment = QPushButton("Add New Payment")
        record_payment.setObjectName("primaryButton")
        record_payment.clicked.connect(self.record_invoice_payment)
        payment_row.addWidget(self.payment_amount)
        payment_row.addWidget(record_payment)
        payment_row.addStretch(1)
        invoices_layout.addLayout(payment_row)
        invoice_saved_actions = QHBoxLayout()
        invoice_saved_actions.setSpacing(10)
        open_invoice = QPushButton("Open Invoice")
        open_invoice_pdf = QPushButton("Open Invoice PDF")
        open_invoice.setObjectName("primaryButton")
        open_invoice.clicked.connect(lambda: self.open_history("invoice"))
        open_invoice_pdf.clicked.connect(lambda: self.open_history_pdf("invoice"))
        invoice_saved_actions.addWidget(open_invoice)
        invoice_saved_actions.addWidget(open_invoice_pdf)
        invoice_saved_actions.addStretch(1)
        invoices_layout.addLayout(invoice_saved_actions)

        invoice_danger_actions = QHBoxLayout()
        invoice_danger_actions.setSpacing(10)
        void_invoice = QPushButton("Void Invoice")
        delete_invoice = QPushButton("Delete Invoice")
        void_invoice.setObjectName("dangerButton")
        delete_invoice.setObjectName("dangerButton")
        void_invoice.clicked.connect(lambda: self.void_history_record("invoice"))
        delete_invoice.clicked.connect(lambda: self.delete_history_record("invoice"))
        invoice_danger_actions.addStretch(1)
        invoice_danger_actions.addWidget(void_invoice)
        invoice_danger_actions.addWidget(delete_invoice)
        invoices_layout.addLayout(invoice_danger_actions)

        estimates_tab = QWidget()
        estimates_layout = QVBoxLayout(estimates_tab)
        estimates_layout.setSpacing(14)
        estimates_layout.addWidget(self.section_title("Saved Estimates"))
        self.estimate_stats_label = QLabel("")
        self.estimate_stats_label.setObjectName("mutedText")
        estimates_layout.addWidget(self.estimate_stats_label)
        self.estimate_search = QLineEdit()
        self.estimate_search.setPlaceholderText("Search estimates")
        self.estimate_search.textChanged.connect(self.populate_estimate_history)
        estimates_layout.addWidget(self.estimate_search)
        estimates_layout.addWidget(self.estimate_history)
        estimate_saved_actions = QHBoxLayout()
        estimate_saved_actions.setSpacing(10)
        open_estimate = QPushButton("Open Estimate")
        open_estimate_pdf = QPushButton("Open Estimate PDF")
        make_invoice = QPushButton("Make Invoice From Estimate")
        open_estimate.setObjectName("primaryButton")
        make_invoice.setObjectName("primaryButton")
        open_estimate.clicked.connect(lambda: self.open_history("estimate"))
        open_estimate_pdf.clicked.connect(lambda: self.open_history_pdf("estimate"))
        make_invoice.clicked.connect(self.make_invoice_from_estimate)
        estimate_saved_actions.addWidget(open_estimate)
        estimate_saved_actions.addWidget(open_estimate_pdf)
        estimate_saved_actions.addWidget(make_invoice)
        estimate_saved_actions.addStretch(1)
        estimates_layout.addLayout(estimate_saved_actions)

        estimate_danger_actions = QHBoxLayout()
        estimate_danger_actions.setSpacing(10)
        void_estimate = QPushButton("Void Estimate")
        delete_estimate = QPushButton("Delete Estimate")
        void_estimate.setObjectName("dangerButton")
        delete_estimate.setObjectName("dangerButton")
        void_estimate.clicked.connect(lambda: self.void_history_record("estimate"))
        delete_estimate.clicked.connect(lambda: self.delete_history_record("estimate"))
        estimate_danger_actions.addStretch(1)
        estimate_danger_actions.addWidget(void_estimate)
        estimate_danger_actions.addWidget(delete_estimate)
        estimates_layout.addLayout(estimate_danger_actions)

        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setSpacing(12)
        settings_layout.addWidget(self.section_title("Company Settings"))
        settings_form = QFormLayout()
        settings_form.setSpacing(10)
        self.company_name = QLineEdit()
        self.owner_name = QLineEdit()
        self.company_phone = QLineEdit()
        self.company_email = QLineEdit()
        self.company_address = QLineEdit()
        self.default_notes = QTextEdit()
        self.default_notes.setMinimumHeight(90)
        settings_form.addRow("Company Name", self.company_name)
        settings_form.addRow("Owner / Contact", self.owner_name)
        settings_form.addRow("Phone", self.company_phone)
        settings_form.addRow("Email", self.company_email)
        settings_form.addRow("Address", self.company_address)
        settings_form.addRow("Default Notes", self.default_notes)
        for field in (self.company_name, self.owner_name, self.company_address):
            field.textChanged.connect(lambda _, f=field: autocorrect_line_edit(f))
            field.editingFinished.connect(lambda f=field: autocorrect_line_edit_on_finish(f))
        self.default_notes.textChanged.connect(lambda: autocorrect_text_edit(self.default_notes))
        settings_layout.addLayout(settings_form)
        self.logo_status = QLabel()
        self.logo_status.setObjectName("mutedText")
        settings_layout.addWidget(self.logo_status)
        settings_actions = QHBoxLayout()
        settings_actions.setSpacing(10)
        change_logo = QPushButton("Change Logo")
        save_settings = QPushButton("Save Settings")
        save_settings.setObjectName("primaryButton")
        change_logo.clicked.connect(self.change_logo)
        save_settings.clicked.connect(self.save_settings)
        settings_actions.addWidget(change_logo)
        settings_actions.addWidget(save_settings)
        settings_actions.addStretch(1)
        settings_layout.addLayout(settings_actions)
        settings_layout.addStretch(1)

        self.content_stack.addWidget(drafts_tab)
        self.content_stack.addWidget(customers_tab)
        self.content_stack.addWidget(invoices_tab)
        self.content_stack.addWidget(estimates_tab)
        self.content_stack.addWidget(settings_tab)

        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarPanel")
        sidebar_widget.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(12)
        sidebar_layout.addWidget(self.nav_list, 1)
        backup = QPushButton("Backup Data")
        backup.setObjectName("primaryButton")
        backup.clicked.connect(self.create_backup)
        sidebar_layout.addWidget(backup)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(sidebar_widget)
        body.addWidget(self.content_stack, 1)
        layout.addLayout(body, 1)

        self.nav_list.setCurrentRow(0)

    def section_title(self, text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def refresh_logo(self):
        current_logo_path = logo_path()
        if os.path.exists(current_logo_path):
            self.logo_label.setPixmap(QPixmap(current_logo_path).scaledToWidth(118, Qt.SmoothTransformation))
            self.logo_label.setText("")
        else:
            self.logo_label.setPixmap(QPixmap())
            self.logo_label.setText("ADAEL\nCONSTRUCTION")
            self.logo_label.setStyleSheet(f"font-size:20px; font-weight:800; color:{BRAND_BLUE};")
        if hasattr(self, "logo_status"):
            if os.path.exists(current_logo_path):
                self.logo_status.setText(f"Current logo: {os.path.basename(current_logo_path)}")
            else:
                self.logo_status.setText("Current logo: not found")

    def refresh(self):
        self.all_drafts = read_json(DRAFTS_FILE, [])
        self.all_customers = read_json(CUSTOMERS_FILE, {})
        self.all_invoice_history = read_json(INVOICE_HISTORY_FILE, [])
        self.all_estimate_history = read_json(ESTIMATE_HISTORY_FILE, [])
        self.populate_drafts()
        self.populate_customers()
        self.populate_invoice_history()
        self.populate_estimate_history()
        self.load_settings()
        self.refresh_logo()

    def search_match(self, query, *values):
        if not query:
            return True
        haystack = " ".join(str(value or "") for value in values).lower()
        return query.lower() in haystack

    def invoice_sort_key(self, record):
        sort_choice = self.invoice_sort.currentText() if hasattr(self, "invoice_sort") else "Newest / Number"
        paid = invoice_paid_total(record)
        balance = invoice_balance(record)
        status = record.get("status") if record.get("status") in {"VOID", "PAST"} else payment_status(record.get("total", 0), paid)
        if sort_choice == "Customer Name":
            return str(record.get("customer_name_big", "")).lower()
        if sort_choice == "Date":
            return str(record.get("invoice_date", ""))
        if sort_choice == "Total":
            return clean_float(record.get("total", 0))
        if sort_choice == "Balance":
            return balance
        if sort_choice == "Status":
            return status
        return document_sort_key(record)

    def populate_drafts(self):
        query = self.draft_search.text().strip() if hasattr(self, "draft_search") else ""
        self.drafts.clear()
        for draft in self.all_drafts:
            if not self.search_match(
                query,
                draft.get("document_type"),
                draft.get("invoice_number"),
                draft.get("customer_name_big"),
                draft.get("customer_phone_small"),
                draft.get("customer_email_small"),
                draft.get("customer_address_small"),
                draft.get("customer_city_state_zip"),
            ):
                continue
            item = QListWidgetItem(
                f"{draft.get('document_type', 'invoice').title()} {draft.get('invoice_number', '')} - "
                f"{draft.get('customer_name_big') or 'No customer'}"
            )
            item.setData(Qt.UserRole, draft)
            self.drafts.addItem(item)

    def populate_customers(self):
        query = self.customer_search.text().strip() if hasattr(self, "customer_search") else ""
        current_name = self.customers.currentData().get("name") if self.customers.currentData() else ""
        self.customers.blockSignals(True)
        self.customers.clear()
        self.customers.addItem("Select Saved Customer", None)
        selected_index = 0
        for name, info in sorted(self.all_customers.items()):
            if not self.search_match(
                query,
                name,
                info.get("phone"),
                info.get("email"),
                info.get("address"),
                info.get("city_state_zip"),
            ):
                continue
            self.customers.addItem(name, {"name": name, **info})
            if name == current_name:
                selected_index = self.customers.count() - 1
        self.customers.setCurrentIndex(selected_index)
        self.customers.blockSignals(False)
        self.load_customer_editor()

    def populate_invoice_history(self):
        query = self.invoice_search.text().strip() if hasattr(self, "invoice_search") else ""
        self.invoice_history.setRowCount(0)
        sort_choice = self.invoice_sort.currentText() if hasattr(self, "invoice_sort") else "Newest / Number"
        reverse = sort_choice in ["Newest / Number", "Date", "Total", "Balance"]
        records = sorted(self.all_invoice_history, key=self.invoice_sort_key, reverse=reverse)
        for record in records:
            paid = invoice_paid_total(record)
            balance = invoice_balance(record)
            status = record.get("status") if record.get("status") in {"VOID", "PAST"} else payment_status(record.get("total", 0), paid)
            record["amount_paid"] = str(paid)
            record["balance_due"] = balance
            if not self.search_match(
                query,
                record.get("invoice_number"),
                record.get("customer_name_big"),
                record.get("customer_phone_small"),
                record.get("customer_email_small"),
                record.get("customer_address_small"),
                record.get("customer_city_state_zip"),
                status,
                record.get("total"),
                paid,
                balance,
            ):
                continue
            row = self.invoice_history.rowCount()
            self.invoice_history.insertRow(row)
            values = [
                str(record.get("invoice_number", "")),
                record.get("customer_name_big") or "No customer",
                money(record.get("total", 0)),
                money(balance),
                status,
                friendly_date(record.get("invoice_date", "")),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.UserRole, record)
                cell.setTextAlignment(Qt.AlignVCenter | (Qt.AlignLeft if column in (0, 1) else Qt.AlignCenter))
                if status == "VOID":
                    cell.setForeground(QColor("#9b1c1c"))
                elif status == "PAID":
                    cell.setForeground(QColor("#1a7f43"))
                elif status == "PARTIAL":
                    cell.setForeground(QColor("#b45309"))
                elif status == "UNPAID":
                    cell.setForeground(QColor("#c22626"))
                self.invoice_history.setItem(row, column, cell)
        self.update_payment_history()
        self.update_invoice_stats()

    def update_invoice_stats(self):
        if not hasattr(self, "invoice_stats_label"):
            return
        count = len(self.all_invoice_history)
        outstanding = sum(
            invoice_balance(record) for record in self.all_invoice_history
            if record.get("status") != "VOID"
        )
        label = "No invoices saved yet" if count == 0 else (
            f"{count} invoice{'s' if count != 1 else ''} saved  ·  {money(outstanding)} outstanding"
        )
        self.invoice_stats_label.setText(label)

    def populate_estimate_history(self):
        query = self.estimate_search.text().strip() if hasattr(self, "estimate_search") else ""
        self.estimate_history.setRowCount(0)
        for record in self.all_estimate_history:
            status = record.get("status") or "SAVED"
            if not self.search_match(
                query,
                record.get("invoice_number"),
                record.get("customer_name_big"),
                record.get("customer_phone_small"),
                record.get("customer_email_small"),
                record.get("customer_address_small"),
                record.get("customer_city_state_zip"),
                status,
                record.get("total"),
            ):
                continue
            row = self.estimate_history.rowCount()
            self.estimate_history.insertRow(row)
            values = [
                str(record.get("invoice_number", "")),
                record.get("customer_name_big") or "No customer",
                money(record.get("total", 0)),
                status,
                friendly_date(record.get("invoice_date", "")),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.UserRole, record)
                cell.setTextAlignment(Qt.AlignVCenter | (Qt.AlignLeft if column in (0, 1) else Qt.AlignCenter))
                if status == "VOID":
                    cell.setForeground(QColor("#9b1c1c"))
                self.estimate_history.setItem(row, column, cell)
        self.update_estimate_stats()

    def update_estimate_stats(self):
        if not hasattr(self, "estimate_stats_label"):
            return
        count = len(self.all_estimate_history)
        label = "No estimates saved yet" if count == 0 else f"{count} estimate{'s' if count != 1 else ''} saved"
        self.estimate_stats_label.setText(label)

    def selected_item_data(self, list_widget):
        item = list_widget.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def mark_history_selection(self, document_type):
        self.selected_history_type = document_type
        if document_type == "invoice":
            self.estimate_history.clearSelection()
        else:
            self.invoice_history.clearSelection()
        self.update_payment_history()

    def select_invoice_history(self, _item):
        self.mark_history_selection("invoice")
        self.update_payment_history()

    def update_payment_history(self):
        if not hasattr(self, "payment_history"):
            return
        record = self.selected_item_data(self.invoice_history)
        self.payment_select.blockSignals(True)
        self.payment_select.clear()
        if not record:
            self.payment_history.setPlainText("Select an invoice to see payment history.")
            self.payment_select.addItem("Fix a past payment...", None)
            self.payment_select.blockSignals(False)
            return
        payments = record.get("payments") or []
        lines = [
            f"Invoice {record.get('invoice_number', '')} - {record.get('customer_name_big') or 'No customer'}",
            f"Total: {money(record.get('total', 0))}",
            f"Paid: {money(invoice_paid_total(record))}",
            f"Balance Left: {money(invoice_balance(record))}",
            "",
            "Payments:",
        ]
        if payments:
            for index, payment in enumerate(payments, start=1):
                lines.append(f"{index}. {friendly_date(payment.get('date'))} - {money(payment.get('amount', 0))}")
            self.payment_select.addItem("Fix a past payment...", None)
            for index, payment in enumerate(payments):
                label = f"{friendly_date(payment.get('date'))} - {money(payment.get('amount', 0))}"
                self.payment_select.addItem(label, index)
        else:
            lines.append("No payments recorded yet.")
            self.payment_select.addItem("No payments recorded yet", None)
        self.payment_select.blockSignals(False)
        self.payment_history.setPlainText("\n".join(lines))

    def open_selected_draft(self):
        draft = self.selected_item_data(self.drafts)
        if draft:
            self.window.open_editor(draft.get("document_type", "invoice"), draft)

    def delete_selected_draft(self):
        draft = self.selected_item_data(self.drafts)
        if not draft:
            return
        label = draft.get("customer_name_big") or draft.get("project_name") or "this draft"
        answer = QMessageBox.question(
            self,
            "Delete Draft",
            f"Delete \"{label}\"? This unfinished work can't be recovered.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        drafts = [item for item in read_json(DRAFTS_FILE, []) if item.get("draft_id") != draft.get("draft_id")]
        write_json(DRAFTS_FILE, drafts)
        self.refresh()

    def load_customer_editor(self):
        if not hasattr(self, "edit_customer_name"):
            return
        customer = self.customers.currentData()
        self.edit_customer_name.setText(customer.get("name", "") if customer else "")
        self.edit_customer_phone.setText(customer.get("phone", "") if customer else "")
        self.edit_customer_email.setText(customer.get("email", "") if customer else "")
        self.edit_customer_address.setText(customer.get("address", "") if customer else "")
        self.edit_customer_city_state_zip.setText(customer.get("city_state_zip", "") if customer else "")

    def save_customer_changes(self):
        customer = self.customers.currentData()
        new_name = self.edit_customer_name.text().strip()
        if not customer or not new_name:
            QMessageBox.information(self, "Save Customer", "Select a customer and enter a customer name first.")
            return
        customers = read_json(CUSTOMERS_FILE, {})
        old_name = customer["name"]
        if new_name != old_name:
            customers.pop(old_name, None)
        customers[new_name] = {
            "phone": self.edit_customer_phone.text().strip(),
            "email": self.edit_customer_email.text().strip(),
            "address": self.edit_customer_address.text().strip(),
            "city_state_zip": self.edit_customer_city_state_zip.text().strip(),
            "updated_at": datetime.today().strftime("%Y/%m/%d %H:%M:%S"),
        }
        write_json(CUSTOMERS_FILE, customers)
        self.customer_search.clear()
        self.refresh()
        index = self.customers.findText(new_name)
        if index >= 0:
            self.customers.setCurrentIndex(index)
        QMessageBox.information(self, "Customer Saved", "Customer information was updated.")

    def new_for_customer(self, document_type):
        customer = self.customers.currentData()
        if not customer:
            return
        data = {
            "customer_name_big": customer["name"],
            "customer_phone_small": customer.get("phone", ""),
            "customer_email_small": customer.get("email", ""),
            "customer_address_small": customer.get("address", ""),
            "customer_city_state_zip": customer.get("city_state_zip", ""),
        }
        self.window.open_editor(document_type, data)

    def delete_customer(self):
        customer = self.customers.currentData()
        if not customer:
            return
        answer = QMessageBox.question(
            self,
            "Delete Customer",
            f"Delete \"{customer.get('name', '')}\" from saved customers?\n\n"
            "Their past invoices and estimates are not affected - only the saved contact card.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        customers = read_json(CUSTOMERS_FILE, {})
        customers.pop(customer["name"], None)
        write_json(CUSTOMERS_FILE, customers)
        self.refresh()

    def import_customers_from_pdfs(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            QMessageBox.warning(
                self,
                "PDF Import Needs Setup",
                "PDF importing needs the pypdf package.\n\n"
                "Install/update the desktop requirements, then try again.",
            )
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Old Invoice PDFs",
            APP_DIR,
            "PDF Files (*.pdf)",
        )
        if not file_paths:
            return

        customers = read_json(CUSTOMERS_FILE, {})
        history = read_json(INVOICE_HISTORY_FILE, [])
        output_dir = os.path.join(APP_DIR, "invoices")
        os.makedirs(output_dir, exist_ok=True)
        imported = 0
        skipped = []
        for file_path in file_paths:
            try:
                reader = PdfReader(file_path)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                customer = extract_customer_from_pdf_text(text)
                name = customer.pop("name", "").strip()
                if not name:
                    skipped.append(os.path.basename(file_path))
                    continue
                customer_key = matching_customer_key(customers, name)
                existing = customers.get(customer_key, {})
                customers[customer_key] = {
                    "phone": customer.get("phone") or existing.get("phone", ""),
                    "email": customer.get("email") or existing.get("email", ""),
                    "address": customer.get("address") or existing.get("address", ""),
                    "city_state_zip": customer.get("city_state_zip") or existing.get("city_state_zip", ""),
                    "source_pdf": os.path.basename(file_path),
                    "updated_at": datetime.today().strftime("%Y/%m/%d %H:%M:%S"),
                }

                past_number = get_next_past_invoice_number()
                pdf_name = f"past_invoice_{past_number}.pdf"
                pdf_path = os.path.join(output_dir, pdf_name)
                shutil.copyfile(file_path, pdf_path)
                total = extract_total_from_pdf_text(text)
                history = [record for record in history if record.get("invoice_number") != past_number]
                history.append({
                    "draft_id": f"invoice_{past_number}",
                    "document_type": "invoice",
                    "invoice_number": past_number,
                    "invoice_date": today_text(),
                    "due_date": "",
                    "customer_name_big": customer_key,
                    "customer_phone_small": customers[customer_key].get("phone", ""),
                    "customer_email_small": customers[customer_key].get("email", ""),
                    "customer_address_small": customers[customer_key].get("address", ""),
                    "customer_city_state_zip": customers[customer_key].get("city_state_zip", ""),
                    "items": [],
                    "notes": "Imported past invoice PDF.",
                    "additional_subtotal": "",
                    "amount_paid": "",
                    "payments": [],
                    "subtotal": total,
                    "total": total,
                    "balance_due": total,
                    "pdf_path": pdf_path,
                    "pdf_name": pdf_name,
                    "source_pdf": os.path.basename(file_path),
                    "saved_at": datetime.today().strftime("%Y/%m/%d %H:%M:%S"),
                    "status": "PAST",
                })
                increase_past_invoice_number()
                imported += 1
            except Exception:
                skipped.append(os.path.basename(file_path))

        write_json(CUSTOMERS_FILE, customers)
        write_json(INVOICE_HISTORY_FILE, sorted(history, key=document_sort_key, reverse=True))
        self.refresh()
        message = f"Imported {imported} past invoice(s)."
        if skipped:
            message += "\n\nCould not read these clearly:\n" + "\n".join(skipped[:8])
            if len(skipped) > 8:
                message += f"\n...and {len(skipped) - 8} more"
        QMessageBox.information(self, "PDF Import Complete", message)

    def load_settings(self):
        if not hasattr(self, "company_name"):
            return
        settings = get_settings()
        self.company_name.setText(settings["company_name"])
        self.owner_name.setText(settings["owner_name"])
        self.company_phone.setText(settings["phone"])
        self.company_email.setText(settings["email"])
        self.company_address.setText(settings["address"])
        self.default_notes.setPlainText(settings["default_notes"])

    def save_settings(self):
        settings = {
            "company_name": self.company_name.text().strip(),
            "owner_name": self.owner_name.text().strip(),
            "phone": self.company_phone.text().strip(),
            "email": self.company_email.text().strip(),
            "address": self.company_address.text().strip(),
            "default_notes": self.default_notes.toPlainText().strip(),
        }
        write_json(SETTINGS_FILE, settings)
        QMessageBox.information(self, "Settings Saved", "Company settings were saved.")

    def change_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Logo",
            APP_DIR,
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not file_path:
            return
        try:
            shutil.copyfile(file_path, WRITABLE_LOGO_PATH)
            self.refresh_logo()
            QMessageBox.information(self, "Logo Updated", "The logo was updated for future PDFs.")
        except OSError as error:
            QMessageBox.critical(self, "Logo Error", f"The logo could not be updated.\n\nDetails: {error}")

    def record_invoice_payment(self):
        record = self.selected_history_record("invoice")
        if not record:
            QMessageBox.information(self, "Add New Payment", "Select a saved invoice first.")
            return
        ok, result, updated_record = apply_invoice_payment(record.get("invoice_number"), self.payment_amount.text())
        if not ok:
            QMessageBox.warning(self, "Add New Payment", result)
            return
        self.payment_amount.clear()
        self.refresh()
        self.update_payment_history()
        QMessageBox.information(
            self,
            "Payment Recorded",
            f"Payment added: {money(result)} on {friendly_date(today_text())}\n"
            f"Total: {money(updated_record.get('total', 0))}\n"
            f"Balance left: {money(updated_record.get('balance_due', 0))}\n"
            f"Status: {friendly_payment_status(updated_record.get('status'))}",
        )

    def edit_selected_payment(self):
        # Read the dropdown's selection BEFORE touching anything else -
        # selected_history_record() re-populates this same dropdown as a
        # side effect, which would wipe out the selection we're about to read.
        index = self.payment_select.currentData()
        record = self.selected_item_data(self.invoice_history)
        if not record:
            QMessageBox.information(self, "Edit Payment", "Select a saved invoice first.")
            return
        if index is None:
            QMessageBox.information(self, "Edit Payment", "Pick a payment from the dropdown first.")
            return
        payments = record.get("payments") or []
        if not (0 <= index < len(payments)):
            return
        current_amount = money(payments[index].get("amount", 0))
        new_amount, ok = QInputDialog.getText(
            self,
            "Edit Payment",
            f"Payment from {friendly_date(payments[index].get('date'))} is currently {current_amount}.\n"
            f"Enter the corrected amount:",
        )
        if not ok or not new_amount.strip():
            return
        success, result, updated_record = edit_invoice_payment(record.get("invoice_number"), index, new_amount)
        if not success:
            QMessageBox.warning(self, "Edit Payment", result)
            return
        self.refresh()
        self.update_payment_history()
        QMessageBox.information(
            self,
            "Payment Updated",
            f"Payment corrected to {money(result)}.\n"
            f"Total: {money(updated_record.get('total', 0))}\n"
            f"Balance left: {money(updated_record.get('balance_due', 0))}\n"
            f"Status: {friendly_payment_status(updated_record.get('status'))}",
        )

    def delete_selected_payment(self):
        # Same ordering fix as edit_selected_payment: read the dropdown first.
        index = self.payment_select.currentData()
        record = self.selected_item_data(self.invoice_history)
        if not record:
            QMessageBox.information(self, "Delete Payment", "Select a saved invoice first.")
            return
        if index is None:
            QMessageBox.information(self, "Delete Payment", "Pick a payment from the dropdown first.")
            return
        payments = record.get("payments") or []
        if not (0 <= index < len(payments)):
            return
        label = f"{friendly_date(payments[index].get('date'))} - {money(payments[index].get('amount', 0))}"
        answer = QMessageBox.question(
            self,
            "Delete Payment",
            f"Remove this payment entirely?\n\n{label}\n\nThis can't be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        success, message, updated_record = delete_invoice_payment(record.get("invoice_number"), index)
        if not success:
            QMessageBox.warning(self, "Delete Payment", message)
            return
        self.refresh()
        self.update_payment_history()
        QMessageBox.information(
            self,
            "Payment Deleted",
            f"Total: {money(updated_record.get('total', 0))}\n"
            f"Balance left: {money(updated_record.get('balance_due', 0))}\n"
            f"Status: {friendly_payment_status(updated_record.get('status'))}",
        )

    def open_history(self, document_type):
        record = self.selected_item_data(self.invoice_history if document_type == "invoice" else self.estimate_history)
        if record:
            self.window.open_editor(document_type, record, loaded_history=True)

    def selected_history(self):
        if self.selected_history_type == "invoice":
            return "invoice", self.selected_item_data(self.invoice_history)
        if self.selected_history_type == "estimate":
            return "estimate", self.selected_item_data(self.estimate_history)
        return None, None

    def history_file(self, document_type):
        return INVOICE_HISTORY_FILE if document_type == "invoice" else ESTIMATE_HISTORY_FILE

    def open_selected_pdf(self):
        _, record = self.selected_history()
        if not record:
            QMessageBox.information(self, "Open PDF", "Select a saved invoice or estimate first.")
            return
        pdf_path = record.get("pdf_path", "")
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.warning(self, "Missing PDF", "That saved PDF could not be found.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

    def void_selected_history(self):
        document_type, record = self.selected_history()
        if not record:
            QMessageBox.information(self, "Void", "Select a saved invoice or estimate first.")
            return
        history_file = self.history_file(document_type)
        history = read_json(history_file, [])
        for saved in history:
            if saved.get("invoice_number") == record.get("invoice_number"):
                saved["status"] = "VOID"
                saved["voided_at"] = datetime.today().strftime("%Y/%m/%d %H:%M:%S")
                break
        write_json(history_file, history)
        self.refresh()

    def void_history_record(self, document_type):
        record = self.selected_history_record(document_type)
        if not record:
            QMessageBox.information(self, "Void", f"Select a saved {document_type} first.")
            return
        answer = QMessageBox.question(
            self,
            "Void",
            f"Mark {document_type} {record.get('invoice_number', '')} as VOID?\n\n"
            "This flags it as cancelled everywhere it's listed. It stays in your records but "
            "payments can no longer be recorded against it.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        history_file = self.history_file(document_type)
        history = read_json(history_file, [])
        for saved in history:
            if saved.get("invoice_number") == record.get("invoice_number"):
                saved["status"] = "VOID"
                saved["voided_at"] = datetime.today().strftime("%Y/%m/%d %H:%M:%S")
                break
        write_json(history_file, history)
        self.refresh()

    def delete_selected_history(self):
        document_type, record = self.selected_history()
        if not record:
            QMessageBox.information(self, "Delete Saved", "Select a saved invoice or estimate first.")
            return
        answer = QMessageBox.question(
            self,
            "Delete Saved",
            f"Delete {document_type} {record.get('invoice_number', '')} from the saved list?\n\n"
            "The PDF file will stay in the folder.",
        )
        if answer != QMessageBox.Yes:
            return
        history_file = self.history_file(document_type)
        history = [
            saved for saved in read_json(history_file, [])
            if saved.get("invoice_number") != record.get("invoice_number")
        ]
        write_json(history_file, history)
        self.refresh()

    def selected_history_record(self, document_type):
        list_widget = self.invoice_history if document_type == "invoice" else self.estimate_history
        self.mark_history_selection(document_type)
        return self.selected_item_data(list_widget)

    def open_history_pdf(self, document_type):
        record = self.selected_history_record(document_type)
        if not record:
            QMessageBox.information(self, "Open PDF", f"Select a saved {document_type} first.")
            return
        pdf_path = record.get("pdf_path", "")
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.warning(self, "Missing PDF", "That saved PDF could not be found.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))

    def delete_history_record(self, document_type):
        record = self.selected_history_record(document_type)
        if not record:
            QMessageBox.information(self, "Delete Saved", f"Select a saved {document_type} first.")
            return
        answer = QMessageBox.question(
            self,
            "Delete Saved",
            f"Delete {document_type} {record.get('invoice_number', '')} from the saved list?\n\n"
            "The PDF file will stay in the folder.",
        )
        if answer != QMessageBox.Yes:
            return
        history_file = self.history_file(document_type)
        history = [
            saved for saved in read_json(history_file, [])
            if saved.get("invoice_number") != record.get("invoice_number")
        ]
        write_json(history_file, history)
        self.refresh()

    def create_backup(self):
        timestamp = datetime.today().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"adael_backup_{timestamp}.zip")
        write_backup_zip(backup_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(BACKUP_DIR))
        QMessageBox.information(self, "Backup Created", f"Backup saved here:\n{backup_path}")

    def make_invoice_from_estimate(self):
        estimate = self.selected_item_data(self.estimate_history)
        if not estimate:
            return
        new_invoice = estimate.copy()
        new_invoice["document_type"] = "invoice"
        new_invoice["invoice_number"] = get_next_number("invoice")
        increase_number("invoice")
        new_invoice["invoice_date"] = today_text()
        new_invoice["amount_paid"] = ""
        new_invoice["payments"] = []
        new_invoice["balance_due"] = clean_float(new_invoice.get("total", 0))
        new_invoice.pop("pdf_path", None)
        new_invoice.pop("pdf_name", None)
        new_invoice.pop("status", None)
        self.window.open_editor("invoice", new_invoice)


class EditorPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.document_type = "invoice"
        self.loaded_history = False
        self.current_draft_id = None
        self.current_payments = []
        self.loaded_pdf_path = ""
        self.loaded_pdf_name = ""
        self.loaded_saved_at = ""
        self.loaded_status = ""

        # Outer layout holds only the scroll area — fixes fullscreen cut-off
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        outer.addWidget(scroll)
        scroll.setWidget(inner)
        layout.setContentsMargins(32, 22, 32, 22)
        layout.setSpacing(14)

        top = QHBoxLayout()
        self.home_button = QPushButton("Home")
        self.home_button.setObjectName("secondaryButton")
        self.home_button.clicked.connect(self.back_home)
        self.title = QLabel("INVOICE")
        self.title.setAlignment(Qt.AlignRight)
        self.title.setObjectName("editorTitle")
        top.addWidget(self.home_button)
        top.addStretch()
        top.addWidget(self.title)
        layout.addLayout(top)

        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(14)
        form_grid.setVerticalSpacing(10)
        self.number = QLineEdit()
        self.number.setReadOnly(True)
        self.date = QLineEdit(today_text())
        self.date.setReadOnly(True)
        self.customer_lookup = QComboBox()
        self.customer_lookup.setEditable(True)
        self.customer_lookup.setInsertPolicy(QComboBox.NoInsert)
        self.customer_lookup.setPlaceholderText("Look up saved customer")
        self.customer_lookup.activated.connect(self.apply_customer_lookup)
        self.customer_name = QLineEdit()
        self.customer_phone = QLineEdit()
        self.customer_email = QLineEdit()
        self.customer_address = QLineEdit()
        self.customer_city_state_zip = QLineEdit()
        self.customer_name.setPlaceholderText("Customer Name")
        self.customer_phone.setPlaceholderText("Phone Number")
        self.customer_email.setPlaceholderText("Email")
        self.customer_address.setPlaceholderText("Street Address")
        self.customer_city_state_zip.setPlaceholderText("City, State ZIP")
        form_grid.addWidget(QLabel("Number"), 0, 0)
        form_grid.addWidget(self.number, 0, 1)
        form_grid.addWidget(QLabel("Date"), 0, 2)
        form_grid.addWidget(self.date, 0, 3)
        form_grid.addWidget(QLabel("Customer Lookup"), 1, 0)
        form_grid.addWidget(self.customer_lookup, 1, 1, 1, 3)
        form_grid.addWidget(QLabel("Customer Name"), 2, 0)
        form_grid.addWidget(self.customer_name, 2, 1, 1, 3)
        form_grid.addWidget(QLabel("Phone"), 3, 0)
        form_grid.addWidget(self.customer_phone, 3, 1)
        form_grid.addWidget(QLabel("Email"), 3, 2)
        form_grid.addWidget(self.customer_email, 3, 3)
        form_grid.addWidget(QLabel("Address"), 4, 0)
        form_grid.addWidget(self.customer_address, 4, 1, 1, 3)
        form_grid.addWidget(QLabel("City / State / ZIP"), 5, 0)
        form_grid.addWidget(self.customer_city_state_zip, 5, 1, 1, 3)
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("Project / Job Name (e.g. Kitchen Remodel — 123 Main St)")
        form_grid.addWidget(QLabel("Project Name"), 6, 0)
        form_grid.addWidget(self.project_name, 6, 1, 1, 3)
        layout.addLayout(form_grid)
        for field in (self.customer_name, self.customer_address, self.customer_city_state_zip, self.project_name):
            field.textChanged.connect(lambda _, f=field: autocorrect_line_edit(f))
            field.editingFinished.connect(lambda f=field: autocorrect_line_edit_on_finish(f))

        self.payment_summary = QLabel()
        self.payment_summary.setObjectName("paymentSummary")
        self.payment_summary.setWordWrap(True)
        self.payment_summary.setTextFormat(Qt.RichText)
        self.payment_summary.setVisible(False)
        layout.addWidget(self.payment_summary)

        self.items = QTableWidget(0, 5)
        self.items.setHorizontalHeaderLabels(["Item", "Description", "Qty", "Unit Price", "Amount"])
        self.items.setAlternatingRowColors(True)
        self.items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items.verticalHeader().setVisible(False)
        self.items.verticalHeader().setDefaultSectionSize(42)
        self.items.verticalHeader().setMinimumSectionSize(42)
        self.items.setMinimumHeight(310)
        self.items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.items.setColumnWidth(0, 170)
        self.items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items.horizontalHeader().setMinimumHeight(38)
        for column in [2, 3, 4]:
            self.items.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.items.itemChanged.connect(self.handle_item_changed)
        layout.addWidget(self.items, 1)

        item_buttons = QHBoxLayout()
        item_buttons.setSpacing(10)
        add_item = QPushButton("+ Add Item")
        delete_item = QPushButton("Delete Selected Item")
        add_item.setObjectName("primaryButton")
        delete_item.setObjectName("dangerButton")
        add_item.clicked.connect(lambda: self.add_item())
        delete_item.clicked.connect(self.delete_item)
        item_buttons.addWidget(add_item)
        item_buttons.addWidget(delete_item)
        item_buttons.addStretch()
        layout.addLayout(item_buttons)

        bottom = QHBoxLayout()
        bottom.setSpacing(18)
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Notes, payment terms, job details, warranty info...")
        self.notes.setMinimumHeight(150)
        self.notes.textChanged.connect(lambda: autocorrect_text_edit(self.notes))
        self.notes.textChanged.connect(self.mark_notes_spelling)
        bottom.addWidget(self.notes, 2)

        totals_box = QFormLayout()
        totals_box.setSpacing(10)
        self.additional = QLineEdit()
        self.discount = QLineEdit()
        self.discount.setPlaceholderText("e.g. 50 or 10%")
        self.discount.setToolTip("Type a flat dollar amount (50) or a percentage off the subtotal (10%)")
        self.amount_paid = QLineEdit()
        self.subtotal_label = QLabel("$0.00")
        self.total_label = QLabel("$0.00")
        self.balance_label = QLabel("$0.00")
        self.add_payment_button = QPushButton("+ Add Payment")
        self.add_payment_button.setObjectName("secondaryButton")
        self.add_payment_button.clicked.connect(self.add_payment)
        self.save_button = QPushButton("Save Changes")
        self.save_button.setObjectName("secondaryButton")
        self.save_button.clicked.connect(self.save_changes)
        self.preview_button = QPushButton("Preview PDF")
        self.generate_button = QPushButton("Generate PDF")
        self.preview_button.setMinimumHeight(42)
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.setMinimumHeight(42)
        self.save_button.setMinimumHeight(42)
        self.preview_button.clicked.connect(self.preview_pdf)
        self.generate_button.clicked.connect(self.generate_pdf)
        self.additional.textChanged.connect(self.recalculate)
        self.discount.textChanged.connect(self.recalculate)
        self.amount_paid.textChanged.connect(self.recalculate)
        totals_box.addRow("Subtotal", self.subtotal_label)
        totals_box.addRow("Discount", self.discount)
        totals_box.addRow("Other Charges", self.additional)
        totals_box.addRow("Amount Paid", self.amount_paid)
        totals_box.addRow(self.add_payment_button)
        totals_box.addRow("Total", self.total_label)
        totals_box.addRow("Balance Due", self.balance_label)
        totals_box.addRow(self.save_button)
        totals_box.addRow(self.preview_button)
        totals_box.addRow(self.generate_button)
        totals_widget = QWidget()
        totals_widget.setObjectName("totalsPanel")
        totals_widget.setLayout(totals_box)
        bottom.addWidget(totals_widget, 1)
        layout.addLayout(bottom)

    def load_document(self, document_type, data=None, loaded_history=False):
        self.document_type = document_type
        self.loaded_history = loaded_history
        data = data or {}
        self.refresh_customer_lookup()
        self.current_draft_id = data.get("draft_id")
        title = "ESTIMATE" if document_type == "estimate" else "INVOICE"
        self.title.setText(title)
        self.preview_button.setText(f"Preview {title.title()} PDF")
        self.generate_button.setText(f"Generate {title.title()} PDF")
        self.amount_paid.setVisible(document_type == "invoice")
        self.current_payments = data.get("payments") or []
        # Keep hold of fields that aren't part of the editable form, so
        # "Save Changes" can write them back untouched instead of blanking
        # them out or triggering a brand-new PDF/history entry.
        self.loaded_pdf_path = data.get("pdf_path", "")
        self.loaded_pdf_name = data.get("pdf_name", "")
        self.loaded_saved_at = data.get("saved_at", "")
        self.loaded_status = data.get("status", "")
        # Once an invoice has real payment history, only "Add Payment" (here
        # or from the Home screen) should touch it - editing here and
        # resaving must never overwrite or collapse the dated payment records.
        self.amount_paid.setReadOnly(document_type == "invoice" and bool(self.current_payments))
        self.amount_paid.setToolTip(
            "Use the \"+ Add Payment\" button to add payments - "
            "editing this box won't change anything once payments exist."
            if self.current_payments else ""
        )
        can_add_payment = document_type == "invoice" and loaded_history and self.loaded_status != "VOID"
        self.add_payment_button.setVisible(can_add_payment)
        self.save_button.setText("Save Changes" if loaded_history else "Save Draft")
        if document_type == "invoice" and self.current_payments:
            paid_total = round(sum(clean_float(p.get("amount")) for p in self.current_payments), 2)
            lines = [
                f"{friendly_date(p.get('date'))} — {money(p.get('amount', 0))} received"
                for p in self.current_payments
            ]
            self.payment_summary.setText(
                "<b>Payments received (" + money(paid_total) + " total):</b><br>" + "<br>".join(lines)
            )
            self.payment_summary.setVisible(True)
        else:
            self.payment_summary.setVisible(False)
        if data.get("invoice_number"):
            self.number.setText(str(data.get("invoice_number")))
        else:
            # Brand new document - reserve this number right away so opening
            # a second new invoice/estimate before finishing this one can
            # never end up reusing the same number and overwriting it later.
            reserved_number = get_next_number(document_type)
            increase_number(document_type)
            self.number.setText(str(reserved_number))
        self.date.setText(str(data.get("invoice_date") or today_text()))
        self.customer_name.setText(str(data.get("customer_name_big", "")))
        self.customer_phone.setText(str(data.get("customer_phone_small", "")))
        self.customer_email.setText(str(data.get("customer_email_small", "")))
        self.customer_address.setText(str(data.get("customer_address_small", "")))
        self.customer_city_state_zip.setText(str(data.get("customer_city_state_zip", "")))
        self.project_name.setText(str(data.get("project_name", "")))
        self.notes.setPlainText(str(data.get("notes", "")))
        self.additional.setText(str(data.get("additional_subtotal", "")))
        self.discount.setText(str(data.get("discount", "")))
        self.amount_paid.setText(str(data.get("amount_paid", "")))
        self.items.blockSignals(True)
        self.items.setRowCount(0)
        for item in data.get("items") or [{"description": "", "qty": "", "price": ""}]:
            self.add_item(item, block=True)
        self.items.blockSignals(False)
        self.recalculate()
        self.update_spelling_marks()

    def refresh_customer_lookup(self):
        current_text = self.customer_lookup.currentText()
        self.customer_lookup.blockSignals(True)
        self.customer_lookup.clear()
        for name, info in sorted(read_json(CUSTOMERS_FILE, {}).items()):
            self.customer_lookup.addItem(name, {"name": name, **info})
        if current_text:
            self.customer_lookup.setEditText(current_text)
        else:
            self.customer_lookup.setCurrentIndex(-1)
        completer = self.customer_lookup.completer()
        if completer:
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
        self.customer_lookup.blockSignals(False)

    def apply_customer_lookup(self, index):
        customer = self.customer_lookup.itemData(index)
        if not customer:
            return
        self.customer_name.setText(customer.get("name", ""))
        self.customer_phone.setText(customer.get("phone", ""))
        self.customer_email.setText(customer.get("email", ""))
        self.customer_address.setText(customer.get("address", ""))
        self.customer_city_state_zip.setText(customer.get("city_state_zip", ""))

    def add_item(self, item=None, block=False):
        if item is None:
            item = {"title": "", "description": "", "qty": "", "price": ""}
        row = self.items.rowCount()
        self.items.insertRow(row)
        self.items.setRowHeight(row, 42)
        values = [
            item.get("title", ""),
            item.get("description", ""),
            item.get("qty", ""),
            item.get("price", ""),
            "",
        ]
        for column, value in enumerate(values):
            table_item = QTableWidgetItem(str(value))
            alignment = Qt.AlignVCenter | (Qt.AlignLeft if column in (0, 1) else Qt.AlignCenter)
            table_item.setTextAlignment(alignment)
            if column == 4:
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
            self.items.setItem(row, column, table_item)
        self.mark_item_spelling(row, 0)
        self.mark_item_spelling(row, 1)
        if not block:
            self.recalculate()
            self.items.setCurrentCell(row, 0)
            self.items.scrollToItem(self.items.item(row, 0), QAbstractItemView.PositionAtCenter)

    def delete_item(self):
        row = self.items.currentRow()
        if row < 0:
            return
        title = self.cell_text(row, 0).strip()
        description = self.cell_text(row, 1).strip()
        qty = self.cell_text(row, 2).strip()
        price = self.cell_text(row, 3).strip()
        if title or description or qty or price:
            label = title or description or "this line item"
            answer = QMessageBox.question(
                self,
                "Delete Item",
                f"Delete \"{label}\"?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.items.removeRow(row)
        self.recalculate()

    def handle_item_changed(self, item):
        try:
            column = item.column() if item else -1
            row = item.row() if item else -1
        except RuntimeError:
            return
        if column in (0, 1):
            fixed = autocorrected_text(item.text())
            if fixed != item.text():
                self.items.blockSignals(True)
                item.setText(fixed)
                self.items.blockSignals(False)
        self.recalculate()
        if column in (0, 1):
            self.mark_item_spelling(row, column)

    def update_spelling_marks(self):
        self.mark_notes_spelling()
        for row in range(self.items.rowCount()):
            self.mark_item_spelling(row, 0)
            self.mark_item_spelling(row, 1)

    def mark_notes_spelling(self):
        selections = []
        underline = QTextCharFormat()
        underline.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        underline.setUnderlineColor(QColor("#d92d20"))
        for issue in text_issues(self.notes.toPlainText()):
            cursor = self.notes.textCursor()
            cursor.setPosition(issue["start"])
            cursor.setPosition(issue["end"], QTextCursor.KeepAnchor)
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = underline
            selections.append(selection)
        self.notes.setExtraSelections(selections)

    def mark_item_spelling(self, row, column):
        item = self.items.item(row, column)
        if not item:
            return
        issues = text_issues(item.text())
        font = item.font()
        font.setUnderline(bool(issues))
        item.setFont(font)
        if issues:
            item.setForeground(QColor("#b42318"))
            suggestions = ", ".join(f"{issue['wrong']} -> {issue['right']}" for issue in issues[:4])
            item.setToolTip(f"Possible typo: {suggestions}")
        else:
            item.setForeground(QColor("#1f2933"))
            item.setToolTip("")

    def item_data(self):
        items = []
        for row in range(self.items.rowCount()):
            items.append({
                "title": self.cell_text(row, 0),
                "description": self.cell_text(row, 1),
                "qty": self.cell_text(row, 2),
                "price": self.cell_text(row, 3),
            })
        return items

    def cell_text(self, row, column):
        item = self.items.item(row, column)
        return item.text() if item else ""

    def totals(self):
        subtotal = 0
        for item in self.item_data():
            qty_text = str(item.get("qty", "")).strip()
            qty = clean_float(qty_text)
            price = clean_float(item.get("price", ""))
            if price and not qty_text:
                qty = 1
            subtotal += qty * price
        subtotal = round(subtotal, 2)
        additional = clean_float(self.additional.text())
        discount = resolve_discount(self.discount.text(), subtotal)
        total = round(max(subtotal - discount + additional, 0), 2)
        paid = clean_float(self.amount_paid.text()) if self.document_type == "invoice" else 0
        return subtotal, additional, discount, total, paid, round(max(total - paid, 0), 2)

    def recalculate(self):
        self.items.blockSignals(True)
        for row, item in enumerate(self.item_data()):
            qty_text = str(item.get("qty", "")).strip()
            qty = clean_float(qty_text)
            price = clean_float(item.get("price", ""))
            if price and not qty_text:
                qty = 1
            amount = qty * price
            amount_item = QTableWidgetItem(money(amount))
            amount_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
            self.items.setItem(row, 4, amount_item)
        self.items.blockSignals(False)
        subtotal, _, _, total, _, balance = self.totals()
        self.subtotal_label.setText(money(subtotal))
        self.total_label.setText(money(total))
        self.balance_label.setText(money(balance))

    def document_data(self):
        subtotal, additional, discount, total, paid, balance = self.totals()
        return {
            "draft_id": self.current_draft_id or f"{self.document_type}_{self.number.text()}",
            "document_type": self.document_type,
            "invoice_number": self.number.text(),
            "invoice_date": self.date.text(),
            "due_date": "",
            "customer_name_big": self.customer_name.text(),
            "customer_phone_small": self.customer_phone.text(),
            "customer_email_small": self.customer_email.text(),
            "customer_address_small": self.customer_address.text(),
            "customer_city_state_zip": self.customer_city_state_zip.text(),
            "project_name": self.project_name.text(),
            "items": self.item_data(),
            "notes": self.notes.toPlainText(),
            "additional_subtotal": self.additional.text(),
            "discount": self.discount.text(),
            "amount_paid": self.amount_paid.text(),
            "payments": self.current_payments,
            "subtotal": subtotal,
            "total": total,
            "balance_due": balance,
        }

    def has_content(self, data):
        notes = data["notes"].strip()
        default_notes = get_settings().get("default_notes", "").strip()
        return any([
            data["customer_name_big"].strip(),
            data["project_name"].strip(),
            data["customer_phone_small"].strip(),
            data["customer_email_small"].strip(),
            data["customer_address_small"].strip(),
            data["customer_city_state_zip"].strip(),
            notes and notes != default_notes,
            str(data["additional_subtotal"]).strip(),
            str(data["discount"]).strip(),
            data["document_type"] == "invoice" and str(data["amount_paid"]).strip(),
            any(
                item.get("title", "").strip() or item["description"].strip()
                or str(item["qty"]).strip() or str(item["price"]).strip()
                for item in data["items"]
            ),
        ])

    def save_draft(self):
        if self.loaded_history:
            return
        data = self.document_data()
        if not self.has_content(data):
            return
        data["updated_at"] = datetime.today().strftime("%Y/%m/%d %H:%M:%S")
        drafts = [draft for draft in read_json(DRAFTS_FILE, []) if draft.get("draft_id") != data["draft_id"]]
        drafts.append(data)
        write_json(DRAFTS_FILE, sorted(drafts, key=lambda draft: draft.get("updated_at", ""), reverse=True))

    def back_home(self):
        self.save_draft()
        self.window.show_home()

    def save_changes(self):
        """The plain Save button. For a brand-new/in-progress document this
        just saves a draft. For an already-generated invoice or estimate
        it updates the saved record in place - notes, items, discount,
        whatever changed - without touching the existing PDF file or
        recorded payments, and without the "want to send it?" prompt that
        Generate PDF shows."""
        if not self.loaded_history:
            data = self.document_data()
            if not self.has_content(data):
                QMessageBox.information(self, "Nothing to Save", "Add some details first, then save.")
                return
            data["updated_at"] = datetime.today().strftime("%Y/%m/%d %H:%M:%S")
            drafts = [draft for draft in read_json(DRAFTS_FILE, []) if draft.get("draft_id") != data["draft_id"]]
            drafts.append(data)
            write_json(DRAFTS_FILE, sorted(drafts, key=lambda draft: draft.get("updated_at", ""), reverse=True))
            QMessageBox.information(self, "Draft Saved", "Saved. Pick this back up anytime from the Home screen.")
            return

        data = self.document_data()
        data["pdf_path"] = self.loaded_pdf_path
        data["pdf_name"] = self.loaded_pdf_name
        data["saved_at"] = self.loaded_saved_at or datetime.today().strftime("%Y/%m/%d %H:%M:%S")
        if self.document_type == "invoice":
            if self.loaded_status in {"VOID", "PAST"}:
                data["status"] = self.loaded_status
            else:
                data["status"] = payment_status(data["total"], invoice_paid_total(data))
        else:
            data["status"] = self.loaded_status or "SAVED"

        history_file = INVOICE_HISTORY_FILE if self.document_type == "invoice" else ESTIMATE_HISTORY_FILE
        history = [record for record in read_json(history_file, []) if record.get("invoice_number") != data["invoice_number"]]
        history.append(data)
        write_json(history_file, sorted(history, key=document_sort_key, reverse=True))
        self.save_customer(data)
        self.loaded_status = data["status"]
        QMessageBox.information(
            self,
            "Changes Saved",
            "Changes saved.\n\nThe existing PDF file wasn't touched — use \"Generate PDF\" "
            "if you need a fresh PDF that includes these changes.",
        )

    def add_payment(self):
        if self.document_type != "invoice" or not self.loaded_history:
            return
        amount_text, ok = QInputDialog.getText(self, "Add Payment", "Payment amount received:")
        if not ok or not amount_text.strip():
            return
        success, result, updated_record = apply_invoice_payment(self.number.text(), amount_text)
        if not success:
            QMessageBox.warning(self, "Add Payment", result)
            return
        QMessageBox.information(
            self,
            "Payment Recorded",
            f"Payment added: {money(result)} on {friendly_date(today_text())}\n"
            f"Total: {money(updated_record.get('total', 0))}\n"
            f"Balance left: {money(updated_record.get('balance_due', 0))}\n"
            f"Status: {friendly_payment_status(updated_record.get('status'))}",
        )
        # Refresh this same editor screen in place so the updated payment,
        # balance, and status show up immediately without navigating away.
        self.load_document("invoice", updated_record, loaded_history=True)

    def preview_pdf(self):
        try:
            data = self.document_data()
            pdf_path = self.create_pdf(data, preview=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
        except Exception as error:
            QMessageBox.critical(
                self,
                "Preview Error",
                "The preview PDF could not be created.\n\n"
                "Make sure wkhtmltopdf is installed on this computer.\n\n"
                f"Details: {error}"
            )

    def generate_pdf(self):
        try:
            data = self.document_data()
            pdf_path = self.create_pdf(data, preview=False)
            self.save_customer(data)
            self.save_history(data, pdf_path)
            self.clear_current_draft(data["draft_id"])
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
            QMessageBox.information(self, "PDF Created", f"Saved and opened PDF:\n{pdf_path}")
            self._offer_send(data)
            self.window.show_home()
        except Exception as error:
            QMessageBox.critical(
                self,
                "PDF Error",
                "The PDF could not be created.\n\n"
                "Make sure wkhtmltopdf is installed on this computer.\n\n"
                f"Details: {error}"
            )

    def _offer_send(self, data):
        email_raw = data.get("customer_email_small", "").strip()
        if not email_raw:
            return
        doc_label = "Estimate" if self.document_type == "estimate" else "Invoice"
        doc_num = data.get("invoice_number", "")
        total = money(data.get("total", 0))
        project = data.get("project_name", "").strip()
        project_line = f" – {project}" if project else ""
        customer = data.get("customer_name_big", "").strip()

        settings = get_settings()
        company = settings.get("company_name", "Adael Construction LLC")
        msg_body = (
            f"Hi {customer}, your {doc_label} #{doc_num}{project_line} "
            f"from {company} is ready. Total: {total}. "
            f"Please reach out with any questions."
        )

        answer = QMessageBox.question(
            self,
            f"Send {doc_label}",
            f"Open Yahoo Mail to email this {doc_label.lower()} to {email_raw}?\n\n"
            f"Message preview:\n{msg_body}\n\n"
            f"(The PDF opened on this computer — attach it to the email before sending.)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        subject = urllib.parse.quote(f"{doc_label} #{doc_num} from {company}")
        email_body = urllib.parse.quote(msg_body)
        to_address = urllib.parse.quote(email_raw)
        QDesktopServices.openUrl(QUrl(
            f"https://compose.mail.yahoo.com/?to={to_address}&subject={subject}&body={email_body}"
        ))

    def save_customer(self, data):
        name = data["customer_name_big"].strip()
        if not name:
            return
        customers = read_json(CUSTOMERS_FILE, {})
        customer_key = matching_customer_key(customers, name)
        existing = customers.get(customer_key, {})
        customers[customer_key] = {
            "phone": data["customer_phone_small"].strip() or existing.get("phone", ""),
            "email": data["customer_email_small"].strip() or existing.get("email", ""),
            "address": data["customer_address_small"].strip() or existing.get("address", ""),
            "city_state_zip": data["customer_city_state_zip"].strip() or existing.get("city_state_zip", ""),
            "updated_at": datetime.today().strftime("%Y/%m/%d %H:%M:%S"),
        }
        write_json(CUSTOMERS_FILE, customers)

    def save_history(self, data, pdf_path):
        data = data.copy()
        data["pdf_path"] = pdf_path
        data["pdf_name"] = os.path.basename(pdf_path)
        data["saved_at"] = datetime.today().strftime("%Y/%m/%d %H:%M:%S")
        if self.document_type == "invoice":
            payments = data.get("payments") or []
            if not payments and clean_float(data["amount_paid"]) > 0:
                payments.append({
                    "amount": clean_float(data["amount_paid"]),
                    "date": today_text(),
                    "saved_at": data["saved_at"],
                })
            paid = round(sum(clean_float(payment.get("amount")) for payment in payments), 2)
            data["payments"] = payments
            data["amount_paid"] = str(paid)
            data["balance_due"] = round(max(clean_float(data["total"]) - paid, 0), 2)
            data["status"] = payment_status(data["total"], paid)
        else:
            data["status"] = "SAVED"
        history_file = INVOICE_HISTORY_FILE if self.document_type == "invoice" else ESTIMATE_HISTORY_FILE
        history = [record for record in read_json(history_file, []) if record.get("invoice_number") != data["invoice_number"]]
        history.append(data)
        write_json(history_file, sorted(history, key=document_sort_key, reverse=True))

    def clear_current_draft(self, draft_id):
        drafts = [draft for draft in read_json(DRAFTS_FILE, []) if draft.get("draft_id") != draft_id]
        write_json(DRAFTS_FILE, drafts)

    def create_pdf(self, data, preview=False):
        document_title = "Estimate" if self.document_type == "estimate" else "Invoice"
        document_label = "Estimate" if self.document_type == "estimate" else "Invoice"
        recipient_label = "Customer"
        settings = get_settings()
        current_logo_path = logo_path()
        if current_logo_path and os.path.exists(current_logo_path):
            logo_html = f'<img src="{image_to_data_uri(current_logo_path)}" width="160">'
        else:
            logo_html = '<div style="font-size:15px; font-weight:700; color:#22394a; letter-spacing:0.5px;">ADAEL<br>CONSTRUCTION</div>'

        rows = ""
        for index, item in enumerate(data["items"], start=1):
            qty = clean_float(item.get("qty", "")) or (1 if clean_float(item.get("price", "")) else 0)
            price = clean_float(item.get("price", ""))
            title = item.get("title", "").strip()
            description = item.get("description", "").strip()
            description_html = html.escape(description).replace("\n", "<br>")
            if title and description:
                item_html = f'<div class="item-title">{html.escape(title)}</div><div class="party-line">{description_html}</div>'
            elif title:
                item_html = f'<div class="item-title">{html.escape(title)}</div>'
            elif description:
                item_html = f'<div class="item-title">{description_html}</div>'
            else:
                item_html = ""
            rows += f"""
            <tr>
                <td class="num-col">{index}</td>
                <td>{item_html}</td>
                <td class="qty-col">{format_qty(qty)}</td>
                <td class="price-col">{money(price)}</td>
                <td class="price-col">{money(qty * price)}</td>
            </tr>
            """

        discount_text_raw = str(data.get("discount", "")).strip()
        discount_amount = resolve_discount(discount_text_raw, data.get("subtotal", 0))
        discount_label = f"Discount ({discount_text_raw})" if discount_text_raw.endswith("%") else "Discount"
        discount_html = (
            f'<div class="totals-line"><span>{discount_label}</span><span>-{money(discount_amount)}</span></div>'
            if discount_amount else ""
        )

        # Amount Paid / Other Charges / Balance Due / Subtotal are for Thiago's
        # dad's own tracking inside the app only -- intentionally left off the
        # printed PDF so customers only ever see the Discount (if any) and Total.

        project_row = ""
        if data.get("project_name", "").strip():
            project_row = f"""<div class="meta-row"><div class="meta-label">Project</div><div class="meta-value">{html.escape(data.get("project_name", ""))}</div></div>"""

        provider_lines = "".join(
            f'<div class="party-line">{html.escape(part)}</div>'
            for part in [settings.get("phone", ""), settings.get("email", "")]
            if part
        )
        customer_lines = "".join(
            f'<div class="party-line">{html.escape(part)}</div>'
            for part in [
                data["customer_phone_small"],
                data["customer_email_small"],
                data["customer_address_small"],
                data["customer_city_state_zip"],
            ]
            if part
        )

        notes_stripped = str(data.get("notes", "")).strip()
        notes_html = html.escape(notes_stripped).replace("\n", "<br>")
        notes_cell_html = (
            f'<div class="label-caps">Notes</div><div class="notes-text">{notes_html}</div>' if notes_stripped else ""
        )

        footer_html = " &nbsp;&middot;&nbsp; ".join(
            html.escape(part) for part in [settings.get("owner_name", ""), settings.get("phone", ""), settings.get("email", "")] if part
        )

        pdf_html = f"""
        <html>
        <head>
        <meta charset="UTF-8">
        <style>
            * {{ box-sizing: border-box; }}
            body {{ font-family: "Segoe UI", Arial, sans-serif; padding: 40px 44px; color: #2b2f33; font-size: 12.5px; }}
            .label-caps {{ font-size: 10px; letter-spacing: 1.4px; text-transform: uppercase; color: {BRAND_BLUE}; font-weight: 700; margin-bottom: 7px; }}
            .header-row {{ display: table; width: 100%; margin-bottom: 8px; }}
            .header-left {{ display: table-cell; width: 42%; vertical-align: top; }}
            .header-right {{ display: table-cell; width: 58%; vertical-align: top; text-align: right; }}
            .party-name {{ font-size: 14px; font-weight: 700; color: #22394a; margin-bottom: 3px; }}
            .party-line {{ font-size: 12px; color: #5c6570; line-height: 1.55; }}
            .party-block {{ margin-bottom: 18px; }}
            .from-block {{ margin-top: 6px; }}
            .from-block .party-name {{ font-size: 12px; }}
            .from-block .party-line {{ font-size: 10.5px; }}
            .meta-block {{ margin-top: 22px; }}
            .meta-row {{ display: table; margin-left: auto; margin-bottom: 6px; }}
            .meta-label {{ display: table-cell; font-size: 10px; letter-spacing: 1px; text-transform: uppercase; color: {BRAND_BLUE}; text-align: left; padding-right: 14px; white-space: nowrap; }}
            .meta-value {{ display: table-cell; font-size: 12.5px; font-weight: 600; color: #22394a; text-align: right; white-space: nowrap; }}
            .doc-title {{ text-align: center; font-size: 26px; font-weight: 300; letter-spacing: 8px; text-transform: uppercase; color: {BRAND_BLUE}; margin: 30px 0 26px; }}
            table.items {{ width: 100%; border-collapse: collapse; }}
            table.items th {{ text-align: left; font-size: 10px; letter-spacing: 0.8px; text-transform: uppercase; color: #ffffff; font-weight: 700; padding: 10px 8px; background: {BRAND_BLUE}; }}
            table.items th:first-child {{ border-top-left-radius: 4px; border-bottom-left-radius: 4px; }}
            table.items th:last-child {{ border-top-right-radius: 4px; border-bottom-right-radius: 4px; }}
            table.items td {{ padding: 11px 8px; border-bottom: 1px solid #eef0f3; font-size: 12.5px; color: #333; vertical-align: top; }}
            table.items tr:nth-child(even) td {{ background: #eaf2f8; }}
            .item-title {{ font-weight: 700; color: #22394a; }}
            .num-col {{ width: 30px; color: #7a92a3; }}
            .qty-col {{ width: 60px; text-align: center; }}
            .price-col {{ width: 100px; text-align: right; }}
            table.items th.qty-col {{ text-align: center; }}
            table.items th.price-col {{ text-align: right; }}
            .summary-row {{ display: table; width: 100%; margin-top: 26px; }}
            .notes-cell {{ display: table-cell; width: 55%; vertical-align: top; padding-right: 30px; }}
            .notes-text {{ font-size: 12px; color: #5c6570; line-height: 1.6; }}
            .totals-cell {{ display: table-cell; width: 45%; vertical-align: top; }}
            .totals-line {{ display: table; width: 100%; padding: 5px 0; font-size: 12.5px; color: #5c6570; }}
            .totals-line span {{ display: table-cell; }}
            .totals-line span:last-child {{ text-align: right; color: #22394a; font-weight: 600; }}
            .total-final {{ display: table; width: 100%; margin-top: 10px; padding: 10px 12px; background: {BRAND_BLUE}; border-radius: 4px; font-size: 15px; font-weight: 700; color: #ffffff; }}
            .total-final span {{ display: table-cell; }}
            .total-final span:last-child {{ text-align: right; }}
            .footer {{ margin-top: 44px; padding-top: 16px; border-top: 1px solid #eef0f3; text-align: center; font-size: 10.5px; color: #9aa1a9; line-height: 1.7; }}
            .watermark {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 100%; text-align: center; white-space: nowrap; font-size: 110px; font-weight: 800; letter-spacing: 6px; color: {BRAND_BLUE}; opacity: 0.08; z-index: 0; }}
        </style>
        </head>
        <body>
            {'<div class="watermark">ESTIMATE</div>' if self.document_type == "estimate" else ""}
            <div class="header-row">
                <div class="header-left">
                    {logo_html}
                    <div class="party-block from-block">
                        <div class="party-name">{html.escape(settings.get("company_name", ""))}</div>
                        {provider_lines}
                    </div>
                </div>
                <div class="header-right">
                    <div class="meta-block">
                        <div class="meta-row"><div class="meta-label">{document_label} No</div><div class="meta-value">{html.escape(data["invoice_number"])}</div></div>
                        <div class="meta-row"><div class="meta-label">Date</div><div class="meta-value">{html.escape(data["invoice_date"])}</div></div>
                        {project_row}
                    </div>
                </div>
            </div>
            <div class="party-block" style="margin-top:24px;">
                <div class="label-caps">{recipient_label}</div>
                <div class="party-name">{html.escape(data["customer_name_big"] or "Customer Name")}</div>
                {customer_lines}
            </div>
            <div class="doc-title">{document_title}</div>
            <table class="items">
                <tr><th class="num-col">No</th><th>Description</th><th class="qty-col">Qty</th><th class="price-col">Unit Price</th><th class="price-col">Amount</th></tr>
                {rows}
            </table>
            <div class="summary-row">
                <div class="notes-cell">{notes_cell_html}</div>
                <div class="totals-cell">
                    {discount_html}
                    <div class="total-final"><span>Total</span><span>{money(data["total"])}</span></div>
                </div>
            </div>
            <div class="footer">{footer_html}</div>
        </body>
        </html>
        """
        folder = "estimates" if self.document_type == "estimate" else "invoices"
        output_dir = PREVIEW_DIR if preview else os.path.join(APP_DIR, folder)
        os.makedirs(output_dir, exist_ok=True)
        if preview:
            # Previews are throwaway - clear out old ones so this folder
            # never quietly fills up with hundreds of leftover files.
            for old_file in os.listdir(PREVIEW_DIR):
                try:
                    os.remove(os.path.join(PREVIEW_DIR, old_file))
                except OSError:
                    pass
            timestamp = datetime.today().strftime("%Y%m%d_%H%M%S")
            filename = f"preview_{folder[:-1]}_{data['invoice_number']}_{timestamp}.pdf"
        else:
            filename = f"{folder[:-1]}_{data['invoice_number']}.pdf"
        path = os.path.join(output_dir, filename)
        config = pdfkit_config()
        options = {"enable-local-file-access": ""}
        if config:
            pdfkit.from_string(pdf_html, path, options=options, configuration=config)
        else:
            pdfkit.from_string(pdf_html, path, options=options)
        return path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TA Invoices and Estimates")
        self.resize(1250, 820)
        self.stack = QStackedWidget()
        self.home = HomePage(self)
        self.editor = EditorPage(self)
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.editor)
        self.setCentralWidget(self.stack)
        self.show_home()

    def show_home(self):
        self.home.refresh()
        self.stack.setCurrentWidget(self.home)

    def open_editor(self, document_type, data=None, loaded_history=False):
        self.editor.load_document(document_type, data, loaded_history)
        self.stack.setCurrentWidget(self.editor)

    def closeEvent(self, event):
        if self.stack.currentWidget() == self.editor:
            self.editor.save_draft()
        event.accept()


def _version_tuple(version_string):
    parts = re.findall(r"\d+", version_string or "")
    return tuple(int(part) for part in parts) if parts else (0,)


def https_context():
    """Some Windows PCs (especially freshly set up ones) don't have a
    complete local certificate store, which makes the bundled Python's SSL
    checks fail with CERTIFICATE_VERIFY_FAILED even though the connection
    itself is fine. Using certifi's bundled certificate list instead of
    relying on Windows' own store sidesteps that. Falls back to the normal
    default context if anything about this goes wrong, so this can never be
    the thing that breaks the update check."""
    try:
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def log_update_event(message):
    """Writes one dated line to update_log.txt in the app folder describing
    what happened during an update check. This is the only way Thiago can
    see why an update did or didn't happen on a computer he isn't sitting
    at - it never shows anything to the person using the app, and it can
    never crash the app even if writing the log itself fails."""
    try:
        with open(UPDATE_LOG_FILE, "a") as file:
            file.write(f"{datetime.today().strftime('%Y/%m/%d %H:%M:%S')} - {message}\n")
    except Exception:
        pass


def check_for_update():
    """Returns (download_url, version_string) if a newer build exists online, else None.
    Never raises - any problem (no internet, GitHub down, no release yet) just
    means no update is found, and the app opens normally."""
    try:
        request = urllib.request.Request(
            UPDATE_FEED_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "AdaelInvoiceApp"},
        )
        with urllib.request.urlopen(request, timeout=4, context=https_context()) as response:
            data = json.loads(response.read().decode("utf-8"))

        remote_version = data.get("tag_name", "")
        log_update_event(f"Checked for updates OK. This computer: {CURRENT_VERSION}. Latest online: {remote_version}.")
        if _version_tuple(remote_version) <= _version_tuple(CURRENT_VERSION):
            log_update_event("Already on the latest version - nothing to download.")
            return None

        for asset in data.get("assets", []):
            if asset.get("name", "").lower().endswith(".exe"):
                log_update_event(f"Found version {remote_version} online - attempting to download it now.")
                return asset.get("browser_download_url"), remote_version

        log_update_event(f"Version {remote_version} exists online but has no .exe file attached to it - can't update.")
        return None
    except Exception as error:
        log_update_event(f"Could not check for updates - {type(error).__name__}: {error}")
        return None


def download_and_relaunch(download_url):
    """Downloads the new exe, writes a tiny helper script that swaps it in
    after this process exits, and launches that helper. Returns True if the
    handoff succeeded (caller should then exit immediately)."""
    if not getattr(sys, "frozen", False):
        log_update_event("Running from source (not a built exe) - skipping self-update.")
        return False  # only self-update the real built .exe, never the dev script

    current_exe = sys.executable
    exe_dir = os.path.dirname(current_exe)
    new_exe_path = os.path.join(exe_dir, "_update_download.exe")
    updater_bat_path = os.path.join(exe_dir, "_apply_update.bat")

    try:
        with urllib.request.urlopen(download_url, timeout=60, context=https_context()) as response:
            with open(new_exe_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
    except Exception as error:
        log_update_event(f"Download failed - {type(error).__name__}: {error}")
        return False

    # Windows Defender (and other antivirus) commonly grabs a brief lock on a
    # freshly-downloaded exe to scan it, which makes an immediate "move" fail.
    # This retries a few times with short waits instead of giving up on the
    # first try, and logs every step so a failure here is actually visible
    # instead of just silently leaving the old version in place.
    bat_contents = (
        "@echo off\r\n"
        f'set LOGFILE="{UPDATE_LOG_FILE}"\r\n'
        f'echo %date% %time% - Updater started, waiting for the app to fully close... >> %LOGFILE%\r\n'
        "timeout /t 3 /nobreak >nul\r\n"
        "set ATTEMPTS=0\r\n"
        ":retry\r\n"
        "set /a ATTEMPTS+=1\r\n"
        f'move /Y "{new_exe_path}" "{current_exe}" >nul 2>&1\r\n'
        "if errorlevel 1 (\r\n"
        '  echo %date% %time% - Move attempt %ATTEMPTS% failed - file may still be locked. >> %LOGFILE%\r\n'
        "  if %ATTEMPTS% LSS 6 (\r\n"
        "    timeout /t 2 /nobreak >nul\r\n"
        "    goto retry\r\n"
        "  )\r\n"
        '  echo %date% %time% - Gave up after 6 attempts - keeping the old version and relaunching it. >> %LOGFILE%\r\n'
        f'  start "" "{current_exe}"\r\n'
        '  del "%~f0"\r\n'
        "  exit /b\r\n"
        ")\r\n"
        'echo %date% %time% - File swap succeeded on attempt %ATTEMPTS%. >> %LOGFILE%\r\n'
        f'start "" "{current_exe}"\r\n'
        'echo %date% %time% - Relaunch command issued. >> %LOGFILE%\r\n'
        'del "%~f0"\r\n'
    )
    try:
        with open(updater_bat_path, "w") as bat_file:
            bat_file.write(bat_contents)

        subprocess.Popen(
            ["cmd", "/c", updater_bat_path],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except Exception as error:
        log_update_event(f"Downloaded fine, but could not launch the updater helper - {type(error).__name__}: {error}")
        return False

    log_update_event("Download complete - handing off to the updater script to finish the swap.")
    return True


def run_update_check_if_available(app):
    """Checks for a newer release and, if found, shows a brief 'Updating...'
    banner with no buttons/clicks required, then swaps in the new version
    and relaunches. Returns True if an update was applied (caller should
    exit immediately and let the relaunch take over)."""
    update = check_for_update()
    if not update:
        return False

    download_url, remote_version = update

    banner = QLabel(f"  Updating to version {remote_version}...  ")
    banner.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
    banner.setStyleSheet(
        "background:#4b7391; color:white; font-size:16px; "
        "font-weight:600; padding:18px; border-radius:6px;"
    )
    banner.setAlignment(Qt.AlignCenter)
    banner.adjustSize()
    screen = app.primaryScreen().geometry()
    banner.move(screen.center().x() - banner.width() // 2, screen.center().y() - banner.height() // 2)
    banner.show()
    app.processEvents()

    success = download_and_relaunch(download_url)
    if not success:
        banner.close()
        return False

    return True


def main():
    app = QApplication(sys.argv)
    if run_update_check_if_available(app):
        sys.exit(0)

    auto_backup_if_needed()

    app.setStyleSheet("""
        QWidget {
            font-family: "Segoe UI", Arial;
            font-size: 14px;
            color: #1f2933;
            background: #f7f9fb;
        }
        QLabel {
            background: transparent;
        }
        QLabel#homeTitle {
            font-size: 32px;
            font-weight: 800;
            color: #4b7391;
        }
        QLabel#editorTitle {
            font-size: 30px;
            font-weight: 800;
            color: #4b7391;
        }
        QLabel#sectionTitle {
            font-size: 16px;
            font-weight: 800;
            color: #4b7391;
            padding-top: 8px;
        }
        QLabel#mutedText {
            font-size: 15px;
            color: #667085;
        }
        QPushButton {
            background: #ffffff;
            border: 1px solid #c7d7e4;
            border-radius: 5px;
            padding: 8px 12px;
            font-weight: 600;
        }
        QPushButton:hover {
            background: #edf4f8;
            border-color: #4b7391;
        }
        QPushButton#primaryButton {
            background: #4b7391;
            border-color: #4b7391;
            color: white;
        }
        QPushButton#primaryButton:hover {
            background: #3f627c;
        }
        QPushButton#secondaryButton {
            background: #eef4f8;
            color: #31536d;
        }
        QPushButton#dangerButton {
            color: #9b1c1c;
            border-color: #e7b8b8;
        }
        QPushButton#dangerButton:hover {
            background: #fff1f1;
        }
        QLineEdit, QTextEdit, QComboBox, QListWidget, QTableWidget {
            background: #ffffff;
            border: 1px solid #c7d7e4;
            border-radius: 5px;
            padding: 6px;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border-color: #4b7391;
        }
        QListWidget#panelList {
            padding: 6px;
        }
        QWidget#sidebarPanel {
            background: transparent;
        }
        QListWidget#sidebarNav {
            background: #ffffff;
            border: 1px solid #c7d7e4;
            border-radius: 8px;
            padding: 8px;
            font-size: 14px;
        }
        QListWidget#sidebarNav::item {
            padding: 12px 14px;
            border-radius: 6px;
            margin-bottom: 4px;
            font-weight: 600;
            color: #31536d;
        }
        QListWidget#sidebarNav::item:selected {
            background: #4b7391;
            color: #ffffff;
        }
        QListWidget#sidebarNav::item:hover:!selected {
            background: #eef4f8;
        }
        QListWidget::item {
            padding: 8px;
            border-radius: 4px;
        }
        QListWidget::item:selected {
            background: #d9e8f2;
            color: #1f2933;
        }
        QTableWidget {
            gridline-color: #c7d7e4;
            alternate-background-color: #e8f1f7;
        }
        QTableWidget::item {
            padding: 2px 7px;
        }
        QTableWidget::item:selected {
            background: #d9e8f2;
            color: #1f2933;
        }
        QTableWidget QLineEdit {
            background: #ffffff;
            border: 2px solid #4b7391;
            border-radius: 3px;
            padding: 4px 6px;
            color: #1f2933;
            selection-background-color: #4b7391;
            selection-color: #ffffff;
        }
        QWidget#totalsPanel {
            background: #ffffff;
            border: 1px solid #c7d7e4;
            border-radius: 6px;
            padding: 14px;
        }
        QLabel#paymentSummary {
            background: #eef7f0;
            border: 1px solid #bfe3c8;
            border-radius: 6px;
            padding: 10px 14px;
            color: #1a4d2e;
            font-size: 13px;
        }
        QHeaderView::section {
            background: #4b7391;
            color: white;
            font-weight: bold;
            padding: 8px;
            border: 1px solid #3f627c;
        }
    """)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_path = os.path.join(APP_DIR, "desktop_app_error.log")
        with open(log_path, "w") as log_file:
            log_file.write(traceback.format_exc())
        raise
