from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QFrame, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QMenu, QCheckBox, QApplication, QSpinBox, QTextEdit, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QFont, QColor, QBrush, QAction
import json
import random
import re

from utils.constants import REQUESTS_INSTALLED
from core.keyword_generator import generate_keywords_api
from ui.components import ImportVolumeDialog

class KeywordsTab(QWidget):
    send_to_trends_signal = pyqtSignal(list)
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window # Reference to main app for status bar etc.
        self.select_all_state = False
        self._model_value_by_label = {}
        self.setup_ui()
        
    def setup_ui(self):
        content_layout = QVBoxLayout(self)
        content_layout.setContentsMargins(35, 30, 35, 30)
        content_layout.setSpacing(25)
        
        # Header
        header_label = QLabel("Keywords Tool")
        header_label.setObjectName("header_label")
        header_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        content_layout.addWidget(header_label)
        
        # Input Row Container
        input_frame = QFrame()
        input_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        input_frame.setObjectName("input_frame")
        input_grid_layout = QGridLayout(input_frame)
        input_grid_layout.setContentsMargins(20, 20, 20, 20)
        input_grid_layout.setHorizontalSpacing(16)
        input_grid_layout.setVerticalSpacing(12)
        
        # --- Seed Keyword Section ---
        seed_layout = QVBoxLayout()
        seed_layout.setSpacing(8)
        
        seed_label_layout = QHBoxLayout()
        seed_label = QLabel("Seed keyword(s):")
        seed_label.setObjectName("input_label")
        
        question_icon = QLabel("?")
        question_icon.setObjectName("question_icon")
        question_icon.setFixedSize(16, 16)
        question_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        seed_label_layout.addWidget(seed_label)
        seed_label_layout.addWidget(question_icon)
        seed_label_layout.addStretch()
        
        self.seed_input = QLineEdit()
        self.seed_input.setPlaceholderText("Enter seed keyword (e.g. dog toy or dog * toy)")
        self.seed_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.seed_input.setMinimumWidth(220)
        self.seed_input.setMinimumHeight(42)
        
        seed_layout.addLayout(seed_label_layout)
        seed_layout.addWidget(self.seed_input)
        
        # --- Country Section ---
        country_layout = QVBoxLayout()
        country_layout.setSpacing(8)
        
        country_label = QLabel("Country:")
        country_label.setObjectName("input_label")
        self.country_combo = QComboBox()
        self.country_combo.addItems([
            "Worldwide", "United States", "Viet Nam", "United Kingdom", "Japan", "South Korea", 
            "India", "Brazil", "Germany", "France", "Spain", "Italy", "Thailand", 
            "Indonesia", "Russia", "Mexico", "Turkey", "Philippines", "Australia", "Canada"
        ])
        self.country_combo.setMinimumHeight(42)
        self.country_combo.setMinimumWidth(120)
        
        country_layout.addWidget(country_label)
        country_layout.addWidget(self.country_combo)
        
        # --- Search Range Section ---
        range_layout = QVBoxLayout()
        range_layout.setSpacing(8)
        
        range_label = QLabel("Search range:")
        range_label.setObjectName("input_label")
        self.range_combo = QComboBox()
        self.range_combo.addItems(["a - z, 0 - 9 (after seed keyword)", "a - z (after seed keyword)", "0 - 9 (after seed keyword)"])
        self.range_combo.setMinimumHeight(42)
        self.range_combo.setMinimumWidth(210)
        
        range_layout.addWidget(range_label)
        range_layout.addWidget(self.range_combo)

        # --- Model Section ---
        model_layout = QVBoxLayout()
        model_layout.setSpacing(8)

        model_label = QLabel("Model:")
        model_label.setObjectName("input_label")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(42)
        self.model_combo.setMinimumWidth(180)
        self._setup_gemini_model_choices()

        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)

        # --- Prompt Mode Section ---
        prompt_mode_layout = QVBoxLayout()
        prompt_mode_layout.setSpacing(8)

        prompt_mode_label_layout = QHBoxLayout()
        prompt_mode_label = QLabel("Prompt Mode:")
        prompt_mode_label.setObjectName("input_label")
        self.prompt_mode_help_icon = QLabel("?")
        self.prompt_mode_help_icon.setObjectName("question_icon")
        self.prompt_mode_help_icon.setFixedSize(16, 16)
        self.prompt_mode_help_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt_mode_label_layout.addWidget(prompt_mode_label)
        prompt_mode_label_layout.addWidget(self.prompt_mode_help_icon)
        prompt_mode_label_layout.addStretch()
        self.prompt_mode_combo = QComboBox()
        self.prompt_mode_combo.addItems([
            "Balanced",
            "Balanced v2",
            "Broad Seed",
            "Sub Niche",
            "Micro Niche",
            "Deep Niche",
            "Micro Niche Expansion",
            "Seed Expansion Only",
            "Custom",
        ])
        self.prompt_mode_combo.setCurrentText("Balanced")
        self.prompt_mode_combo.setMinimumHeight(42)
        self.prompt_mode_combo.setMinimumWidth(150)
        self.prompt_mode_combo.setToolTip("Choose how aggressively Gemini should expand the seed keyword.")

        prompt_mode_layout.addLayout(prompt_mode_label_layout)
        prompt_mode_layout.addWidget(self.prompt_mode_combo)

        # --- Count Section ---
        count_layout = QVBoxLayout()
        count_layout.setSpacing(8)

        count_label = QLabel("Keyword count:")
        count_label.setObjectName("input_label")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(10, 500)
        self.count_spin.setSingleStep(10)
        self.count_spin.setValue(10)
        self.count_spin.setMinimumHeight(42)
        self.count_spin.setMinimumWidth(95)
        self.count_spin.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.count_spin.setStyleSheet("""
            QSpinBox {
                background-color: #2b2b2b;
                border: 1px solid #444444;
                padding: 8px 12px;
                border-radius: 5px;
                color: #ffffff;
                font-size: 14px;
            }
            QSpinBox:focus {
                border: 2px solid #e50914;
                background-color: #333333;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 18px;
                border: none;
                background: transparent;
            }
            QSpinBox::up-arrow, QSpinBox::down-arrow {
                width: 8px;
                height: 8px;
            }
        """)

        count_layout.addWidget(count_label)
        count_layout.addWidget(self.count_spin)
        
        # --- Generate Button ---
        self.generate_btn = QPushButton("✓ Generate")
        self.generate_btn.setObjectName("generate_btn")
        self.generate_btn.setMinimumHeight(42)
        self.generate_btn.setMinimumWidth(150)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.generate_btn.clicked.connect(self.generate_keywords)
        self.generate_btn.setText("Generate")
        
        # One-row compact layout.
        input_grid_layout.addLayout(seed_layout, 0, 0, 1, 1)
        input_grid_layout.addLayout(country_layout, 0, 1, 1, 1)
        input_grid_layout.addLayout(range_layout, 0, 2, 1, 1)
        input_grid_layout.addLayout(model_layout, 0, 3, 1, 1)
        input_grid_layout.addLayout(prompt_mode_layout, 0, 4, 1, 1)
        input_grid_layout.addLayout(count_layout, 0, 5, 1, 1)
        input_grid_layout.addWidget(self.generate_btn, 0, 6, 1, 1, alignment=Qt.AlignmentFlag.AlignBottom)
        input_grid_layout.setColumnStretch(0, 3)
        input_grid_layout.setColumnStretch(1, 2)
        input_grid_layout.setColumnStretch(2, 3)
        input_grid_layout.setColumnStretch(3, 2)
        input_grid_layout.setColumnStretch(4, 2)
        input_grid_layout.setColumnStretch(5, 1)
        input_grid_layout.setColumnStretch(6, 1)
        
        content_layout.addWidget(input_frame)

        # --- Custom Prompt Section (UI only for now) ---
        self.custom_prompt_frame = QFrame()
        self.custom_prompt_frame.setObjectName("input_frame")
        self.custom_prompt_frame.setVisible(False)
        custom_prompt_layout = QVBoxLayout(self.custom_prompt_frame)
        custom_prompt_layout.setContentsMargins(20, 18, 20, 18)
        custom_prompt_layout.setSpacing(10)

        custom_prompt_header = QHBoxLayout()
        custom_prompt_label = QLabel("Custom Prompt:")
        custom_prompt_label.setObjectName("input_label")
        self.custom_prompt_hint = QLabel("Used only when Prompt Mode = Custom")
        self.custom_prompt_hint.setObjectName("selection_label")
        self.custom_prompt_hint.setStyleSheet("color: #9a9a9a; font-size: 12px;")
        self.custom_prompt_toggle_btn = QPushButton("Hide")
        self.custom_prompt_save_btn = QPushButton("Save Prompt")
        self.custom_prompt_load_btn = QPushButton("Load Prompt")
        self.custom_prompt_random_btn = QPushButton("Random Prompt")
        self.custom_prompt_similar_btn = QPushButton("Similar Prompt")
        self.custom_prompt_toggle_btn.setObjectName("bottom_red_btn")
        self.custom_prompt_save_btn.setObjectName("bottom_red_btn")
        self.custom_prompt_load_btn.setObjectName("bottom_red_btn")
        self.custom_prompt_random_btn.setObjectName("bottom_red_btn")
        self.custom_prompt_similar_btn.setObjectName("bottom_red_btn")
        self.custom_prompt_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_prompt_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_prompt_load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_prompt_random_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_prompt_similar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_prompt_toggle_btn.setFixedHeight(30)
        self.custom_prompt_save_btn.setFixedHeight(30)
        self.custom_prompt_load_btn.setFixedHeight(30)
        self.custom_prompt_random_btn.setFixedHeight(30)
        self.custom_prompt_similar_btn.setFixedHeight(30)
        self.custom_prompt_toggle_btn.setMinimumWidth(70)
        self.custom_prompt_save_btn.setMinimumWidth(105)
        self.custom_prompt_load_btn.setMinimumWidth(105)
        self.custom_prompt_random_btn.setMinimumWidth(118)
        self.custom_prompt_similar_btn.setMinimumWidth(112)
        custom_prompt_header.addWidget(custom_prompt_label)
        custom_prompt_header.addStretch()
        custom_prompt_header.addWidget(self.custom_prompt_hint)
        custom_prompt_header.addWidget(self.custom_prompt_random_btn)
        custom_prompt_header.addWidget(self.custom_prompt_similar_btn)
        custom_prompt_header.addWidget(self.custom_prompt_load_btn)
        custom_prompt_header.addWidget(self.custom_prompt_save_btn)
        custom_prompt_header.addWidget(self.custom_prompt_toggle_btn)

        self.custom_prompt_body = QWidget()
        custom_prompt_body_layout = QVBoxLayout(self.custom_prompt_body)
        custom_prompt_body_layout.setContentsMargins(0, 0, 0, 0)
        custom_prompt_body_layout.setSpacing(0)
        self.custom_prompt_input = QTextEdit()
        self.custom_prompt_input.setPlaceholderText(
            "Paste your custom English prompt here. This is UI only for now; backend will be connected in the next step."
        )
        self.custom_prompt_input.setMinimumHeight(120)
        self.custom_prompt_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.custom_prompt_input.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #111111;
                border: 1px solid #444444;
                border-radius: 5px;
                padding: 8px;
                selection-background-color: #e50914;
                selection-color: #ffffff;
            }
        """)
        custom_prompt_body_layout.addWidget(self.custom_prompt_input)

        custom_prompt_layout.addLayout(custom_prompt_header)
        custom_prompt_layout.addWidget(self.custom_prompt_body)
        content_layout.addWidget(self.custom_prompt_frame)

        self._custom_prompt_collapsed = False
        self.custom_prompt_load_btn.clicked.connect(self._load_custom_prompt)
        self.custom_prompt_random_btn.clicked.connect(self._fill_random_custom_prompt)
        self.custom_prompt_similar_btn.clicked.connect(self._fill_similar_custom_prompt)
        self.custom_prompt_save_btn.clicked.connect(self._save_custom_prompt)
        self.custom_prompt_toggle_btn.clicked.connect(self._toggle_custom_prompt_body)
        self.prompt_mode_combo.currentTextChanged.connect(self._handle_prompt_mode_ui)
        self._handle_prompt_mode_ui(self.prompt_mode_combo.currentText())
        
        # ====================
        # DATA GRID
        # ====================
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["[ Click ] All", "🔍 Rank", "🔍 Word Count", "🔍 Character Count", "🔍 Seed", "🔍 Keyword"])
        self.table.horizontalHeader().sectionClicked.connect(self.handle_header_clicked)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 150)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemChanged.connect(self.handle_checkbox_change)
        
        content_layout.addWidget(self.table, stretch=1)
        
        # ====================
        # BOTTOM STATUS & TOOLBAR
        # ====================
        bottom_toolbar = QFrame()
        bottom_toolbar.setObjectName("bottom_toolbar")
        bottom_layout = QHBoxLayout(bottom_toolbar)
        bottom_layout.setContentsMargins(0, 5, 0, 0)
        
        # Left: Volume Data
        self.btn_volume = QPushButton("Volume Data")
        self.btn_volume.setObjectName("bottom_red_btn")
        self.btn_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.setup_volume_menu()
        bottom_layout.addWidget(self.btn_volume)
        bottom_layout.addStretch()
        
        # Center: Toggle + Selection Label
        center_widget = QWidget()
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(20)
        
        self.toggle_bilingual = QCheckBox("Song ngữ")
        self.toggle_bilingual.setObjectName("toggle_switch")
        self.toggle_bilingual.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.selection_label = QLabel("Total Items: 0  |  Selected rows: 0")
        self.selection_label.setObjectName("selection_label")
        self.selection_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.selection_label.setStyleSheet("color: #bbbbbb;")
        
        center_layout.addWidget(self.toggle_bilingual)
        center_layout.addWidget(self.selection_label)
        bottom_layout.addWidget(center_widget)
        bottom_layout.addStretch()
        
        # Right: File, Filters, Clear
        bottom_right_widget = QWidget()
        bottom_right_layout = QHBoxLayout(bottom_right_widget)
        bottom_right_layout.setContentsMargins(0, 0, 0, 0)
        bottom_right_layout.setSpacing(10)
        
        self.btn_file = QPushButton("File")
        self.btn_filters = QPushButton("Filters")
        self.btn_clear = QPushButton("Clear")
        
        for btn in [self.btn_file, self.btn_filters, self.btn_clear]:
            btn.setObjectName("bottom_red_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            bottom_right_layout.addWidget(btn)
            
        self.btn_filters.clicked.connect(self.show_filters_placeholder)
        self.btn_clear.clicked.connect(self.clear_grid_data)
        self.setup_file_menu()
            
        bottom_layout.addWidget(bottom_right_widget)
        content_layout.addWidget(bottom_toolbar)

    def setup_volume_menu(self):
        menu_vol = QMenu(self.btn_volume)
        menu_vol.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 25px 8px 20px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
        """)
        action_import = menu_vol.addAction("Import search volume data")
        action_import.triggered.connect(self.open_import_volume_dialog)
        
        ke_menu = menu_vol.addMenu("Keywords Everywhere")
        ke_menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 25px 8px 20px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
        """)
        action_ke_selected = ke_menu.addAction("Send SELECTED to Keywords Everywhere tool")
        action_ke_all = ke_menu.addAction("Send ALL to Keywords Everywhere tool")
        action_ke_open = ke_menu.addAction("Open the Keywords Everywhere tool")
        
        action_ke_selected.triggered.connect(lambda: self.mock_action("Send SELECTED to Keywords Everywhere tool"))
        action_ke_all.triggered.connect(lambda: self.mock_action("Send ALL to Keywords Everywhere tool"))
        action_ke_open.triggered.connect(lambda: self.mock_action("Open the Keywords Everywhere tool"))
        
        self.btn_volume.setMenu(menu_vol)

    def setup_file_menu(self):
        menu_file = QMenu(self.btn_file)
        menu_file.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 25px 8px 20px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
        """)
        action_csv = menu_file.addAction("Save to CSV")
        action_excel = menu_file.addAction("Save to Excel")
        action_txt = menu_file.addAction("Save to TXT")
        menu_file.addSeparator()
        action_copy_all = menu_file.addAction("Copy ALL Keywords")
        
        self.btn_file.setMenu(menu_file)
        
        action_csv.triggered.connect(lambda: self.export_data("csv"))
        action_excel.triggered.connect(lambda: self.export_data("excel"))
        action_txt.triggered.connect(lambda: self.export_data("txt"))
        action_copy_all.triggered.connect(self.copy_all_keywords)

    def _handle_prompt_mode_ui(self, mode_text):
        is_custom = str(mode_text or "").strip().lower() == "custom"
        hint_text = self._prompt_mode_hint_text(mode_text)
        if hasattr(self, "prompt_mode_help_icon"):
            self.prompt_mode_help_icon.setToolTip(hint_text)
            self.prompt_mode_help_icon.setStatusTip(hint_text)
        if hasattr(self, "prompt_mode_combo"):
            self.prompt_mode_combo.setToolTip(hint_text)
        if hasattr(self, "custom_prompt_frame"):
            self.custom_prompt_frame.setVisible(is_custom)
        if is_custom and hasattr(self, "custom_prompt_body"):
            self.custom_prompt_body.setVisible(not getattr(self, "_custom_prompt_collapsed", False))
            self.custom_prompt_toggle_btn.setText("Show" if getattr(self, "_custom_prompt_collapsed", False) else "Hide")

    def _prompt_mode_hint_text(self, mode_text):
        normalized = str(mode_text or "").strip().lower()
        if normalized == "balanced v2":
            return "Legacy balanced behavior before the newer seed-preserving rules and seed-biased ranking were added."
        if normalized == "broad seed":
            return "Broad parent-topic ideas. Good when the seed is still large and you want scalable branches."
        if normalized == "sub niche":
            return "Return child niches under the main topic. Standalone niche terms are allowed and do not need to repeat the parent seed."
        if normalized == "micro niche":
            return "Return very specific subtopics, problems, or audience slices inside the topic. No need to keep the parent seed at the front."
        if normalized == "deep niche":
            return "Go one to two levels deeper into subtopics, audience slices, and content angles."
        if normalized == "micro niche expansion":
            return "Best for niche-of-niche seeds like 'fish gaming'. Forces sharper sub-angles, formats, audiences, and use cases."
        if normalized == "seed expansion only":
            return "Keep the original seed phrase in almost every output and mainly expand with strong modifiers like at home, business, setup, cost, tips, or for beginners."
        if normalized == "custom":
            return "Use your own English prompt directly."
        return "Balanced mix of scalable opportunities and specific sub-niche ideas."

    def _toggle_custom_prompt_body(self):
        self._custom_prompt_collapsed = not getattr(self, "_custom_prompt_collapsed", False)
        if hasattr(self, "custom_prompt_body"):
            self.custom_prompt_body.setVisible(not self._custom_prompt_collapsed)
        if hasattr(self, "custom_prompt_toggle_btn"):
            self.custom_prompt_toggle_btn.setText("Show" if self._custom_prompt_collapsed else "Hide")

    def _save_custom_prompt(self):
        prompt_text = self._get_custom_prompt_text() if hasattr(self, "_get_custom_prompt_text") else ""
        if not prompt_text:
            QMessageBox.warning(self, "Empty Custom Prompt", "There is no custom prompt to save.")
            return

        default_name = "custom_prompt.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Custom Prompt",
            default_name,
            "Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(prompt_text)
            QMessageBox.information(self, "Saved", f"Custom prompt saved to:\n{file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _load_custom_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Custom Prompt",
            "",
            "Text Files (*.txt);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                prompt_text = handle.read()
            if hasattr(self, "custom_prompt_input"):
                self.custom_prompt_input.setPlainText(prompt_text)
            if getattr(self, "_custom_prompt_collapsed", False):
                self._toggle_custom_prompt_body()
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    def _fill_random_custom_prompt(self):
        prompt_text = self._build_random_custom_prompt()
        if hasattr(self, "custom_prompt_input"):
            self.custom_prompt_input.setPlainText(prompt_text)
        if getattr(self, "_custom_prompt_collapsed", False):
            self._toggle_custom_prompt_body()

    def _fill_similar_custom_prompt(self):
        current_text = self._get_custom_prompt_text()
        prompt_text = self._build_similar_custom_prompt(current_text)
        if hasattr(self, "custom_prompt_input"):
            self.custom_prompt_input.setPlainText(prompt_text)
        if getattr(self, "_custom_prompt_collapsed", False):
            self._toggle_custom_prompt_body()

    def _build_random_custom_prompt(self):
        seed_text = self.seed_input.text().strip() if hasattr(self, "seed_input") else ""
        target_country = self.country_combo.currentText().strip() if hasattr(self, "country_combo") else "Worldwide"
        target_count = int(self.count_spin.value()) if hasattr(self, "count_spin") else 10
        seed_value = seed_text or "[SEED_KEYWORD]"
        country_value = target_country or "Worldwide"
        templates = [
            (
                "You are a YouTube keyword strategist.\n"
                "Generate up to {count} strong YouTube keyword ideas related to \"{seed}\".\n"
                "Prioritize scalable opportunities, strong search intent, and keywords that can support many future videos.\n"
                "Avoid over-niche ideas too early. Keep the list practical and performance-oriented.\n"
                "Market focus: {country}.\n"
                "Return only a clean comma-separated list."
            ),
            (
                "You are an expert in discovering high-performing YouTube search terms.\n"
                "For the topic \"{seed}\", generate up to {count} keyword ideas that are broad enough to scale, but focused enough to attract intent-driven viewers.\n"
                "Prefer raw search terms, problem-first keywords, and repeatable content opportunities.\n"
                "Avoid generic filler and avoid going too deep unless the seed itself is already specific.\n"
                "Country focus: {country}.\n"
                "Output only a comma-separated list."
            ),
            (
                "Act as a YouTube niche expansion strategist.\n"
                "Starting from \"{seed}\", produce up to {count} keyword opportunities suitable for channels that want repeatable, searchable, monetizable content.\n"
                "Mix short keywords, practical problem terms, and a few strong phrase-level opportunities.\n"
                "Do not add commentary, numbering, or explanations.\n"
                "Geography: {country}.\n"
                "Return only comma-separated keywords."
            ),
            (
                "You are helping a creator find scalable YouTube keyword opportunities from the seed \"{seed}\".\n"
                "Generate up to {count} ideas for {country}.\n"
                "Favor keywords that can branch into multiple subtopics later, instead of micro-niches immediately.\n"
                "Prefer terms with clear search demand, cloning potential, and series potential.\n"
                "Return only a comma-separated list with no extra text."
            ),
        ]
        return random.choice(templates).format(count=target_count, seed=seed_value, country=country_value)

    def _build_similar_custom_prompt(self, current_text):
        current = str(current_text or "").strip()
        if not current:
            return self._build_random_custom_prompt()

        seed_text = self.seed_input.text().strip() if hasattr(self, "seed_input") else ""
        target_country = self.country_combo.currentText().strip() if hasattr(self, "country_combo") else "Worldwide"
        target_count = int(self.count_spin.value()) if hasattr(self, "count_spin") else 10
        seed_value = seed_text or "[SEED_KEYWORD]"
        country_value = target_country or "Worldwide"

        current = re.sub(r"\s+", " ", current).strip()
        current = re.sub(
            r"return only a clean comma-separated list\.?$",
            "",
            current,
            flags=re.IGNORECASE,
        ).strip()

        rewritten = self._rewrite_custom_prompt_template(
            current_text=current,
            seed_value=seed_value,
            country_value=country_value,
            target_count=target_count,
        )
        if rewritten:
            return rewritten

        variants = [
            (
                current
                + "\nAdd emphasis on scalable parent-topic opportunities before going into small sub-niches."
                + f"\nKeep the focus on YouTube search behavior in {country_value}."
            ),
            (
                current
                + "\nFavor short and medium-length keywords with strong cloning potential."
                + "\nInclude raw terms, problem-first terms, and a few phrase-based opportunities."
            ),
            (
                current
                + f"\nGenerate no more than {target_count} ideas connected to \"{seed_value}\"."
                + "\nPrefer opportunities that can later expand into multiple subtopics or content series."
            ),
            (
                current
                + "\nReduce generic blog-style phrases."
                + "\nIncrease preference for search-driven YouTube keywords with clearer viewer intent."
            ),
        ]
        return random.choice(variants).strip() + "\nReturn only a clean comma-separated list."

    def _rewrite_custom_prompt_template(self, current_text, seed_value, country_value, target_count):
        prompt = str(current_text or "").strip()
        if not prompt:
            return ""

        rewritten = prompt

        # Keep the same sentence structure, but update the most common variable fields.
        rewritten = re.sub(
            r"(?i)\b(?:exactly|up to|only)\s+\d+\b",
            f"only {target_count}",
            rewritten,
        )
        rewritten = re.sub(
            r'(?i)(related to\s+)(["\']?)([^,"\n]+)\2',
            lambda m: f'{m.group(1)}{seed_value}',
            rewritten,
            count=1,
        )
        rewritten = re.sub(
            r'(?i)(for the topic\s+)(["\'])(.+?)\2',
            lambda m: f'{m.group(1)}"{seed_value}"',
            rewritten,
            count=1,
        )
        rewritten = re.sub(
            r'(?i)(seed\s+["\'])(.+?)(["\'])',
            lambda m: f'{m.group(1)}{seed_value}{m.group(3)}',
            rewritten,
            count=1,
        )
        rewritten = re.sub(
            r'(?i)(market focus:\s*)(.+?)(?=[\.\n]|$)',
            lambda m: f'{m.group(1)}{country_value}',
            rewritten,
            count=1,
        )
        rewritten = re.sub(
            r'(?i)(country focus:\s*)(.+?)(?=[\.\n]|$)',
            lambda m: f'{m.group(1)}{country_value}',
            rewritten,
            count=1,
        )
        rewritten = re.sub(
            r'(?i)(geography:\s*)(.+?)(?=[\.\n]|$)',
            lambda m: f'{m.group(1)}{country_value}',
            rewritten,
            count=1,
        )
        rewritten = re.sub(
            r'(?i)(generate\s+(?:up to|only)\s+\d+\s+ideas\s+for\s+)(.+?)(?=[\.\n]|$)',
            lambda m: f'{m.group(1)}{country_value}',
            rewritten,
            count=1,
        )

        has_country_clause = any(
            marker in rewritten.lower()
            for marker in ("market focus:", "country focus:", "geography:")
        )
        has_generate_for_country = bool(
            re.search(r'(?i)generate\s+(?:up to|only)\s+\d+\s+ideas\s+for\s+.+?(?=[\.\n]|$)', rewritten)
        )

        if rewritten == prompt and seed_value not in rewritten:
            return ""

        if not has_country_clause and not has_generate_for_country and country_value:
            rewritten = rewritten.strip() + f"\nMarket focus: {country_value}."

        if "comma-separated" not in rewritten.lower():
            rewritten = rewritten.strip() + "\nReturn only a clean comma-separated list."
        return rewritten.strip()

    def generate_keywords(self):
        if not REQUESTS_INSTALLED:
            QMessageBox.critical(self, "Missing Dependency", "The 'requests' module is missing. Please run:\n\npip install requests")
            return

        seed_text = self.seed_input.text().strip()
        target_country = self.country_combo.currentText()
        target_count = int(self.count_spin.value())
        provider = "gemini"
        model_name = self._selected_model_value()
        prompt_mode = self._selected_prompt_mode()
        prompt_mode_raw = self.prompt_mode_combo.currentText().strip() if hasattr(self, "prompt_mode_combo") else prompt_mode
        if not seed_text:
            QMessageBox.warning(self, "Empty Input", "Please enter a seed keyword first.")
            return
        if str(prompt_mode_raw or "").strip().lower() == "custom" and not self._get_custom_prompt_text():
            QMessageBox.warning(self, "Empty Custom Prompt", "Please enter a custom prompt first.")
            return
            
        self.generate_btn.setText("Generating...")
        self.generate_btn.setEnabled(False)
        QApplication.processEvents()
        
        prompt = self._resolve_generation_prompt(
            seed_text=seed_text,
            target_country=target_country,
            target_count=target_count,
            bilingual=self.toggle_bilingual.isChecked(),
            prompt_mode=prompt_mode,
        )
        try:
            content = generate_keywords_api(prompt, provider=provider, model_name=model_name)
            generated_list = self._parse_generated_keywords(content, target_count)
        except Exception as e:
            QMessageBox.critical(self, "API Error", str(e))
            generated_list = []
        finally:
            self.generate_btn.setText("✓ Generate")
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("Generate")
            
        if not generated_list:
            return
            
        results = []
        seen = set()
        rank = 1
        for keyword in generated_list:
            if len(results) >= target_count:
                break
            keyword = " ".join(keyword.split())
            if keyword.lower() not in seen:
                seen.add(keyword.lower())
                results.append((str(rank), str(len(keyword.split())), str(len(keyword)), seed_text, keyword))
                rank += 1
            
        self.populate_table(results)

    def _build_keyword_generation_prompt(self, seed_text, target_country, target_count, bilingual=False, prompt_mode="Balanced"):
        seed_scope = self._classify_seed_scope(seed_text)
        normalized_mode = self._normalize_prompt_mode(prompt_mode)
        if normalized_mode == "balanced v2":
            return self._build_legacy_balanced_prompt(
                seed_text=seed_text,
                target_country=target_country,
                target_count=target_count,
                bilingual=bilingual,
                seed_scope=seed_scope,
            )

        normalized_seed = " ".join(str(seed_text or "").strip().lower().split())
        seed_tokens = [token for token in normalized_seed.split() if token]
        preserve_seed_phrase = len(seed_tokens) >= 2 and "*" not in normalized_seed
        native_rules = ""
        if target_country != "Worldwide":
            native_rules = (
                f"- Geography focus: {target_country}.\n"
                f"- Use the natural primary language spoken by YouTube viewers in {target_country}.\n"
                f"- Reflect realistic local search behavior, local slang if appropriate, and localized content angles.\n"
            )
        else:
            native_rules = (
                "- Geography focus: Worldwide.\n"
                "- Prefer globally understandable, broad-market YouTube search phrasing.\n"
            )

        bilingual_rule = ""
        if bilingual:
            bilingual_rule = (
                "- Bilingual mode: output each keyword as `native language keyword - English translation`.\n"
            )

        seed_phrase_rules = ""
        if preserve_seed_phrase:
            seed_phrase_rules = (
                f"- The seed phrase `{seed_text}` is already a meaningful niche phrase.\n"
                f"- Keep the core phrase `{seed_text}` or a very close direct variant in MOST outputs.\n"
                "- Expand mainly by adding high-intent modifiers after or around the seed phrase, such as:\n"
                "  - at home\n"
                "  - business\n"
                "  - for beginners\n"
                "  - setup\n"
                "  - equipment\n"
                "  - cost\n"
                "  - profit\n"
                "  - tutorial\n"
                "  - guide\n"
                "  - ideas\n"
                "  - tips\n"
                "  - mistakes\n"
                "  - method\n"
                "  - indoor\n"
                "  - backyard\n"
                "- Do NOT drift too far into adjacent topics unless they are still obviously inside the seed phrase.\n"
                f"- Good example style for `{seed_text}`: `{seed_text} at home`, `{seed_text} business`, `{seed_text} for beginners`, `{seed_text} setup`, `{seed_text} profit`.\n"
            )

        extra_seed_specific_rule = (
            "- If the seed is already narrow or weirdly specific, expand into actual content angles, not shallow paraphrases of the same phrase.\n"
        )

        if normalized_mode == "broad seed":
            scope_rules = (
                "- Prompt mode: BROAD SEED.\n"
                "- Prioritize broader, scalable, higher-demand YouTube keyword opportunities.\n"
                "- Stay at the strong parent-topic layer or one step below it.\n"
                "- Do NOT go too deep into tiny micro-niches unless the seed itself is already narrow.\n"
                "- Favor keywords that are easier to scale into many videos and easier to clone into multiple content branches.\n"
                "- Prefer a healthy mix of short root terms, strong problem terms, and only some broader phrases.\n"
                "- Example behavior for broad topics: `health` should produce outputs closer to `cramp`, `sleep`, `anxiety`, `weight loss`, `gut health`, not overly detailed micro-angles.\n"
            )
        elif normalized_mode == "sub niche":
            scope_rules = (
                "- Prompt mode: SUB NICHE.\n"
                "- Return strong child niches that sit one layer below the parent topic.\n"
                "- Standalone sub-niche terms are allowed and often preferred.\n"
                "- Do NOT force the parent seed to appear in every keyword.\n"
                "- Favor distinct niche branches, not tiny wording variations.\n"
                "- Good example behavior: if the seed is `health`, outputs can look like `cramps`, `sleep`, `anxiety`, `gut health`, `weight loss`, `hormones`, `skin care`.\n"
                "- Each output should still feel like a real YouTube niche or search direction, not a random vague word.\n"
            )
        elif normalized_mode == "micro niche":
            scope_rules = (
                "- Prompt mode: MICRO NICHE.\n"
                "- Return very specific subtopics, problems, audience slices, or intent phrases inside the topic.\n"
                "- Do NOT force the parent seed to appear in every output.\n"
                "- Go deeper than sub-niche mode, but keep every output human-searchable.\n"
                "- Favor terms with sharp intent, concrete use case, or obvious video angle.\n"
                "- Good example behavior: if the seed is `health`, outputs can look like `leg cramps at night`, `high cortisol symptoms`, `insulin resistance signs`, `period cramps relief`, `sleep anxiety`, `bloating after eating`.\n"
                "- Avoid generic filler and avoid full sentence outputs.\n"
            )
        elif normalized_mode == "deep niche":
            scope_rules = (
                "- Prompt mode: DEEP NICHE.\n"
                "- Go one to two layers deeper than normal into sub-niches, subtopics, and detailed content angles.\n"
                "- Favor keywords that can still support repeatable series, but allow narrower search opportunities.\n"
                "- It is acceptable to return more detailed and more specific YouTube search phrases than the balanced mode.\n"
                "- If the seed is already specific, expand it further into adjacent sub-problems, use cases, and audience slices.\n"
                "- For already-good niche phrases, prefer modifier expansions before jumping to loosely related adjacent branches.\n"
            )
        elif normalized_mode == "micro niche expansion":
            scope_rules = (
                "- Prompt mode: MICRO NICHE EXPANSION.\n"
                "- Treat the seed as a niche-of-a-niche starting point and expand downward into very specific, usable YouTube content branches.\n"
                "- Do NOT just paraphrase the seed keyword with tiny wording changes.\n"
                "- First priority: produce strong seed-preserving expansions with useful modifiers and intents.\n"
                "- Second priority: only after that, add a few tighter sub-angles that are still clearly inside the same niche.\n"
                "- For most outputs, add a real angle such as:\n"
                "  - audience slice\n"
                "  - subgenre or subtopic\n"
                "  - challenge or series format\n"
                "  - beginner vs advanced intent\n"
                "  - platform, device, game title, tool, or version\n"
                "  - problem, goal, mechanic, or use case\n"
                "  - comparison, mod, build, strategy, tutorial, or trend angle\n"
                "- If the seed already combines a topic with a parent niche, push into subtopics inside that combination.\n"
                "- Example behavior: for `fish gaming`, move toward outputs like specific fish game genres, fishing game mobile, fishing simulator beginner tips, fish game challenge ideas, fish game shorts ideas, cozy fishing games, fishing game pc, not just `fish gaming channel` or `fish gaming videos`.\n"
                "- At least 70 percent of the outputs should contain a real modifier, sub-angle, or use-case beyond the raw seed phrase.\n"
                "- Favor ideas that still feel searchable by humans and can become repeatable series, not random brainstorm fragments.\n"
            )
        elif normalized_mode == "seed expansion only":
            scope_rules = (
                "- Prompt mode: SEED EXPANSION ONLY.\n"
                f"- Keep the exact seed phrase `{seed_text}` in almost every output.\n"
                "- Your main job is to expand the seed by adding useful modifiers, not by drifting into adjacent topics.\n"
                "- Strong modifier examples include:\n"
                "  - at home\n"
                "  - business\n"
                "  - for beginners\n"
                "  - setup\n"
                "  - equipment\n"
                "  - cost\n"
                "  - profit\n"
                "  - mistakes\n"
                "  - tutorial\n"
                "  - tips\n"
                "  - guide\n"
                "  - ideas\n"
                "  - strategy\n"
                "  - indoor\n"
                "  - backyard\n"
                "- At least 80 percent of the outputs should contain the full seed phrase plus one or more meaningful modifiers.\n"
                "- Avoid adjacent branches unless they still visibly preserve the seed phrase.\n"
                f"- Good output style for `{seed_text}`: `{seed_text} at home`, `{seed_text} business`, `{seed_text} for beginners`, `{seed_text} setup`, `{seed_text} tips`.\n"
            )
        elif seed_scope == "broad":
            scope_rules = (
                "- The seed keyword is BROAD.\n"
                "- Return broader, stronger, higher-demand YouTube search terms inside this topic.\n"
                "- Stay at the main opportunity layer first.\n"
                "- Do NOT go too deep into tiny sub-niches too early.\n"
                "- Prefer scalable terms that can support many videos and larger search demand.\n"
                "- Example behavior: if the seed is `health`, outputs should look closer to `cramp`, `sick`, `lose weight`, `sleep`, `anxiety`, not ultra-specific micro-angles.\n"
            )
        else:
            scope_rules = (
                "- The seed keyword is already SPECIFIC.\n"
                "- You should expand into sub-niches, subtopics, and more detailed search opportunities inside this topic.\n"
                "- It is acceptable to go more specific because the seed is already narrow enough.\n"
            )

        return f"""You are a senior YouTube niche research strategist and keyword discovery expert.
 
 Your task is to generate up to {target_count} high-opportunity YouTube keyword ideas from the seed keyword below.
 
Seed keyword: "{seed_text}"

Strategy requirements:
- Focus on YouTube search intent, not blog SEO or generic topic brainstorming.
- Prefer keywords that suggest specific sub-niches, repeatable video series, clear audience intent, and practical monetization potential.
  - Favor ideas that can work for solo creators, faceless channels, Shorts, long-form, or both.
  - Avoid broad, generic, saturated, or vague keywords unless they are sharply narrowed.
  - Avoid filler variations that are only tiny wording changes.
  - Do NOT reject a keyword just because it is unusually short, niche, weird, or non-obvious.
  - If a short or uncommon keyword has strong YouTube performance potential, include it.
  - Some strong opportunities may be single-word or two-word terms. That is acceptable if the opportunity is real.
  {scope_rules}
  - Prefer keywords with stronger opportunity through one or more of these:
    - clearer audience
    - lower competition angle
    - better repeatable series potential
    - stronger search intent
    - easier production workflow
    - stronger monetization fit
  - Include a strong mix of keyword types when relevant:
    - raw short terms
    - symptom or problem-first terms
    - condition or topic terms
    - solution-seeking terms
    - long-tail search terms
    - series-friendly sub-niche terms
  - Especially for niches like health, finance, beauty, fitness, education, and software:
    - actively include short high-intent search terms if they have real performance potential
    - include pain-point words, symptom words, condition words, or problem words
    - do not over-convert everything into long-tail phrases
  - Think silently about:
    - searchability
    - niche specificity
    - series potential
    - faceless suitability
  - monetization potential
  - content repeatability
  - competition weakness
  {extra_seed_specific_rule}
  {seed_phrase_rules}

  Formatting rules:
  - Each keyword must be natural and human-searchable.
  - Prefer concise keywords, but allow longer keywords when they are more realistic or higher-opportunity.
  - Do not force unnatural phrasing just to keep the keyword short.
  - Some outputs should be very short when appropriate, including single-word and two-word terms.
  - If the seed keyword is broad, include some sharp high-signal short keywords related to the niche.
  - Do not output sentences, explanations, categories, bullet points, numbering, or commentary.
- Support wildcard * naturally if the seed keyword uses it.
{native_rules}{bilingual_rule}
Output rules:
  - Return ONLY a clean comma-separated list.
  - Return the best ideas first.
  - Return no more than {target_count} items.
- No numbering.
- No headers.
  - No quotation marks.
  - No markdown.
  - No extra notes.
  """

    def _build_legacy_balanced_prompt(self, seed_text, target_country, target_count, bilingual=False, seed_scope="broad"):
        if target_country != "Worldwide":
            native_rules = (
                f"- Geography focus: {target_country}.\n"
                f"- Use the natural primary language spoken by YouTube viewers in {target_country}.\n"
                f"- Reflect realistic local search behavior in {target_country}.\n"
            )
        else:
            native_rules = (
                "- Geography focus: Worldwide.\n"
                "- Prefer globally understandable YouTube search phrasing.\n"
            )

        bilingual_rule = ""
        if bilingual:
            bilingual_rule = (
                "- Bilingual mode: output each keyword as `native language keyword - English translation`.\n"
            )

        if seed_scope == "broad":
            scope_rules = (
                "- The seed keyword is BROAD.\n"
                "- Return broader, stronger, higher-demand YouTube search terms inside this topic.\n"
                "- Stay at the main opportunity layer first.\n"
                "- Do NOT go too deep into tiny sub-niches too early.\n"
                "- Prefer scalable terms that can support many videos and larger search demand.\n"
                "- Example behavior: if the seed is `health`, outputs should look closer to `cramp`, `sick`, `lose weight`, `sleep`, `anxiety`, not ultra-specific micro-angles.\n"
            )
        else:
            scope_rules = (
                "- The seed keyword is already SPECIFIC.\n"
                "- You should expand into sub-niches, subtopics, and more detailed search opportunities inside this topic.\n"
                "- It is acceptable to go more specific because the seed is already narrow enough.\n"
            )

        return f"""You are a senior YouTube niche research strategist and keyword discovery expert.

Your task is to generate up to {target_count} high-opportunity YouTube keyword ideas from the seed keyword below.

Seed keyword: "{seed_text}"

Strategy requirements:
- Focus on YouTube search intent, not blog SEO or generic topic brainstorming.
- Prefer keywords that suggest specific sub-niches, repeatable video series, clear audience intent, and practical monetization potential.
- Favor ideas that can work for solo creators, faceless channels, Shorts, long-form, or both.
- Avoid broad, generic, saturated, or vague keywords unless they are sharply narrowed.
- Avoid filler variations that are only tiny wording changes.
- Do NOT reject a keyword just because it is unusually short, niche, weird, or non-obvious.
- If a short or uncommon keyword has strong YouTube performance potential, include it.
- Some strong opportunities may be single-word or two-word terms. That is acceptable if the opportunity is real.
{scope_rules}
- Prefer keywords with stronger opportunity through one or more of these:
  - clearer audience
  - lower competition angle
  - better repeatable series potential
  - stronger search intent
  - easier production workflow
  - stronger monetization fit
- Include a strong mix of keyword types when relevant:
  - raw short terms
  - symptom or problem-first terms
  - condition or topic terms
  - solution-seeking terms
  - long-tail search terms
  - series-friendly sub-niche terms
- Especially for niches like health, finance, beauty, fitness, education, and software:
  - actively include short high-intent search terms if they have real performance potential
  - include pain-point words, symptom words, condition words, or problem words
  - do not over-convert everything into long-tail phrases
- Think silently about:
  - searchability
  - niche specificity
  - series potential
  - faceless suitability
  - monetization potential
  - content repeatability
  - competition weakness

Formatting rules:
- Each keyword must be natural and human-searchable.
- Prefer concise keywords, but allow longer keywords when they are more realistic or higher-opportunity.
- Do not force unnatural phrasing just to keep the keyword short.
- Some outputs should be very short when appropriate, including single-word and two-word terms.
- If the seed keyword is broad, include some sharp high-signal short keywords related to the niche.
- Do not output sentences, explanations, categories, bullet points, numbering, or commentary.
- Support wildcard * naturally if the seed keyword uses it.
{native_rules}{bilingual_rule}
Output rules:
- Return ONLY a clean comma-separated list.
- Return the best ideas first.
- Return no more than {target_count} items.
- No numbering.
- No headers.
- No quotation marks.
- No markdown.
- No extra notes.
"""

    def _normalize_prompt_mode(self, prompt_mode):
        text = str(prompt_mode or "").strip().lower()
        valid_modes = {
            "balanced",
            "balanced v2",
            "broad seed",
            "sub niche",
            "micro niche",
            "deep niche",
            "micro niche expansion",
            "seed expansion only",
            "custom",
        }
        return text if text in valid_modes else "balanced"

    def _selected_prompt_mode(self):
        if not hasattr(self, "prompt_mode_combo"):
            return "Balanced"
        selected = self.prompt_mode_combo.currentText().strip()
        if not selected:
            return "Balanced"
        if selected.lower() == "custom":
            return "Custom"
        return selected

    def _get_custom_prompt_text(self):
        if not hasattr(self, "custom_prompt_input"):
            return ""
        return self.custom_prompt_input.toPlainText().strip()

    def _resolve_generation_prompt(self, seed_text, target_country, target_count, bilingual, prompt_mode):
        if self._normalize_prompt_mode(prompt_mode) == "custom":
            return self._get_custom_prompt_text()
        return self._build_keyword_generation_prompt(
            seed_text=seed_text,
            target_country=target_country,
            target_count=target_count,
            bilingual=bilingual,
            prompt_mode=prompt_mode,
        )

    def _classify_seed_scope(self, seed_text):
        text = " ".join(str(seed_text or "").strip().lower().split())
        if not text:
            return "broad"

        specific_terms = {
            "cramp", "migraine", "anxiety", "bloating", "fatigue", "insomnia", "acid reflux",
            "constipation", "vertigo", "eczema", "psoriasis", "pcos", "adhd", "autism",
            "ibs", "scoliosis", "tinnitus", "sciatica",
        }
        broad_terms = {
            "health", "fitness", "beauty", "finance", "money", "business", "productivity",
            "gaming", "education", "sleep", "weight loss", "travel", "food", "diet",
            "software", "ai", "motivation", "study", "english", "workout", "skin care",
        }
        if text in specific_terms:
            return "specific"
        if text in broad_terms:
            return "broad"

        word_count = len(text.split())
        if "*" in text:
            return "specific"
        if word_count <= 1:
            return "broad"
        if word_count >= 3:
            return "specific"
        return "specific"

    def _parse_generated_keywords(self, raw_text, target_count):
        text = str(raw_text or "").strip()
        if not text:
            return []

        candidates = []

        # Try JSON first if the model ignored the formatting rule.
        parsed_json = None
        try:
            parsed_json = json.loads(text)
        except Exception:
            parsed_json = None

        if isinstance(parsed_json, list):
            candidates.extend(str(item).strip() for item in parsed_json if str(item).strip())
        elif isinstance(parsed_json, dict):
            for key in ("keywords", "ideas", "results", "items"):
                value = parsed_json.get(key)
                if isinstance(value, list):
                    candidates.extend(str(item).strip() for item in value if str(item).strip())
                    break

        if not candidates:
            parts = re.split(r"[\n,;]+", text)
            for part in parts:
                item = str(part).strip()
                if not item:
                    continue
                item = re.sub(r'^\s*[\-\*\u2022]+\s*', "", item)
                item = re.sub(r"^\s*\d+[\.\)\-:]\s*", "", item)
                item = item.strip().strip('"').strip("'").strip()
                if item:
                    candidates.append(item)

        cleaned = []
        seen = set()
        for item in candidates:
            normalized = " ".join(str(item).split()).strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(normalized)
            if len(cleaned) >= int(target_count):
                break
        return cleaned

    def _setup_gemini_model_choices(self):
        options = [
            ("Gemini 2.5 Flash", "gemini-2.5-flash"),
            ("Gemini 2.5 Flash Lite", "gemini-2.5-flash-lite"),
        ]
        self._model_value_by_label = {label: value for label, value in options}
        self.model_combo.clear()
        for label, _ in options:
            self.model_combo.addItem(label)
        self.model_combo.setCurrentIndex(1)

    def _selected_model_value(self):
        label = self.model_combo.currentText().strip() if hasattr(self, "model_combo") else ""
        return self._model_value_by_label.get(label, "")

    def populate_table(self, data):
        self.table.blockSignals(True)
        self.table.setRowCount(len(data))
        for row, row_data in enumerate(data):
            chk_item = QTableWidgetItem("")
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, chk_item)
            for col, text in enumerate(row_data, start=1):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col in [1, 2, 3] else Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.table.setItem(row, col, item)
            vol_item = QTableWidgetItem("-")
            vol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, vol_item)
        self.select_all_state = False
        header_item = self.table.horizontalHeaderItem(0)
        if header_item: header_item.setText("[ ] All")
        self.table.blockSignals(False)
        self.update_selection_count()

    def handle_header_clicked(self, logicalIndex):
        if logicalIndex == 0:
            self.select_all_state = not self.select_all_state
            new_state = Qt.CheckState.Checked if self.select_all_state else Qt.CheckState.Unchecked
            header_item = self.table.horizontalHeaderItem(0)
            if header_item: header_item.setText("[x] All" if self.select_all_state else "[ ] All")
            self.table.blockSignals(True)
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(new_state)
                    self.update_row_color(row, self.select_all_state)
            self.table.blockSignals(False)
            self.update_selection_count()

    def update_row_color(self, row, is_checked):
        bg_brush = QBrush(QColor("#4a1a25")) if is_checked else QBrush()
        for col in range(1, self.table.columnCount()):
            cell = self.table.item(row, col)
            if cell: cell.setBackground(bg_brush)

    def handle_checkbox_change(self, item):
        if item.column() == 0:
            self.update_row_color(item.row(), item.checkState() == Qt.CheckState.Checked)
            self.update_selection_count()

    def update_selection_count(self):
        count = sum(1 for row in range(self.table.rowCount()) if self.table.item(row, 0) and self.table.item(row, 0).checkState() == Qt.CheckState.Checked)
        total = self.table.rowCount()
        self.selection_label.setText(f"Total Items: {total}  |  Selected rows: {count}")

    def show_context_menu(self, position):
        menu = QMenu(self.table)
        menu.setStyleSheet("QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; } QMenu::item { padding: 8px 25px 8px 20px; } QMenu::item:selected { background-color: #e50914; color: #ffffff; }")
        
        menu.addAction("Send SELECTED to Trends tool").triggered.connect(lambda: self.send_to_trends(True))
        menu.addAction("Send ALL to Trends tool").triggered.connect(lambda: self.send_to_trends(False))
        menu.addSeparator()
        menu.addAction("Send to Video search tool").triggered.connect(self.send_to_video)
        menu.addAction("Send to Channel search tool").triggered.connect(self.send_to_channel)
        menu.addSeparator()
        
        vol_menu = menu.addMenu("Volume Data")
        vol_menu.addAction("Import search volume data").triggered.connect(self.open_import_volume_dialog)

        hashtags_menu = menu.addMenu("Hashtags")
        hashtags_menu.addAction("Copy SELECTED keywords as hashtags").triggered.connect(
            lambda: self.copy_keywords_as_hashtags(selected_only=True)
        )
        hashtags_menu.addAction("Copy ALL keywords as hashtags").triggered.connect(
            lambda: self.copy_keywords_as_hashtags(selected_only=False)
        )
        
        search_menu = menu.addMenu("Search")
        item = self.table.itemAt(position)
        keyword = self.table.item(item.row(), 5).text() if item and self.table.item(item.row(), 5) else ""
        search_menu.setEnabled(bool(keyword))
        from utils.helpers import web_search
        for engine in ["Google Trends", "Google Search", "YouTube Search", "Bing Search", "Amazon", "eBay"]:
            search_menu.addAction(engine).triggered.connect(lambda checked, e=engine, kw=keyword: web_search(e, kw))
            
        menu.exec(self.table.viewport().mapToGlobal(position))

    def send_to_trends(self, selected_only):
        keywords = []
        for row in range(self.table.rowCount()):
            if selected_only:
                chk = self.table.item(row, 0)
                if not (chk and chk.checkState() == Qt.CheckState.Checked): continue
            kw_item = self.table.item(row, 5)
            if kw_item: keywords.append(kw_item.text())
        if not keywords:
            QMessageBox.warning(self, "No Keywords", "No keywords to send.")
            return
        self.send_to_trends_signal.emit(keywords)

    def send_to_video(self): self._send_to_tool("video")
    def send_to_channel(self): self._send_to_tool("channel")

    def _selected_keyword_rows(self):
        checked_rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked_rows.append(row)
        if checked_rows:
            return checked_rows
        if self.table.selectionModel() is None:
            return []
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def _keyword_texts_for_rows(self, rows):
        keywords = []
        for row in rows:
            item = self.table.item(row, 5)
            if item is None:
                continue
            text = item.text().strip()
            if text:
                keywords.append(text)
        return keywords

    @staticmethod
    def _keyword_to_hashtag(keyword):
        compact = re.sub(r"[^\w]+", "", str(keyword or "").strip(), flags=re.UNICODE)
        compact = compact.strip("_")
        if not compact:
            return ""
        return f"#{compact}"

    def copy_keywords_as_hashtags(self, selected_only):
        rows = self._selected_keyword_rows() if selected_only else list(range(self.table.rowCount()))
        keywords = self._keyword_texts_for_rows(rows)
        if not keywords:
            message = "Please select at least one keyword." if selected_only else "No keywords to copy."
            QMessageBox.warning(self, "Hashtags", message)
            return

        hashtags = []
        seen = set()
        for keyword in keywords:
            hashtag = self._keyword_to_hashtag(keyword)
            if not hashtag:
                continue
            lowered = hashtag.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            hashtags.append(hashtag)

        if not hashtags:
            QMessageBox.warning(self, "Hashtags", "No valid hashtags could be created.")
            return

        QApplication.clipboard().setText("\n".join(hashtags))
        QMessageBox.information(self, "Hashtags", f"Copied {len(hashtags)} hashtag(s).")

    def _send_to_tool(self, target):
        keywords = []
        has_sel = any(self.table.item(r,0).checkState()==Qt.CheckState.Checked for r in range(self.table.rowCount()) if self.table.item(r,0))
        for r in range(self.table.rowCount()):
            if has_sel and not (self.table.item(r,0) and self.table.item(r,0).checkState()==Qt.CheckState.Checked): continue
            kw = self.table.item(r, 5)
            if kw: keywords.append(kw.text())
        if not keywords:
            return
        if target == "video" and self.main_window is not None:
            self.main_window.handle_send_to_videos(keywords, source_tool="Keywords")
            return
        QMessageBox.information(self, "Sent", f"Sent {len(keywords)} keywords to {target} search tool.")

    def mock_action(self, name): QMessageBox.information(self, "Action", f"Selected: '{name}'")
    def show_filters_placeholder(self): QMessageBox.information(self, "Filters", "Will be implemented soon.")
    def clear_grid_data(self):
        if QMessageBox.question(self, 'Clear', 'Clear all data?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)
            self.update_selection_count()
    def copy_all_keywords(self):
        kws = [self.table.item(r,5).text() for r in range(self.table.rowCount()) if self.table.item(r,5)]
        if kws:
            QApplication.clipboard().setText("\n".join(kws))
            QMessageBox.information(self, "Copied", f"Copied {len(kws)} keywords.")

    def export_data(self, fmt):
        try:
            import pandas as pd
            data = [[self.table.item(r,c).text() if self.table.item(r,c) else "" for c in range(1, self.table.columnCount())] for r in range(self.table.rowCount())]
            h = [self.table.horizontalHeaderItem(c).text().replace("🔍 ","") for c in range(1, self.table.columnCount())]
            df = pd.DataFrame(data, columns=h)
            path, _ = QFileDialog.getSaveFileName(self, f"Save {fmt.upper()}", "", f"{fmt.upper()} Files (*.{fmt})")
            if path:
                if fmt == "csv": df.to_csv(path, index=False)
                elif fmt == "excel": df.to_excel(path, index=False)
                elif fmt == "txt": df.to_csv(path, sep='\t', index=False)
                QMessageBox.information(self, "Success", f"Saved to {path}")
        except Exception as e: QMessageBox.warning(self, "Error", str(e))

    def open_import_volume_dialog(self): ImportVolumeDialog(self).exec()
    def get_keywords_count(self): return self.table.rowCount()
    def get_keywords_list(self): return [self.table.item(r,5).text() for r in range(self.table.rowCount()) if self.table.item(r,5)]
    def receive_keywords_from_trends(self, keywords, source_tool="Trends"):
        clean_keywords = []
        seen = set()
        for keyword in keywords or []:
            text = " ".join(str(keyword or "").split()).strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            clean_keywords.append(text)
        if not clean_keywords:
            return False, ""

        primary_seed = clean_keywords[0]
        self.seed_input.setText(primary_seed)
        self.seed_input.setCursorPosition(len(primary_seed))
        self.seed_input.setFocus()
        self.seed_input.selectAll()
        self.seed_input.setToolTip(
            f"Received {len(clean_keywords)} keyword(s) from {source_tool}. Current seed: {primary_seed}"
        )
        return True, primary_seed

    def apply_volume_data(self, vmap):
        m = 0
        self.table.blockSignals(True)
        for r in range(self.table.rowCount()):
            kw = ' '.join(self.table.item(r,5).text().lower().strip().split())
            if kw in vmap:
                it = QTableWidgetItem(vmap[kw])
                it.setForeground(QColor("#00ff00"))
                self.table.setItem(r, 6, it) # We might need to ensure col 6 exists
                m += 1
        self.table.blockSignals(False)
        return m
