from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
    QCheckBox, QRadioButton, QMessageBox, QFileDialog, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

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
        
        # We'll need to carefully look at how we get rowCount
        # In original, it was self.main_app.table.rowCount()
        rows_count = str(self.main_app.get_keywords_count())
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
        keywords = self.main_app.get_keywords_list()
        
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
        try:
            import pandas as pd
        except ImportError:
            QMessageBox.warning(self, "Missing Library", "Please run 'pip install pandas' to use this feature.")
            return
        
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
                        kw = ' '.join(raw_kw.lower().strip().split())
                        vol = str(row[vol_col]).strip()
                        volume_map[kw] = vol
            except Exception as e:
                print("Error processing CSV:", e)
                
        matched = self.main_app.apply_volume_data(volume_map)
        
        if matched > 0:
            QMessageBox.information(self, "Success", f"Imported search volume data for {matched} keywords successfully")
        else:
            QMessageBox.warning(self, "Missing", "No matching keywords found in the current grid")
        self.close()
