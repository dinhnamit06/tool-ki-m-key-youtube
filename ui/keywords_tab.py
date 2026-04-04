from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QFrame, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QMenu, QCheckBox, QApplication, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QFont, QColor, QBrush, QAction
import json
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
        input_grid_layout.addLayout(count_layout, 0, 4, 1, 1)
        input_grid_layout.addWidget(self.generate_btn, 0, 5, 1, 1, alignment=Qt.AlignmentFlag.AlignBottom)
        input_grid_layout.setColumnStretch(0, 3)
        input_grid_layout.setColumnStretch(1, 2)
        input_grid_layout.setColumnStretch(2, 3)
        input_grid_layout.setColumnStretch(3, 2)
        input_grid_layout.setColumnStretch(4, 1)
        input_grid_layout.setColumnStretch(5, 1)
        
        content_layout.addWidget(input_frame)
        
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

    def generate_keywords(self):
        if not REQUESTS_INSTALLED:
            QMessageBox.critical(self, "Missing Dependency", "The 'requests' module is missing. Please run:\n\npip install requests")
            return

        seed_text = self.seed_input.text().strip()
        target_country = self.country_combo.currentText()
        target_count = int(self.count_spin.value())
        provider = "gemini"
        model_name = self._selected_model_value()
        if not seed_text:
            QMessageBox.warning(self, "Empty Input", "Please enter a seed keyword first.")
            return
            
        self.generate_btn.setText("Generating...")
        self.generate_btn.setEnabled(False)
        QApplication.processEvents()
        
        prompt = self._build_keyword_generation_prompt(
            seed_text=seed_text,
            target_country=target_country,
            target_count=target_count,
            bilingual=self.toggle_bilingual.isChecked(),
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

    def _build_keyword_generation_prompt(self, seed_text, target_country, target_count, bilingual=False):
        seed_scope = self._classify_seed_scope(seed_text)
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
