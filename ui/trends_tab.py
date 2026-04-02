from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, 
    QPushButton, QFrame, QSizePolicy, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMessageBox, QMenu, QCheckBox, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.trends_fetcher import TrendsFetcherWorker

class TrendsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(20)
        
        header_label = QLabel("Trends Tool")
        header_label.setObjectName("header_label")
        header_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        layout.addWidget(header_label)

        # --- TRENDS TOP ACTION BAR ---
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_trends_go = QPushButton("Go")
        self.btn_trends_go.setFixedSize(120, 28)
        self.btn_trends_go.setStyleSheet("background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trends_go.clicked.connect(self.start_trends_fetch)
        
        self.btn_trends_stop = QPushButton("Stop")
        self.btn_trends_stop.setFixedSize(120, 28)
        self.btn_trends_stop.setStyleSheet("background-color: #444444; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trends_stop.clicked.connect(self.stop_trends_fetch)
        self.btn_trends_stop.hide()
        
        self.btn_trends_settings = QPushButton("Settings")
        self.btn_trends_settings.setFixedSize(100, 28)
        self.btn_trends_settings.setStyleSheet("background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.btn_trends_browser = QPushButton("Browser")
        self.btn_trends_browser.setFixedSize(100, 28)
        self.btn_trends_browser.setStyleSheet("background-color: #e50914; color: white; border: none; font-weight: bold; border-radius: 4px;")
        self.btn_trends_browser.setCursor(Qt.CursorShape.PointingHandCursor)
        
        top_layout.addWidget(self.btn_trends_go)
        top_layout.addWidget(self.btn_trends_stop)
        top_layout.addSpacing(140)
        top_layout.addWidget(self.btn_trends_settings)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_trends_browser)
        
        layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- LEFT PANEL ---
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 5, 10, 0)
        left_layout.setSpacing(12)
        left_panel.setStyleSheet("background-color: transparent;")
        
        from PyQt6.QtWidgets import QFormLayout
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0,0,0,0)
        form_layout.setSpacing(8)
        
        combo_style = "background-color: #ffffff; color: #000000; padding: 4px; border: 1px solid #cccccc; border-radius: 2px; font-size: 12px; min-width: 140px;"
        label_style = "color: #f1f1f1; font-size: 13px;"
        
        self.t_combo_country = QComboBox()
        self.t_combo_country.addItems(["Worldwide", "United States", "Viet Nam", "United Kingdom", "Japan"])
        self.t_combo_country.setStyleSheet(combo_style)
        lbl_country = QLabel("Country:")
        lbl_country.setStyleSheet(label_style)
        form_layout.addRow(lbl_country, self.t_combo_country)
        
        self.t_combo_period = QComboBox()
        self.t_combo_period.addItems(["Past 30 days", "Past 7 days", "Past 12 months", "2004 - present"])
        self.t_combo_period.setStyleSheet(combo_style)
        lbl_period = QLabel("Time Period:")
        lbl_period.setStyleSheet(label_style)
        form_layout.addRow(lbl_period, self.t_combo_period)
        
        self.t_combo_cat = QComboBox()
        self.t_combo_cat.addItems(["All Categories", "Arts & Entertainment", "Autos & Vehicles", "Beauty & Fitness", "Games"])
        self.t_combo_cat.setStyleSheet(combo_style)
        lbl_cat = QLabel("Category:")
        lbl_cat.setStyleSheet(label_style)
        form_layout.addRow(lbl_cat, self.t_combo_cat)
        
        self.t_combo_prop = QComboBox()
        self.t_combo_prop.addItems(["Youtube Search", "Web Search", "Image Search", "News Search", "Google Shopping"])
        self.t_combo_prop.setStyleSheet(combo_style)
        lbl_prop = QLabel("Property:")
        lbl_prop.setStyleSheet(label_style)
        form_layout.addRow(lbl_prop, self.t_combo_prop)
        
        left_layout.addLayout(form_layout)
        
        kw_label = QLabel("Enter one keyword per line:")
        kw_label.setStyleSheet("color: #bbbbbb; font-size: 12px; margin-top: 10px;")
        left_layout.addWidget(kw_label)
        
        self.trends_input = QTextEdit()
        self.trends_input.setStyleSheet("background-color: #ffffff; color: #000000; border: 1px solid #aaa; border-radius: 2px;")
        self.trends_input.setText("diy crafts\ndiy wall decor\ndiy videos\ndiy yarn\ndiy upholstered headboard\ndiy zipline\ndiy tiktok\ndiy aquarium")
        left_layout.addWidget(self.trends_input, stretch=1)
        
        # --- RIGHT AREA (TABLE) ---
        self.trends_table = QTableWidget()
        self.trends_table.setColumnCount(12)
        headers = ["✔", "Chart", "🔍 Keyword", "🔍 Country", "🔍 Time Period", "🔍 Category", "🔍 Property", "🔍 Word Count", "🔍 Character Count", "🔍 Total Average", "🔍 Trend Slope", "🔍 Trending Spike"]
        self.trends_table.setHorizontalHeaderLabels(headers)
        self.trends_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.trends_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.trends_table.setColumnWidth(0, 30)
        self.trends_table.setColumnWidth(1, 40)
        self.trends_table.verticalHeader().setVisible(False)
        self.trends_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.trends_table.setStyleSheet("QTableWidget { background-color: #ffffff; color: #000000; gridline-color: #dddddd; border: 1px solid #cccccc; } QHeaderView::section { background-color: #f0f0f0; color: #000000; font-weight: bold; border: 1px solid #cccccc; padding: 4px; }")
        self.trends_table.itemDoubleClicked.connect(self.show_trend_chart)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(self.trends_table)
        splitter.setSizes([260, 800])
        layout.addWidget(splitter, stretch=1)
        
        # --- BOTTOM TOOLBAR ---
        bottom_toolbar = QFrame()
        b_layout = QHBoxLayout(bottom_toolbar)
        self.t_btn_vol = QPushButton("Volume Data")
        self.t_btn_hash = QPushButton("Hashtags")
        self.t_status = QLabel("Total Items: 0")
        self.t_status.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 11px;")
        self.t_btn_file = QPushButton("File")
        self.t_btn_clear = QPushButton("Clear")
        for btn in [self.t_btn_vol, self.t_btn_hash, self.t_btn_file, self.t_btn_clear]:
            btn.setStyleSheet("background-color: #e50914; color: #ffffff; border: none; border-radius: 4px; font-weight: bold; padding: 7px 18px;")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.t_btn_clear.clicked.connect(lambda: self.trends_table.setRowCount(0))
        b_layout.addWidget(self.t_btn_vol)
        b_layout.addWidget(self.t_btn_hash)
        b_layout.addStretch()
        b_layout.addWidget(self.t_status)
        b_layout.addStretch()
        b_layout.addWidget(self.t_btn_file)
        b_layout.addWidget(self.t_btn_clear)
        layout.addWidget(bottom_toolbar)

    def start_trends_fetch(self):
        text = self.trends_input.toPlainText()
        keywords = [line.strip() for line in text.split("\n") if line.strip()]
        if not keywords:
            QMessageBox.warning(self, "No Keywords", "Please enter keywords.")
            return
        self.trends_table.setRowCount(0)
        self.trends_table.setSortingEnabled(False)
        self.btn_trends_go.hide()
        self.btn_trends_stop.show()
        self.trends_worker = TrendsFetcherWorker(keywords, self.t_combo_country.currentText(), self.t_combo_period.currentText(), self.t_combo_cat.currentText(), self.t_combo_prop.currentText())
        self.trends_worker.progress_signal.connect(self.on_trends_progress)
        self.trends_worker.finished_signal.connect(self.on_trends_finished)
        self.trends_worker.error_signal.connect(self.on_trends_error)
        self.trends_worker.status_signal.connect(lambda msg: self.t_status.setText(msg))
        self.trends_worker.start()

    def stop_trends_fetch(self):
        if hasattr(self, 'trends_worker') and self.trends_worker.isRunning():
            self.trends_worker.is_running = False
            self.btn_trends_stop.setText("Stopping...")

    def on_trends_progress(self, data):
        row = self.trends_table.rowCount()
        self.trends_table.insertRow(row)
        chk = QTableWidgetItem(); chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled); chk.setCheckState(Qt.CheckState.Unchecked); self.trends_table.setItem(row, 0, chk)
        chart = QTableWidgetItem("📈"); chart.setTextAlignment(Qt.AlignmentFlag.AlignCenter); 
        if data.get("RawData"): chart.setData(Qt.ItemDataRole.UserRole, data["RawData"])
        self.trends_table.setItem(row, 1, chart)
        self.trends_table.setItem(row, 2, QTableWidgetItem(str(data["Keyword"])))
        self.trends_table.setItem(row, 3, QTableWidgetItem(str(data["Country"])))
        self.trends_table.setItem(row, 4, QTableWidgetItem(str(data["Time Period"])))
        self.trends_table.setItem(row, 5, QTableWidgetItem(str(data["Category"])))
        self.trends_table.setItem(row, 6, QTableWidgetItem(str(data["Property"])))
        for i, val in enumerate([data["Word Count"], data["Character Count"], data["Total Average"], data["Trend Slope"], data["Trending Spike"]], start=7):
            it = QTableWidgetItem(); it.setData(Qt.ItemDataRole.DisplayRole, val); self.trends_table.setItem(row, i, it)
        self.t_status.setText(f"Total Items: {self.trends_table.rowCount()}")

    def on_trends_finished(self):
        self.btn_trends_stop.hide(); self.btn_trends_stop.setText("Stop"); self.btn_trends_go.show()
        self.trends_table.setSortingEnabled(True); self.trends_table.sortItems(9, Qt.SortOrder.DescendingOrder)
        QMessageBox.information(self, "Finished", "Trends data fetching complete!")

    def on_trends_error(self, err):
        self.btn_trends_stop.hide(); self.btn_trends_go.show()
        QMessageBox.critical(self, "Error", err)

    def show_trend_chart(self, item):
        if item.column() != 1: return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data: return
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
            from PyQt6.QtWidgets import QDialog
            dialog = QDialog(self); dialog.setWindowTitle(f"Searches Over Time"); dialog.resize(600, 400); l = QVBoxLayout(dialog)
            fig, ax = plt.subplots(figsize=(6, 4)); ax.plot(data, color='#e50914', linewidth=2, marker='o', markersize=4)
            ax.set_title(f"Interest Over Time"); ax.grid(True, linestyle='--', alpha=0.6)
            canvas = FigureCanvas(fig); l.addWidget(canvas); dialog.exec(); plt.close(fig)
        except Exception as e: QMessageBox.warning(self, "Chart Error", str(e))
