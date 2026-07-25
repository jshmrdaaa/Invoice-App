import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import traceback
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

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

# ============================================================
# AUTO-UPDATE
# ============================================================
# Bump this number every time you build and release a new version.
CURRENT_VERSION = "1.0.0"

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


def today_text():
    return datetime.today().strftime("%Y/%m/%d")


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
    total = clean_float(total)
    paid = clean_float(amount_paid)
    if total <= 0:
        return "SAVED"
    if paid >= total:
        return "PAID"
    if paid > 0:
        return "PARTIAL"
    return "UNPAID"


def invoice_paid_total(record):
    payments = record.get("payments") or []
    if payments:
        return sum(clean_float(payment.get("amount")) for payment in payments)
    return clean_float(record.get("amount_paid", 0))


def invoice_balance(record):
    return max(clean_float(record.get("total", 0)) - invoice_paid_total(record), 0)


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
        subtitle = QLabel("Invoices & Estimates")
        subtitle.setObjectName("mutedText")
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        new_invoice = QPushButton("New Invoice")
        new_estimate = QPushButton("New Estimate")
        new_invoice.setObjectName("primaryButton")
        new_estimate.setObjectName("primaryButton")
        new_invoice.setMinimumHeight(42)
        new_estimate.setMinimumHeight(42)
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
        self.invoice_history = QListWidget()
        self.estimate_history = QListWidget()
        self.selected_history_type = None
        self.all_drafts = []
        self.all_customers = {}
        self.all_invoice_history = []
        self.all_estimate_history = []
        for list_widget in [self.drafts, self.invoice_history, self.estimate_history]:
            list_widget.setObjectName("panelList")
            list_widget.setMinimumHeight(120)
            list_widget.setMaximumHeight(180)
            list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            list_widget.setAlternatingRowColors(True)
        self.invoice_history.itemClicked.connect(self.select_invoice_history)
        self.estimate_history.itemClicked.connect(lambda _item: self.mark_history_selection("estimate"))

        tabs = QTabWidget()
        tabs.setObjectName("homeTabs")
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

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
        invoices_layout.setSpacing(12)
        invoices_layout.addWidget(self.section_title("Saved Invoices"))
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
        self.payment_history.setMinimumHeight(70)
        self.payment_history.setMaximumHeight(95)
        self.payment_history.setPlaceholderText("Select an invoice to see payment history.")
        invoices_layout.addWidget(self.payment_history)
        payment_row = QHBoxLayout()
        payment_row.setSpacing(10)
        self.payment_amount = QLineEdit()
        self.payment_amount.setPlaceholderText("Payment amount")
        record_payment = QPushButton("Record Payment")
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
        void_invoice = QPushButton("Void Invoice")
        delete_invoice = QPushButton("Delete Invoice")
        void_invoice.setObjectName("dangerButton")
        delete_invoice.setObjectName("dangerButton")
        open_invoice.clicked.connect(lambda: self.open_history("invoice"))
        open_invoice_pdf.clicked.connect(lambda: self.open_history_pdf("invoice"))
        void_invoice.clicked.connect(lambda: self.void_history_record("invoice"))
        delete_invoice.clicked.connect(lambda: self.delete_history_record("invoice"))
        invoice_saved_actions.addWidget(open_invoice)
        invoice_saved_actions.addWidget(open_invoice_pdf)
        invoice_saved_actions.addWidget(void_invoice)
        invoice_saved_actions.addWidget(delete_invoice)
        invoice_saved_actions.addStretch(1)
        invoices_layout.addLayout(invoice_saved_actions)

        estimates_tab = QWidget()
        estimates_layout = QVBoxLayout(estimates_tab)
        estimates_layout.setSpacing(12)
        estimates_layout.addWidget(self.section_title("Saved Estimates"))
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
        void_estimate = QPushButton("Void Estimate")
        delete_estimate = QPushButton("Delete Estimate")
        make_invoice.setObjectName("primaryButton")
        void_estimate.setObjectName("dangerButton")
        delete_estimate.setObjectName("dangerButton")
        open_estimate.clicked.connect(lambda: self.open_history("estimate"))
        open_estimate_pdf.clicked.connect(lambda: self.open_history_pdf("estimate"))
        make_invoice.clicked.connect(self.make_invoice_from_estimate)
        void_estimate.clicked.connect(lambda: self.void_history_record("estimate"))
        delete_estimate.clicked.connect(lambda: self.delete_history_record("estimate"))
        estimate_saved_actions.addWidget(open_estimate)
        estimate_saved_actions.addWidget(open_estimate_pdf)
        estimate_saved_actions.addWidget(make_invoice)
        estimate_saved_actions.addWidget(void_estimate)
        estimate_saved_actions.addWidget(delete_estimate)
        estimate_saved_actions.addStretch(1)
        estimates_layout.addLayout(estimate_saved_actions)

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

        tabs.addTab(drafts_tab, "Drafts")
        tabs.addTab(customers_tab, "Customers")
        tabs.addTab(invoices_tab, "Invoices")
        tabs.addTab(estimates_tab, "Estimates")
        tabs.addTab(settings_tab, "Settings")
        layout.addWidget(tabs, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        backup = QPushButton("Backup Data")
        backup.setObjectName("primaryButton")
        backup.clicked.connect(self.create_backup)
        bottom.addStretch(1)
        bottom.addWidget(backup)
        layout.addLayout(bottom)

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
        self.invoice_history.clear()
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
            item = QListWidgetItem(
                f"{record.get('invoice_number', '')} - {record.get('customer_name_big') or 'No customer'} - "
                f"Total {money(record.get('total', 0))} - Paid {money(paid)} - Balance {money(balance)} - {status}"
            )
            item.setData(Qt.UserRole, record)
            self.invoice_history.addItem(item)
        self.update_payment_history()

    def populate_estimate_history(self):
        query = self.estimate_search.text().strip() if hasattr(self, "estimate_search") else ""
        self.estimate_history.clear()
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
            item = QListWidgetItem(
                f"{record.get('invoice_number', '')} - {record.get('customer_name_big') or 'No customer'} - "
                f"{money(record.get('total', 0))} - {status}"
            )
            item.setData(Qt.UserRole, record)
            self.estimate_history.addItem(item)

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
        if not record:
            self.payment_history.setPlainText("Select an invoice to see payment history.")
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
                lines.append(f"{index}. {payment.get('date') or ''} - {money(payment.get('amount', 0))}")
        else:
            lines.append("No payments recorded yet.")
        self.payment_history.setPlainText("\n".join(lines))

    def open_selected_draft(self):
        draft = self.selected_item_data(self.drafts)
        if draft:
            self.window.open_editor(draft.get("document_type", "invoice"), draft)

    def delete_selected_draft(self):
        draft = self.selected_item_data(self.drafts)
        if not draft:
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
            QMessageBox.information(self, "Record Payment", "Select a saved invoice first.")
            return
        if record.get("status") == "VOID":
            QMessageBox.warning(self, "Record Payment", "This invoice is void, so a payment cannot be added.")
            return
        payment = clean_float(self.payment_amount.text())
        if payment <= 0:
            QMessageBox.warning(self, "Record Payment", "Enter a payment amount greater than $0.00.")
            return
        current_balance = invoice_balance(record)
        if current_balance <= 0:
            QMessageBox.information(self, "Record Payment", "This invoice is already fully paid.")
            return
        if payment > current_balance:
            payment = current_balance

        history = read_json(INVOICE_HISTORY_FILE, [])
        updated_record = None
        for saved in history:
            if saved.get("invoice_number") == record.get("invoice_number"):
                payments = saved.get("payments") or []
                payments.append({
                    "amount": payment,
                    "date": today_text(),
                    "saved_at": datetime.today().strftime("%Y/%m/%d %H:%M:%S"),
                })
                paid = sum(clean_float(item.get("amount")) for item in payments)
                saved["payments"] = payments
                saved["amount_paid"] = str(paid)
                saved["balance_due"] = invoice_balance(saved)
                saved["status"] = payment_status(saved.get("total", 0), paid)
                updated_record = saved
                break

        write_json(INVOICE_HISTORY_FILE, history)
        self.payment_amount.clear()
        self.refresh()
        self.update_payment_history()
        if updated_record:
            QMessageBox.information(
                self,
                "Payment Recorded",
                f"Payment added: {money(payment)}\n"
                f"Balance left: {money(updated_record.get('balance_due', 0))}",
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
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.today().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"adael_backup_{timestamp}.zip")
        files = [
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
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as backup:
            for path in files:
                if os.path.exists(path):
                    backup.write(path, os.path.basename(path))
            for folder in ["invoices", "estimates"]:
                folder_path = os.path.join(APP_DIR, folder)
                if os.path.exists(folder_path):
                    for filename in os.listdir(folder_path):
                        full_path = os.path.join(folder_path, filename)
                        if os.path.isfile(full_path):
                            backup.write(full_path, os.path.join(folder, filename))
        QDesktopServices.openUrl(QUrl.fromLocalFile(BACKUP_DIR))
        QMessageBox.information(self, "Backup Created", f"Backup saved here:\n{backup_path}")

    def make_invoice_from_estimate(self):
        estimate = self.selected_item_data(self.estimate_history)
        if not estimate:
            return
        new_invoice = estimate.copy()
        new_invoice["document_type"] = "invoice"
        new_invoice["invoice_number"] = get_next_number("invoice")
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

        self.items = QTableWidget(0, 4)
        self.items.setHorizontalHeaderLabels(["Description", "Qty", "Unit Price", "Amount"])
        self.items.setAlternatingRowColors(True)
        self.items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items.verticalHeader().setVisible(False)
        self.items.verticalHeader().setDefaultSectionSize(42)
        self.items.verticalHeader().setMinimumSectionSize(42)
        self.items.setMinimumHeight(310)
        self.items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.items.horizontalHeader().setMinimumHeight(38)
        for column in [1, 2, 3]:
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
        self.notes.textChanged.connect(self.mark_notes_spelling)
        bottom.addWidget(self.notes, 2)

        totals_box = QFormLayout()
        totals_box.setSpacing(10)
        self.additional = QLineEdit()
        self.amount_paid = QLineEdit()
        self.subtotal_label = QLabel("$0.00")
        self.total_label = QLabel("$0.00")
        self.balance_label = QLabel("$0.00")
        self.preview_button = QPushButton("Preview PDF")
        self.generate_button = QPushButton("Generate PDF")
        self.preview_button.setMinimumHeight(42)
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.setMinimumHeight(42)
        self.preview_button.clicked.connect(self.preview_pdf)
        self.generate_button.clicked.connect(self.generate_pdf)
        self.additional.textChanged.connect(self.recalculate)
        self.amount_paid.textChanged.connect(self.recalculate)
        totals_box.addRow("Other Charges", self.additional)
        totals_box.addRow("Amount Paid", self.amount_paid)
        totals_box.addRow("Subtotal", self.subtotal_label)
        totals_box.addRow("Total", self.total_label)
        totals_box.addRow("Balance Due", self.balance_label)
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
        self.number.setText(str(data.get("invoice_number") or get_next_number(document_type)))
        self.date.setText(str(data.get("invoice_date") or today_text()))
        self.customer_name.setText(str(data.get("customer_name_big", "")))
        self.customer_phone.setText(str(data.get("customer_phone_small", "")))
        self.customer_email.setText(str(data.get("customer_email_small", "")))
        self.customer_address.setText(str(data.get("customer_address_small", "")))
        self.customer_city_state_zip.setText(str(data.get("customer_city_state_zip", "")))
        self.project_name.setText(str(data.get("project_name", "")))
        default_notes = get_settings().get("default_notes", "")
        self.notes.setPlainText(str(data.get("notes", default_notes)))
        self.additional.setText(str(data.get("additional_subtotal", "")))
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
            item = {"description": "", "qty": "", "price": ""}
        row = self.items.rowCount()
        self.items.insertRow(row)
        self.items.setRowHeight(row, 42)
        values = [
            item.get("description", ""),
            item.get("qty", ""),
            item.get("price", ""),
            "",
        ]
        for column, value in enumerate(values):
            table_item = QTableWidgetItem(str(value))
            alignment = Qt.AlignVCenter | (Qt.AlignLeft if column == 0 else Qt.AlignCenter)
            table_item.setTextAlignment(alignment)
            if column == 3:
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
            self.items.setItem(row, column, table_item)
        self.mark_item_spelling(row)
        if not block:
            self.recalculate()
            self.items.setCurrentCell(row, 0)
            self.items.scrollToItem(self.items.item(row, 0), QAbstractItemView.PositionAtCenter)

    def delete_item(self):
        row = self.items.currentRow()
        if row >= 0:
            self.items.removeRow(row)
            self.recalculate()

    def handle_item_changed(self, item):
        try:
            column = item.column() if item else -1
            row = item.row() if item else -1
        except RuntimeError:
            return
        self.recalculate()
        if column == 0:
            self.mark_item_spelling(row)

    def update_spelling_marks(self):
        self.mark_notes_spelling()
        for row in range(self.items.rowCount()):
            self.mark_item_spelling(row)

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

    def mark_item_spelling(self, row):
        item = self.items.item(row, 0)
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
                "description": self.cell_text(row, 0),
                "qty": self.cell_text(row, 1),
                "price": self.cell_text(row, 2),
            })
        return items

    def cell_text(self, row, column):
        item = self.items.item(row, column)
        return item.text() if item else ""

    def totals(self):
        subtotal = 0
        for item in self.item_data():
            qty_text = str(item.get("qty", "")).strip()
            qty = clean_int(qty_text)
            price = clean_float(item.get("price", ""))
            if price and not qty_text:
                qty = 1
            subtotal += qty * price
        additional = clean_float(self.additional.text())
        total = subtotal + additional
        paid = clean_float(self.amount_paid.text()) if self.document_type == "invoice" else 0
        return subtotal, additional, total, paid, max(total - paid, 0)

    def recalculate(self):
        self.items.blockSignals(True)
        for row, item in enumerate(self.item_data()):
            qty_text = str(item.get("qty", "")).strip()
            qty = clean_int(qty_text)
            price = clean_float(item.get("price", ""))
            if price and not qty_text:
                qty = 1
            amount = qty * price
            amount_item = QTableWidgetItem(money(amount))
            amount_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            amount_item.setFlags(amount_item.flags() & ~Qt.ItemIsEditable)
            self.items.setItem(row, 3, amount_item)
        self.items.blockSignals(False)
        subtotal, _, total, _, balance = self.totals()
        self.subtotal_label.setText(money(subtotal))
        self.total_label.setText(money(total))
        self.balance_label.setText(money(balance))

    def document_data(self):
        subtotal, additional, total, paid, balance = self.totals()
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
            "amount_paid": self.amount_paid.text(),
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
            data["document_type"] == "invoice" and str(data["amount_paid"]).strip(),
            any(item["description"].strip() or str(item["qty"]).strip() or str(item["price"]).strip() for item in data["items"]),
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
            if not self.loaded_history:
                increase_number(self.document_type)
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))
            QMessageBox.information(self, "PDF Created", f"Saved and opened PDF:\n{pdf_path}")
            self._offer_sms(data)
            self.window.show_home()
        except Exception as error:
            QMessageBox.critical(
                self,
                "PDF Error",
                "The PDF could not be created.\n\n"
                "Make sure wkhtmltopdf is installed on this computer.\n\n"
                f"Details: {error}"
            )

    def _offer_sms(self, data):
        phone_raw = data.get("customer_phone_small", "").strip()
        if not phone_raw:
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

        box = QMessageBox(self)
        box.setWindowTitle(f"Send {doc_label} by Text")
        box.setText(
            f"Send a text to {phone_raw}?\n\n"
            f"This will open your phone's messaging app (via Phone Link) "
            f"pre-filled with the message. Just tap Send.\n\n"
            f"Message preview:\n{msg_body}"
        )
        send_btn = box.addButton(f"Open Messaging App", QMessageBox.AcceptRole)
        box.addButton("Skip", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == send_btn:
            phone_digits = re.sub(r"\D", "", phone_raw)
            sms_body = urllib.parse.quote(msg_body)
            QDesktopServices.openUrl(QUrl(f"sms:{phone_digits}?body={sms_body}"))

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
            paid = sum(clean_float(payment.get("amount")) for payment in payments)
            data["payments"] = payments
            data["amount_paid"] = str(paid)
            data["balance_due"] = max(clean_float(data["total"]) - paid, 0)
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
        document_title = "ESTIMATE" if self.document_type == "estimate" else "INVOICE"
        document_label = "Estimate" if self.document_type == "estimate" else "Invoice"
        recipient_label = "Estimate For" if self.document_type == "estimate" else "Invoice To"
        additional_label = "Other Charges"
        settings = get_settings()
        footer_parts = [
            settings.get("company_name", ""),
            settings.get("owner_name", ""),
            settings.get("phone", ""),
            settings.get("email", ""),
            settings.get("address", ""),
            settings.get("default_notes", ""),
        ]
        footer_html = "<br>".join(html.escape(part) for part in footer_parts if part)
        current_logo_path = logo_path()
        if current_logo_path and os.path.exists(current_logo_path):
            logo_html = f'<img src="{image_to_data_uri(current_logo_path)}" width="205">'
        else:
            logo_html = '<div style="font-size:24px; font-weight:bold; color:#4b7391;">ADAEL<br>CONSTRUCTION</div>'
        rows = ""
        for index, item in enumerate(data["items"], start=1):
            qty = clean_int(item.get("qty", "")) or (1 if clean_float(item.get("price", "")) else 0)
            price = clean_float(item.get("price", ""))
            rows += f"""
            <tr>
                <td>{index}</td>
                <td>{html.escape(item.get("description", ""))}</td>
                <td>{qty}</td>
                <td>{money(price)}</td>
                <td>{money(qty * price)}</td>
            </tr>
            """

        payment_html = ""
        if self.document_type == "invoice":
            payment_html = f"""
            <div><strong>Amount Paid:</strong> {money(data["amount_paid"])}</div>
            <div><strong>Balance Due:</strong> {money(data["balance_due"])}</div>
            """

        signature_block = ""
        if self.document_type == "estimate":
            signature_block = """
            <div style="margin-top:36px; border-top: 1px solid #ccc; padding-top: 18px;">
                <table style="width:100%; font-size:13px; color:#444;">
                    <tr>
                        <td style="width:48%; padding-right:16px;">
                            <div style="border-bottom:1px solid #333; height:38px; margin-bottom:6px;"></div>
                            <div><strong>Customer Signature</strong></div>
                        </td>
                        <td style="width:4%;"></td>
                        <td style="width:48%;">
                            <div style="border-bottom:1px solid #333; height:38px; margin-bottom:6px;"></div>
                            <div><strong>Date</strong></div>
                        </td>
                    </tr>
                </table>
                <div style="margin-top:10px; font-size:11px; color:#666; text-align:center; font-style:italic;">
                    By signing this document the customer agrees to the services and conditions outlined in this document.
                </div>
            </div>"""

        pdf_html = f"""
        <html>
        <head>
        <style>
            body {{ font-family: "Segoe UI", Arial, sans-serif; padding: 24px 34px; color: #222; }}
            .top {{ display: table; width: 100%; height: 126px; margin-bottom: 22px; }}
            .logo {{ display: table-cell; width: 245px; vertical-align: middle; }}
            .title {{ display: table-cell; vertical-align: middle; background: {BRAND_BLUE}; color: white; text-align: right; padding-right: 24px; }}
            .title h1 {{ font-size: 34px; margin: 0 0 10px; }}
            .title p {{ font-size: 18px; margin: 0; line-height: 1.55; }}
            .section-label {{ color: {BRAND_BLUE}; font-size: 16px; font-weight: bold; }}
            .customer-name {{ font-size: 22px; font-weight: bold; margin: 7px 0; }}
            .customer-details {{ font-size: 18px; line-height: 1.6; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
            th {{ background: {BRAND_BLUE}; color: white; padding: 8px; }}
            td {{ border: 1px solid #c7d7e4; padding: 8px; }}
            tr:nth-child(odd) td {{ background: #e8f1f7; }}
            .summary {{ display: table; width: 100%; margin-top: 24px; }}
            .notes {{ display: table-cell; width: 58%; border: 1px solid #c7d7e4; background: #f7fafc; padding: 12px; min-height: 70px; font-size: 16px; vertical-align: top; }}
            .summary-spacer {{ display: table-cell; width: 24px; }}
            .totals {{ display: table-cell; width: 320px; border: 1px solid #c7d7e4; font-size: 14px; vertical-align: top; }}
            .totals-lines {{ padding: 10px 14px; line-height: 1.55; }}
            .total-bar {{ background: {BRAND_BLUE}; color: white; display: flex; justify-content: space-between; padding: 10px 14px; font-size: 16px; font-weight: bold; }}
            .footer {{ margin-top: 28px; text-align: center; font-size: 12px; line-height: 1.35; }}
        </style>
        </head>
        <body>
            <div class="top">
                <div class="logo">{logo_html}</div>
                <div class="title">
                    <h1>{document_title}</h1>
                    <p><strong>{document_label} No:</strong> {html.escape(data["invoice_number"])}<br>
                    <strong>Date:</strong> {html.escape(data["invoice_date"])}{('<br><strong>Project:</strong> ' + html.escape(data.get('project_name', ''))) if data.get('project_name', '').strip() else ''}</p>
                </div>
            </div>
            <div class="section-label">{recipient_label}:</div>
            <div class="customer-name">{html.escape(data["customer_name_big"] or "Customer Name")}</div>
            <div class="customer-details">
                <div>{html.escape(data["customer_phone_small"])}</div>
                <div>{html.escape(data["customer_email_small"])}</div>
                <div>{html.escape(data["customer_address_small"])}</div>
                <div>{html.escape(data["customer_city_state_zip"])}</div>
            </div>
            <table>
                <tr><th>NO</th><th>DESCRIPTION</th><th>QTY</th><th>UNIT PRICE</th><th>AMOUNT</th></tr>
                {rows}
            </table>
            <div class="summary">
                <div class="notes"><div class="section-label">Notes:</div>{html.escape(data["notes"])}</div>
                <div class="summary-spacer"></div>
                <div class="totals">
                    <div class="totals-lines">
                        <div><strong>Subtotal:</strong> {money(data["subtotal"])}</div>
                        <div><strong>{additional_label}:</strong> {money(data["additional_subtotal"])}</div>
                        {payment_html}
                    </div>
                    <div class="total-bar"><span>TOTAL</span><span>{money(data["total"])}</span></div>
                </div>
            </div>
            <div class="footer">{footer_html}</div>
            {signature_block}
        </body>
        </html>
        """
        folder = "estimates" if self.document_type == "estimate" else "invoices"
        output_dir = PREVIEW_DIR if preview else os.path.join(APP_DIR, folder)
        os.makedirs(output_dir, exist_ok=True)
        if preview:
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


def check_for_update():
    """Returns (download_url, version_string) if a newer build exists online, else None.
    Never raises - any problem (no internet, GitHub down, no release yet) just
    means no update is found, and the app opens normally."""
    try:
        request = urllib.request.Request(
            UPDATE_FEED_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "AdaelInvoiceApp"},
        )
        with urllib.request.urlopen(request, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))

        remote_version = data.get("tag_name", "")
        if _version_tuple(remote_version) <= _version_tuple(CURRENT_VERSION):
            return None

        for asset in data.get("assets", []):
            if asset.get("name", "").lower().endswith(".exe"):
                return asset.get("browser_download_url"), remote_version

        return None
    except Exception:
        return None


def download_and_relaunch(download_url):
    """Downloads the new exe, writes a tiny helper script that swaps it in
    after this process exits, and launches that helper. Returns True if the
    handoff succeeded (caller should then exit immediately)."""
    if not getattr(sys, "frozen", False):
        return False  # only self-update the real built .exe, never the dev script

    current_exe = sys.executable
    exe_dir = os.path.dirname(current_exe)
    new_exe_path = os.path.join(exe_dir, "_update_download.exe")
    updater_bat_path = os.path.join(exe_dir, "_apply_update.bat")

    try:
        with urllib.request.urlopen(download_url, timeout=60) as response:
            with open(new_exe_path, "wb") as out_file:
                shutil.copyfileobj(response, out_file)
    except Exception:
        return False

    bat_contents = (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'move /Y "{new_exe_path}" "{current_exe}"\r\n'
        f'start "" "{current_exe}"\r\n'
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
    except Exception:
        return False

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
        QWidget#totalsPanel {
            background: #ffffff;
            border: 1px solid #c7d7e4;
            border-radius: 6px;
            padding: 14px;
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
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_path = os.path.join(APP_DIR, "desktop_app_error.log")
        with open(log_path, "w") as log_file:
            log_file.write(traceback.format_exc())
        raise
