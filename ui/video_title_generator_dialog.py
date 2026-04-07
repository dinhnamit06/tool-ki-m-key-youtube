import csv
import random
import re
import webbrowser
from urllib.parse import quote_plus

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QDialog,
    QMessageBox,
    QHeaderView,
    QMenu,
)


class VideoTitleGeneratorDialog(QDialog):
    def __init__(self, parent=None, initial_keyword=""):
        super().__init__(parent)
        self.setWindowTitle("Video Title Generator")
        self.resize(1180, 660)
        self._all_titles = []
        self._filtered_keyword = ""
        self._setup_ui(initial_keyword=initial_keyword)

    def _setup_ui(self, initial_keyword):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(8)

        lbl_input = QLabel("Enter one or two keywords related to your video topic:")
        top.addWidget(lbl_input)

        self.input_keywords = QLineEdit()
        self.input_keywords.setPlaceholderText("e.g. lose weight")
        self.input_keywords.setText(str(initial_keyword or "").strip())
        self.input_keywords.setMinimumWidth(360)
        top.addWidget(self.input_keywords, stretch=1)

        top.addWidget(QLabel("Select number of titles:"))
        self.combo_count = QComboBox()
        self.combo_count.addItems(["10 random titles", "20 random titles", "30 random titles", "50 random titles"])
        self.combo_count.setCurrentIndex(0)
        self.combo_count.setMinimumWidth(160)
        top.addWidget(self.combo_count)

        self.btn_generate = QPushButton("Generate")
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.setStyleSheet(
            "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#ff1a25; }"
        )
        self.btn_generate.clicked.connect(self.generate_titles)
        top.addWidget(self.btn_generate)

        root.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["", "Title", "Word Count", "Character Count", "Controls"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        self.table.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; gridline-color:#dddddd; border:1px solid #cfcfcf; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:1px solid #d0d0d0; font-weight:700; padding:4px; }"
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 26)
        self.table.setColumnWidth(2, 96)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 220)
        root.addWidget(self.table, stretch=1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.lbl_total = QLabel("Total: 0")
        bottom.addWidget(self.lbl_total)
        bottom.addStretch()

        self.btn_file = QPushButton("File")
        self.btn_filters = QPushButton("Filters")
        self.btn_clear = QPushButton("Clear")
        for btn in (self.btn_file, self.btn_filters, self.btn_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
                "QPushButton:hover { background:#ff1a25; }"
            )
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_filters.clicked.connect(self.open_filter_dialog)
        self._setup_file_menu()

        bottom.addWidget(self.btn_file)
        bottom.addWidget(self.btn_filters)
        bottom.addWidget(self.btn_clear)
        root.addLayout(bottom)

        self.setStyleSheet(
            "QDialog { background:#ffffff; color:#111111; }"
            "QLabel { color:#111111; }"
            "QLineEdit, QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:5px 8px; }"
        )

    def _setup_file_menu(self):
        menu = QMenu(self.btn_file)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #c7c7c7; }"
            "QMenu::item { padding:6px 18px; }"
            "QMenu::item:selected { background:#f1d5df; color:#111111; }"
        )
        act_csv = menu.addAction("Save to CSV")
        act_txt = menu.addAction("Save to TXT")
        menu.addSeparator()
        act_copy = menu.addAction("Copy ALL titles")
        act_csv.triggered.connect(self.save_csv)
        act_txt.triggered.connect(self.save_txt)
        act_copy.triggered.connect(self.copy_all_titles)
        self.btn_file.setMenu(menu)

    @staticmethod
    def _word_count(text):
        return len([w for w in re.split(r"\s+", str(text).strip()) if w])

    def _target_count(self):
        text = self.combo_count.currentText().strip()
        match = re.search(r"\d+", text)
        return int(match.group(0)) if match else 10

    def generate_titles(self):
        keyword_text = self.input_keywords.text().strip()
        if not keyword_text:
            QMessageBox.warning(self, "Video Title Generator", "Please enter at least one keyword.")
            return
        count = self._target_count()
        titles = self._build_titles(keyword_text, count)
        self._all_titles = titles
        self._filtered_keyword = ""
        self._render_titles(titles)

    def _build_titles(self, keyword_text, target_count):
        topic = re.sub(r"\s+", " ", keyword_text).strip()
        if not topic:
            return []
        variants = [part.strip() for part in re.split(r"[,;/|]+", topic) if part.strip()]
        primary = variants[0] if variants else topic
        secondary = variants[1] if len(variants) > 1 else primary

        numbers = [3, 5, 7, 9, 10, 12, 15]
        hooks = [
            "Beginners Need to Know",
            "That Actually Works",
            "Most People Ignore",
            "You Can Try Today",
            "Without Wasting Time",
            "For Fast Results",
            "Step by Step",
            "Like a Pro",
        ]
        templates = [
            "Breaking News: {topic}",
            "{n} {topic} Tips That Actually Work",
            "{n} Mistakes to Avoid in {topic}",
            "How to Start {topic} for Beginners",
            "The Ultimate {topic} Guide ({n} Steps)",
            "{n} Secrets of {topic} You Should Know",
            "Why Your {topic} Is Not Working ({n} Fixes)",
            "Top {n} {topic} Ideas for This Year",
            "{topic} vs {secondary}: Which One Is Better?",
            "I Tried {topic} for {n} Days - Here's What Happened",
            "{n} Proven Ways to Improve {topic}",
            "How to Master {topic} in {n} Simple Steps",
            "Stop Doing This in {topic} ({n} Big Mistakes)",
            "{n} Powerful {topic} Hacks for Beginners",
            "{topic}: {hook}",
            "The Truth About {topic} ({n} Things Nobody Tells You)",
            "{n} Smart {topic} Strategies to Grow Faster",
            "Can You Really Improve {topic}? ({n} Real Tips)",
            "{n} Best Tools for {topic}",
            "How to Get Better at {topic} Without Stress",
        ]

        rng = random.Random()
        titles = []
        seen = set()
        max_attempts = max(80, target_count * 20)
        for _ in range(max_attempts):
            tpl = rng.choice(templates)
            title = tpl.format(
                topic=primary,
                secondary=secondary,
                n=rng.choice(numbers),
                hook=rng.choice(hooks),
            )
            title = re.sub(r"\s+", " ", title).strip(" -")
            key = title.lower()
            if not title or key in seen:
                continue
            seen.add(key)
            titles.append(title)
            if len(titles) >= target_count:
                break

        if len(titles) < target_count:
            base = primary
            idx = 1
            while len(titles) < target_count:
                fallback = f"{idx} Ways to Improve {base}"
                if fallback.lower() not in seen:
                    seen.add(fallback.lower())
                    titles.append(fallback)
                idx += 1
        return titles

    def _render_titles(self, titles):
        self.table.setRowCount(0)
        for title in titles:
            row = self.table.rowCount()
            self.table.insertRow(row)

            check_item = QTableWidgetItem("")
            check_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check_item)

            title_item = QTableWidgetItem(title)
            self.table.setItem(row, 1, title_item)

            word_item = QTableWidgetItem(str(self._word_count(title)))
            word_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, word_item)

            char_item = QTableWidgetItem(str(len(title)))
            char_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, char_item)

            controls_widget = self._create_controls_widget(title)
            self.table.setCellWidget(row, 4, controls_widget)

        self.lbl_total.setText(f"Total: {len(titles)}")

    def _create_controls_widget(self, title):
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.setSpacing(4)
        lay.addWidget(self._make_link_button("Copy", lambda: self._copy_title(title)))
        lay.addWidget(self._make_link_button("Youtube", lambda: self._open_search("youtube", title)))
        lay.addWidget(self._make_link_button("Google", lambda: self._open_search("google", title)))
        lay.addStretch()
        return wrap

    def _make_link_button(self, text, callback):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; color:#1a0dab; text-decoration: underline; padding:0; }"
            "QPushButton:hover { color:#0b57d0; }"
        )
        btn.clicked.connect(callback)
        return btn

    @staticmethod
    def _open_search(engine, title):
        query = quote_plus(str(title).strip())
        if not query:
            return
        if engine == "youtube":
            webbrowser.open_new_tab(f"https://www.youtube.com/results?search_query={query}")
        else:
            webbrowser.open_new_tab(f"https://www.google.com/search?q={query}")

    @staticmethod
    def _copy_title(title):
        QApplication.clipboard().setText(str(title))

    def _visible_titles(self):
        titles = []
        for row in range(self.table.rowCount()):
            if self.table.isRowHidden(row):
                continue
            item = self.table.item(row, 1)
            if item is not None:
                text = item.text().strip()
                if text:
                    titles.append(text)
        return titles

    def clear_all(self):
        self.table.setRowCount(0)
        self._all_titles = []
        self._filtered_keyword = ""
        self.lbl_total.setText("Total: 0")

    def open_filter_dialog(self):
        if not self._all_titles:
            QMessageBox.information(self, "Video Title Generator", "No titles to filter.")
            return
        text, ok = QInputDialog.getText(
            self,
            "Filter Titles",
            "Title contains (leave empty to reset):",
            text=self._filtered_keyword,
        )
        if not ok:
            return
        self._filtered_keyword = str(text or "").strip()
        keyword = self._filtered_keyword.lower()
        for row in range(self.table.rowCount()):
            title_item = self.table.item(row, 1)
            title = title_item.text().lower() if title_item is not None else ""
            hide = bool(keyword) and keyword not in title
            self.table.setRowHidden(row, hide)
        self.lbl_total.setText(f"Total: {len(self._visible_titles())}")

    def copy_all_titles(self):
        titles = self._visible_titles()
        if not titles:
            QMessageBox.warning(self, "Video Title Generator", "No titles to copy.")
            return
        QApplication.clipboard().setText("\n".join(titles))
        QMessageBox.information(self, "Video Title Generator", f"Copied {len(titles)} titles.")

    def save_csv(self):
        titles = self._visible_titles()
        if not titles:
            QMessageBox.warning(self, "Video Title Generator", "No titles to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Titles CSV", "video_titles.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Title", "Word Count", "Character Count"])
                for title in titles:
                    writer.writerow([title, self._word_count(title), len(title)])
            QMessageBox.information(self, "Video Title Generator", f"Saved to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Video Title Generator", f"Save failed:\n{exc}")

    def save_txt(self):
        titles = self._visible_titles()
        if not titles:
            QMessageBox.warning(self, "Video Title Generator", "No titles to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Titles TXT", "video_titles.txt", "Text Files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(titles))
            QMessageBox.information(self, "Video Title Generator", f"Saved to:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self, "Video Title Generator", f"Save failed:\n{exc}")

