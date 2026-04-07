from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.video_to_text_spinner import spin_content


class VideosContentSpinnerDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        source_title="",
        source_description="",
        source_label="",
        apply_callback=None,
    ):
        super().__init__(parent)
        self._source_title = str(source_title or "").strip()
        self._source_description = str(source_description or "").strip()
        self._source_label = str(source_label or "").strip()
        self._apply_callback = apply_callback
        self.setWindowTitle("Content Spinner Tool")
        self.setModal(True)
        self.resize(980, 680)
        self._setup_ui()
        self._load_best_source()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background:#ffffff; }"
            "QLabel { color:#111111; font-size:13px; }"
            "QTextEdit, QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:4px; padding:6px 8px; }"
            "QCheckBox { color:#111111; font-size:13px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; selection-background-color:#f1d5df; selection-color:#111111; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        top_info = QLabel(
            self._source_label
            or "Load content from the selected video, spin it, then copy or apply the rewritten text."
        )
        top_info.setWordWrap(True)
        root.addWidget(top_info)

        controls = QGridLayout()
        controls.setHorizontalSpacing(12)
        controls.setVerticalSpacing(8)

        controls.addWidget(QLabel("Spin mode:"), 0, 0)
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Basic", "Sentence Spin", "Paragraph Spin", "AI Enhanced (Later)"])
        controls.addWidget(self.combo_mode, 0, 1)

        controls.addWidget(QLabel("Strength:"), 0, 2)
        self.combo_strength = QComboBox()
        self.combo_strength.addItems(["Light", "Medium", "Strong"])
        controls.addWidget(self.combo_strength, 0, 3)
        root.addLayout(controls)

        options = QHBoxLayout()
        options.setSpacing(18)
        self.chk_preserve_meaning = QCheckBox("Preserve meaning")
        self.chk_preserve_meaning.setChecked(True)
        self.chk_avoid_repetition = QCheckBox("Avoid repetition")
        self.chk_avoid_repetition.setChecked(True)
        self.chk_keep_keywords = QCheckBox("Keep important keywords")
        self.chk_keep_keywords.setChecked(True)
        options.addWidget(self.chk_preserve_meaning)
        options.addWidget(self.chk_avoid_repetition)
        options.addWidget(self.chk_keep_keywords)
        options.addStretch()
        root.addLayout(options)

        source_buttons = QHBoxLayout()
        source_buttons.setSpacing(8)
        self.btn_use_title = QPushButton("Use Title")
        self.btn_use_description = QPushButton("Use Description")
        self.btn_use_both = QPushButton("Use Title + Description")
        for btn in (self.btn_use_title, self.btn_use_description, self.btn_use_both):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background:#2d2d2d; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
                "QPushButton:hover { background:#3a3a3a; }"
            )
        self.btn_use_title.clicked.connect(lambda: self._load_source_text("title"))
        self.btn_use_description.clicked.connect(lambda: self._load_source_text("description"))
        self.btn_use_both.clicked.connect(lambda: self._load_source_text("both"))
        source_buttons.addWidget(self.btn_use_title)
        source_buttons.addWidget(self.btn_use_description)
        source_buttons.addWidget(self.btn_use_both)
        source_buttons.addStretch()
        root.addLayout(source_buttons)

        editors = QHBoxLayout()
        editors.setSpacing(12)

        left_wrap = QWidget()
        left_layout = QVBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(QLabel("Source content"))
        self.text_source = QTextEdit()
        self.text_source.setPlaceholderText("Source text to rewrite...")
        left_layout.addWidget(self.text_source, stretch=1)
        self.lbl_source_stats = QLabel("Source: 0 words | 0 characters")
        left_layout.addWidget(self.lbl_source_stats)

        right_wrap = QWidget()
        right_layout = QVBoxLayout(right_wrap)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(QLabel("Spun result"))
        self.text_result = QTextEdit()
        self.text_result.setPlaceholderText("Preview/result will appear here.")
        right_layout.addWidget(self.text_result, stretch=1)
        self.lbl_result_stats = QLabel("Result: 0 words | 0 characters")
        right_layout.addWidget(self.lbl_result_stats)

        editors.addWidget(left_wrap, stretch=1)
        editors.addWidget(right_wrap, stretch=1)
        root.addLayout(editors, stretch=1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.btn_preview = QPushButton("Preview")
        self.btn_spin = QPushButton("Spin Content")
        self.btn_copy = QPushButton("Copy")
        self.btn_apply_title = QPushButton("Send to Title")
        self.btn_apply_description = QPushButton("Send to Description")
        self.btn_clear = QPushButton("Clear")
        self.btn_close = QPushButton("Close")

        red_style = (
            "QPushButton { background:#e50914; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#ff1a25; }"
        )
        dark_style = (
            "QPushButton { background:#2d2d2d; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#3a3a3a; }"
        )
        soft_style = (
            "QPushButton { background:#f0f0f0; color:#111111; border:1px solid #c7c7c7; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#e6e6e6; }"
        )
        for btn in (self.btn_preview, self.btn_spin, self.btn_copy, self.btn_apply_title, self.btn_apply_description):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(red_style if btn in (self.btn_preview, self.btn_spin) else dark_style)
        for btn in (self.btn_clear, self.btn_close):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(soft_style)

        self.btn_preview.clicked.connect(self._preview_spin)
        self.btn_spin.clicked.connect(self._spin_into_result)
        self.btn_copy.clicked.connect(self._copy_result)
        self.btn_apply_title.clicked.connect(lambda: self._apply_result("Title"))
        self.btn_apply_description.clicked.connect(lambda: self._apply_result("Description"))
        self.btn_clear.clicked.connect(self._clear_all)
        self.btn_close.clicked.connect(self.close)

        buttons.addWidget(self.btn_preview)
        buttons.addWidget(self.btn_spin)
        buttons.addWidget(self.btn_copy)
        buttons.addWidget(self.btn_apply_title)
        buttons.addWidget(self.btn_apply_description)
        buttons.addStretch()
        buttons.addWidget(self.btn_clear)
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

        self.text_source.textChanged.connect(self._update_source_stats)
        self.text_result.textChanged.connect(self._update_result_stats)

        has_source = bool(self._source_title or self._source_description)
        self.btn_use_title.setEnabled(bool(self._source_title))
        self.btn_use_description.setEnabled(bool(self._source_description))
        self.btn_use_both.setEnabled(has_source)
        self.btn_apply_title.setEnabled(callable(self._apply_callback))
        self.btn_apply_description.setEnabled(callable(self._apply_callback))

    @staticmethod
    def _word_count(text):
        return len([part for part in str(text or "").split() if part.strip()])

    def _update_source_stats(self):
        text = self.text_source.toPlainText()
        self.lbl_source_stats.setText(
            f"Source: {self._word_count(text):,} words | {len(text):,} characters"
        )

    def _update_result_stats(self):
        text = self.text_result.toPlainText()
        self.lbl_result_stats.setText(
            f"Result: {self._word_count(text):,} words | {len(text):,} characters"
        )

    def _load_best_source(self):
        if self._source_description:
            self._load_source_text("description")
            return
        if self._source_title:
            self._load_source_text("title")

    def _load_source_text(self, mode):
        if mode == "title":
            text = self._source_title
        elif mode == "description":
            text = self._source_description
        else:
            parts = [part for part in (self._source_title, self._source_description) if part]
            text = "\n\n".join(parts)
        self.text_source.setPlainText(text)

    def _options(self):
        return {
            "mode": self.combo_mode.currentText(),
            "strength": self.combo_strength.currentText(),
            "preserve_meaning": self.chk_preserve_meaning.isChecked(),
            "avoid_repetition": self.chk_avoid_repetition.isChecked(),
            "keep_keywords": self.chk_keep_keywords.isChecked(),
        }

    def _spin_source_text(self):
        source_text = self.text_source.toPlainText().strip()
        if not source_text:
            QMessageBox.warning(self, "Content Spinner Tool", "Please provide source content first.")
            return ""
        return spin_content(source_text, **self._options()).strip()

    def _preview_spin(self):
        spun = self._spin_source_text()
        if not spun:
            return
        self.text_result.setPlainText(spun)

    def _spin_into_result(self):
        spun = self._spin_source_text()
        if not spun:
            return
        self.text_result.setPlainText(spun)
        QMessageBox.information(self, "Content Spinner Tool", "Spin Content complete.")

    def _copy_result(self):
        text = self.text_result.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Content Spinner Tool", "No spun content to copy.")
            return
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Content Spinner Tool", "Copied spun content to clipboard.")

    def _apply_result(self, target_field):
        text = self.text_result.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Content Spinner Tool", "No spun content to apply.")
            return
        if not callable(self._apply_callback):
            QMessageBox.information(self, "Content Spinner Tool", "Apply target is not available here.")
            return
        self._apply_callback(target_field, text)
        QMessageBox.information(self, "Content Spinner Tool", f"Updated video {target_field.lower()}.")

    def _clear_all(self):
        self.text_source.clear()
        self.text_result.clear()

