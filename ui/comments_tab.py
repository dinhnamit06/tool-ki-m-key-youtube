from __future__ import annotations

import csv
import html
import re
import tempfile
from collections import Counter
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.comments_fetcher import CommentsLoadVideoWorker
from ui.videos_tab import DEFAULT_STOP_WORDS, StopWordsDialog, VideoNumericFilterDialog
from utils.constants import TABLE_SCROLLBAR_STYLE


class AnalyzeCommentsDialog(QDialog):
    TABLE_COLUMNS = [
        "",
        "Word Combination",
        "Occurrences in Comments",
        "Percentage in Comments",
        "Avg. Likes",
        "Number of Words",
    ]
    NUMERIC_COLUMNS = {
        "Occurrences in Comments",
        "Percentage in Comments",
        "Avg. Likes",
        "Number of Words",
    }

    def __init__(self, parent=None, stop_words=None):
        super().__init__(parent)
        self.setWindowTitle("Analyze Comments")
        self.setModal(True)
        self.resize(1120, 640)
        self._stop_words = [str(word).strip().lower() for word in (stop_words or DEFAULT_STOP_WORDS) if str(word).strip()]
        self._source_comment_rows: list[dict] = []
        self._all_word_rows: list[dict] = []
        self._numeric_filters: dict[str, str] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        lbl_words = QLabel("Number of words:")
        lbl_words.setStyleSheet("QLabel { color:#111111; font-size:13px; }")
        top_row.addWidget(lbl_words)

        self.combo_word_count = QComboBox()
        self.combo_word_count.addItems([str(i) for i in range(1, 7)])
        self.combo_word_count.setCurrentText("3")
        self.combo_word_count.setFixedWidth(64)
        self.combo_word_count.setStyleSheet(
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #c7c7c7; border-radius:3px; padding:4px 8px; }"
            "QComboBox::drop-down { border:none; width:18px; }"
        )
        top_row.addWidget(self.combo_word_count)

        self.chk_use_stop_words = QCheckBox("Use stop words")
        self.chk_use_stop_words.setChecked(True)
        self.chk_use_stop_words.setStyleSheet("QCheckBox { color:#111111; font-size:13px; }")
        top_row.addWidget(self.chk_use_stop_words)

        self.btn_stop_words = QPushButton("Stop Words")
        self.btn_stop_words.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop_words.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        top_row.addWidget(self.btn_stop_words)
        top_row.addStretch()

        self.btn_generate = QPushButton("Generate Word Stats")
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.setStyleSheet(
            "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
            "QPushButton:hover { background-color:#ff1a25; }"
        )
        top_row.addWidget(self.btn_generate)
        root.addLayout(top_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; gridline-color:#d8d8d8; border:1px solid #cfcfcf; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:1px solid #d0d0d0; font-weight:700; padding:4px; }"
            + TABLE_SCROLLBAR_STYLE
        )
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.sectionClicked.connect(self._on_header_clicked)
        self.table.setColumnWidth(0, 26)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(3, 180)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(5, 130)
        root.addWidget(self.table, stretch=1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.btn_file = QPushButton("File")
        self.btn_view_comments = QPushButton("View Comments")
        self.btn_clear_filters = QPushButton("Clear Filters")
        self.btn_clear = QPushButton("Clear")
        for btn in (self.btn_file, self.btn_view_comments, self.btn_clear_filters, self.btn_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color:#e50914; color:#ffffff; border:none; border-radius:4px; padding:6px 14px; font-weight:700; }"
                "QPushButton:hover { background-color:#ff1a25; }"
            )
            btn.setMinimumHeight(30)
        self.btn_file.setMinimumWidth(78)
        self.btn_view_comments.setMinimumWidth(150)
        self.btn_clear_filters.setMinimumWidth(118)
        self.btn_clear.setMinimumWidth(92)

        action_row.addWidget(self.btn_file)
        action_row.addWidget(self.btn_view_comments)
        action_row.addStretch()
        action_row.addWidget(self.btn_clear_filters)
        action_row.addWidget(self.btn_clear)
        root.addLayout(action_row)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.lbl_total = QLabel("Total: 0")
        self.lbl_status = QLabel("Done")
        self.lbl_total.setStyleSheet("QLabel { color:#111111; font-size:12px; }")
        self.lbl_status.setStyleSheet("QLabel { color:#111111; font-size:12px; }")
        status_row.addWidget(self.lbl_total)
        status_row.addStretch()
        status_row.addWidget(self.lbl_status)
        status_row.addStretch()
        root.addLayout(status_row)
        self.setStyleSheet("QDialog { background:#ffffff; }")

    def stop_words(self) -> list[str]:
        return list(self._stop_words)

    def set_stop_words(self, stop_words) -> None:
        self._stop_words = [str(word).strip().lower() for word in (stop_words or []) if str(word).strip()]

    def set_source_comments(self, rows: list[dict]) -> None:
        self._source_comment_rows = [dict(row) for row in (rows or []) if isinstance(row, dict)]

    def selected_word_count(self) -> int:
        try:
            return max(1, int(self.combo_word_count.currentText().strip()))
        except Exception:
            return 1

    @staticmethod
    def _parse_number(raw_value):
        text = str(raw_value or "").strip()
        if not text:
            return 0.0
        match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", "").replace("+", ""))
        if not match:
            return 0.0
        try:
            return float(match.group(0))
        except Exception:
            return 0.0

    @staticmethod
    def _evaluate_expression(value, expression):
        expr = str(expression or "").strip()
        if not expr:
            return True
        match = re.fullmatch(r"(>=|<=|!=|==|=|>|<)\s*(-?\d+(?:\.\d+)?)", expr)
        if not match:
            return None
        operator = match.group(1)
        target = float(match.group(2))
        if operator == ">":
            return value > target
        if operator == "<":
            return value < target
        if operator == ">=":
            return value >= target
        if operator == "<=":
            return value <= target
        if operator in {"=", "=="}:
            return value == target
        if operator == "!=":
            return value != target
        return None

    def _refresh_header_filter_tooltips(self) -> None:
        for index, column_name in enumerate(self.TABLE_COLUMNS):
            item = self.table.horizontalHeaderItem(index)
            if item is None:
                continue
            if column_name in self.NUMERIC_COLUMNS:
                expr = str(self._numeric_filters.get(column_name, "")).strip()
                item.setToolTip(f"Active filter: {expr}" if expr else "Click to filter this numeric column")
            else:
                item.setToolTip("")

    def _filtered_rows(self, rows: list[dict]) -> list[dict]:
        results = []
        for row in rows:
            matched = True
            for column_name, expression in self._numeric_filters.items():
                if column_name == "Occurrences in Comments":
                    value = self._parse_number(row.get("occurrences", 0))
                elif column_name == "Percentage in Comments":
                    value = self._parse_number(row.get("percentage", 0.0))
                elif column_name == "Avg. Likes":
                    value = self._parse_number(row.get("avg_likes", 0.0))
                elif column_name == "Number of Words":
                    value = self._parse_number(row.get("word_count", 0))
                else:
                    value = None
                if value is None or self._evaluate_expression(value, expression) is not True:
                    matched = False
                    break
            if matched:
                results.append(row)
        return results

    def _render_rows(self, rows: list[dict]) -> None:
        self.table.setRowCount(0)
        for row_data in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            checkbox_item = QTableWidgetItem("")
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, checkbox_item)
            values = [
                str(row_data.get("phrase", "")),
                f"{int(row_data.get('occurrences', 0)):,}",
                f"{float(row_data.get('percentage', 0.0)):.1f}",
                f"{float(row_data.get('avg_likes', 0.0)):,.1f}",
                f"{int(row_data.get('word_count', 0))}",
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if offset >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, offset, item)
        self.lbl_total.setText(f"Total: {len(rows):,}")
        self._refresh_header_filter_tooltips()

    @staticmethod
    def _tokenize_comment(text: str) -> list[str]:
        return [
            token.lower()
            for token in re.findall(r"[^\W_]+", str(text or ""), flags=re.UNICODE)
            if token and not token.isdigit()
        ]

    def _is_blocked_phrase(self, tokens: list[str]) -> bool:
        stop_single = {word for word in self._stop_words if " " not in word}
        stop_phrases = {word for word in self._stop_words if " " in word}
        phrase = " ".join(tokens).strip().lower()
        if not phrase:
            return True
        if phrase in stop_phrases:
            return True
        return any(token in stop_single for token in tokens)

    def generate_word_stats(self) -> None:
        comment_rows = [dict(row) for row in self._source_comment_rows]
        if not comment_rows:
            QMessageBox.information(self, "Analyze Comments", "No comments available to analyze.")
            return
        word_count = self.selected_word_count()
        use_stop_words = self.chk_use_stop_words.isChecked()
        aggregates: dict[str, dict] = {}
        total_comments = 0
        for row in comment_rows:
            comment_text = str(row.get("comment", "")).strip()
            if not comment_text:
                continue
            total_comments += 1
            likes = self._parse_number(row.get("likes", "0"))
            tokens = self._tokenize_comment(comment_text)
            if len(tokens) < word_count:
                continue
            seen_in_comment = set()
            for start in range(0, len(tokens) - word_count + 1):
                phrase_tokens = tokens[start:start + word_count]
                if use_stop_words and self._is_blocked_phrase(phrase_tokens):
                    continue
                phrase = " ".join(phrase_tokens).strip()
                if not phrase or phrase in seen_in_comment:
                    continue
                seen_in_comment.add(phrase)
                entry = aggregates.setdefault(
                    phrase,
                    {
                        "phrase": phrase,
                        "occurrences": 0,
                        "avg_likes_sum": 0.0,
                        "word_count": word_count,
                        "matches": [],
                    },
                )
                entry["occurrences"] += 1
                entry["avg_likes_sum"] += likes
                entry["matches"].append(dict(row))

        rows = []
        for entry in aggregates.values():
            occurrences = int(entry["occurrences"])
            rows.append(
                {
                    "phrase": entry["phrase"],
                    "occurrences": occurrences,
                    "percentage": (occurrences / max(1, total_comments)) * 100.0,
                    "avg_likes": entry["avg_likes_sum"] / max(1, occurrences),
                    "word_count": int(entry["word_count"]),
                    "matches": list(entry.get("matches", [])),
                }
            )
        rows.sort(key=lambda item: (-item["occurrences"], item["phrase"]))
        self._all_word_rows = rows
        self._render_rows(self._filtered_rows(rows))
        self.lbl_status.setText("Done")

    def reset_filters(self) -> None:
        self._numeric_filters = {}
        self._render_rows(self._filtered_rows(self._all_word_rows))
        self.lbl_status.setText("Done")

    def clear_results(self) -> None:
        self._all_word_rows = []
        self._numeric_filters = {}
        self.table.setRowCount(0)
        self.lbl_total.setText("Total: 0")
        self.lbl_status.setText("Done")
        self._refresh_header_filter_tooltips()

    def _on_header_clicked(self, section: int) -> None:
        if section < 0 or section >= len(self.TABLE_COLUMNS):
            return
        column_name = self.TABLE_COLUMNS[section]
        if column_name not in self.NUMERIC_COLUMNS:
            return
        dlg = VideoNumericFilterDialog(self, column_name=column_name, current_expression=self._numeric_filters.get(column_name, ""))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        expression = dlg.selected_expression()
        if expression is None or not str(expression).strip():
            self._numeric_filters.pop(column_name, None)
        else:
            if self._evaluate_expression(1.0, expression) is None:
                QMessageBox.warning(
                    self,
                    "Analyze Comments",
                    "Numeric filter format is invalid. Use examples like >100, >=5, <2, =0.",
                )
                return
            self._numeric_filters[column_name] = str(expression).strip()
        self._render_rows(self._filtered_rows(self._all_word_rows))
        self.lbl_status.setText("Done")

    def selected_phrase_row(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        phrase = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
        for row_data in self._all_word_rows:
            if str(row_data.get("phrase", "")).strip() == phrase:
                return row_data
        return None

    def _serialize_rows_csv(self, rows: list[dict]) -> list[list[str]]:
        output = [["Word Combination", "Occurrences in Comments", "Percentage in Comments", "Avg. Likes", "Number of Words"]]
        for row in rows:
            output.append(
                [
                    str(row.get("phrase", "")),
                    str(int(row.get("occurrences", 0))),
                    f"{float(row.get('percentage', 0.0)):.1f}",
                    f"{float(row.get('avg_likes', 0.0)):,.1f}",
                    str(int(row.get("word_count", 0))),
                ]
            )
        return output

    def export_rows_to_csv(self, rows: list[dict]) -> None:
        if not rows:
            QMessageBox.information(self, "Analyze Comments", "No rows available to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Comments Analysis CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
        with open(file_path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerows(self._serialize_rows_csv(rows))

    def export_rows_to_txt(self, rows: list[dict]) -> None:
        if not rows:
            QMessageBox.information(self, "Analyze Comments", "No rows available to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Comments Analysis TXT", "", "Text Files (*.txt)")
        if not file_path:
            return
        lines = ["Word Combination\tOccurrences in Comments\tPercentage in Comments\tAvg. Likes\tNumber of Words"]
        for row in rows:
            lines.append(
                "\t".join(
                    [
                        str(row.get("phrase", "")),
                        str(int(row.get("occurrences", 0))),
                        f"{float(row.get('percentage', 0.0)):.1f}",
                        f"{float(row.get('avg_likes', 0.0)):,.1f}",
                        str(int(row.get("word_count", 0))),
                    ]
                )
            )
        Path(file_path).write_text("\n".join(lines), encoding="utf-8")

    def visible_rows(self) -> list[dict]:
        return self._filtered_rows(self._all_word_rows)

    def open_view_comments_html(self) -> None:
        row_data = self.selected_phrase_row()
        if not row_data:
            QMessageBox.information(self, "Analyze Comments", "Please select one phrase row first.")
            return
        phrase = str(row_data.get("phrase", "")).strip()
        matches = list(row_data.get("matches", []))
        if not phrase or not matches:
            QMessageBox.information(self, "Analyze Comments", "No matching comments found for this phrase.")
            return

        safe_phrase = html.escape(phrase)
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)

        def highlight_text(comment_text: str) -> str:
            escaped = html.escape(str(comment_text or ""))
            return pattern.sub(lambda m: f"<mark>{html.escape(m.group(0))}</mark>", escaped)

        cards = []
        for row in matches:
            cards.append(
                f"""
                <div class="comment-card">
                  <div class="icon"></div>
                  <div class="content">
                    <div class="meta"><strong>Posted:</strong> {html.escape(str(row.get('posted', '') or 'not-given'))}</div>
                    <div class="message"><strong>Message:</strong> {highlight_text(str(row.get('comment', '')))}</div>
                  </div>
                </div>
                """
            )

        html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Post Comments</title>
<style>
body {{ font-family: Arial, sans-serif; background:#d7d7db; margin:0; padding:0 0 30px; }}
.wrap {{ max-width: 1060px; margin: 0 auto; padding: 16px 20px; }}
.bar {{ background:#d94a22; color:#fff; padding:8px 12px; margin-bottom:2px; font-weight:700; }}
.bar input {{ vertical-align:middle; }}
.comment-card {{ display:flex; gap:12px; border:2px solid #d46e60; background:#efefef; margin:14px 0; padding:10px; }}
.icon {{ width:36px; height:36px; border-radius:18px; background:#5ea1da; flex:0 0 auto; margin-top:2px; }}
.content {{ flex:1; color:#1b1b1b; }}
.meta {{ margin-bottom:8px; }}
.message {{ line-height:1.5; }}
mark {{ background:#ffe84a; padding:0 2px; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="bar">Word Combination: {safe_phrase} &nbsp;&nbsp; <label><input type="checkbox" checked onclick="document.body.classList.toggle('no-highlight', !this.checked);"> highlight all</label></div>
  <div class="bar">Occurrences Found: {len(matches)}</div>
  {''.join(cards)}
</div>
<script>
document.body.classList.remove('no-highlight');
document.addEventListener('change', function(e) {{
  if(e.target && e.target.type === 'checkbox') {{
    document.querySelectorAll('mark').forEach(function(m) {{
      m.style.background = e.target.checked ? '#ffe84a' : 'transparent';
    }});
  }}
}});
</script>
</body>
</html>"""
        output_path = Path(tempfile.gettempdir()) / "tubevibe_comments.html"
        output_path.write_text(html_body, encoding="utf-8")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path)))


class CommentsTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._incoming_payload = ""
        self._queued_video_links: list[str] = []
        self._loaded_video_info: dict = {}
        self._load_worker = None
        self._loading_video_active = False
        self._load_run_token = 0
        self._webengine_view_class = None
        self._browser_view = None
        self._extract_run_token = 0
        self._extract_session_active = False
        self._autoscroll_active = False
        self._remaining_scroll_steps = 0
        self._comment_key_to_row: dict[tuple[str, str, str], int] = {}
        self._comment_filters = self._default_comment_filter_state()
        self._comments_analysis_stop_words = list(DEFAULT_STOP_WORDS)
        self._scroll_extract_timer = QTimer(self)
        self._scroll_extract_timer.setInterval(1400)
        self._scroll_extract_timer.timeout.connect(self._run_extract_cycle)
        self._setup_ui()
        self._refresh_extract_controls()

    COMMENT_TABLE_DEFAULT_WIDTHS = {
        0: 34,
        1: 160,
        2: 190,
        3: 110,
        4: 70,
        5: 70,
        6: 100,
        7: 110,
        8: 420,
    }

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("commentsShell")
        shell.setStyleSheet("QFrame#commentsShell { background:#111111; }")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("commentsTopBar")
        top_bar.setStyleSheet("QFrame#commentsTopBar { background:#111111; border-bottom:1px solid #2a2a2a; }")
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 18, 24, 18)
        top_layout.setSpacing(12)

        lbl_title = QLabel("Comments")
        lbl_title.setStyleSheet("QLabel { color:#ffffff; font-size:24px; font-weight:700; }")
        top_layout.addWidget(lbl_title)

        row = QHBoxLayout()
        row.setSpacing(8)

        lbl_link = QLabel("Video link or ID:")
        lbl_link.setStyleSheet("QLabel { color:#f1f1f1; font-size:13px; }")
        row.addWidget(lbl_link)

        self.input_video_link = QLineEdit()
        self.input_video_link.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.input_video_link.setStyleSheet(
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
            "border-radius:4px; padding:6px 8px; font-size:13px; }"
        )
        row.addWidget(self.input_video_link, stretch=1)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; "
            "padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        self.btn_load_video = QPushButton("1. Load Video")
        self.btn_load_video.setStyleSheet(button_style)
        self.btn_load_video.clicked.connect(self._load_video)
        row.addWidget(self.btn_load_video)

        lbl_step2 = QLabel("Step 2:")
        lbl_step2.setStyleSheet("QLabel { color:#f1f1f1; font-size:13px; font-weight:600; }")
        row.addWidget(lbl_step2)

        lbl_scrolls = QLabel("Page scrolls:")
        lbl_scrolls.setStyleSheet("QLabel { color:#f1f1f1; font-size:13px; }")
        row.addWidget(lbl_scrolls)

        self.combo_page_scrolls = QComboBox()
        self.combo_page_scrolls.addItems(["5", "10", "20", "30", "50", "100"])
        self.combo_page_scrolls.setCurrentText("10")
        self.combo_page_scrolls.setStyleSheet(
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
            "border-radius:4px; padding:5px 8px; font-size:13px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; "
            "selection-background-color:#e24a22; selection-color:#ffffff; }"
        )
        row.addWidget(self.combo_page_scrolls)

        self.btn_scroll_extract = QPushButton("2. Scroll & Extract")
        self.btn_scroll_extract.setStyleSheet(button_style)
        self.btn_scroll_extract.clicked.connect(self._start_scroll_extract)
        row.addWidget(self.btn_scroll_extract)

        row.addStretch()
        top_layout.addLayout(row)

        body = QFrame()
        body.setObjectName("commentsBody")
        body.setStyleSheet("QFrame#commentsBody { background:#111111; }")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 18, 24, 18)
        body_layout.setSpacing(14)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        body_layout.addWidget(splitter, stretch=1)

        left = QFrame()
        left.setObjectName("commentsLeftPanel")
        left.setStyleSheet(
            "QFrame#commentsLeftPanel { background:#181b1f; border:1px solid #31363f; border-radius:10px; }"
        )
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        lbl_left = QLabel("Loaded Video")
        lbl_left.setStyleSheet("QLabel { color:#ffffff; font-size:16px; font-weight:700; }")
        left_layout.addWidget(lbl_left)

        self.browser_stack = QStackedWidget()
        self.browser_stack.setStyleSheet("QStackedWidget { background:#ffffff; border:1px solid #d4d7dc; border-radius:6px; }")

        self.text_loaded_video = QPlainTextEdit()
        self.text_loaded_video.setReadOnly(True)
        self.text_loaded_video.setPlaceholderText("No video loaded")
        self.text_loaded_video.setPlainText("No video loaded")
        self.text_loaded_video.setStyleSheet(
            "QPlainTextEdit { background:#ffffff; color:#111111; border:none; padding:10px; font-size:13px; }"
        )
        self.text_loaded_video.setMinimumHeight(360)
        self.browser_stack.addWidget(self.text_loaded_video)
        left_layout.addWidget(self.browser_stack, stretch=1)

        left_buttons = QHBoxLayout()
        left_buttons.setSpacing(8)
        self.btn_extract_comments = QPushButton("Extract Comments")
        self.btn_start_autoscroll = QPushButton("Start Autoscroll")
        for btn in (self.btn_extract_comments, self.btn_start_autoscroll):
            btn.setStyleSheet(button_style)
            left_buttons.addWidget(btn)
        self.btn_extract_comments.clicked.connect(self._extract_comments_now)
        self.btn_start_autoscroll.clicked.connect(self._toggle_autoscroll)
        left_buttons.addStretch()
        left_layout.addLayout(left_buttons)

        right = QFrame()
        right.setObjectName("commentsRightPanel")
        right.setStyleSheet(
            "QFrame#commentsRightPanel { background:#181b1f; border:1px solid #31363f; border-radius:10px; }"
        )
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(10)

        lbl_table = QLabel("Extracted Comments")
        lbl_table.setStyleSheet("QLabel { color:#ffffff; font-size:16px; font-weight:700; }")
        right_layout.addWidget(lbl_table)

        self.table_comments = QTableWidget(0, 9)
        self.table_comments.setHorizontalHeaderLabels(
            ["", "Commenter", "Commenter Channel", "Posted", "Likes", "Replies", "Has Question", "Has Profanity", "Comment"]
        )
        self.table_comments.verticalHeader().setVisible(False)
        self.table_comments.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_comments.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_comments.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_comments.setAlternatingRowColors(False)
        self.table_comments.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_comments.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; "
            "gridline-color:#e6e6e6; font-size:13px; }"
            "QTableWidget::item { padding:6px; }"
            "QTableWidget::item:selected { background:#f5d7d0; color:#111111; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:none; border-right:1px solid #d7d7d7; "
            "border-bottom:1px solid #d7d7d7; padding:8px 6px; font-weight:700; }"
        )
        self._reset_comment_column_widths()
        self.table_comments.horizontalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        self.table_comments.verticalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        self.table_comments.customContextMenuRequested.connect(self._open_comments_context_menu)
        right_layout.addWidget(self.table_comments, stretch=1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([360, 860])

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        bottom_row.addStretch()

        self.btn_file = QPushButton("File")
        self.btn_analyze = QPushButton("Analyze")
        self.btn_filters = QPushButton("Filters")
        self.btn_clear = QPushButton("Clear")
        for btn in (self.btn_file, self.btn_analyze, self.btn_filters, self.btn_clear):
            btn.setStyleSheet(button_style)
            bottom_row.addWidget(btn)

        self.btn_file.clicked.connect(self._open_comments_file_menu)
        self.btn_analyze.clicked.connect(self._open_comments_analyze_menu)
        self.btn_filters.clicked.connect(self._open_comments_filters_menu)
        self.btn_clear.clicked.connect(self._clear_comments_shell)

        body_layout.addLayout(bottom_row)

        shell_layout.addWidget(top_bar)
        shell_layout.addWidget(body, stretch=1)
        root.addWidget(shell)

    def _coming_soon(self, label: str):
        QMessageBox.information(self, label, f"{label} will be implemented in the next step.")

    def _default_comment_filter_state(self) -> dict:
        return {
            "commenter_contains": "",
            "posted_contains": "",
            "has_question_only": False,
            "has_profanity_only": False,
        }

    def _comments_menu_style(self) -> str:
        return (
            "QMenu { background:#f4f4f4; color:#222222; border:1px solid #a8a8a8; }"
            "QMenu::item { padding:6px 22px; margin:1px 4px; }"
            "QMenu::item:selected { background:#f1d5df; color:#111111; }"
            "QMenu::separator { height:1px; background:#d0d0d0; margin:4px 8px; }"
        )

    def _row_payload_from_table(self, row: int) -> dict:
        def cell(col: int) -> str:
            item = self.table_comments.item(row, col)
            return item.text().strip() if item is not None else ""

        return {
            "_checked": (
                self.table_comments.item(row, 0).checkState() == Qt.CheckState.Checked
                if self.table_comments.item(row, 0) is not None
                else False
            ),
            "commenter": cell(1),
            "commenter_channel": cell(2),
            "posted": cell(3),
            "likes": cell(4),
            "replies": cell(5),
            "has_question": cell(6),
            "has_profanity": cell(7),
            "comment": cell(8),
        }

    def _collect_comment_rows(self, *, include_hidden: bool) -> list[dict]:
        rows: list[dict] = []
        for row in range(self.table_comments.rowCount()):
            if not include_hidden and self.table_comments.isRowHidden(row):
                continue
            rows.append(self._row_payload_from_table(row))
        return rows

    def _serialize_comment_rows_as_tsv(self, rows: list[dict]) -> str:
        headers = [
            "Commenter",
            "Commenter Channel",
            "Posted",
            "Likes",
            "Replies",
            "Has Question",
            "Has Profanity",
            "Comment",
        ]
        lines = ["\t".join(headers)]
        for row in rows:
            lines.append(
                "\t".join(
                    [
                        row.get("commenter", ""),
                        row.get("commenter_channel", ""),
                        row.get("posted", ""),
                        row.get("likes", ""),
                        row.get("replies", ""),
                        row.get("has_question", ""),
                        row.get("has_profanity", ""),
                        row.get("comment", "").replace("\t", " ").replace("\r", " ").replace("\n", " "),
                    ]
                )
            )
        return "\n".join(lines)

    def _selected_comment_rows(self) -> list[dict]:
        row_indexes = sorted({index.row() for index in self.table_comments.selectionModel().selectedRows()})
        return [self._row_payload_from_table(row) for row in row_indexes]

    def _copy_comment_rows_to_clipboard(self, rows: list[dict]) -> None:
        if not rows:
            QMessageBox.information(self, "Comments", "No rows available.")
            return
        QApplication.clipboard().setText(self._serialize_comment_rows_as_tsv(rows))
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Copied {len(rows)} comment rows to clipboard.", 3000)

    def _copy_comments_only_to_clipboard(self, rows: list[dict]) -> None:
        if not rows:
            QMessageBox.information(self, "Comments", "No rows available.")
            return
        text = "\n".join(row.get("comment", "") for row in rows if row.get("comment", ""))
        QApplication.clipboard().setText(text)
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Copied {len(rows)} comments to clipboard.", 3000)

    def _export_comment_rows_to_csv(self, rows: list[dict]) -> None:
        if not rows:
            QMessageBox.information(self, "Comments", "No rows available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Comments CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        headers = [
            "Commenter",
            "Commenter Channel",
            "Posted",
            "Likes",
            "Replies",
            "Has Question",
            "Has Profanity",
            "Comment",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(
                    [
                        row.get("commenter", ""),
                        row.get("commenter_channel", ""),
                        row.get("posted", ""),
                        row.get("likes", ""),
                        row.get("replies", ""),
                        row.get("has_question", ""),
                        row.get("has_profanity", ""),
                        row.get("comment", ""),
                    ]
                )
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Exported {len(rows)} comments to {Path(path).name}.", 4000)

    def _export_comment_rows_to_txt(self, rows: list[dict]) -> None:
        if not rows:
            QMessageBox.information(self, "Comments", "No rows available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Comments TXT", "", "Text Files (*.txt)")
        if not path:
            return
        Path(path).write_text(self._serialize_comment_rows_as_tsv(rows), encoding="utf-8")
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Exported {len(rows)} comments to {Path(path).name}.", 4000)

    def _open_comments_file_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(self._comments_menu_style())
        visible_rows = self._collect_comment_rows(include_hidden=False)
        all_rows = self._collect_comment_rows(include_hidden=True)
        menu.addAction("Export VISIBLE rows to CSV", lambda: self._export_comment_rows_to_csv(visible_rows))
        menu.addAction("Export ALL rows to CSV", lambda: self._export_comment_rows_to_csv(all_rows))
        menu.addAction("Export VISIBLE rows to TXT", lambda: self._export_comment_rows_to_txt(visible_rows))
        menu.addAction("Export ALL rows to TXT", lambda: self._export_comment_rows_to_txt(all_rows))
        copy_menu = menu.addMenu("Copy")
        copy_menu.addAction("Copy VISIBLE rows to clipboard", lambda: self._copy_comment_rows_to_clipboard(visible_rows))
        copy_menu.addAction("Copy ALL rows to clipboard", lambda: self._copy_comment_rows_to_clipboard(all_rows))
        copy_menu.addAction("Copy VISIBLE comments", lambda: self._copy_comments_only_to_clipboard(visible_rows))
        copy_menu.addAction("Copy ALL comments", lambda: self._copy_comments_only_to_clipboard(all_rows))
        menu.exec(self.btn_file.mapToGlobal(self.btn_file.rect().bottomLeft()))

    def _show_report_dialog(self, title: str, body: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(780, 520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(body.strip() or "No data.")
        editor.setStyleSheet(
            "QPlainTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
            "padding:8px; font-size:13px; }"
        )
        layout.addWidget(editor, stretch=1)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:7px 16px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )
        close_btn.clicked.connect(dialog.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)
        dialog.exec()

    def _analyze_keywords_in_comments(self) -> None:
        rows = self._collect_comment_rows(include_hidden=False)
        if not rows:
            QMessageBox.information(self, "Comments", "No visible comments available.")
            return
        dlg = AnalyzeCommentsDialog(self, stop_words=self._comments_analysis_stop_words)
        dlg.set_source_comments(rows)
        dlg.btn_generate.clicked.connect(dlg.generate_word_stats)
        dlg.btn_view_comments.clicked.connect(dlg.open_view_comments_html)
        dlg.btn_clear_filters.clicked.connect(dlg.reset_filters)
        dlg.btn_clear.clicked.connect(dlg.clear_results)
        dlg.btn_stop_words.clicked.connect(lambda: self._open_comments_stop_words_dialog(dlg))
        dlg.btn_file.clicked.connect(lambda: self._open_analyze_comments_file_menu(dlg))
        dlg.exec()

    def _show_profanity_list(self) -> None:
        rows = [row for row in self._collect_comment_rows(include_hidden=False) if row.get("has_profanity", "").strip().upper() != "NO"]
        if not rows:
            QMessageBox.information(self, "Comments", "No profanity matches found in visible rows.")
            return
        lines = [f"Visible rows with profanity: {len(rows)}", ""]
        for idx, row in enumerate(rows, start=1):
            lines.extend(
                [
                    f"{idx}. {row.get('commenter', 'not-given')} | {row.get('posted', 'not-given')} | {row.get('has_profanity', 'NO')}",
                    row.get("comment", ""),
                    "",
                ]
            )
        self._show_report_dialog("Profanity List", "\n".join(lines))

    def _open_comments_analyze_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(self._comments_menu_style())
        menu.addAction("Analyze keywords in comments", self._analyze_keywords_in_comments)
        menu.addAction("Profanity list", self._show_profanity_list)
        menu.exec(self.btn_analyze.mapToGlobal(self.btn_analyze.rect().bottomLeft()))

    def _open_comments_stop_words_dialog(self, owner_dialog=None):
        current_words = (
            owner_dialog.stop_words()
            if owner_dialog is not None and hasattr(owner_dialog, "stop_words")
            else list(self._comments_analysis_stop_words)
        )
        dlg = StopWordsDialog(self, stop_words=current_words)
        dlg.btn_file.clicked.connect(lambda: self._open_stop_words_file_menu(dlg))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updated_words = dlg.stop_words()
        self._comments_analysis_stop_words = list(updated_words)
        if owner_dialog is not None and hasattr(owner_dialog, "set_stop_words"):
            owner_dialog.set_stop_words(updated_words)

    def _open_stop_words_file_menu(self, dialog):
        if dialog is None:
            return
        menu = QMenu(self)
        menu.setStyleSheet(self._comments_menu_style())
        act_load = menu.addAction("Load TXT")
        act_save = menu.addAction("Save TXT")
        chosen = menu.exec(dialog.btn_file.mapToGlobal(dialog.btn_file.rect().bottomLeft()))
        if chosen == act_load:
            self._load_stop_words_from_txt(dialog)
        elif chosen == act_save:
            self._save_stop_words_to_txt(dialog)

    def _load_stop_words_from_txt(self, dialog):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Stop Words TXT",
            "",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return
        try:
            text_data = Path(file_path).read_text(encoding="utf-8-sig")
        except Exception:
            try:
                text_data = Path(file_path).read_text(encoding="utf-8")
            except Exception as exc:
                QMessageBox.warning(self, "Stop Words", f"Failed to read file:\n{exc}")
                return
        dialog.text_words.setPlainText(str(text_data or "").strip())

    def _save_stop_words_to_txt(self, dialog):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stop Words TXT",
            "stop_words.txt",
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(dialog.text_words.toPlainText(), encoding="utf-8-sig")
        except Exception as exc:
            QMessageBox.warning(self, "Stop Words", f"Failed to save file:\n{exc}")

    def _open_analyze_comments_file_menu(self, dialog: AnalyzeCommentsDialog) -> None:
        if dialog is None:
            return
        menu = QMenu(self)
        menu.setStyleSheet(self._comments_menu_style())
        visible_rows = dialog.visible_rows()
        all_rows = list(dialog._all_word_rows)
        act_visible_csv = menu.addAction("Export VISIBLE rows to CSV")
        act_all_csv = menu.addAction("Export ALL rows to CSV")
        act_visible_txt = menu.addAction("Export VISIBLE rows to TXT")
        act_all_txt = menu.addAction("Export ALL rows to TXT")
        chosen = menu.exec(dialog.btn_file.mapToGlobal(dialog.btn_file.rect().bottomLeft()))
        if chosen == act_visible_csv:
            dialog.export_rows_to_csv(visible_rows)
        elif chosen == act_all_csv:
            dialog.export_rows_to_csv(all_rows)
        elif chosen == act_visible_txt:
            dialog.export_rows_to_txt(visible_rows)
        elif chosen == act_all_txt:
            dialog.export_rows_to_txt(all_rows)

    def _row_matches_comment_filters(self, payload: dict) -> bool:
        commenter_filter = self._comment_filters.get("commenter_contains", "").strip().lower()
        posted_filter = self._comment_filters.get("posted_contains", "").strip().lower()
        if commenter_filter and commenter_filter not in payload.get("commenter", "").lower():
            return False
        if posted_filter and posted_filter not in payload.get("posted", "").lower():
            return False
        if self._comment_filters.get("has_question_only") and payload.get("has_question", "").strip().upper() != "YES":
            return False
        profanity_value = payload.get("has_profanity", "").strip().upper()
        if self._comment_filters.get("has_profanity_only") and (not profanity_value or profanity_value == "NO"):
            return False
        return True

    def _apply_comment_filters(self) -> None:
        visible = 0
        total = self.table_comments.rowCount()
        for row in range(total):
            payload = self._row_payload_from_table(row)
            keep = self._row_matches_comment_filters(payload)
            self.table_comments.setRowHidden(row, not keep)
            if keep:
                visible += 1
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Comments filters applied. Showing {visible}/{total} rows.", 3000)

    def _prompt_comment_filter_text(self, title: str, key: str, prompt: str) -> None:
        current = self._comment_filters.get(key, "")
        value, ok = QInputDialog.getText(self, title, prompt, text=str(current))
        if not ok:
            return
        self._comment_filters[key] = str(value).strip()
        self._apply_comment_filters()

    def _toggle_comment_filter(self, key: str) -> None:
        self._comment_filters[key] = not bool(self._comment_filters.get(key))
        self._apply_comment_filters()

    def _reset_comment_filters(self) -> None:
        self._comment_filters = self._default_comment_filter_state()
        self._apply_comment_filters()

    def _open_comments_filters_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(self._comments_menu_style())
        menu.addAction(
            "Commenter contains...",
            lambda: self._prompt_comment_filter_text("Commenter Filter", "commenter_contains", "Commenter contains:"),
        )
        menu.addAction(
            "Posted contains...",
            lambda: self._prompt_comment_filter_text("Posted Filter", "posted_contains", "Posted contains:"),
        )
        action_question = menu.addAction("Has Question only")
        action_question.setCheckable(True)
        action_question.setChecked(bool(self._comment_filters.get("has_question_only")))
        action_question.triggered.connect(lambda _checked=False: self._toggle_comment_filter("has_question_only"))
        action_profanity = menu.addAction("Has Profanity only")
        action_profanity.setCheckable(True)
        action_profanity.setChecked(bool(self._comment_filters.get("has_profanity_only")))
        action_profanity.triggered.connect(lambda _checked=False: self._toggle_comment_filter("has_profanity_only"))
        menu.addSeparator()
        menu.addAction("Reset Filters", self._reset_comment_filters)
        menu.exec(self.btn_filters.mapToGlobal(self.btn_filters.rect().bottomLeft()))

    def _sync_comments_context_selection(self, pos) -> None:
        clicked_item = self.table_comments.itemAt(pos)
        if clicked_item is None:
            return
        clicked_row = clicked_item.row()
        selected_rows = {index.row() for index in self.table_comments.selectionModel().selectedRows()}
        if clicked_row in selected_rows:
            return
        self.table_comments.selectRow(clicked_row)

    def _open_comments_context_menu(self, pos) -> None:
        self._sync_comments_context_selection(pos)
        menu = QMenu(self.table_comments)
        menu.setStyleSheet(self._comments_menu_style())

        comments_tool_menu = menu.addMenu("Comments tool")
        comments_tool_menu.addAction("Analyze keywords in comments", self._analyze_keywords_in_comments)
        comments_tool_menu.addAction("Profanity list", self._show_profanity_list)

        checkboxes_menu = menu.addMenu("Checkboxes")
        checkboxes_menu.addAction("Check SELECTED rows", lambda: self._set_selected_comment_rows_checked(True))
        checkboxes_menu.addAction("Uncheck SELECTED rows", lambda: self._set_selected_comment_rows_checked(False))
        checkboxes_menu.addAction("Check ALL rows", lambda: self._set_all_comment_rows_checked(True))
        checkboxes_menu.addAction("Uncheck ALL rows", lambda: self._set_all_comment_rows_checked(False))

        filters_menu = menu.addMenu("Filters")
        filters_menu.addAction(
            "Commenter contains...",
            lambda: self._prompt_comment_filter_text("Commenter Filter", "commenter_contains", "Commenter contains:"),
        )
        filters_menu.addAction(
            "Posted contains...",
            lambda: self._prompt_comment_filter_text("Posted Filter", "posted_contains", "Posted contains:"),
        )
        action_question = filters_menu.addAction("Has Question only")
        action_question.setCheckable(True)
        action_question.setChecked(bool(self._comment_filters.get("has_question_only")))
        action_question.triggered.connect(lambda _checked=False: self._toggle_comment_filter("has_question_only"))
        action_profanity = filters_menu.addAction("Has Profanity only")
        action_profanity.setCheckable(True)
        action_profanity.setChecked(bool(self._comment_filters.get("has_profanity_only")))
        action_profanity.triggered.connect(lambda _checked=False: self._toggle_comment_filter("has_profanity_only"))
        filters_menu.addSeparator()
        filters_menu.addAction("Reset Filters", self._reset_comment_filters)

        copy_menu = menu.addMenu("Copy")
        copy_menu.addAction("Copy SELECTED rows to clipboard", lambda: self._copy_comment_rows_to_clipboard(self._selected_comment_rows()))
        copy_menu.addAction("Copy ALL rows to clipboard", lambda: self._copy_comment_rows_to_clipboard(self._collect_comment_rows(include_hidden=True)))
        copy_menu.addAction("Copy SELECTED comments", lambda: self._copy_comments_only_to_clipboard(self._selected_comment_rows()))
        copy_menu.addAction("Copy ALL comments", lambda: self._copy_comments_only_to_clipboard(self._collect_comment_rows(include_hidden=True)))

        search_menu = menu.addMenu("Search")
        search_menu.addAction("Search current row", self._search_current_comment_row)
        search_menu.addAction("Search SELECTED rows", self._search_selected_comment_rows)
        search_menu.addAction("Search ALL rows", self._search_all_comment_rows)

        menu.addSeparator()
        menu.addAction("Auto-fit column widths", self._auto_fit_comment_column_widths)
        menu.addAction("Reset column widths", self._reset_comment_column_widths)

        delete_menu = menu.addMenu("Delete")
        delete_menu.addAction("Delete SELECTED rows", self._delete_selected_comment_rows)
        delete_menu.addAction("Delete ALL rows", self._delete_all_comment_rows)

        menu.exec(self.table_comments.viewport().mapToGlobal(pos))

    def _selected_comment_row_indexes(self) -> list[int]:
        return sorted({index.row() for index in self.table_comments.selectionModel().selectedRows()})

    def _set_comment_checkbox_state_for_rows(self, row_indexes: list[int], checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in row_indexes:
            item = self.table_comments.item(row, 0)
            if item is None:
                item = QTableWidgetItem("")
                self.table_comments.setItem(row, 0, item)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(state)

    def _set_selected_comment_rows_checked(self, checked: bool) -> None:
        rows = self._selected_comment_row_indexes()
        if not rows:
            QMessageBox.information(self, "Comments", "Please select at least one row.")
            return
        self._set_comment_checkbox_state_for_rows(rows, checked)

    def _set_all_comment_rows_checked(self, checked: bool) -> None:
        rows = list(range(self.table_comments.rowCount()))
        if not rows:
            QMessageBox.information(self, "Comments", "No rows available.")
            return
        self._set_comment_checkbox_state_for_rows(rows, checked)

    def _build_comment_search_url(self, payload: dict) -> str:
        commenter_channel = str(payload.get("commenter_channel", "")).strip()
        if commenter_channel.startswith("http://") or commenter_channel.startswith("https://"):
            return commenter_channel
        commenter = str(payload.get("commenter", "")).strip()
        if commenter:
            return "https://www.youtube.com/results?search_query=" + QUrl.toPercentEncoding(commenter).data().decode("ascii")
        return ""

    def _open_comment_search_urls(self, rows: list[dict], scope_label: str) -> None:
        urls = []
        for row in rows:
            url = self._build_comment_search_url(row)
            if url and url not in urls:
                urls.append(url)
        if not urls:
            QMessageBox.information(self, "Comments", "No search targets available.")
            return
        if len(urls) > 5:
            answer = QMessageBox.question(
                self,
                "Comments",
                f"{scope_label} will open {len(urls)} browser tabs. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        opened = 0
        for url in urls:
            if QDesktopServices.openUrl(QUrl(url)):
                opened += 1
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(f"Opened {opened} comment search target(s).", 3000)

    def _search_current_comment_row(self) -> None:
        row = self.table_comments.currentRow()
        if row < 0:
            QMessageBox.information(self, "Comments", "Please select a row first.")
            return
        self._open_comment_search_urls([self._row_payload_from_table(row)], "Current row search")

    def _search_selected_comment_rows(self) -> None:
        rows = [self._row_payload_from_table(row) for row in self._selected_comment_row_indexes()]
        if not rows:
            QMessageBox.information(self, "Comments", "Please select at least one row.")
            return
        self._open_comment_search_urls(rows, "Selected rows search")

    def _search_all_comment_rows(self) -> None:
        rows = self._collect_comment_rows(include_hidden=True)
        if not rows:
            QMessageBox.information(self, "Comments", "No rows available.")
            return
        self._open_comment_search_urls(rows, "All rows search")

    def _auto_fit_comment_column_widths(self) -> None:
        self.table_comments.resizeColumnsToContents()
        max_widths = {
            0: 40,
            1: 220,
            2: 300,
            3: 130,
            4: 90,
            5: 90,
            6: 130,
            7: 180,
            8: 620,
        }
        for col, max_width in max_widths.items():
            self.table_comments.setColumnWidth(col, min(self.table_comments.columnWidth(col), max_width))

    def _reset_comment_column_widths(self) -> None:
        for col, width in self.COMMENT_TABLE_DEFAULT_WIDTHS.items():
            self.table_comments.setColumnWidth(col, width)

    def _rebuild_comment_key_index_from_table(self) -> None:
        self._comment_key_to_row = {}
        for row in range(self.table_comments.rowCount()):
            payload = self._row_payload_from_table(row)
            key = self._comment_row_key(payload)
            if any(key):
                self._comment_key_to_row[key] = row

    def _delete_selected_comment_rows(self) -> None:
        row_indexes = self._selected_comment_row_indexes()
        if not row_indexes:
            QMessageBox.information(self, "Comments", "Please select at least one row.")
            return
        answer = QMessageBox.question(
            self,
            "Comments",
            f"Delete {len(row_indexes)} selected row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for row in reversed(row_indexes):
            self.table_comments.removeRow(row)
        self._rebuild_comment_key_index_from_table()
        self._apply_comment_filters()

    def _delete_all_comment_rows(self) -> None:
        total = self.table_comments.rowCount()
        if total <= 0:
            QMessageBox.information(self, "Comments", "No rows available.")
            return
        answer = QMessageBox.question(
            self,
            "Comments",
            f"Delete all {total} row(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._clear_comment_rows()
        self._apply_comment_filters()

    def _refresh_extract_controls(self):
        load_busy = self._loading_video_active or self._load_worker is not None
        extracting = self._extract_session_active or self._autoscroll_active
        self.combo_page_scrolls.setEnabled(not load_busy and not extracting)
        self.btn_scroll_extract.setEnabled(not load_busy and not extracting)
        self.btn_extract_comments.setEnabled(not load_busy and not extracting)
        self.btn_start_autoscroll.setEnabled(not load_busy)
        self.btn_scroll_extract.setText("Scrolling..." if self._extract_session_active else "2. Scroll & Extract")
        self.btn_start_autoscroll.setText("Stop Autoscroll" if self._autoscroll_active else "Start Autoscroll")

    def _clear_comment_rows(self):
        self.table_comments.setRowCount(0)
        self._comment_key_to_row = {}

    def _stop_comment_extraction(self):
        self._extract_run_token += 1
        self._extract_session_active = False
        self._autoscroll_active = False
        self._remaining_scroll_steps = 0
        self._scroll_extract_timer.stop()
        self._refresh_extract_controls()

    def _comment_row_key(self, payload: dict) -> tuple[str, str, str]:
        return (
            str(payload.get("commenter", "")).strip().lower(),
            str(payload.get("posted", "")).strip().lower(),
            str(payload.get("comment", "")).strip().lower(),
        )

    def _set_comment_table_row(self, row: int, payload: dict):
        existing_checkbox = self.table_comments.item(row, 0)
        checked_state = existing_checkbox.checkState() if existing_checkbox is not None else Qt.CheckState.Unchecked
        values = [
            "",
            str(payload.get("commenter", "")).strip(),
            str(payload.get("commenter_channel", "")).strip(),
            str(payload.get("posted", "")).strip(),
            str(payload.get("likes", "")).strip(),
            str(payload.get("replies", "")).strip(),
            str(payload.get("has_question", "")).strip(),
            str(payload.get("has_profanity", "")).strip(),
            str(payload.get("comment", "")).strip(),
        ]
        for col, value in enumerate(values):
            item = self.table_comments.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.table_comments.setItem(row, col, item)
            item.setText(value)
            if col == 0:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(checked_state)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col in (2, 8):
                item.setToolTip(value)

    def _merge_comment_rows(self, rows: list[dict]) -> int:
        new_count = 0
        for payload in rows or []:
            key = self._comment_row_key(payload)
            if not any(key):
                continue
            existing_row = self._comment_key_to_row.get(key)
            if existing_row is None:
                existing_row = self.table_comments.rowCount()
                self.table_comments.insertRow(existing_row)
                self._comment_key_to_row[key] = existing_row
                new_count += 1
            self._set_comment_table_row(existing_row, payload)
        self._apply_comment_filters()
        return new_count

    def _ensure_video_browser_ready(self) -> bool:
        if self._browser_view is None:
            QMessageBox.information(
                self,
                "Comments",
                "Please load a YouTube video into the embedded browser first.",
            )
            return False
        return True

    def _build_comments_extract_js(self, scroll_after: bool) -> str:
        scroll_step = 720 if scroll_after else 0
        return f"""
            (() => {{
                const clean = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
                const profanityWords = [
                    'fuck', 'fucking', 'fucked', 'shit', 'bitch', 'bastard', 'asshole',
                    'damn', 'dick', 'piss', 'crap', 'wtf', 'motherfucker', 'slut'
                ];
                const results = [];
                const root = document.scrollingElement || document.documentElement || document.body;
                const commentsAnchor = document.querySelector('ytd-comments-header-renderer, #comments');
                if (commentsAnchor && root) {{
                    const anchorTop = commentsAnchor.getBoundingClientRect().top + window.scrollY - 120;
                    if (root.scrollTop < anchorTop) {{
                        root.scrollTop = anchorTop;
                    }} else if ({scroll_step} > 0) {{
                        root.scrollTop = Math.min(root.scrollTop + {scroll_step}, root.scrollHeight);
                    }}
                }} else if (root && {scroll_step} > 0) {{
                    root.scrollTop = Math.min(root.scrollTop + {scroll_step}, root.scrollHeight);
                }}

                const parseReplies = (thread) => {{
                    const texts = [];
                    thread.querySelectorAll('ytd-button-renderer button, ytd-button-renderer a, tp-yt-paper-button, button, a').forEach((node) => {{
                        const text = clean(node.innerText || node.textContent || '');
                        if (text && /repl/i.test(text)) texts.push(text);
                    }});
                    for (const text of texts) {{
                        const match = text.match(/(\\d[\\d,\\.]*)/);
                        if (match) return match[1];
                        if (/reply/i.test(text)) return '1+';
                    }}
                    return '0';
                }};

                document.querySelectorAll('ytd-comment-thread-renderer').forEach((thread) => {{
                    const authorNode = thread.querySelector('#author-text');
                    const contentNode = thread.querySelector('#content-text');
                    const commenter = clean(authorNode?.innerText || authorNode?.textContent || '');
                    const commenterChannel = clean(authorNode?.href || authorNode?.getAttribute('href') || '');
                    const posted = clean(thread.querySelector('#published-time-text a, #published-time-text')?.innerText || '');
                    const likes = clean(thread.querySelector('#vote-count-middle')?.innerText || '') || '0';
                    const comment = clean(contentNode?.innerText || contentNode?.textContent || '');
                    if (!commenter || !comment) return;
                    const commentLower = comment.toLowerCase();
                    const matchedProfanity = [];
                    profanityWords.forEach((word) => {{
                        if (commentLower.includes(word) && !matchedProfanity.includes(word)) {{
                            matchedProfanity.push(word);
                        }}
                    }});
                    const hasQuestion = comment.includes('?') ? 'YES' : 'NO';
                    const hasProfanity = matchedProfanity.length ? `YES: ${{matchedProfanity.join(', ')}}` : 'NO';
                    const replies = parseReplies(thread);
                    results.push({{
                        commenter,
                        commenter_channel: commenterChannel,
                        posted,
                        likes,
                        replies,
                        has_question: hasQuestion,
                        has_profanity: hasProfanity,
                        comment
                    }});
                }});

                return {{
                    url: window.location.href || '',
                    scrollTop: root ? root.scrollTop : 0,
                    scrollHeight: root ? root.scrollHeight : 0,
                    count: results.length,
                    comments: results
                }};
            }})();
        """

    def _ensure_browser_view(self) -> bool:
        if self._browser_view is not None:
            return True
        if self._webengine_view_class is None:
            try:
                from PyQt6.QtWebEngineWidgets import QWebEngineView as ImportedWebEngineView
                self._webengine_view_class = ImportedWebEngineView
            except Exception as exc:
                self.text_loaded_video.setPlainText(
                    "\n".join(
                        [
                            "Embedded browser could not load.",
                            "",
                            "Install with:",
                            "python -m pip install PyQt6-WebEngine",
                            "",
                            str(exc).strip(),
                        ]
                    ).strip()
                )
                self.browser_stack.setCurrentWidget(self.text_loaded_video)
                return False
        try:
            self._browser_view = self._webengine_view_class()
            self.browser_stack.addWidget(self._browser_view)
            self.browser_stack.setCurrentWidget(self._browser_view)
            self._browser_view.loadFinished.connect(self._on_browser_load_finished)
            return True
        except Exception as exc:
            self._browser_view = None
            self.text_loaded_video.setPlainText(
                "\n".join(
                    [
                        "Failed to create embedded browser.",
                        "",
                        str(exc).strip(),
                    ]
                ).strip()
            )
            self.browser_stack.setCurrentWidget(self.text_loaded_video)
            return False

    def _show_loaded_video_text(self, text: str):
        self.text_loaded_video.setPlainText(str(text or "").strip() or "No video loaded")
        self.browser_stack.setCurrentWidget(self.text_loaded_video)

    def _load_video_in_browser(self, video_url: str):
        if not video_url:
            return
        if self._ensure_browser_view() and self._browser_view is not None:
            self.browser_stack.setCurrentWidget(self._browser_view)
            self._browser_view.setUrl(QUrl(video_url))
        else:
            self._show_loaded_video_text(
                "\n".join(
                    [
                        "Video metadata loaded.",
                        "",
                        f"Open in browser manually: {video_url}",
                    ]
                ).strip()
            )

    def _request_stop_load_worker(self):
        worker = self._load_worker
        if worker is None:
            return
        try:
            worker.request_stop()
        except Exception:
            pass

    def _cleanup_load_worker(self):
        worker = self._load_worker
        if worker is None:
            return
        self._load_worker = None
        try:
            worker.quit()
            worker.wait(1500)
        except Exception:
            pass
        try:
            worker.deleteLater()
        except Exception:
            pass
        self._refresh_extract_controls()

    def _format_loaded_video_info(self, payload: dict) -> str:
        lines = [
            str(payload.get("title", "")).strip() or "(Untitled video)",
            "",
            f"Video URL: {str(payload.get('webpage_url', payload.get('normalized_url', ''))).strip() or 'not-given'}",
            f"Video ID: {str(payload.get('video_id', '')).strip() or 'not-given'}",
            f"Channel: {str(payload.get('channel_name', '')).strip() or 'not-given'}",
            f"Channel URL: {str(payload.get('channel_url', '')).strip() or 'not-given'}",
            f"Posted: {str(payload.get('posted', '')).strip() or 'not-given'}",
            f"Duration: {str(payload.get('duration', '')).strip() or 'not-given'}",
            f"Views: {str(payload.get('view_count', '')).strip() or 'not-given'}",
            f"Comments: {str(payload.get('comment_count', '')).strip() or 'not-given'}",
        ]
        description = str(payload.get("description", "")).strip()
        if description:
            lines.extend(["", "Description:", description])
        if len(self._queued_video_links) > 1:
            lines.extend(["", f"Queued links: {len(self._queued_video_links)}"])
        return "\n".join(lines).strip()

    def _load_video(self):
        if self._load_worker is not None:
            QMessageBox.information(self, "Load Video", "Video loading is already running.")
            return
        text = self.input_video_link.text().strip()
        if not text:
            QMessageBox.information(self, "Load Video", "Please enter a video link or ID first.")
            return

        self._load_run_token += 1
        self._stop_comment_extraction()
        self._clear_comment_rows()
        run_token = self._load_run_token
        self._set_load_video_busy(True)
        self._show_loaded_video_text("Loading video metadata...")

        worker = CommentsLoadVideoWorker(text)
        self._load_worker = worker

        def _status(message: str):
            if run_token != self._load_run_token:
                return
            self._show_loaded_video_text(str(message))
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(str(message), 3000)

        def _loaded(payload: dict):
            if run_token != self._load_run_token:
                return
            self._loaded_video_info = dict(payload or {})
            normalized = str(self._loaded_video_info.get("normalized_url", "")).strip()
            if normalized:
                self.input_video_link.setText(normalized)
            self._load_video_in_browser(normalized or str(self._loaded_video_info.get("webpage_url", "")).strip())
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage("Video metadata loaded into Comments tool.", 5000)

        def _error(message: str):
            if run_token != self._load_run_token:
                return
            self._loaded_video_info = {}
            self._show_loaded_video_text(
                "\n".join(
                    [
                        "Unable to load video.",
                        "",
                        str(message).strip() or "Unknown error.",
                    ]
                ).strip()
            )
            QMessageBox.warning(self, "Load Video", str(message).strip() or "Unable to load video metadata.")

        def _finished():
            if run_token != self._load_run_token:
                return
            self._cleanup_load_worker()
            self._set_load_video_busy(False)

        worker.status_signal.connect(_status)
        worker.loaded_signal.connect(_loaded)
        worker.error_signal.connect(_error)
        worker.finished_signal.connect(_finished)
        worker.start()

    def _set_load_video_busy(self, busy: bool):
        self._loading_video_active = bool(busy)
        self.btn_load_video.setEnabled(not busy)
        self.input_video_link.setReadOnly(bool(busy))
        self.btn_load_video.setText("Loading..." if busy else "1. Load Video")
        self._refresh_extract_controls()

    def _on_browser_load_finished(self, ok: bool):
        if not ok:
            return
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Video page loaded. Ready to extract comments.", 4000)

    def _run_extract_js(self, *, scroll_after: bool):
        if not self._ensure_video_browser_ready():
            return
        token = self._extract_run_token
        js_code = self._build_comments_extract_js(scroll_after=scroll_after)
        self._browser_view.page().runJavaScript(
            js_code,
            lambda payload, run_token=token: self._handle_comment_extract_payload(payload, run_token),
        )

    def _handle_comment_extract_payload(self, payload, run_token: int):
        if run_token != self._extract_run_token:
            return
        if not isinstance(payload, dict):
            return
        comments = payload.get("comments", []) if isinstance(payload.get("comments", []), list) else []
        new_count = self._merge_comment_rows(comments)
        total_count = self.table_comments.rowCount()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(
                f"Comments loaded: {total_count} total ({new_count} new).",
                3500,
            )
        if self._extract_session_active and self._remaining_scroll_steps <= 0:
            self._extract_session_active = False
            self._scroll_extract_timer.stop()
            self._refresh_extract_controls()
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(
                    f"Scroll & Extract complete. Loaded {total_count} unique comments.",
                    5000,
                )

    def _run_extract_cycle(self):
        if self._autoscroll_active:
            self._run_extract_js(scroll_after=True)
            return
        if self._extract_session_active:
            if self._remaining_scroll_steps <= 0:
                self._extract_session_active = False
                self._scroll_extract_timer.stop()
                self._refresh_extract_controls()
                return
            self._remaining_scroll_steps -= 1
            self._run_extract_js(scroll_after=True)
            return
        self._scroll_extract_timer.stop()

    def _extract_comments_now(self):
        if self._load_worker is not None:
            QMessageBox.information(self, "Extract Comments", "Please wait for Load Video to finish first.")
            return
        if self._extract_session_active or self._autoscroll_active:
            QMessageBox.information(self, "Extract Comments", "Scrolling or autoscroll is already running.")
            return
        self._extract_run_token += 1
        self._run_extract_js(scroll_after=False)

    def _start_scroll_extract(self):
        if self._load_worker is not None:
            QMessageBox.information(self, "Scroll & Extract", "Please wait for Load Video to finish first.")
            return
        if self._autoscroll_active or self._extract_session_active:
            QMessageBox.information(self, "Scroll & Extract", "Extraction is already running.")
            return
        try:
            total_scrolls = max(1, int(self.combo_page_scrolls.currentText()))
        except Exception:
            total_scrolls = 10
        if not self._ensure_video_browser_ready():
            return
        self._extract_run_token += 1
        self._extract_session_active = True
        self._remaining_scroll_steps = total_scrolls
        self._refresh_extract_controls()
        self._run_extract_cycle()
        self._scroll_extract_timer.start()

    def _toggle_autoscroll(self):
        if self._load_worker is not None:
            QMessageBox.information(self, "Autoscroll", "Please wait for Load Video to finish first.")
            return
        if self._autoscroll_active:
            self._autoscroll_active = False
            self._scroll_extract_timer.stop()
            self._refresh_extract_controls()
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage("Autoscroll stopped.", 3000)
            return
        if self._extract_session_active:
            QMessageBox.information(self, "Autoscroll", "Scroll & Extract is already running.")
            return
        if not self._ensure_video_browser_ready():
            return
        self._extract_run_token += 1
        self._autoscroll_active = True
        self._refresh_extract_controls()
        self._run_extract_cycle()
        self._scroll_extract_timer.start()
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Autoscroll started.", 3000)

    def _extract_first_url(self, text: str) -> str:
        for token in str(text or "").replace("\r", "\n").split():
            clean = token.strip().strip(",;")
            if clean.startswith("http://") or clean.startswith("https://"):
                return clean
        return ""

    def _is_video_target(self, text: str) -> bool:
        value = str(text or "").strip()
        if not value:
            return False
        lower = value.lower()
        if lower.startswith(("http://", "https://")):
            return any(
                marker in lower
                for marker in (
                    "youtube.com/watch?",
                    "youtube.com/shorts/",
                    "youtube.com/live/",
                    "youtu.be/",
                )
            )
        return len(value) == 11 and all(ch.isalnum() or ch in "-_" for ch in value)

    def _extract_first_video_target(self, text: str) -> str:
        raw = str(text or "").replace("\r", "\n")
        for token in raw.split():
            clean = token.strip().strip(",;")
            if self._is_video_target(clean):
                return clean
        for line in raw.splitlines():
            clean = line.strip().strip(",;")
            if self._is_video_target(clean):
                return clean
        return ""

    def receive_payload(self, text, hint_text=""):
        payload = str(text or "").strip()
        self._incoming_payload = payload
        first_target = self._extract_first_video_target(payload)
        if first_target:
            self._loaded_video_info = {}
            self._stop_comment_extraction()
            self._clear_comment_rows()
            self.input_video_link.setText(first_target)
            self._queued_video_links = [
                line.strip()
                for line in payload.splitlines()
                if self._is_video_target(line.strip())
            ]
            self._show_loaded_video_text(
                "\n".join(
                    filter(
                        None,
                        [
                            "Incoming payload received.",
                            f"Primary target: {first_target}",
                            f"Queued links: {len(self._queued_video_links)}" if self._queued_video_links else "",
                            hint_text.strip() if str(hint_text or "").strip() else "",
                        ],
                    )
                ).strip()
            )
        else:
            self._loaded_video_info = {}
            self._stop_comment_extraction()
            self._clear_comment_rows()
            self.input_video_link.clear()
            self._queued_video_links = []
            self._show_loaded_video_text(
                "\n".join(filter(None, ["Incoming payload received.", payload, hint_text.strip() if str(hint_text or "").strip() else ""])).strip()
            )
        if hint_text and self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(str(hint_text), 4000)

    def receive_links_for_import(self, links, hint_text=""):
        clean_links = [
            str(link).strip()
            for link in (links or [])
            if str(link).strip() and self._is_video_target(str(link).strip())
        ]
        self._loaded_video_info = {}
        self._stop_comment_extraction()
        self._clear_comment_rows()
        self._queued_video_links = clean_links
        self._incoming_payload = "\n".join(clean_links)
        if clean_links:
            self.input_video_link.setText(clean_links[0])
            self._show_loaded_video_text(
                "\n".join(
                    filter(
                        None,
                        [
                            "Incoming links received.",
                            f"Primary target: {clean_links[0]}",
                            f"Queued links: {len(clean_links)}",
                            hint_text.strip() if str(hint_text or "").strip() else "",
                        ],
                    )
                ).strip()
            )
        else:
            self._show_loaded_video_text("No video loaded")
        if hint_text and self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(str(hint_text), 4000)

    def _clear_comments_shell(self):
        self._load_run_token += 1
        self._request_stop_load_worker()
        self._cleanup_load_worker()
        self._stop_comment_extraction()
        self._comment_filters = self._default_comment_filter_state()
        self._loaded_video_info = {}
        self._incoming_payload = ""
        self._queued_video_links = []
        self.input_video_link.clear()
        if self._browser_view is not None:
            try:
                self._browser_view.stop()
                self._browser_view.setUrl(QUrl("about:blank"))
            except Exception:
                pass
        self._show_loaded_video_text("No video loaded")
        self._clear_comment_rows()
        self._set_load_video_busy(False)
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage("Comments tool cleared.", 3000)

    def shutdown(self):
        self._load_run_token += 1
        self._request_stop_load_worker()
        self._cleanup_load_worker()
        self._stop_comment_extraction()
        if self._browser_view is not None:
            try:
                self._browser_view.stop()
            except Exception:
                pass
        self._set_load_video_busy(False)
