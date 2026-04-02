import sys

try:
    import requests
    REQUESTS_INSTALLED = True
except ImportError:
    REQUESTS_INSTALLED = False

# Gemini API Config
GEMINI_API_KEY = "AIzaSyDX6QyjGovw_42klLrTLe2tfWg10B283jI"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
GEMINI_HEADERS = {
    "Content-Type": "application/json"
}

# Trends Mappings
CAT_MAP = {
    "All Categories": 0, 
    "Arts & Entertainment": 3, 
    "Autos & Vehicles": 47, 
    "Beauty & Fitness": 44, 
    "Games": 8
}

PROP_MAP = {
    "Youtube Search": "youtube", 
    "YouTube Search": "youtube", 
    "Web Search": "", 
    "Image Search": "images", 
    "News Search": "news", 
    "Google Shopping": "froogle"
}

GEO_MAP = {
    "Worldwide": "", 
    "United States": "US", 
    "Viet Nam": "VN", 
    "United Kingdom": "GB", 
    "Japan": "JP"
}

TIME_MAP = {
    "Past 30 days": "today 1-m", 
    "Past 7 days": "now 7-d", 
    "Past 12 months": "today 12-m", 
    "2004 - present": "all"
}

# Stylesheets
MAIN_STYLE = """
QMainWindow { background-color: #121212; }
QWidget { color: #ffffff; font-family: "Segoe UI", Arial, sans-serif; font-size: 14px; }
#sidebar { background-color: #1a1a1a; border-right: 1px solid #333333; }
#sidebar_title { color: #e50914; letter-spacing: 1px; }
#sidebar_subtitle { color: #aaaaaa; }
#navbar { background-color: #1e1e1e; border-bottom: 2px solid #333333; }
QLabel#inactive_tab { color: #aaaaaa; padding: 20px 15px; font-size: 15px; }
QLabel#inactive_tab:hover { color: #ffffff; background-color: #252525; }
QLabel#active_tab { color: #ffffff; background-color: #2a2a2a; padding: 20px 15px; border-bottom: 3px solid #e50914; font-weight: bold; font-size: 15px; }
QFrame#input_frame { background-color: #1e1e1e; border-radius: 8px; border: 1px solid #333333; }
QLabel#header_label { color: #f1f1f1; }
QLabel#input_label { color: #bbbbbb; font-weight: 500; }
QLabel#question_icon { background-color: #e50914; color: #ffffff; border-radius: 8px; font-size: 11px; font-weight: bold; }
QLineEdit { background-color: #2b2b2b; border: 1px solid #444444; padding: 8px 12px; border-radius: 5px; color: #ffffff; font-size: 15px; }
QLineEdit:focus { border: 2px solid #e50914; background-color: #333333; }
QComboBox { background-color: #2b2b2b; border: 1px solid #444444; padding: 8px 12px; border-radius: 5px; color: #ffffff; font-size: 14px; }
QComboBox:focus { border: 2px solid #e50914; }
QComboBox::drop-down { border: none; width: 30px; }
QComboBox QAbstractItemView { background-color: #333333; color: #ffffff; selection-background-color: #e50914; border: 1px solid #444444; }
QPushButton#generate_btn { background-color: #e50914; color: #ffffff; border: none; border-radius: 5px; font-weight: bold; font-size: 15px; padding: 8px 25px; }
QPushButton#generate_btn:hover { background-color: #ff1a25; }
QPushButton#generate_btn:pressed { background-color: #cc0812; }
QTableWidget { background-color: #1e1e1e; alternate-background-color: #252525; color: #ffffff; border: 1px solid #333333; border-radius: 6px; font-size: 14px; gridline-color: #333333; }
QTableWidget::item { padding: 5px; border-bottom: 1px solid #2a2a2a; }
QTableWidget::item:selected { background-color: #3d141e; color: #ffffff; }
QHeaderView::section { background-color: #2b2b2b; color: #ffffff; font-weight: bold; padding: 8px 5px; border: none; border-right: 1px solid #333333; border-bottom: 2px solid #333333; }
QTableCornerButton::section { background-color: #2b2b2b; border: none; border-bottom: 2px solid #333333; }

QPushButton#bottom_red_btn { background-color: #e50914; color: #ffffff; border: none; border-radius: 4px; font-weight: bold; font-size: 13px; padding: 7px 18px; }
QPushButton#bottom_red_btn:hover { background-color: #ff1a25; }
QPushButton#bottom_red_btn:pressed { background-color: #cc0812; }
QCheckBox#toggle_switch { color: #ffffff; font-weight: bold; font-size: 13px; spacing: 8px; }
QCheckBox#toggle_switch::indicator { width: 36px; height: 18px; border-radius: 9px; background-color: #444444; border: 2px solid #333333; }
QCheckBox#toggle_switch::indicator:checked { background-color: #e50914; }
"""
