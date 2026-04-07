MAIN_STYLE = """
QMainWindow { background-color: #eef3f8; }
QWidget {
    color: #18202a;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QFrame#sidebar {
    background-color: #f5f8fc;
    border-right: 1px solid #dbe3ee;
}
QFrame#topbar {
    background-color: #ffffff;
    border-bottom: 1px solid #dbe3ee;
}
QFrame#content_card {
    background-color: #ffffff;
    border: 1px solid #dbe3ee;
    border-radius: 14px;
}
QFrame#metric_card {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2287d8, stop:1 #65f2b8);
    border: none;
    border-radius: 14px;
}
QFrame#channel_card {
    background-color: #ffffff;
    border: 1px solid #dbe3ee;
    border-radius: 18px;
}
QLabel#app_title {
    color: #18202a;
    font-size: 20px;
    font-weight: 700;
}
QLabel#section_title {
    color: #18202a;
    font-size: 16px;
    font-weight: 700;
}
QLabel#muted_label {
    color: #6d7886;
}
QLabel#sidebar_logo {
    color: #111111;
    font-size: 22px;
    font-weight: 800;
    padding: 4px 0;
}
QToolButton#sidebar_btn {
    background-color: transparent;
    color: #4d5867;
    border: none;
    padding: 8px 10px;
    text-align: left;
    border-radius: 10px;
    font-size: 13px;
}
QToolButton#sidebar_btn:hover {
    background-color: #eaf0f8;
    color: #18202a;
}
QToolButton#sidebar_btn[active="true"] {
    background-color: #111827;
    color: #ffffff;
    font-weight: 700;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #18202a;
    border: 1px solid #c9d4e2;
    border-radius: 10px;
    padding: 7px 9px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 2px solid #2287d8;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QPushButton {
    background-color: #1f2937;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton:hover { background-color: #111827; }
QPushButton#primary_btn {
    background-color: #2452d6;
}
QPushButton#primary_btn:hover {
    background-color: #1f46b6;
}
QPushButton#accent_btn {
    background-color: #0f172a;
}
QPushButton#ghost_btn {
    background-color: #ffffff;
    color: #18202a;
    border: 1px solid #c9d4e2;
}
QPushButton#ghost_btn:hover {
    background-color: #f5f8fc;
}
QScrollArea {
    border: none;
    background: transparent;
}
QTableWidget {
    background-color: #ffffff;
    color: #18202a;
    border: 1px solid #dbe3ee;
    border-radius: 10px;
    gridline-color: #e6edf5;
    selection-background-color: #e8f2ff;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #f5f8fc;
    color: #18202a;
    border: none;
    border-right: 1px solid #dbe3ee;
    border-bottom: 1px solid #dbe3ee;
    padding: 8px;
    font-weight: 700;
}
QCheckBox {
    color: #18202a;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QRadioButton {
    color: #18202a;
}
"""
