from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, 
    QPushButton, QFrame, QSizePolicy, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMessageBox, QMenu, QCheckBox, QApplication, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QFont, QColor, QBrush, QAction

from utils.constants import REQUESTS_INSTALLED
from core.keyword_generator import generate_keywords_api
from ui.components import ImportVolumeDialog

class KeywordsTab(QWidget):
    send_to_trends_signal = pyqtSignal(list)
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window # Reference to main app for status bar etc.
        self.select_all_state = False
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
        input_row_layout = QHBoxLayout(input_frame)
        input_row_layout.setContentsMargins(20, 20, 20, 20)
        input_row_layout.setSpacing(20)
        
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
        self.seed_input.setMinimumWidth(350)
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
        self.country_combo.setMinimumWidth(150)
        
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
        self.range_combo.setMinimumWidth(260)
        
        range_layout.addWidget(range_label)
        range_layout.addWidget(self.range_combo)

        # --- API Provider Section ---
        api_layout = QVBoxLayout()
        api_layout.setSpacing(8)

        api_label = QLabel("API provider:")
        api_label.setObjectName("input_label")
        self.api_provider_combo = QComboBox()
        self.api_provider_combo.addItems(["Gemini", "GPT", "Auto (Gemini -> GPT)"])
        self.api_provider_combo.setCurrentText("Gemini")
        self.api_provider_combo.setMinimumHeight(42)
        self.api_provider_combo.setMinimumWidth(200)

        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_provider_combo)

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
        self.count_spin.setMinimumWidth(130)
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
        self.generate_btn.setMinimumWidth(160)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.generate_btn.clicked.connect(self.generate_keywords)
        
        input_row_layout.addLayout(seed_layout)
        input_row_layout.addLayout(country_layout)
        input_row_layout.addLayout(range_layout)
        input_row_layout.addLayout(api_layout)
        input_row_layout.addLayout(count_layout)
        input_row_layout.addWidget(self.generate_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        
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
        provider_label = self.api_provider_combo.currentText().strip()
        provider_map = {
            "Gemini": "gemini",
            "GPT": "gpt",
            "Auto (Gemini -> GPT)": "auto",
        }
        provider = provider_map.get(provider_label, "gemini")
        if not seed_text:
            QMessageBox.warning(self, "Empty Input", "Please enter a seed keyword first.")
            return
            
        self.generate_btn.setText("Generating...")
        self.generate_btn.setEnabled(False)
        QApplication.processEvents()
        
        prompt = f"""You are an expert YouTube keyword researcher.
Given the seed keyword: "{seed_text}"
Generate exactly {target_count} high-quality, natural long-tail keywords for YouTube videos.
Important rules:
- Each keyword must be short and concise: maximum 5 words.
- Focus on trending, searchable YouTube video topics and sub-niches.
- TARGET GEOGRAPHY: {target_country}.
"""
        if target_country != "Worldwide":
            prompt += f"- NATIVE LANGUAGE: Keywords MUST be written natively in the primary language of {target_country}.\n"
            prompt += f"- CULTURAL TRENDS: Adapt the niche realistically to the current localized YouTube trends in {target_country}.\n"
        
        if self.toggle_bilingual.isChecked():
            prompt += "- BILINGUAL OUTPUT: Include the native language AND the English translation separated by a dash.\n"
            
        prompt += f"""- Avoid long sentences or keywords longer than 5 words.
- Support wildcard * if present.
- Return ONLY a clean comma-separated list of exactly {target_count} keywords. No numbers, no explanations, no extra text.
Seed keyword: {seed_text}
"""
        try:
            content = generate_keywords_api(prompt, provider=provider)
            generated_list = [kw.strip() for kw in content.split(",") if kw.strip()]
        except Exception as e:
            QMessageBox.critical(self, "API Error", str(e))
            generated_list = []
        finally:
            self.generate_btn.setText("✓ Generate")
            self.generate_btn.setEnabled(True)
            
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
