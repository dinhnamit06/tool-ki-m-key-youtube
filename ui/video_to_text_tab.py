import re

from PyQt6.QtGui import QAction, QDesktopServices, QTextCursor, QTextDocument
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QMenu,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.video_to_text_ai import AIPunctuateWorker, AIStructureWorker
from core.video_to_text_cleaner import clean_script_text
from core.video_to_text_formatter import auto_punctuate_transcript
from core.video_to_text_fetcher import VideoToTextWorker, normalize_video_text_input
from core.video_to_text_rewriter import AIRewriteWorker, local_rewrite_similar_script
from core.video_to_text_spinner import spin_content
from core.video_to_text_structure import extract_structure, format_structure_output
from core.video_to_text_summarizer import summarize_text


class FindReplaceDialog(QDialog):
    def __init__(self, owner_tab, parent=None):
        super().__init__(parent)
        self.owner_tab = owner_tab
        self.setWindowTitle("Find / Replace")
        self.setModal(True)
        self.resize(520, 210)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background:#1a1a1a; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #cfd4dc; border-radius:3px; padding:6px 8px; }"
            "QCheckBox { color:#ffffff; font-size:13px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        lbl_find = QLabel("Find:")
        lbl_replace = QLabel("Replace with:")
        self.input_find = QLineEdit()
        self.input_replace = QLineEdit()

        form.addWidget(lbl_find, 0, 0)
        form.addWidget(self.input_find, 0, 1)
        form.addWidget(lbl_replace, 1, 0)
        form.addWidget(self.input_replace, 1, 1)
        root.addLayout(form)

        options_row = QHBoxLayout()
        options_row.setSpacing(18)
        self.chk_match_case = QCheckBox("Match case")
        self.chk_whole_word = QCheckBox("Whole word")
        self.chk_wrap_search = QCheckBox("Wrap search")
        self.chk_wrap_search.setChecked(True)
        options_row.addWidget(self.chk_match_case)
        options_row.addWidget(self.chk_whole_word)
        options_row.addWidget(self.chk_wrap_search)
        options_row.addStretch()
        root.addLayout(options_row)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:3px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        self.btn_find_next = QPushButton("Find Next")
        self.btn_replace_one = QPushButton("Replace")
        self.btn_replace_all = QPushButton("Replace All")
        self.btn_close = QPushButton("Close")

        for btn in (self.btn_find_next, self.btn_replace_one, self.btn_replace_all, self.btn_close):
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(button_style)

        self.btn_find_next.clicked.connect(self._find_next)
        self.btn_replace_one.clicked.connect(self._replace_one)
        self.btn_replace_all.clicked.connect(self._replace_all)
        self.btn_close.clicked.connect(self.close)

        buttons_row.addWidget(self.btn_find_next)
        buttons_row.addWidget(self.btn_replace_one)
        buttons_row.addWidget(self.btn_replace_all)
        buttons_row.addStretch()
        buttons_row.addWidget(self.btn_close)
        root.addLayout(buttons_row)

    def _options(self) -> dict:
        return {
            "find_text": self.input_find.text(),
            "replace_text": self.input_replace.text(),
            "match_case": self.chk_match_case.isChecked(),
            "whole_word": self.chk_whole_word.isChecked(),
            "wrap_search": self.chk_wrap_search.isChecked(),
        }

    def _find_next(self):
        found = self.owner_tab.find_next_in_output(**self._options())
        if not found:
            QMessageBox.information(self, "Find / Replace", "No more matches were found.")

    def _replace_one(self):
        replaced = self.owner_tab.replace_current_in_output(**self._options())
        if not replaced:
            QMessageBox.information(self, "Find / Replace", "Nothing was replaced.")

    def _replace_all(self):
        count = self.owner_tab.replace_all_in_output(**self._options())
        if count <= 0:
            QMessageBox.information(self, "Find / Replace", "No matches were replaced.")
        else:
            QMessageBox.information(self, "Find / Replace", f"Replaced {count} match(es).")


class ContentSpinnerDialog(QDialog):
    def __init__(self, owner_tab, parent=None):
        super().__init__(parent)
        self.owner_tab = owner_tab
        self.setWindowTitle("Content Spinner")
        self.setModal(True)
        self.resize(560, 300)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background:#1a1a1a; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QLineEdit, QComboBox, QTextEdit { background:#ffffff; color:#111111; border:1px solid #cfd4dc; border-radius:3px; padding:6px 8px; }"
            "QCheckBox { color:#ffffff; font-size:13px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; selection-background-color:#e24a22; selection-color:#ffffff; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        lbl_intro = QLabel("Create a rewritten variation of the current transcript without changing the main meaning.")
        lbl_intro.setWordWrap(True)
        root.addWidget(lbl_intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        lbl_mode = QLabel("Spin mode:")
        lbl_strength = QLabel("Spin strength:")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Basic",
            "Sentence Spin",
            "Paragraph Spin",
            "AI Enhanced (Later)",
        ])
        self.combo_strength = QComboBox()
        self.combo_strength.addItems(["Light", "Medium", "Strong"])

        grid.addWidget(lbl_mode, 0, 0)
        grid.addWidget(self.combo_mode, 0, 1)
        grid.addWidget(lbl_strength, 1, 0)
        grid.addWidget(self.combo_strength, 1, 1)
        root.addLayout(grid)

        options_row = QHBoxLayout()
        options_row.setSpacing(18)
        self.chk_preserve_meaning = QCheckBox("Preserve meaning")
        self.chk_preserve_meaning.setChecked(True)
        self.chk_avoid_repetition = QCheckBox("Avoid repetition")
        self.chk_avoid_repetition.setChecked(True)
        self.chk_keep_keywords = QCheckBox("Keep important keywords")
        self.chk_keep_keywords.setChecked(True)
        options_row.addWidget(self.chk_preserve_meaning)
        options_row.addWidget(self.chk_avoid_repetition)
        options_row.addWidget(self.chk_keep_keywords)
        options_row.addStretch()
        root.addLayout(options_row)

        stats_text = self.owner_tab.text_output.toPlainText()
        word_count = len([part for part in stats_text.split() if part.strip()])
        line_count = len([line for line in stats_text.splitlines() if line.strip()])
        self.lbl_stats = QLabel(f"Source content: {line_count:,} lines | {word_count:,} words | {len(stats_text):,} characters")
        self.lbl_stats.setStyleSheet("QLabel { color:#d6d6d6; font-size:12px; }")
        root.addWidget(self.lbl_stats)

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setPlaceholderText("Spun preview will appear here in the next step.")
        self.preview_box.setMinimumHeight(120)
        root.addWidget(self.preview_box, stretch=1)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:3px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        self.btn_preview = QPushButton("Preview")
        self.btn_spin = QPushButton("Spin Content")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_preview, self.btn_spin, self.btn_close):
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(button_style)

        self.btn_preview.clicked.connect(self._preview_spin)
        self.btn_spin.clicked.connect(self._apply_spin)
        self.btn_close.clicked.connect(self.close)

        buttons_row.addWidget(self.btn_preview)
        buttons_row.addWidget(self.btn_spin)
        buttons_row.addStretch()
        buttons_row.addWidget(self.btn_close)
        root.addLayout(buttons_row)

    def _options(self) -> dict:
        return {
            "mode": self.combo_mode.currentText(),
            "strength": self.combo_strength.currentText(),
            "preserve_meaning": self.chk_preserve_meaning.isChecked(),
            "avoid_repetition": self.chk_avoid_repetition.isChecked(),
            "keep_keywords": self.chk_keep_keywords.isChecked(),
        }

    def _preview_spin(self):
        spun = self.owner_tab.generate_spun_content(**self._options())
        if not spun:
            QMessageBox.information(self, "Content Spinner", "There is no content to spin.")
            return
        self.preview_box.setPlainText(spun)

    def _apply_spin(self):
        spun = self.owner_tab.apply_spun_content(**self._options())
        if not spun:
            QMessageBox.information(self, "Content Spinner", "There is no content to spin.")
            return
        self.preview_box.setPlainText(spun)
        QMessageBox.information(self, "Content Spinner", "Spin Content complete.")


class CleanScriptDialog(QDialog):
    def __init__(self, owner_tab, parent=None):
        super().__init__(parent)
        self.owner_tab = owner_tab
        self.setWindowTitle("Clean Script")
        self.setModal(True)
        self.resize(620, 340)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background:#1a1a1a; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QComboBox, QTextEdit { background:#ffffff; color:#111111; border:1px solid #cfd4dc; border-radius:3px; padding:6px 8px; }"
            "QCheckBox { color:#ffffff; font-size:13px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; selection-background-color:#e24a22; selection-color:#ffffff; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        lbl_intro = QLabel("Clean transcript noise, filler words, and repeated caption artifacts before further processing.")
        lbl_intro.setWordWrap(True)
        root.addWidget(lbl_intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        lbl_mode = QLabel("Clean mode:")
        lbl_output_style = QLabel("Output style:")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Basic",
            "Strong Cleanup",
            "AI Enhanced (Later)",
        ])
        self.combo_output_style = QComboBox()
        self.combo_output_style.addItems([
            "Readable Transcript",
            "Clean Script",
            "Minimal Cleanup",
        ])

        grid.addWidget(lbl_mode, 0, 0)
        grid.addWidget(self.combo_mode, 0, 1)
        grid.addWidget(lbl_output_style, 1, 0)
        grid.addWidget(self.combo_output_style, 1, 1)
        root.addLayout(grid)

        options_row_one = QHBoxLayout()
        options_row_one.setSpacing(18)
        self.chk_remove_filler = QCheckBox("Remove filler words")
        self.chk_remove_filler.setChecked(True)
        self.chk_remove_repeated = QCheckBox("Remove repeated lines")
        self.chk_remove_repeated.setChecked(True)
        options_row_one.addWidget(self.chk_remove_filler)
        options_row_one.addWidget(self.chk_remove_repeated)
        options_row_one.addStretch()
        root.addLayout(options_row_one)

        options_row_two = QHBoxLayout()
        options_row_two.setSpacing(18)
        self.chk_fix_noise = QCheckBox("Fix spacing and punctuation noise")
        self.chk_fix_noise.setChecked(True)
        self.chk_preserve_meaning = QCheckBox("Preserve original meaning")
        self.chk_preserve_meaning.setChecked(True)
        options_row_two.addWidget(self.chk_fix_noise)
        options_row_two.addWidget(self.chk_preserve_meaning)
        options_row_two.addStretch()
        root.addLayout(options_row_two)

        source_text = self.owner_tab.text_output.toPlainText()
        word_count = len([part for part in source_text.split() if part.strip()])
        line_count = len([line for line in source_text.splitlines() if line.strip()])
        self.lbl_stats = QLabel(f"Source content: {line_count:,} lines | {word_count:,} words | {len(source_text):,} characters")
        self.lbl_stats.setStyleSheet("QLabel { color:#d6d6d6; font-size:12px; }")
        root.addWidget(self.lbl_stats)

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setPlaceholderText("Cleaned preview will appear here in the next step.")
        self.preview_box.setMinimumHeight(130)
        root.addWidget(self.preview_box, stretch=1)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:3px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        self.btn_preview = QPushButton("Preview")
        self.btn_clean = QPushButton("Clean Script")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_preview, self.btn_clean, self.btn_close):
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(button_style)

        self.btn_preview.clicked.connect(self._preview_clean)
        self.btn_clean.clicked.connect(self._apply_clean)
        self.btn_close.clicked.connect(self.close)

        buttons_row.addWidget(self.btn_preview)
        buttons_row.addWidget(self.btn_clean)
        buttons_row.addStretch()
        buttons_row.addWidget(self.btn_close)
        root.addLayout(buttons_row)

    def _options(self) -> dict:
        return {
            "mode": self.combo_mode.currentText(),
            "output_style": self.combo_output_style.currentText(),
            "remove_filler_words": self.chk_remove_filler.isChecked(),
            "remove_repeated_lines": self.chk_remove_repeated.isChecked(),
            "fix_spacing_and_noise": self.chk_fix_noise.isChecked(),
            "preserve_original_meaning": self.chk_preserve_meaning.isChecked(),
        }

    def _preview_clean(self):
        cleaned = self.owner_tab.generate_clean_script(**self._options())
        if not cleaned:
            QMessageBox.information(self, "Clean Script", "There is no content to clean.")
            return
        self.preview_box.setPlainText(cleaned)

    def _apply_clean(self):
        cleaned = self.owner_tab.apply_clean_script(**self._options())
        if not cleaned:
            QMessageBox.information(self, "Clean Script", "There is no content to clean.")
            return
        self.preview_box.setPlainText(cleaned)
        QMessageBox.information(self, "Clean Script", "Clean Script complete.")


class SummarizeDialog(QDialog):
    def __init__(self, owner_tab, parent=None):
        super().__init__(parent)
        self.owner_tab = owner_tab
        self.setWindowTitle("Summarize")
        self.setModal(True)
        self.resize(620, 340)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background:#1a1a1a; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QComboBox, QTextEdit { background:#ffffff; color:#111111; border:1px solid #cfd4dc; border-radius:3px; padding:6px 8px; }"
            "QCheckBox { color:#ffffff; font-size:13px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; selection-background-color:#e24a22; selection-color:#ffffff; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        lbl_intro = QLabel("Generate a clean summary from the current transcript or cleaned script.")
        lbl_intro.setWordWrap(True)
        root.addWidget(lbl_intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        lbl_mode = QLabel("Summary mode:")
        lbl_length = QLabel("Summary length:")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Short Summary",
            "Bullet Summary",
            "Key Takeaways",
        ])
        self.combo_length = QComboBox()
        self.combo_length.addItems([
            "Short",
            "Medium",
            "Detailed",
        ])

        grid.addWidget(lbl_mode, 0, 0)
        grid.addWidget(self.combo_mode, 0, 1)
        grid.addWidget(lbl_length, 1, 0)
        grid.addWidget(self.combo_length, 1, 1)
        root.addLayout(grid)

        options_row = QHBoxLayout()
        options_row.setSpacing(18)
        self.chk_use_cleaned_text = QCheckBox("Prefer cleaned text if available")
        self.chk_use_cleaned_text.setChecked(True)
        self.chk_keep_names = QCheckBox("Keep important names and keywords")
        self.chk_keep_names.setChecked(True)
        options_row.addWidget(self.chk_use_cleaned_text)
        options_row.addWidget(self.chk_keep_names)
        options_row.addStretch()
        root.addLayout(options_row)

        source_text = self.owner_tab.text_output.toPlainText()
        word_count = len([part for part in source_text.split() if part.strip()])
        line_count = len([line for line in source_text.splitlines() if line.strip()])
        self.lbl_stats = QLabel(f"Source content: {line_count:,} lines | {word_count:,} words | {len(source_text):,} characters")
        self.lbl_stats.setStyleSheet("QLabel { color:#d6d6d6; font-size:12px; }")
        root.addWidget(self.lbl_stats)

        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setPlaceholderText("Summary preview will appear here in the next step.")
        self.preview_box.setMinimumHeight(130)
        root.addWidget(self.preview_box, stretch=1)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:3px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        self.btn_preview = QPushButton("Preview")
        self.btn_summarize = QPushButton("Summarize")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_preview, self.btn_summarize, self.btn_close):
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(button_style)

        self.btn_preview.clicked.connect(self._preview_summary)
        self.btn_summarize.clicked.connect(self._apply_summary)
        self.btn_close.clicked.connect(self.close)

        buttons_row.addWidget(self.btn_preview)
        buttons_row.addWidget(self.btn_summarize)
        buttons_row.addStretch()
        buttons_row.addWidget(self.btn_close)
        root.addLayout(buttons_row)

    def _options(self) -> dict:
        return {
            "mode": self.combo_mode.currentText(),
            "length": self.combo_length.currentText(),
            "prefer_cleaned_text": self.chk_use_cleaned_text.isChecked(),
            "keep_names_and_keywords": self.chk_keep_names.isChecked(),
        }

    def _preview_summary(self):
        summary = self.owner_tab.generate_summary_content(**self._options())
        if not summary:
            QMessageBox.information(self, "Summarize", "There is no content to summarize.")
            return
        self.preview_box.setPlainText(summary)

    def _apply_summary(self):
        summary = self.owner_tab.apply_summary_content(**self._options())
        if not summary:
            QMessageBox.information(self, "Summarize", "There is no content to summarize.")
            return
        self.preview_box.setPlainText(summary)
        QMessageBox.information(self, "Summarize", "Summarize complete.")


class ExtractStructureDialog(QDialog):
    def __init__(self, owner_tab, parent=None):
        super().__init__(parent)
        self.owner_tab = owner_tab
        self._worker = None
        self._apply_after_finish = False
        self._is_closing = False
        self.setWindowTitle("Extract Structure")
        self.setModal(True)
        self.resize(760, 520)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background:#1a1a1a; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QComboBox, QTextEdit { background:#ffffff; color:#111111; border:1px solid #cfd4dc; border-radius:3px; padding:6px 8px; }"
            "QCheckBox { color:#ffffff; font-size:13px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; selection-background-color:#e24a22; selection-color:#ffffff; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        lbl_intro = QLabel("Extract the core video structure into hook, intro, main points, and CTA.")
        lbl_intro.setWordWrap(True)
        root.addWidget(lbl_intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        lbl_mode = QLabel("Structure mode:")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "Basic",
            "Detailed",
            "AI Enhanced (Gemini)",
        ])
        grid.addWidget(lbl_mode, 0, 0)
        grid.addWidget(self.combo_mode, 0, 1)
        root.addLayout(grid)

        options_row = QHBoxLayout()
        options_row.setSpacing(18)
        self.chk_prefer_cleaned = QCheckBox("Prefer cleaned text if available")
        self.chk_prefer_cleaned.setChecked(True)
        self.chk_keep_original_flow = QCheckBox("Preserve original flow")
        self.chk_keep_original_flow.setChecked(True)
        options_row.addWidget(self.chk_prefer_cleaned)
        options_row.addWidget(self.chk_keep_original_flow)
        options_row.addStretch()
        root.addLayout(options_row)

        source_text = self.owner_tab.text_output.toPlainText()
        word_count = len([part for part in source_text.split() if part.strip()])
        line_count = len([line for line in source_text.splitlines() if line.strip()])
        self.lbl_stats = QLabel(f"Source content: {line_count:,} lines | {word_count:,} words | {len(source_text):,} characters")
        self.lbl_stats.setStyleSheet("QLabel { color:#d6d6d6; font-size:12px; }")
        root.addWidget(self.lbl_stats)

        self.lbl_runtime = QLabel("")
        self.lbl_runtime.setStyleSheet("QLabel { color:#bfc9d8; font-size:12px; }")
        root.addWidget(self.lbl_runtime)

        sections_grid = QGridLayout()
        sections_grid.setHorizontalSpacing(12)
        sections_grid.setVerticalSpacing(10)

        self.box_hook = QTextEdit()
        self.box_intro = QTextEdit()
        self.box_main_points = QTextEdit()
        self.box_cta = QTextEdit()
        for box in (self.box_hook, self.box_intro, self.box_main_points, self.box_cta):
            box.setReadOnly(True)

        self.box_hook.setPlaceholderText("Hook preview will appear here.")
        self.box_intro.setPlaceholderText("Intro preview will appear here.")
        self.box_main_points.setPlaceholderText("Main points preview will appear here.")
        self.box_cta.setPlaceholderText("CTA preview will appear here.")
        self.box_hook.setMinimumHeight(80)
        self.box_intro.setMinimumHeight(90)
        self.box_main_points.setMinimumHeight(150)
        self.box_cta.setMinimumHeight(80)

        sections_grid.addWidget(QLabel("Hook"), 0, 0)
        sections_grid.addWidget(QLabel("Intro"), 0, 1)
        sections_grid.addWidget(self.box_hook, 1, 0)
        sections_grid.addWidget(self.box_intro, 1, 1)
        sections_grid.addWidget(QLabel("Main Points"), 2, 0)
        sections_grid.addWidget(QLabel("CTA"), 2, 1)
        sections_grid.addWidget(self.box_main_points, 3, 0)
        sections_grid.addWidget(self.box_cta, 3, 1)
        root.addLayout(sections_grid)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:3px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        self.btn_preview = QPushButton("Preview")
        self.btn_extract = QPushButton("Extract Structure")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_preview, self.btn_extract, self.btn_close):
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(button_style)

        self.btn_preview.clicked.connect(self._preview_structure)
        self.btn_extract.clicked.connect(self._apply_structure)
        self.btn_close.clicked.connect(self.close)

        buttons_row.addWidget(self.btn_preview)
        buttons_row.addWidget(self.btn_extract)
        buttons_row.addStretch()
        buttons_row.addWidget(self.btn_close)
        root.addLayout(buttons_row)

    def _options(self) -> dict:
        return {
            "mode": self.combo_mode.currentText(),
            "prefer_cleaned_text": self.chk_prefer_cleaned.isChecked(),
            "preserve_original_flow": self.chk_keep_original_flow.isChecked(),
        }

    def _render_structure(self, structure: dict):
        self.box_hook.setPlainText(str(structure.get("hook", "")).strip())
        self.box_intro.setPlainText(str(structure.get("intro", "")).strip())
        points = [str(item).strip() for item in (structure.get("main_points", []) or []) if str(item).strip()]
        self.box_main_points.setPlainText("\n".join(f"{idx}. {point}" for idx, point in enumerate(points, start=1)))
        self.box_cta.setPlainText(str(structure.get("cta", "")).strip())

    def _preview_structure(self):
        self._start_structure_job(apply_after_finish=False)

    def _apply_structure(self):
        self._start_structure_job(apply_after_finish=True)

    def _set_busy_state(self, busy: bool):
        self.combo_mode.setDisabled(busy)
        self.chk_prefer_cleaned.setDisabled(busy)
        self.chk_keep_original_flow.setDisabled(busy)
        self.btn_preview.setDisabled(busy)
        self.btn_extract.setDisabled(busy)
        self.btn_close.setDisabled(False)

    def _start_structure_job(self, *, apply_after_finish: bool):
        options = self._options()
        mode = str(options.get("mode", "")).strip()
        if mode == "AI Enhanced (Gemini)":
            if self.owner_tab.has_active_long_running_task():
                QMessageBox.information(self, "Extract Structure", "Another long-running task is already running. Please wait for it to finish first.")
                return
            source_text = self.owner_tab.resolve_source_text(bool(options.get("prefer_cleaned_text")))
            if not source_text.strip():
                QMessageBox.information(self, "Extract Structure", "There is no content to analyze.")
                return
            self._apply_after_finish = apply_after_finish
            self._set_busy_state(True)
            self.lbl_runtime.setText("AI Enhanced structure extraction is running...")
            self._worker = AIStructureWorker(
                source_text,
                preserve_original_flow=bool(options.get("preserve_original_flow")),
            )
            self.owner_tab.register_background_worker(self._worker)
            self._worker.status_signal.connect(self._handle_worker_status)
            self._worker.error_signal.connect(self._handle_worker_error)
            self._worker.finished_signal.connect(self._handle_worker_finished)
            self._worker.finished.connect(self._cleanup_worker_reference)
            self._worker.start()
            return

        structure = self.owner_tab.generate_structure_content(**options)
        if not structure:
            QMessageBox.information(self, "Extract Structure", "There is no content to analyze.")
            return
        self._render_structure(structure)
        if apply_after_finish:
            self.owner_tab.apply_structure_result(structure)
            QMessageBox.information(self, "Extract Structure", "Structure extraction complete.")

    def _handle_worker_status(self, message: str):
        worker = self.sender()
        if self._is_closing or worker is not self._worker:
            return
        runtime_message = str(message or "AI Enhanced structure extraction is running...")
        self.lbl_runtime.setText(runtime_message)
        if self.owner_tab.main_window and self.owner_tab.main_window.statusBar():
            self.owner_tab.main_window.statusBar().showMessage(runtime_message, 3000)

    def _handle_worker_error(self, message: str):
        worker = self.sender()
        if self._is_closing or worker is not self._worker:
            return
        options = self._options()
        self.lbl_runtime.setText("AI failed. Falling back to local structure extraction...")
        if self.owner_tab.main_window and self.owner_tab.main_window.statusBar():
            self.owner_tab.main_window.statusBar().showMessage(
                f"AI Extract Structure failed. Falling back to local mode. {str(message or '').strip()}",
                5000,
            )
        structure = self.owner_tab.generate_structure_content(
            mode="Detailed",
            prefer_cleaned_text=bool(options.get("prefer_cleaned_text")),
            preserve_original_flow=bool(options.get("preserve_original_flow")),
        )
        if not structure:
            self._set_busy_state(False)
            self.lbl_runtime.setText("")
            QMessageBox.warning(self, "Extract Structure", str(message or "Could not extract structure."))
            return
        self._render_structure(structure)
        if self._apply_after_finish:
            self.owner_tab.apply_structure_result(structure)
            QMessageBox.information(self, "Extract Structure", "Structure extraction complete.")
        self._set_busy_state(False)
        self.lbl_runtime.setText("")

    def _handle_worker_finished(self, structure: dict):
        worker = self.sender()
        if self._is_closing or worker is not self._worker:
            return
        if not structure:
            self._set_busy_state(False)
            self.lbl_runtime.setText("")
            QMessageBox.information(self, "Extract Structure", "There is no content to analyze.")
            return
        self._render_structure(structure)
        if self._apply_after_finish:
            self.owner_tab.apply_structure_result(structure)
            QMessageBox.information(self, "Extract Structure", "Structure extraction complete.")
        self._set_busy_state(False)
        self.lbl_runtime.setText("")

    def _cleanup_worker_reference(self):
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
        self.owner_tab.prune_background_workers()

    def closeEvent(self, event):
        self._is_closing = True
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
        self._set_busy_state(False)
        super().closeEvent(event)


class RewriteSimilarScriptDialog(QDialog):
    def __init__(self, owner_tab, parent=None):
        super().__init__(parent)
        self.owner_tab = owner_tab
        self._worker = None
        self._apply_after_finish = False
        self._is_closing = False
        self.setWindowTitle("Rewrite Similar Script")
        self.setModal(True)
        self.resize(680, 380)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background:#1a1a1a; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #cfd4dc; border-radius:3px; padding:5px 8px; }"
            "QCheckBox { color:#ffffff; font-size:13px; }"
            "QTextEdit { background:#ffffff; color:#111111; border:1px solid #cfd4dc; border-radius:3px; padding:8px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        lbl_mode = QLabel("Rewrite mode:")
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(
            [
                "Close Match",
                "Fresh Rewrite",
                "Hook-First Rewrite",
                "Cleaner Script",
            ]
        )

        lbl_style = QLabel("Output style:")
        self.combo_style = QComboBox()
        self.combo_style.addItems(
            [
                "Paragraph Script",
                "Voiceover Script",
                "Simple Script",
            ]
        )

        grid.addWidget(lbl_mode, 0, 0)
        grid.addWidget(self.combo_mode, 0, 1)
        grid.addWidget(lbl_style, 1, 0)
        grid.addWidget(self.combo_style, 1, 1)
        root.addLayout(grid)

        options_row_one = QHBoxLayout()
        options_row_one.setSpacing(18)
        self.chk_preserve_meaning = QCheckBox("Preserve original meaning")
        self.chk_keep_structure = QCheckBox("Keep original structure")
        self.chk_preserve_meaning.setChecked(True)
        self.chk_keep_structure.setChecked(True)
        options_row_one.addWidget(self.chk_preserve_meaning)
        options_row_one.addWidget(self.chk_keep_structure)
        options_row_one.addStretch()
        root.addLayout(options_row_one)

        options_row_two = QHBoxLayout()
        options_row_two.setSpacing(18)
        self.chk_avoid_copy = QCheckBox("Avoid copied phrasing")
        self.chk_prefer_cleaned = QCheckBox("Prefer cleaned text if available")
        self.chk_avoid_copy.setChecked(True)
        self.chk_prefer_cleaned.setChecked(True)
        options_row_two.addWidget(self.chk_avoid_copy)
        options_row_two.addWidget(self.chk_prefer_cleaned)
        options_row_two.addStretch()
        root.addLayout(options_row_two)

        source_text = self.owner_tab.text_output.toPlainText().strip()
        lines = len([line for line in source_text.splitlines() if line.strip()])
        words = len(source_text.split())
        chars = len(source_text)
        self.lbl_source_stats = QLabel(f"Source content: {lines} Lines | {words} Words | {chars} Characters")
        self.lbl_source_stats.setStyleSheet("color:#bbbbbb; font-size:12px;")
        root.addWidget(self.lbl_source_stats)

        self.lbl_runtime = QLabel("")
        self.lbl_runtime.setStyleSheet("color:#bfc9d8; font-size:12px;")
        root.addWidget(self.lbl_runtime)

        lbl_preview = QLabel("Preview")
        root.addWidget(lbl_preview)
        self.preview_box = QTextEdit()
        self.preview_box.setReadOnly(True)
        self.preview_box.setPlaceholderText("Preview of the rewritten script will appear here.")
        root.addWidget(self.preview_box, 1)

        button_style = (
            "QPushButton { background:#e74c1b; color:#ffffff; border:none; border-radius:4px; "
            "padding:7px 14px; font-weight:bold; }"
            "QPushButton:hover { background:#ff6a32; }"
        )
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        self.btn_preview = QPushButton("Preview")
        self.btn_rewrite = QPushButton("Rewrite Script")
        self.btn_close = QPushButton("Close")
        for btn in (self.btn_preview, self.btn_rewrite, self.btn_close):
            btn.setMinimumHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(button_style)

        self.btn_preview.clicked.connect(self._preview_rewrite)
        self.btn_rewrite.clicked.connect(self._apply_rewrite)
        self.btn_close.clicked.connect(self.close)

        buttons_row.addWidget(self.btn_preview)
        buttons_row.addWidget(self.btn_rewrite)
        buttons_row.addStretch()
        buttons_row.addWidget(self.btn_close)
        root.addLayout(buttons_row)

    def _preview_rewrite(self):
        self._start_rewrite_job(apply_after_finish=False)

    def _apply_rewrite(self):
        self._start_rewrite_job(apply_after_finish=True)

    def _options(self) -> dict:
        return {
            "mode": self.combo_mode.currentText(),
            "output_style": self.combo_style.currentText(),
            "preserve_original_meaning": self.chk_preserve_meaning.isChecked(),
            "keep_original_structure": self.chk_keep_structure.isChecked(),
            "avoid_copied_phrasing": self.chk_avoid_copy.isChecked(),
            "prefer_cleaned_text": self.chk_prefer_cleaned.isChecked(),
        }

    def _set_busy_state(self, busy: bool):
        self.combo_mode.setDisabled(busy)
        self.combo_style.setDisabled(busy)
        self.chk_preserve_meaning.setDisabled(busy)
        self.chk_keep_structure.setDisabled(busy)
        self.chk_avoid_copy.setDisabled(busy)
        self.chk_prefer_cleaned.setDisabled(busy)
        self.btn_preview.setDisabled(busy)
        self.btn_rewrite.setDisabled(busy)
        self.btn_close.setDisabled(False)

    def _start_rewrite_job(self, *, apply_after_finish: bool):
        options = self._options()
        if self.owner_tab.has_active_long_running_task():
            QMessageBox.information(self, "Rewrite Similar Script", "Another long-running task is already running. Please wait for it to finish first.")
            return
        source_text = self.owner_tab.resolve_source_text(bool(options.get("prefer_cleaned_text")))
        if not source_text.strip():
            QMessageBox.information(self, "Rewrite Similar Script", "There is no content to rewrite.")
            return
        self._apply_after_finish = apply_after_finish
        self._set_busy_state(True)
        self.lbl_runtime.setText("AI Rewrite Similar Script is running...")
        self._worker = AIRewriteWorker(
            source_text,
            mode=str(options.get("mode", "")),
            output_style=str(options.get("output_style", "")),
            preserve_original_meaning=bool(options.get("preserve_original_meaning")),
            keep_original_structure=bool(options.get("keep_original_structure")),
            avoid_copied_phrasing=bool(options.get("avoid_copied_phrasing")),
        )
        self.owner_tab.register_background_worker(self._worker)
        self._worker.status_signal.connect(self._handle_worker_status)
        self._worker.error_signal.connect(self._handle_worker_error)
        self._worker.finished_signal.connect(self._handle_worker_finished)
        self._worker.finished.connect(self._cleanup_worker_reference)
        self._worker.start()

    def _handle_worker_status(self, message: str):
        worker = self.sender()
        if self._is_closing or worker is not self._worker:
            return
        runtime_message = str(message or "AI Rewrite Similar Script is running...")
        self.lbl_runtime.setText(runtime_message)
        if self.owner_tab.main_window and self.owner_tab.main_window.statusBar():
            self.owner_tab.main_window.statusBar().showMessage(runtime_message, 3000)

    def _handle_worker_error(self, message: str):
        worker = self.sender()
        if self._is_closing or worker is not self._worker:
            return
        options = self._options()
        self.lbl_runtime.setText("AI failed. Falling back to local rewrite...")
        if self.owner_tab.main_window and self.owner_tab.main_window.statusBar():
            self.owner_tab.main_window.statusBar().showMessage(
                f"AI Rewrite failed. Falling back to local rewrite. {str(message or '').strip()}",
                5000,
            )
        rewritten = self.owner_tab.generate_rewritten_script(**options)
        if not rewritten:
            self._set_busy_state(False)
            self.lbl_runtime.setText("")
            QMessageBox.warning(self, "Rewrite Similar Script", str(message or "Could not rewrite content."))
            return
        self.preview_box.setPlainText(rewritten)
        if self._apply_after_finish:
            self.owner_tab.apply_rewritten_result(rewritten)
            QMessageBox.information(self, "Rewrite Similar Script", "Rewrite Similar Script complete.")
        self._set_busy_state(False)
        self.lbl_runtime.setText("")

    def _handle_worker_finished(self, rewritten: str):
        worker = self.sender()
        if self._is_closing or worker is not self._worker:
            return
        result = str(rewritten or "").strip()
        if not result:
            self._set_busy_state(False)
            self.lbl_runtime.setText("")
            QMessageBox.information(self, "Rewrite Similar Script", "There is no content to rewrite.")
            return
        self.preview_box.setPlainText(result)
        if self._apply_after_finish:
            self.owner_tab.apply_rewritten_result(result)
            QMessageBox.information(self, "Rewrite Similar Script", "Rewrite Similar Script complete.")
        self._set_busy_state(False)
        self.lbl_runtime.setText("")

    def _cleanup_worker_reference(self):
        worker = self.sender()
        if worker is self._worker:
            self._worker = None
        self.owner_tab.prune_background_workers()

    def closeEvent(self, event):
        self._is_closing = True
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
        self._set_busy_state(False)
        super().closeEvent(event)


class VideoToTextTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._pending_links = []
        self._worker = None
        self._ai_punctuate_worker = None
        self._background_workers = []
        self._raw_transcript_text = ""
        self._cleaned_transcript_text = ""
        self._structured_output_text = ""
        self._rewritten_script_text = ""
        self._current_text_path = ""
        self._current_video_title = ""
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame()
        shell.setStyleSheet("QFrame { background:#f8f8f8; }")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        content = QFrame()
        content.setStyleSheet("QFrame { background:#ffffff; border-top:1px solid #dadada; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 8, 0, 0)
        content_layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        lbl_input = QLabel("Video link or ID:")
        lbl_input.setStyleSheet("QLabel { color:#111111; font-size:13px; }")
        top_row.addWidget(lbl_input)

        self.input_video_link = QLineEdit()
        self.input_video_link.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.input_video_link.setStyleSheet(
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #cfd4dc; "
            "border-radius:2px; padding:4px 6px; font-size:12px; selection-background-color:#e50914; selection-color:#ffffff; }"
        )
        top_row.addWidget(self.input_video_link, stretch=1)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:3px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
            "QPushButton:disabled { background:#c58b7c; color:#f6e2dc; }"
        )

        self.btn_convert = QPushButton("Convert to Text")
        self.btn_auto_punctuate = QPushButton("Auto Punctuate")
        self.btn_clean_script = QPushButton("Clean Script")
        self.btn_summarize = QPushButton("Summarize")
        self.btn_extract_structure = QPushButton("Extract Structure")
        self.btn_rewrite_similar = QPushButton("Rewrite Similar")
        self.btn_see_video = QPushButton("See Video")
        for btn in (
            self.btn_convert,
            self.btn_auto_punctuate,
            self.btn_clean_script,
            self.btn_summarize,
            self.btn_extract_structure,
            self.btn_rewrite_similar,
            self.btn_see_video,
        ):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(30)
            btn.setStyleSheet(button_style)
        self.btn_convert.clicked.connect(self._start_convert)
        self.btn_auto_punctuate.clicked.connect(self._show_auto_punctuate_menu)
        self.btn_clean_script.clicked.connect(self._show_clean_script_dialog)
        self.btn_summarize.clicked.connect(self._show_summarize_dialog)
        self.btn_extract_structure.clicked.connect(self._show_extract_structure_dialog)
        self.btn_rewrite_similar.clicked.connect(self._show_rewrite_similar_dialog)
        self.btn_see_video.clicked.connect(self._open_current_video)
        top_row.addWidget(self.btn_convert)
        top_row.addWidget(self.btn_auto_punctuate)
        top_row.addWidget(self.btn_clean_script)
        top_row.addWidget(self.btn_summarize)
        top_row.addWidget(self.btn_extract_structure)
        top_row.addWidget(self.btn_rewrite_similar)
        top_row.addWidget(self.btn_see_video)

        top_row.addStretch()

        self.chk_wrap_lines = QCheckBox("Wrap lines")
        self.chk_wrap_lines.setChecked(True)
        self.chk_wrap_lines.setStyleSheet("QCheckBox { color:#111111; font-size:12px; padding-right:8px; }")
        self.chk_wrap_lines.toggled.connect(self._apply_wrap_mode)
        top_row.addWidget(self.chk_wrap_lines)
        content_layout.addLayout(top_row)

        self.text_output = QTextEdit()
        self.text_output.setPlaceholderText("Transcript text will appear here.")
        self.text_output.setStyleSheet(
            "QTextEdit { background:#ffffff; color:#111111; border:1px solid #d9d9d9; border-radius:0; "
            "padding:8px; font-size:13px; selection-background-color:#e50914; selection-color:#ffffff; }"
        )
        self.text_output.textChanged.connect(self._update_status)
        content_layout.addWidget(self.text_output, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(10, 6, 10, 6)
        bottom_row.setSpacing(8)

        self.btn_spinner = QPushButton("Content Spinner")
        self.btn_replace = QPushButton("Replace")
        self.btn_file = QPushButton("File")
        self.btn_copy = QPushButton("Copy")
        self.btn_clear = QPushButton("Clear")

        for btn in (self.btn_spinner, self.btn_replace, self.btn_file, self.btn_copy, self.btn_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(28)
            btn.setStyleSheet(button_style)

        self.btn_spinner.clicked.connect(self._show_spinner_dialog)
        self.btn_replace.clicked.connect(self._show_replace_dialog)
        self.btn_file.clicked.connect(self._show_file_menu)
        self.btn_copy.clicked.connect(self._copy_output)
        self.btn_clear.clicked.connect(self._clear_output)

        bottom_row.addWidget(self.btn_spinner)
        bottom_row.addWidget(self.btn_replace)

        self.lbl_status = QLabel("Content: 0 Lines | 0 Words | 0 Characters")
        self.lbl_status.setStyleSheet("QLabel { color:#111111; font-size:12px; padding:0 8px; }")
        bottom_row.addWidget(self.lbl_status, stretch=1)

        bottom_row.addWidget(self.btn_file)
        bottom_row.addWidget(self.btn_copy)
        bottom_row.addWidget(self.btn_clear)
        content_layout.addLayout(bottom_row)

        shell_layout.addWidget(content, stretch=1)
        root.addWidget(shell)

        self._apply_wrap_mode(True)
        self._update_status()

    def _coming_soon(self, label):
        QMessageBox.information(self, label, f"{label} will be implemented in the next step.")

    def _apply_wrap_mode(self, enabled):
        mode = QTextEdit.LineWrapMode.WidgetWidth if enabled else QTextEdit.LineWrapMode.NoWrap
        self.text_output.setLineWrapMode(mode)

    def _update_status(self):
        text = self.text_output.toPlainText()
        words = len([part for part in text.split() if part.strip()])
        lines = len([line for line in text.splitlines() if line.strip()])
        self.lbl_status.setText(f"Content: {lines:,} Lines | {words:,} Words | {len(text):,} Characters")

    def _open_current_video(self):
        url = normalize_video_text_input(self.input_video_link.text().strip())
        if not url:
            QMessageBox.information(self, "See Video", "Please enter a video link or ID first.")
            return
        QDesktopServices.openUrl(QUrl(url))

    def _show_file_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #cfd4dc; padding:6px; }"
            "QMenu::item { padding:6px 22px 6px 12px; background:transparent; }"
            "QMenu::item:selected { background:#f2d7d1; color:#111111; }"
            "QMenu::separator { height:1px; background:#e3e3e3; margin:4px 8px; }"
        )

        action_save = QAction("Save TXT", self)
        action_load = QAction("Load TXT", self)
        action_export_cleaned = QAction("Export Cleaned Text", self)
        action_save_copy = QAction("Save Copy", self)

        action_save.triggered.connect(self._save_txt)
        action_load.triggered.connect(self._load_txt)
        action_export_cleaned.triggered.connect(self._export_cleaned_text)
        action_save_copy.triggered.connect(self._save_copy)

        menu.addAction(action_save)
        menu.addAction(action_load)
        menu.addSeparator()
        menu.addAction(action_export_cleaned)
        menu.addAction(action_save_copy)
        menu.exec(self.btn_file.mapToGlobal(self.btn_file.rect().bottomLeft()))

    def _show_replace_dialog(self):
        dialog = FindReplaceDialog(self, self)
        dialog.exec()

    def _show_spinner_dialog(self):
        dialog = ContentSpinnerDialog(self, self)
        dialog.exec()

    def _show_auto_punctuate_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#ffffff; color:#111111; border:1px solid #cfd4dc; padding:6px; }"
            "QMenu::item { padding:6px 22px 6px 12px; background:transparent; }"
            "QMenu::item:selected { background:#f2d7d1; color:#111111; }"
        )
        action_basic = QAction("Basic (Fast)", self)
        action_ai = QAction("AI Enhanced (Gemini)", self)
        action_basic.triggered.connect(self._auto_punctuate_basic)
        action_ai.triggered.connect(self._auto_punctuate_ai)
        menu.addAction(action_basic)
        menu.addAction(action_ai)
        menu.exec(self.btn_auto_punctuate.mapToGlobal(self.btn_auto_punctuate.rect().bottomLeft()))

    def _show_clean_script_dialog(self):
        dialog = CleanScriptDialog(self, self)
        dialog.exec()

    def _show_summarize_dialog(self):
        dialog = SummarizeDialog(self, self)
        dialog.exec()

    def _show_extract_structure_dialog(self):
        dialog = ExtractStructureDialog(self, self)
        dialog.exec()

    def _show_rewrite_similar_dialog(self):
        dialog = RewriteSimilarScriptDialog(self, self)
        dialog.exec()

    def resolve_source_text(self, prefer_cleaned_text: bool) -> str:
        current_text = self.text_output.toPlainText()
        source_text = current_text
        if (
            prefer_cleaned_text
            and self._cleaned_transcript_text.strip()
            and current_text.strip() == self._raw_transcript_text.strip()
        ):
            source_text = self._cleaned_transcript_text
        return str(source_text or "").strip()

    def register_background_worker(self, worker):
        if worker is None:
            return
        self.prune_background_workers()
        if worker not in self._background_workers:
            self._background_workers.append(worker)
            worker.finished.connect(self.prune_background_workers)

    def prune_background_workers(self):
        survivors = []
        for worker in list(self._background_workers):
            if worker is None:
                continue
            if worker.isRunning():
                survivors.append(worker)
                continue
            try:
                worker.deleteLater()
            except Exception:
                pass
        self._background_workers = survivors

    def has_active_background_workers(self) -> bool:
        self.prune_background_workers()
        return any(worker.isRunning() for worker in self._background_workers)

    def has_active_long_running_task(self) -> bool:
        if self._worker and self._worker.isRunning():
            return True
        if self._ai_punctuate_worker and self._ai_punctuate_worker.isRunning():
            return True
        return self.has_active_background_workers()

    def request_stop_background_workers(self):
        self.prune_background_workers()
        for worker in list(self._background_workers):
            if worker and worker.isRunning():
                try:
                    worker.request_stop()
                except Exception:
                    pass

    def shutdown_background_workers(self, timeout_ms: int = 2000):
        self.request_stop_background_workers()
        for worker in list(self._background_workers):
            if worker and worker.isRunning():
                if not worker.wait(timeout_ms):
                    worker.terminate()
                    worker.wait(1000)
        self.prune_background_workers()

    def generate_spun_content(
        self,
        *,
        mode: str,
        strength: str,
        preserve_meaning: bool,
        avoid_repetition: bool,
        keep_keywords: bool,
    ) -> str:
        source_text = self.text_output.toPlainText()
        if not source_text.strip():
            return ""
        return spin_content(
            source_text,
            mode=mode,
            strength=strength,
            preserve_meaning=preserve_meaning,
            avoid_repetition=avoid_repetition,
            keep_keywords=keep_keywords,
        )

    def generate_clean_script(
        self,
        *,
        mode: str,
        output_style: str,
        remove_filler_words: bool,
        remove_repeated_lines: bool,
        fix_spacing_and_noise: bool,
        preserve_original_meaning: bool,
    ) -> str:
        source_text = self.text_output.toPlainText()
        if not source_text.strip():
            return ""
        return clean_script_text(
            source_text,
            mode=mode,
            output_style=output_style,
            remove_filler_words=remove_filler_words,
            remove_repeated_lines=remove_repeated_lines,
            fix_spacing_and_noise=fix_spacing_and_noise,
            preserve_original_meaning=preserve_original_meaning,
        )

    def generate_summary_content(
        self,
        *,
        mode: str,
        length: str,
        prefer_cleaned_text: bool,
        keep_names_and_keywords: bool,
    ) -> str:
        current_text = self.text_output.toPlainText()
        source_text = current_text
        if (
            prefer_cleaned_text
            and self._cleaned_transcript_text.strip()
            and current_text.strip() == self._raw_transcript_text.strip()
        ):
            source_text = self._cleaned_transcript_text
        if not source_text.strip():
            return ""
        return summarize_text(
            source_text,
            mode=mode,
            length=length,
            keep_names_and_keywords=keep_names_and_keywords,
        )

    def generate_structure_content(
        self,
        *,
        mode: str,
        prefer_cleaned_text: bool,
        preserve_original_flow: bool,
    ) -> dict:
        source_text = self.resolve_source_text(prefer_cleaned_text)
        if not source_text.strip():
            return {}
        effective_mode = "Detailed" if str(mode or "").strip() in {"AI Enhanced (Later)", "AI Enhanced (Gemini)"} else mode
        structure = extract_structure(
            source_text,
            mode=effective_mode,
            prefer_cleaned=prefer_cleaned_text,
        )
        if not preserve_original_flow and structure.get("main_points"):
            structure["main_points"] = sorted(
                structure.get("main_points", []),
                key=lambda item: len(str(item or "")),
                reverse=True,
            )
        return structure

    def generate_rewritten_script(
        self,
        *,
        mode: str,
        output_style: str,
        preserve_original_meaning: bool,
        keep_original_structure: bool,
        avoid_copied_phrasing: bool,
        prefer_cleaned_text: bool,
    ) -> str:
        source_text = self.resolve_source_text(prefer_cleaned_text)
        if not source_text.strip():
            return ""
        rewritten = local_rewrite_similar_script(
            source_text,
            mode=mode,
            output_style=output_style,
            preserve_original_meaning=preserve_original_meaning,
            keep_original_structure=keep_original_structure,
            avoid_copied_phrasing=avoid_copied_phrasing,
        )
        return str(rewritten or "").strip()

    def apply_structure_result(self, structure: dict) -> dict:
        if not structure:
            return {}
        formatted = format_structure_output(structure)
        self.text_output.setPlainText(formatted)
        self._structured_output_text = formatted
        self._rewritten_script_text = ""
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Extract Structure complete.", 3000)
        return structure

    def apply_rewritten_result(self, rewritten: str) -> str:
        result = str(rewritten or "").strip()
        if not result:
            return ""
        self.text_output.setPlainText(result)
        self._rewritten_script_text = result
        self._structured_output_text = ""
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Rewrite Similar Script complete.", 3000)
        return result

    def apply_structure_content(
        self,
        *,
        mode: str,
        prefer_cleaned_text: bool,
        preserve_original_flow: bool,
    ) -> dict:
        structure = self.generate_structure_content(
            mode=mode,
            prefer_cleaned_text=prefer_cleaned_text,
            preserve_original_flow=preserve_original_flow,
        )
        return self.apply_structure_result(structure)

    def apply_rewritten_script(
        self,
        *,
        mode: str,
        output_style: str,
        preserve_original_meaning: bool,
        keep_original_structure: bool,
        avoid_copied_phrasing: bool,
        prefer_cleaned_text: bool,
    ) -> str:
        rewritten = self.generate_rewritten_script(
            mode=mode,
            output_style=output_style,
            preserve_original_meaning=preserve_original_meaning,
            keep_original_structure=keep_original_structure,
            avoid_copied_phrasing=avoid_copied_phrasing,
            prefer_cleaned_text=prefer_cleaned_text,
        )
        return self.apply_rewritten_result(rewritten)

    def apply_summary_content(
        self,
        *,
        mode: str,
        length: str,
        prefer_cleaned_text: bool,
        keep_names_and_keywords: bool,
    ) -> str:
        summary = self.generate_summary_content(
            mode=mode,
            length=length,
            prefer_cleaned_text=prefer_cleaned_text,
            keep_names_and_keywords=keep_names_and_keywords,
        )
        if not summary:
            return ""
        self.text_output.setPlainText(summary)
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Summarize complete.", 3000)
        return summary

    def apply_clean_script(
        self,
        *,
        mode: str,
        output_style: str,
        remove_filler_words: bool,
        remove_repeated_lines: bool,
        fix_spacing_and_noise: bool,
        preserve_original_meaning: bool,
    ) -> str:
        cleaned = self.generate_clean_script(
            mode=mode,
            output_style=output_style,
            remove_filler_words=remove_filler_words,
            remove_repeated_lines=remove_repeated_lines,
            fix_spacing_and_noise=fix_spacing_and_noise,
            preserve_original_meaning=preserve_original_meaning,
        )
        if not cleaned:
            return ""
        self.text_output.setPlainText(cleaned)
        self._cleaned_transcript_text = cleaned
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Clean Script complete.", 3000)
        return cleaned

    def apply_spun_content(
        self,
        *,
        mode: str,
        strength: str,
        preserve_meaning: bool,
        avoid_repetition: bool,
        keep_keywords: bool,
    ) -> str:
        spun = self.generate_spun_content(
            mode=mode,
            strength=strength,
            preserve_meaning=preserve_meaning,
            avoid_repetition=avoid_repetition,
            keep_keywords=keep_keywords,
        )
        if not spun:
            return ""
        self.text_output.setPlainText(spun)
        self._cleaned_transcript_text = spun
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Content spinner complete.", 3000)
        return spun

    def _build_find_flags(self, match_case: bool, whole_word: bool) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if match_case:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if whole_word:
            flags |= QTextDocument.FindFlag.FindWholeWords
        return flags

    def find_next_in_output(self, *, find_text: str, replace_text: str = "", match_case: bool = False, whole_word: bool = False, wrap_search: bool = True) -> bool:
        needle = str(find_text or "").strip()
        if not needle:
            QMessageBox.information(self, "Find / Replace", "Please enter text to find.")
            return False

        flags = self._build_find_flags(match_case, whole_word)
        found = self.text_output.find(needle, flags)
        if not found and wrap_search:
            cursor = self.text_output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.text_output.setTextCursor(cursor)
            found = self.text_output.find(needle, flags)

        if found and self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Found: {needle}", 2000)
        return found

    def replace_current_in_output(self, *, find_text: str, replace_text: str = "", match_case: bool = False, whole_word: bool = False, wrap_search: bool = True) -> bool:
        needle = str(find_text or "").strip()
        if not needle:
            QMessageBox.information(self, "Find / Replace", "Please enter text to find.")
            return False

        cursor = self.text_output.textCursor()
        has_selection = cursor.hasSelection()
        selected_text = cursor.selectedText() if has_selection else ""

        compare_selected = selected_text
        compare_needle = needle
        if not match_case:
            compare_selected = compare_selected.lower()
            compare_needle = compare_needle.lower()

        if has_selection and compare_selected == compare_needle:
            cursor.insertText(str(replace_text or ""))
            self.text_output.setTextCursor(cursor)
            self._update_status()
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage("Replaced current match.", 2000)
            return True

        found = self.find_next_in_output(
            find_text=needle,
            replace_text=replace_text,
            match_case=match_case,
            whole_word=whole_word,
            wrap_search=wrap_search,
        )
        if not found:
            return False
        cursor = self.text_output.textCursor()
        if cursor.hasSelection():
            cursor.insertText(str(replace_text or ""))
            self.text_output.setTextCursor(cursor)
            self._update_status()
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage("Replaced current match.", 2000)
            return True
        return False

    def replace_all_in_output(self, *, find_text: str, replace_text: str = "", match_case: bool = False, whole_word: bool = False, wrap_search: bool = True) -> int:
        needle = str(find_text or "").strip()
        if not needle:
            QMessageBox.information(self, "Find / Replace", "Please enter text to find.")
            return 0

        document = self.text_output.document()
        cursor = QTextCursor(document)
        flags = self._build_find_flags(match_case, whole_word)
        count = 0

        cursor.beginEditBlock()
        while True:
            cursor = document.find(needle, cursor, flags)
            if cursor.isNull():
                break
            cursor.insertText(str(replace_text or ""))
            count += 1
        cursor.endEditBlock()

        if count > 0:
            self._update_status()
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(f"Replaced {count} match(es).", 3000)
        return count

    def _safe_filename_base(self) -> str:
        title = str(self._current_video_title or "").strip()
        if not title:
            title = "transcript"
        title = re.sub(r'[\\/:*?"<>|]+', "_", title)
        title = re.sub(r"\s+", " ", title).strip(" ._")
        return title or "transcript"

    def _write_text_file(self, path: str, content: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(str(content or ""))
            return True
        except Exception as exc:
            QMessageBox.warning(self, "File", f"Could not save file.\n\n{exc}")
            return False

    def _save_txt(self):
        content = self.text_output.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "Save TXT", "There is no text to save.")
            return
        target_path = self._current_text_path
        if not target_path:
            default_name = f"{self._safe_filename_base()}.txt"
            target_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save TXT",
                default_name,
                "Text Files (*.txt);;All Files (*.*)",
            )
        if not target_path:
            return
        if self._write_text_file(target_path, content):
            self._current_text_path = target_path
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(f"Saved transcript to {target_path}", 4000)

    def _load_txt(self):
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load TXT",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not source_path:
            return
        try:
            with open(source_path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except Exception as exc:
            QMessageBox.warning(self, "Load TXT", f"Could not load file.\n\n{exc}")
            return
        self.text_output.setPlainText(content)
        self._raw_transcript_text = content
        self._cleaned_transcript_text = ""
        self._current_text_path = source_path
        self._current_video_title = ""
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Loaded transcript from {source_path}", 4000)

    def _export_cleaned_text(self):
        cleaned = str(self._cleaned_transcript_text or "").strip()
        if not cleaned:
            QMessageBox.information(self, "Export Cleaned Text", "No cleaned text is available yet. Run Auto Punctuate first.")
            return
        default_name = f"{self._safe_filename_base()}_cleaned.txt"
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Cleaned Text",
            default_name,
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not target_path:
            return
        if self._write_text_file(target_path, cleaned):
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(f"Exported cleaned text to {target_path}", 4000)

    def _save_copy(self):
        content = self.text_output.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "Save Copy", "There is no text to save.")
            return
        default_name = f"{self._safe_filename_base()}_copy.txt"
        target_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Copy",
            default_name,
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not target_path:
            return
        if self._write_text_file(target_path, content):
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(f"Saved copy to {target_path}", 4000)

    def _auto_punctuate_basic(self):
        source_text = self.text_output.toPlainText()
        if not source_text.strip():
            QMessageBox.information(self, "Auto Punctuate", "There is no transcript text to punctuate.")
            return
        punctuated = auto_punctuate_transcript(source_text)
        if not punctuated.strip():
            QMessageBox.information(self, "Auto Punctuate", "Could not punctuate the current transcript.")
            return
        self.text_output.setPlainText(punctuated)
        self._cleaned_transcript_text = punctuated
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Basic Auto Punctuate complete.", 3000)

    def _auto_punctuate_ai(self):
        source_text = self.text_output.toPlainText()
        if not source_text.strip():
            QMessageBox.information(self, "Auto Punctuate", "There is no transcript text to punctuate.")
            return
        if self.has_active_background_workers():
            QMessageBox.information(self, "Auto Punctuate", "Please wait for the current AI task to finish first.")
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Auto Punctuate", "Please wait for Convert to Text to finish first.")
            return
        if self._ai_punctuate_worker and self._ai_punctuate_worker.isRunning():
            QMessageBox.information(self, "Auto Punctuate", "AI Enhanced Auto Punctuate is already running.")
            return
        self.btn_auto_punctuate.setDisabled(True)
        self.btn_clean_script.setDisabled(True)
        self.btn_spinner.setDisabled(True)
        self.btn_replace.setDisabled(True)
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Starting AI Enhanced Auto Punctuate...", 3000)
        self._ai_punctuate_worker = AIPunctuateWorker(source_text)
        self._ai_punctuate_worker.status_signal.connect(self._handle_ai_punctuate_status)
        self._ai_punctuate_worker.error_signal.connect(self._handle_ai_punctuate_error)
        self._ai_punctuate_worker.finished_signal.connect(self._handle_ai_punctuate_finished)
        self._ai_punctuate_worker.finished.connect(self._cleanup_ai_punctuate_worker)
        self._ai_punctuate_worker.start()

    def _handle_ai_punctuate_status(self, message: str):
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(str(message or "AI Enhanced Auto Punctuate is running..."), 3000)

    def _handle_ai_punctuate_error(self, message: str):
        self._restore_ai_punctuate_buttons()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("AI Enhanced Auto Punctuate failed. Falling back to Basic.", 5000)
        basic_output = auto_punctuate_transcript(self.text_output.toPlainText())
        if basic_output.strip():
            self.text_output.setPlainText(basic_output)
            self._cleaned_transcript_text = basic_output
            self._update_status()
        QMessageBox.warning(self, "AI Enhanced Auto Punctuate", f"{message}\n\nApplied Basic Auto Punctuate instead.")

    def _handle_ai_punctuate_finished(self, punctuated: str):
        self._restore_ai_punctuate_buttons()
        result = str(punctuated or "").strip()
        if not result:
            QMessageBox.information(self, "AI Enhanced Auto Punctuate", "No punctuated text was returned.")
            return
        self.text_output.setPlainText(result)
        self._cleaned_transcript_text = result
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("AI Enhanced Auto Punctuate complete.", 4000)

    def _restore_ai_punctuate_buttons(self):
        self.btn_auto_punctuate.setDisabled(False)
        self.btn_clean_script.setDisabled(False)
        self.btn_summarize.setDisabled(False)
        self.btn_extract_structure.setDisabled(False)
        self.btn_rewrite_similar.setDisabled(False)
        self.btn_spinner.setDisabled(False)
        self.btn_replace.setDisabled(False)

    def _cleanup_ai_punctuate_worker(self):
        self._restore_ai_punctuate_buttons()
        if self._ai_punctuate_worker:
            try:
                self._ai_punctuate_worker.deleteLater()
            except Exception:
                pass
        self._ai_punctuate_worker = None

    def shutdown(self):
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            if not self._worker.wait(1500):
                self._worker.terminate()
                self._worker.wait(1000)
        if self._ai_punctuate_worker and self._ai_punctuate_worker.isRunning():
            self._ai_punctuate_worker.request_stop()
            if not self._ai_punctuate_worker.wait(2000):
                self._ai_punctuate_worker.terminate()
                self._ai_punctuate_worker.wait(1000)
        self.shutdown_background_workers(timeout_ms=1000)

    def _copy_output(self):
        text = self.text_output.toPlainText()
        if not text.strip():
            QMessageBox.information(self, "Copy", "There is no text to copy.")
            return
        QApplication.clipboard().setText(text)
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Copied transcript to clipboard.", 3000)

    def _clear_output(self):
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
        if self._ai_punctuate_worker and self._ai_punctuate_worker.isRunning():
            self._ai_punctuate_worker.request_stop()
        self.request_stop_background_workers()
        self.text_output.clear()
        self._raw_transcript_text = ""
        self._cleaned_transcript_text = ""
        self._structured_output_text = ""
        self._rewritten_script_text = ""
        self._current_text_path = ""
        self._current_video_title = ""
        self._update_status()

    def _set_running_state(self, running: bool):
        self.btn_convert.setDisabled(running)
        self.input_video_link.setDisabled(running)
        self.btn_auto_punctuate.setDisabled(running)
        self.btn_clean_script.setDisabled(running)
        self.btn_summarize.setDisabled(running)
        self.btn_extract_structure.setDisabled(running)
        self.btn_rewrite_similar.setDisabled(running)
        self.btn_see_video.setDisabled(running)

    def _start_convert(self):
        raw_input = self.input_video_link.text().strip()
        video_url = normalize_video_text_input(raw_input)
        if not video_url:
            QMessageBox.information(self, "Convert to Text", "Please enter a YouTube video link or ID first.")
            return
        if self.has_active_background_workers():
            QMessageBox.information(self, "Convert to Text", "Please wait for the current AI task to finish first.")
            return
        if self._ai_punctuate_worker and self._ai_punctuate_worker.isRunning():
            QMessageBox.information(self, "Convert to Text", "Please wait for AI Enhanced Auto Punctuate to finish first.")
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Convert to Text", "A conversion is already running.")
            return
        self.input_video_link.setText(video_url)
        self.text_output.clear()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Starting transcript extraction...", 3000)
        self._set_running_state(True)
        self._worker = VideoToTextWorker(video_url)
        self._worker.status_signal.connect(self._handle_runtime_status)
        self._worker.error_signal.connect(self._handle_convert_error)
        self._worker.finished_signal.connect(self._handle_convert_finished)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _handle_runtime_status(self, message: str):
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(str(message or "Working..."), 3000)

    def _handle_convert_error(self, message: str):
        self._set_running_state(False)
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Convert failed: {message}", 5000)
        QMessageBox.warning(self, "Convert to Text", str(message or "Could not extract transcript."))

    def _handle_convert_finished(self, result: dict):
        self._set_running_state(False)
        transcript = str((result or {}).get("transcript", "")).strip()
        self.text_output.setPlainText(transcript)
        self._raw_transcript_text = transcript
        self._cleaned_transcript_text = ""
        self._structured_output_text = ""
        self._rewritten_script_text = ""
        self._current_video_title = str((result or {}).get("title", "")).strip()
        self._current_text_path = ""
        self._update_status()
        title = self._current_video_title
        language = str((result or {}).get("language", "")).strip()
        source = str((result or {}).get("caption_source", "")).strip()
        parts = ["Transcript loaded"]
        if title:
            parts.append(title)
        if language:
            parts.append(language)
        if source:
            parts.append(source)
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(" | ".join(parts), 5000)

    def _cleanup_worker(self):
        if self._worker:
            try:
                self._worker.deleteLater()
            except Exception:
                pass
        self._worker = None

    def receive_payload(self, text, hint_text=""):
        self._pending_links = []
        clean = str(text or "").strip()
        if clean:
            first_line = clean.splitlines()[0].strip()
            self.input_video_link.setText(first_line)
        else:
            self.input_video_link.clear()
        self._update_status()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(str(hint_text or "Received input from another tool."), 4000)

    def receive_links_for_import(self, links, hint_text=""):
        clean_links = [str(link).strip() for link in (links or []) if str(link).strip()]
        self._pending_links = clean_links
        self.input_video_link.setText(clean_links[0] if clean_links else "")
        if clean_links:
            self._update_status()
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(
                    str(hint_text or f"Received {len(clean_links)} link(s). Using the first link in the box."),
                    4000,
                )
        else:
            self._update_status()
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(str(hint_text or "Ready."), 3000)
