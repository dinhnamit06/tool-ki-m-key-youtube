from __future__ import annotations

from typing import Sequence

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.rpm_templates import RPMFilterTemplate, summarize_template


class FilterTemplateDialog(QDialog):
    def __init__(self, templates: Sequence[RPMFilterTemplate], current_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Templates")
        self.resize(860, 520)
        self.setModal(True)
        self._templates = list(templates)
        self.selected_template_name = current_name

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(18)

        title = QLabel("Filter Templates")
        title.setObjectName("section_title")
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(18)

        self.lst_templates = QListWidget()
        self.lst_templates.setMinimumWidth(220)
        self.lst_templates.currentRowChanged.connect(self._on_row_changed)
        for template in self._templates:
            QListWidgetItem(template.name, self.lst_templates)
        body.addWidget(self.lst_templates)

        detail_wrap = QWidget()
        detail_layout = QVBoxLayout(detail_wrap)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(12)

        self.lbl_name = QLabel("")
        self.lbl_name.setObjectName("app_title")
        detail_layout.addWidget(self.lbl_name)

        self.lbl_description = QLabel("")
        self.lbl_description.setObjectName("muted_label")
        self.lbl_description.setWordWrap(True)
        detail_layout.addWidget(self.lbl_description)

        self.lbl_summary_title = QLabel("Template Summary")
        self.lbl_summary_title.setObjectName("section_title")
        detail_layout.addWidget(self.lbl_summary_title)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setStyleSheet(
            "QLabel { background:#f5f8fc; border:1px solid #dbe3ee; border-radius:12px; padding:12px; color:#334155; }"
        )
        detail_layout.addWidget(self.lbl_summary)

        self.lbl_scope_title = QLabel("Usage")
        self.lbl_scope_title.setObjectName("section_title")
        detail_layout.addWidget(self.lbl_scope_title)

        self.lbl_scope = QLabel(
            "Use templates to jump to a known filter bias quickly. Built-in and custom templates can both be loaded here."
        )
        self.lbl_scope.setObjectName("muted_label")
        self.lbl_scope.setWordWrap(True)
        detail_layout.addWidget(self.lbl_scope)
        detail_layout.addStretch()

        body.addWidget(detail_wrap, 1)
        root.addLayout(body, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("ghost_btn")
        self.btn_close.clicked.connect(self.reject)
        actions.addWidget(self.btn_close)
        self.btn_use = QPushButton("Use Template")
        self.btn_use.setObjectName("accent_btn")
        self.btn_use.clicked.connect(self._accept_current)
        actions.addWidget(self.btn_use)
        root.addLayout(actions)

        self._select_initial(current_name)

    def _select_initial(self, current_name: str):
        index = next((idx for idx, item in enumerate(self._templates) if item.name == current_name), 0)
        self.lst_templates.setCurrentRow(index)

    def _on_row_changed(self, row: int):
        if row < 0 or row >= len(self._templates):
            return
        template = self._templates[row]
        self.selected_template_name = template.name
        self.lbl_name.setText(template.name)
        self.lbl_description.setText(template.description)
        self.lbl_summary.setText(summarize_template(template))

    def _accept_current(self):
        if self.lst_templates.currentRow() < 0 and self._templates:
            self.lst_templates.setCurrentRow(0)
        self.accept()
