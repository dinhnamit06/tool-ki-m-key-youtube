import sys
import string
try:
    import requests
    REQUESTS_INSTALLED = True
except ImportError:
    REQUESTS_INSTALLED = False

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QFrame, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QMenu, QCheckBox,
    QDialog, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush, QAction

class TubeVibeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TubeVibe - YouTube Research Pro")
        self.resize(1280, 800)
        self.select_all_state = False
        self.setup_ui()
        self.apply_theme()

    def setup_ui(self):
        # Main central widget and horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ====================
        # LEFT SIDEBAR
        # ====================
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setObjectName("sidebar")
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 20)
        sidebar_layout.setSpacing(8)
        
        title_label = QLabel("TubeVibe")
        title_label.setObjectName("sidebar_title")
        title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        
        subtitle_label = QLabel("YouTube Research Pro")
        subtitle_label.setObjectName("sidebar_subtitle")
        subtitle_label.setFont(QFont("Segoe UI", 11))
        
        sidebar_layout.addWidget(title_label)
        sidebar_layout.addWidget(subtitle_label)
        sidebar_layout.addStretch()

        # ====================
        # RIGHT MAIN AREA
        # ====================
        right_area = QWidget()
        right_layout = QVBoxLayout(right_area)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # 1. Top Navigation Bar
        navbar = QFrame()
        navbar.setObjectName("navbar")
        navbar.setFixedHeight(60)
        navbar_layout = QHBoxLayout(navbar)
        navbar_layout.setContentsMargins(20, 0, 20, 0)
        navbar_layout.setSpacing(10)
        
        tabs = [
            "Welcome", "Keywords", "Trends", "Videos", 
            "Channels", "Video to Text", "Comments"
        ]
        
        for tab in tabs:
            tab_label = QLabel(tab)
            tab_label.setCursor(Qt.CursorShape.PointingHandCursor)
            if tab == "Keywords":
                tab_label.setObjectName("active_tab")
            else:
                tab_label.setObjectName("inactive_tab")
            navbar_layout.addWidget(tab_label)
            
        navbar_layout.addStretch()
        
        # 2. Main Content (Keywords Tool)
        content_area = QWidget()
        content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content_area)
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
        input_row_layout.addWidget(self.generate_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        
        content_layout.addWidget(input_frame)
        
        # ====================
        # DATA GRID
        # ====================
        self.table = QTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setColumnCount(6)
        
        # Setup headers
        self.table.setHorizontalHeaderLabels(["[ Click ] All", "🔍 Rank", "🔍 Word Count", "🔍 Character Count", "🔍 Seed", "🔍 Keyword"])
        
        # Implement Select All by handling the header section click
        self.table.horizontalHeader().sectionClicked.connect(self.handle_header_clicked)
        
        # Table properties
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

        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # Connect Table Checkbox Item Change Signal
        self.table.itemChanged.connect(self.handle_checkbox_change)
        
        content_layout.addWidget(self.table, stretch=1)
        
        # ====================
        # BOTTOM STATUS & TOOLBAR
        # ====================
        bottom_toolbar = QFrame()
        bottom_toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bottom_toolbar.setObjectName("bottom_toolbar")
        bottom_layout = QHBoxLayout(bottom_toolbar)
        bottom_layout.setContentsMargins(0, 5, 0, 0)
        
        # Left: Volume Data
        self.btn_volume = QPushButton("Volume Data")
        self.btn_volume.setObjectName("bottom_red_btn")
        self.btn_volume.setCursor(Qt.CursorShape.PointingHandCursor)
        
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
            
        # File dropdown setup
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
            
        bottom_layout.addWidget(bottom_right_widget)
        content_layout.addWidget(bottom_toolbar)
        
        right_layout.addWidget(navbar)
        right_layout.addWidget(content_area, stretch=1)
        main_layout.addWidget(sidebar)
        main_layout.addWidget(right_area, stretch=1)

    def show_context_menu(self, position):
        menu = QMenu(self.table)
        
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 25px 8px 20px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
            QMenu::separator { height: 1px; background-color: #444444; margin: 4px 0px; }
        """)

        # Add Actions
        action_send_trends_selected = menu.addAction("Send SELECTED to Trends tool")
        action_send_trends_all = menu.addAction("Send ALL to Trends tool")
        
        action_send_trends_selected.triggered.connect(lambda: self.send_to_trends(selected_only=True))
        action_send_trends_all.triggered.connect(lambda: self.send_to_trends(selected_only=False))
        menu.addSeparator()
        
        action_send_video = menu.addAction("Send to Video search tool")
        action_send_channel = menu.addAction("Send to Channel search tool")
        
        action_send_video.triggered.connect(self.send_to_video)
        action_send_channel.triggered.connect(self.send_to_channel)
        menu.addSeparator()
        
        # Volume Data Submenu
        vol_menu = menu.addMenu("Volume Data")
        vol_menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 25px 8px 20px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
        """)
        action_import = vol_menu.addAction("Import search volume data")
        action_import.triggered.connect(self.open_import_volume_dialog)
        
        ke_menu = vol_menu.addMenu("Keywords Everywhere")
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
        menu.addSeparator()
        
        # Copy Submenu
        copy_menu = menu.addMenu("Copy")
        copy_menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 25px 8px 20px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
        """)
        action_copy_selected_rows = copy_menu.addAction("Copy SELECTED rows")
        action_copy_all_rows = copy_menu.addAction("Copy ALL rows")
        action_copy_selected_keywords = copy_menu.addAction("Copy SELECTED keywords")
        
        menu.addSeparator()
        
        # Get right-clicked keyword context
        keyword = ""
        item_clicked = self.table.itemAt(position)
        if item_clicked:
            row = item_clicked.row()
            kw_item = self.table.item(row, 5)
            if kw_item:
                keyword = kw_item.text()
        
        # Search Submenu
        search_menu = menu.addMenu("Search")
        search_menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #ffffff; border: 1px solid #444444; }
            QMenu::item { padding: 8px 25px 8px 20px; }
            QMenu::item:selected { background-color: #e50914; color: #ffffff; }
        """)
        search_menu.setEnabled(bool(keyword))
        
        engines = ["Google Trends", "Google Search", "YouTube Search", "Bing Search", "Amazon", "eBay"]
        for engine in engines:
            act = search_menu.addAction(engine)
            act.triggered.connect(lambda checked, e=engine, kw=keyword: self.web_search(e, kw))
            
        action_delete = menu.addAction("Delete")
        
        # Exec Menu
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        
        # Map actions natively
        if action:
            text = action.text()
            handled_by_signals = [
                "Save to CSV", "Save to Excel", "Save to TXT", 
                "Google Trends", "Google Search", "YouTube Search", 
                "Bing Search", "Amazon", "eBay"
            ]
            if text in handled_by_signals:
                pass # Handled by triggered signals
            elif text == "Send SELECTED to Trends tool":
                self.send_to_trends(selected_only=True)
            elif text == "Send ALL to Trends tool":
                self.send_to_trends(selected_only=False)
            else:
                self.mock_action(text)
            
    def mock_action(self, action_name):
        QMessageBox.information(
            self, 
            "Action Triggered", 
            f"You selected: '{action_name}'\n\n(Logic will be implemented soon!)"
        )

    def show_filters_placeholder(self):
        QMessageBox.information(self, "Filters", "Filters feature will be implemented in the next major step")

    def clear_grid_data(self):
        reply = QMessageBox.question(self, 'Clear Keywords', 
                                     'Are you sure you want to clear all data from the grid?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)
            self.selection_label.setText("Total Items: 0  |  Selected rows: 0")

    def copy_all_keywords(self):
        keywords = []
        for row in range(self.table.rowCount()):
            kw_item = self.table.item(row, 5) # Keyword is col 5
            if kw_item:
                keywords.append(kw_item.text().strip())
        
        if not keywords:
            QMessageBox.warning(self, "No Keywords", "There are no keywords to copy.")
            return

        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(keywords))
        QMessageBox.information(self, "Copied", f"Successfully copied {len(keywords)} keywords to clipboard!")
        
    def send_to_trends(self, selected_only):
        keywords = []
        for row in range(self.table.rowCount()):
            kw_item = self.table.item(row, 5) # Keyword is col 5
            if not kw_item: continue
            
            if selected_only:
                chk_item = self.table.item(row, 0)
                if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                    keywords.append(kw_item.text())
            else:
                keywords.append(kw_item.text())
                
        if not keywords:
            msg = "Please check at least one row to send." if selected_only else "There are no keywords to send."
            QMessageBox.warning(self, "No Keywords", msg)
            return
            
        # Store securely inside application memory for cross-tab sharing
        self.trends_transfer_payload = keywords
        print(f"[INTERNAL] Send Transfer Payload (length {len(keywords)}):", keywords[:5], "...")
        
        prefix = "SELECTED" if selected_only else "ALL"
        QMessageBox.information(self, "Transit Success", f"Successfully sent {len(keywords)} {prefix} keywords to Trends tool.")

    def web_search(self, engine, keyword):
        import webbrowser
        import urllib.parse
        
        if not keyword:
            return
            
        encoded_kw = urllib.parse.quote_plus(keyword)
        url = ""
        
        if engine == "Google Trends":
            encoded_kw_trends = urllib.parse.quote(keyword)
            url = f"https://trends.google.com/trends/explore?q={encoded_kw_trends}"
        elif engine == "Google Search":
            url = f"https://www.google.com/search?q={encoded_kw}"
        elif engine == "YouTube Search":
            url = f"https://www.youtube.com/results?search_query={encoded_kw}"
        elif engine == "Bing Search":
            url = f"https://www.bing.com/search?q={encoded_kw}"
        elif engine == "Amazon":
            url = f"https://www.amazon.com/s?k={encoded_kw}"
        elif engine == "eBay":
            url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_kw}"
            
        if url:
            webbrowser.open(url)
            
    def handle_header_clicked(self, logicalIndex):
        # Trigger mass select/deselect when clicking the checkbox column header
        if logicalIndex == 0:
            self.select_all_state = not self.select_all_state
            new_state = Qt.CheckState.Checked if self.select_all_state else Qt.CheckState.Unchecked
            
            # Switch header bracket text
            header_item = self.table.horizontalHeaderItem(0)
            if header_item:
                header_item.setText("[x] All" if self.select_all_state else "[ ] All")
            
            # Prevent slowdowns when mass updating UI triggers
            self.table.blockSignals(True)
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item:
                    item.setCheckState(new_state)
                    self.update_row_color(row, self.select_all_state)
                    
            self.table.blockSignals(False)
            self.update_selection_count()

    def update_row_color(self, row, is_checked):
        # Tube Atlas pink shadow matching highlight
        bg_brush = QBrush(QColor("#4a1a25")) if is_checked else QBrush()
        
        for col in range(1, self.table.columnCount()):
            cell = self.table.item(row, col)
            if cell:
                cell.setBackground(bg_brush)

    def handle_checkbox_change(self, item):
        # 0 is the check box column
        if item.column() == 0:
            is_checked = item.checkState() == Qt.CheckState.Checked
            self.update_row_color(item.row(), is_checked)
            self.update_selection_count()

    def update_selection_count(self):
        count = 0
        total = self.table.rowCount()
        for row in range(total):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                count += 1
        self.selection_label.setText(f"Total Items: {total}  |  Selected rows: {count}")

    def generate_keywords(self):
        if not REQUESTS_INSTALLED:
            QMessageBox.critical(self, "Missing Dependency", "The 'requests' module is missing. Please run:\n\npip install requests")
            return

        seed_text = self.seed_input.text().strip()
        target_country = self.country_combo.currentText()
        if not seed_text:
            QMessageBox.warning(self, "Empty Input", "Please enter a seed keyword first.")
            return
            
        self.generate_btn.setText("Generating...")
        self.generate_btn.setEnabled(False)
        QApplication.processEvents()
        
        prompt = f"""You are an expert YouTube keyword researcher.

Given the seed keyword: "{seed_text}"

Generate 100 high-quality, natural long-tail keywords for YouTube videos.

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
- Return ONLY a clean comma-separated list of keywords. No numbers, no explanations, no extra text.

Seed keyword: {seed_text}
"""
        
        # Gemini API Config
        api_key = "AIzaSyBdQaRivbh1ptEmE2BkEZopw50dSDbpZDs"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7
            }
        }
        
        generated_list = []
        try:
            if api_key == "YOUR_GEMINI_API_KEY_HERE":
                QMessageBox.warning(self, "Thiếu API Key", "Vui lòng mở file main.py và nhập mã Gemini API Key của bạn vào dòng 270 nhé!")
                return

            response = requests.post(url, headers=headers, json=data, timeout=35)
            response.raise_for_status()
            
            result_json = response.json()
            
            # Navigate Gemini's response schema (which is different from OpenAI/Grok)
            if "candidates" in result_json and len(result_json["candidates"]) > 0:
                content = result_json["candidates"][0]["content"]["parts"][0]["text"]
            else:
                content = ""
            
            # Parse CSV response into a clean list
            generated_list = [kw.strip() for kw in content.split(",") if kw.strip()]
            
        except requests.exceptions.RequestException as e:
            err_msg = f"Lỗi gọi Gemini API (Network/HTTP): {e}"
            if e.response is not None:
                err_msg += f"\n\nChi tiết: {e.response.text}"
            print(err_msg)
            QMessageBox.critical(self, "API Error", err_msg)
        except Exception as e:
            err_msg = f"Đã xảy ra lỗi không xác định lúc giải mã: {e}"
            print(err_msg)
            QMessageBox.critical(self, "Error", err_msg)
            
        finally:
            self.generate_btn.setText("✓ Generate")
            self.generate_btn.setEnabled(True)
            
        if not generated_list:
            return
            
        results = []
        seen = set()
        rank = 1
        
        for keyword in generated_list:
            keyword = " ".join(keyword.split())
            if keyword.lower() not in seen:
                seen.add(keyword.lower())
                word_count = len(keyword.split())
                char_count = len(keyword)
                results.append((str(rank), str(word_count), str(char_count), seed_text, keyword))
                rank += 1
            
        self.populate_table(results)

    def populate_table(self, data):
        # Disconnect updating triggers to prevent huge slowdowns during insertion loops
        self.table.blockSignals(True)
        
        self.table.setRowCount(len(data))
        
        for row, row_data in enumerate(data):
            chk_item = QTableWidgetItem("")
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, chk_item)
            
            for col, text in enumerate(row_data, start=1):
                item = QTableWidgetItem(text)
                if col in [1, 2, 3]:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self.table.setItem(row, col, item)
                
            vol_item = QTableWidgetItem("-")
            vol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 6, vol_item)
                
        # Lock in values & count freshly updated reset array
        self.select_all_state = False
        header_item = self.table.horizontalHeaderItem(0)
        if header_item:
            header_item.setText("[ ] All")
            
        self.table.blockSignals(False)
        self.update_selection_count()

    def get_search_volume_selected(self):
        import random
        # Find selected rows (from checkbox)
        selected_rows = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                selected_rows.append(row)
                
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please check at least one row to fetch search volume.")
            return
            
        self.table.blockSignals(True)
        # Dummy data fetch simulation
        for row in selected_rows:
            vol = random.randint(100, 50000)
            vol_str = f"{vol:,}"
            vol_item = self.table.item(row, 6)
            if vol_item:
                vol_item.setText(vol_str)
                vol_item.setForeground(QColor("#00ff00")) # Highlight it
                
        self.table.blockSignals(False)
        QMessageBox.information(self, "Success", f"Search Volume data loaded for {len(selected_rows)} keywords")

    def export_data(self, format_type):
        from PyQt6.QtWidgets import QFileDialog
        
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "There is no data to export yet.")
            return
            
        headers = []
        for col in range(1, self.table.columnCount()):
            h_item = self.table.horizontalHeaderItem(col)
            headers.append(h_item.text().replace("🔍 ", "").replace("🔥 ", "") if h_item else f"Col{col}")

        data = []
        for row in range(self.table.rowCount()):
            row_data = []
            for col in range(1, self.table.columnCount()):
                item = self.table.item(row, col)
                row_data.append(item.text() if item else "")
            data.append(row_data)
            
        try:
            import pandas as pd
            df = pd.DataFrame(data, columns=headers)
        except ImportError:
            QMessageBox.warning(self, "Missing Library", "Please run 'pip install pandas' to use this feature.")
            return

        if format_type == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "Save as CSV", "", "CSV Files (*.csv)")
            if path:
                try:
                    df.to_csv(path, index=False, encoding="utf-8-sig")
                    QMessageBox.information(self, "Success", f"Data exported successfully to CSV!\n\n{path}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to save CSV: {e}")
                    
        elif format_type == "excel":
            path, _ = QFileDialog.getSaveFileName(self, "Save as Excel", "", "Excel Files (*.xlsx)")
            if path:
                try:
                    df.to_excel(path, index=False)
                    QMessageBox.information(self, "Success", f"Data exported successfully to Excel!\n\n{path}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to save Excel: {e}")
                    
        elif format_type == "txt":
            path, _ = QFileDialog.getSaveFileName(self, "Save as TXT", "", "Text Files (*.txt)")
            if path:
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write("\t".join(headers) + "\n")
                        for row in data:
                            f.write("\t".join(row) + "\n")
                    QMessageBox.information(self, "Success", f"Data exported successfully to TXT!\n\n{path}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to save TXT: {e}")

    def apply_theme(self):
        style = """
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
        self.setStyleSheet(style)

    def open_import_volume_dialog(self):
        diag = ImportVolumeDialog(self)
        diag.exec()

    def send_to_trends(self, selected_only=False):
        keywords = []
        for row in range(self.table.rowCount()):
            if selected_only:
                chk_item = self.table.item(row, 0)
                if not (chk_item and chk_item.checkState() == Qt.CheckState.Checked):
                    continue
            kw_item = self.table.item(row, 5) # Keyword is at col 5
            if kw_item:
                keywords.append(kw_item.text().strip())
                
        if not keywords:
            QMessageBox.warning(self, "No Keywords", "No keywords were found to send.")
            return
            
        self.sent_to_trends = keywords
        print(f"--- SENT {len(keywords)} KEYWORDS TO TRENDS ---")
        for kw in keywords:
            print(kw)
            
        action_type = "selected" if selected_only else "all"
        QMessageBox.information(self, "Trends Data Sent", f"Sent {action_type} {len(keywords)} keywords to Trends tool")

    def send_to_video(self):
        self._send_to_tool("video")

    def send_to_channel(self):
        self._send_to_tool("channel")

    def _send_to_tool(self, target_tool):
        keywords = []
        has_selection = False
        
        for row in range(self.table.rowCount()):
            chk_item = self.table.item(row, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                has_selection = True
                break
                
        for row in range(self.table.rowCount()):
            if has_selection:
                chk_item = self.table.item(row, 0)
                if not (chk_item and chk_item.checkState() == Qt.CheckState.Checked):
                    continue
            kw_item = self.table.item(row, 5)
            if kw_item:
                keywords.append(kw_item.text().strip())
                
        if not keywords:
            QMessageBox.warning(self, "No Keywords", "No keywords were found to send.")
            return
            
        if target_tool == "video":
            self.sent_to_video = keywords
            tool_name = "Video"
        else:
            self.sent_to_channel = keywords
            tool_name = "Channel"
            
        print(f"--- SENT {len(keywords)} KEYWORDS TO {tool_name.upper()} TOOL ---")
        for kw in keywords: print(kw)
        
        QMessageBox.information(self, f"{tool_name} Data Sent", f"Sent {len(keywords)} keywords to {tool_name} search tool")

class DragDropFilesArea(QLabel):
    file_dropped = pyqtSignal(list)
    click_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setText("Drag CSV Files Here\nor Click to Load Files")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #666666; border-radius: 10px;
                background-color: #2b2b2b; color: #888888;
                font-size: 16px; font-weight: bold;
            }
            QLabel:hover {
                border: 2px dashed #e50914; background-color: #333333; color: #ffffff;
            }
        """)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        self.file_dropped.emit(files)

    def mousePressEvent(self, event):
        self.click_requested.emit()
        super().mousePressEvent(event)

class ImportVolumeDialog(QDialog):
    def __init__(self, main_app):
        super().__init__(main_app)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        self.main_app = main_app
        self.setWindowTitle("Get Keyword Search Data")
        self.setFixedSize(850, 480)
        self.setStyleSheet("""
            QDialog { background-color: #333333; color: #ffffff; }
            QLabel { color: #f1f1f1; font-family: "Segoe UI"; }
            QPushButton { background-color: #e50914; color: white; border: none; padding: 8px 15px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #ff1a25; }
            QPushButton#copy_btn { padding: 4px 10px; font-weight: normal; }
            QComboBox { background-color: #ffffff; color: #000000; border: 1px solid #aaa; padding: 5px; }
            QCheckBox, QRadioButton { color: white; font-family: "Segoe UI"; }
        """)
        self.setup_ui()
        
    def setup_ui(self):
        from PyQt6.QtWidgets import QRadioButton
        main_layout = QVBoxLayout(self)
        
        # Red Instructions
        instruction = QLabel(
            "To get keyword search volume, you can insert keyword sets into the free SearchVolume.io or\n"
            "Google Keyword Planner tool. Then import the files into Tube Atlas. Drag and drop the CSV files\n"
            "below, or click the big arrow to load the files. <a href='#'>Help videos</a>"
        )
        instruction.setTextFormat(Qt.TextFormat.RichText)
        instruction.setStyleSheet("background-color: #ffeaea; border: none; padding: 12px; color: #333333; font-weight: 500; border-radius: 4px;")
        main_layout.addWidget(instruction)
        
        main_layout.addSpacing(10)
        content_layout = QHBoxLayout()
        
        # --- LEFT PANEL ---
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        
        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel("Number of keywords per set:"))
        self.combo_size = QComboBox()
        self.combo_size.addItems(["400", "800", "1000", "2000"])
        self.combo_size.setCurrentText("800")
        combo_layout.addWidget(self.combo_size)
        combo_layout.addStretch()
        left_layout.addLayout(combo_layout)
        
        self.check_open = QCheckBox("Open browser when clicking\nthe 'Copy' button")
        self.check_open.setChecked(True)
        left_layout.addWidget(self.check_open)
        
        radio_layout = QHBoxLayout()
        radio_layout.setContentsMargins(25, 0, 0, 0)
        self.radio_sb = QRadioButton("StoryBase")
        self.radio_go = QRadioButton("Google")
        self.radio_go.setChecked(True)
        radio_layout.addWidget(self.radio_sb)
        radio_layout.addWidget(self.radio_go)
        radio_layout.addStretch()
        left_layout.addLayout(radio_layout)
        
        self.sets_table = QTableWidget()
        self.sets_table.setColumnCount(3)
        self.sets_table.setHorizontalHeaderLabels(["Set", "Size", "Copy"])
        self.sets_table.setRowCount(1)
        self.sets_table.setItem(0, 0, QTableWidgetItem("Set 1"))
        rows_count = str(self.main_app.table.rowCount()) if hasattr(self.main_app, 'table') else "0"
        self.sets_table.setItem(0, 1, QTableWidgetItem(rows_count))
        
        copy_btn_cell = QPushButton("Copy")
        copy_btn_cell.setObjectName("copy_btn")
        copy_btn_cell.clicked.connect(self.copy_keywords_to_clipboard)
        self.sets_table.setCellWidget(0, 2, copy_btn_cell)
        
        self.sets_table.verticalHeader().setVisible(False)
        self.sets_table.setColumnWidth(0, 50)
        self.sets_table.setColumnWidth(1, 60)
        self.sets_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.sets_table.setStyleSheet("QTableWidget { background: #ffffff; color: #000000; } QHeaderView::section { background: #e0e0e0; color: #000; font-weight: bold; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc; padding: 4px; }")
        self.sets_table.setFixedHeight(150)
        left_layout.addWidget(self.sets_table)
        left_layout.addStretch()
        
        content_layout.addLayout(left_layout, stretch=1)
        
        # --- MIDDLE PANEL ---
        mid_layout = QVBoxLayout()
        mid_layout.setSpacing(25)
        
        sb_label = QLabel("<b>SearchVolume.io</b><br>A free keywordsearch volume<br>tool which allows you to paste<br>up to 800 keywords at a time.<br><a href='#'>See Help videos</a>")
        sb_label.setTextFormat(Qt.TextFormat.RichText)
        sb_label.setStyleSheet("color: #cccccc;")
        
        go_label = QLabel("<b>Google Keyword Planner</b><br>Another free keyword search<br>data toolwhich allows you to<br>paste up to 2500 keywords at<br>a time. <a href='#'>See Help videos</a>")
        go_label.setTextFormat(Qt.TextFormat.RichText)
        go_label.setStyleSheet("color: #cccccc;")
        
        mid_layout.addWidget(sb_label)
        mid_layout.addWidget(go_label)
        mid_layout.addStretch()
        content_layout.addLayout(mid_layout, stretch=1)
        
        # --- RIGHT PANEL ---
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        
        btn_folder = QPushButton("Open Working Folder")
        import os
        btn_folder.clicked.connect(lambda: os.startfile(os.getcwd()) if hasattr(os, 'startfile') else None)
        right_layout.addWidget(btn_folder, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.drop_area = DragDropFilesArea()
        self.drop_area.file_dropped.connect(self.process_files)
        self.drop_area.click_requested.connect(self.browse_files)
        self.drop_area.setText("⬇\n\nDrag CSV Files Here or Click\nto Load Files")
        self.drop_area.setStyleSheet("""
            QLabel {
                border: 3px dashed #222222; border-radius: 8px;
                background-color: #f7f7f7; color: #111111;
                font-size: 13px; font-weight: bold; padding: 30px;
            }
            QLabel:hover { border-color: #e50914; }
        """)
        right_layout.addWidget(self.drop_area, stretch=1)
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.close)
        right_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
        
        content_layout.addLayout(right_layout, stretch=1)
        main_layout.addLayout(content_layout)

    def copy_keywords_to_clipboard(self):
        table = self.main_app.table
        keywords = []
        for row in range(table.rowCount()):
            kw_item = table.item(row, 5) # Keyword is at column index 5
            if kw_item:
                keywords.append(kw_item.text().strip())
        
        if not keywords:
            QMessageBox.warning(self, "Empty", "No keywords available in the grid to copy.")
            return

        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(keywords))
        
        info_text = f"Copied {len(keywords)} keywords to clipboard! "
        
        if self.radio_go.isChecked():
            info_text += "\n\nPlease go to Google Keyword Planner, paste your keywords, export as CSV, then drag the file back here."
            QMessageBox.information(self, "Copied for Google Ads", info_text)
            if self.check_open.isChecked():
                import webbrowser
                webbrowser.open("https://ads.google.com/home/tools/keyword-planner/")
        else:
            info_text += "\n\nPlease go to StoryBase (SearchVolume.io), paste your keywords, export as CSV, then drag it back here."
            QMessageBox.information(self, "Copied for StoryBase", info_text)
            if self.check_open.isChecked():
                import webbrowser
                webbrowser.open("https://searchvolume.io")

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Volume Data CSV", "", "CSV Files (*.csv)")
        if files: self.process_files(files)

    def process_files(self, files):
        if not files: return
        import pandas as pd
        
        volume_map = {}
        for file in files:
            try:
                df = pd.read_csv(file)
                kw_col = None
                vol_col = None
                for col in df.columns:
                    col_lower = str(col).lower()
                    if "keyword" in col_lower: kw_col = col
                    elif "volume" in col_lower or "search" in col_lower or "searches" in col_lower: vol_col = col
                
                if kw_col and vol_col:
                    for _, row in df.iterrows():
                        raw_kw = str(row[kw_col])
                        # Normalize CSV keyword: lower, strip, and collapse multiple spaces
                        kw = ' '.join(raw_kw.lower().strip().split())
                        vol = str(row[vol_col]).strip()
                        volume_map[kw] = vol
            except Exception as e:
                print("Error processing CSV:", e)
                
        table = self.main_app.table
        
        headers = []
        for i in range(table.columnCount()):
            item = table.horizontalHeaderItem(i)
            headers.append(item.text() if item else "")
            
        sv_col_idx = -1
        if "Search Volume" not in headers:
            sv_col_idx = table.columnCount()
            table.insertColumn(sv_col_idx)
            table.setHorizontalHeaderItem(sv_col_idx, QTableWidgetItem("Search Volume"))
        else:
            sv_col_idx = headers.index("Search Volume")
             
        matched = 0
        table.blockSignals(True)
        for row in range(table.rowCount()):
            kw_item = table.item(row, 5) # Keyword is at column index 5
            if kw_item:
                # Normalize Grid keyword identically: lower, strip, collapse multiple spaces
                kw_text = ' '.join(kw_item.text().lower().strip().split())
                if kw_text in volume_map:
                    vol_item = QTableWidgetItem(volume_map[kw_text])
                    from PyQt6.QtGui import QColor
                    vol_item.setForeground(QColor("#00ff00"))
                    table.setItem(row, sv_col_idx, vol_item)
                    matched += 1
        table.blockSignals(False)
        
        if matched > 0:
            QMessageBox.information(self, "Success", f"Imported search volume data for {matched} keywords successfully")
        else:
            QMessageBox.warning(self, "Missing", "No matching keywords found in the current grid")
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TubeVibeApp()
    window.show()
    sys.exit(app.exec())
