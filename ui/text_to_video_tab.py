from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.text_to_video_planner import create_scene_plan
from core.text_to_video_prompter import (
    AIGenerateScenePromptsWorker,
    build_scene_prompt_template,
    generate_local_scene_prompts,
)
from core.text_to_video_exporter import export_project_package
from core.text_to_video_veo import GenerateSingleSceneWorker
from utils.constants import TABLE_SCROLLBAR_STYLE


class TextToVideoTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._project_status = "Shell ready"
        self._prompt_worker = None
        self._prompt_generation_active = False
        self._prompt_run_token = 0
        self._scene_worker = None
        self._scene_run_token = 0
        self._single_generation_active = False
        self._batch_generation_active = False
        self._batch_scene_queue = []
        self._batch_results = []
        self._batch_failures = []
        self._veo_settings = self._default_veo_settings()
        self._setup_ui()
        self._refresh_interaction_state()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("ttvShell")
        shell.setStyleSheet("QFrame#ttvShell { background:#111111; }")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("ttvTopBar")
        top_bar.setStyleSheet("QFrame#ttvTopBar { background:#111111; border-bottom:1px solid #2a2a2a; }")
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(24, 18, 24, 18)
        top_layout.setSpacing(14)

        lbl_title = QLabel("Text to Video")
        lbl_title.setStyleSheet("QLabel { color:#ffffff; font-size:24px; font-weight:700; }")
        top_layout.addWidget(lbl_title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        lbl_project = QLabel("Project Name:")
        lbl_project.setStyleSheet("QLabel { color:#f1f1f1; font-size:13px; }")
        toolbar.addWidget(lbl_project)

        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("My Veo Project")
        self.input_project_name.setStyleSheet(
            "QLineEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
            "border-radius:4px; padding:6px 8px; font-size:13px; }"
        )
        toolbar.addWidget(self.input_project_name, stretch=1)

        button_style = (
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; "
            "padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        self.btn_load_script = QPushButton("Load Script")
        self.btn_create_scene_plan = QPushButton("Create Scene Plan")
        self.btn_generate_prompts = QPushButton("Generate Prompts")
        self.btn_veo_settings = QPushButton("Veo Settings")
        self.btn_render_project = QPushButton("Render Project")

        for btn in (
            self.btn_load_script,
            self.btn_create_scene_plan,
            self.btn_generate_prompts,
            self.btn_veo_settings,
            self.btn_render_project,
        ):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(32)
            btn.setStyleSheet(button_style)

        self.btn_load_script.clicked.connect(lambda: self._coming_soon("Load Script"))
        self.btn_create_scene_plan.clicked.connect(self._create_scene_plan_from_source)
        self.btn_generate_prompts.clicked.connect(self._generate_scene_prompts)
        self.btn_veo_settings.clicked.connect(self._open_veo_settings_dialog)
        self.btn_render_project.clicked.connect(lambda: self._coming_soon("Render Project"))

        toolbar.addWidget(self.btn_load_script)
        toolbar.addWidget(self.btn_create_scene_plan)
        toolbar.addWidget(self.btn_generate_prompts)
        toolbar.addWidget(self.btn_veo_settings)
        toolbar.addWidget(self.btn_render_project)
        top_layout.addLayout(toolbar)

        body = QFrame()
        body.setObjectName("ttvBody")
        body.setStyleSheet("QFrame#ttvBody { background:#111111; }")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(24, 18, 24, 18)
        body_layout.setSpacing(18)

        left_col = QVBoxLayout()
        left_col.setSpacing(14)
        left_col.addWidget(self._build_project_card())
        left_col.addWidget(self._build_source_script_card(), stretch=1)

        center_col = QVBoxLayout()
        center_col.setSpacing(14)
        center_col.addWidget(self._build_scene_workspace_card(), stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(14)
        right_col.addWidget(self._build_workspace_card())
        right_col.addWidget(self._build_generation_card())
        right_col.addStretch(1)

        body_layout.addLayout(left_col, stretch=3)
        body_layout.addLayout(center_col, stretch=6)
        body_layout.addLayout(right_col, stretch=4)

        bottom_bar = QFrame()
        bottom_bar.setObjectName("ttvBottomBar")
        bottom_bar.setStyleSheet("QFrame#ttvBottomBar { background:#111111; border-top:1px solid #2a2a2a; }")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(24, 10, 24, 16)
        bottom_layout.setSpacing(12)

        self.lbl_scene_count = self._metric_label("Scenes: 0")
        self.lbl_selected_scene = self._metric_label("Selected: 0")
        self.lbl_project_status = self._metric_label("Project Status: Shell ready")
        bottom_layout.addWidget(self.lbl_scene_count)
        bottom_layout.addWidget(self.lbl_selected_scene)
        bottom_layout.addWidget(self.lbl_project_status, stretch=1)

        self.btn_file = QPushButton("File")
        self.btn_clear = QPushButton("Clear")
        for btn in (self.btn_file, self.btn_clear):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(34)
            btn.setStyleSheet(button_style)
        self.btn_file.clicked.connect(lambda: self._coming_soon("File"))
        self.btn_clear.clicked.connect(self._clear_shell)
        bottom_layout.addWidget(self.btn_file)
        bottom_layout.addWidget(self.btn_clear)

        shell_layout.addWidget(top_bar)
        shell_layout.addWidget(body, stretch=1)
        shell_layout.addWidget(bottom_bar)
        root.addWidget(shell)

    def _card_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("panelCard")
        card.setStyleSheet(
            "QFrame#panelCard { background:#181b1f; border:1px solid #31363f; border-radius:10px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        lbl = QLabel(title)
        lbl.setStyleSheet("QLabel { color:#ffffff; font-size:16px; font-weight:700; }")
        layout.addWidget(lbl)
        return card, layout

    def _metric_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "QLabel { background:#161a22; color:#ffffff; border:1px solid #30384b; "
            "border-radius:8px; padding:8px 12px; font-size:13px; font-weight:600; }"
        )
        return lbl

    def _build_project_card(self):
        card, layout = self._card_frame("Project")

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnMinimumWidth(0, 95)

        labels = [
            ("Aspect Ratio", ["16:9", "9:16", "1:1"]),
            ("Scene Duration", ["8 sec", "6 sec", "10 sec"]),
            ("Prompt Style", ["Balanced", "Cinematic", "UGC"]),
            ("Output Goal", ["Veo Clips", "Shot Package", "Storyboard"]),
        ]

        self.combo_aspect_ratio = QComboBox()
        self.combo_scene_duration = QComboBox()
        self.combo_prompt_style = QComboBox()
        self.combo_output_goal = QComboBox()
        combos = [
            self.combo_aspect_ratio,
            self.combo_scene_duration,
            self.combo_prompt_style,
            self.combo_output_goal,
        ]
        for combo, (_, items) in zip(combos, labels):
            combo.addItems(items)
            combo.setStyleSheet(
                "QComboBox { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
                "border-radius:4px; padding:5px 8px; font-size:13px; }"
                "QComboBox QAbstractItemView { background:#ffffff; color:#111111; "
                "selection-background-color:#e24a22; selection-color:#ffffff; }"
            )

        for row, ((text, _), combo) in enumerate(zip(labels, combos)):
            lbl = QLabel(text)
            lbl.setStyleSheet("QLabel { color:#cfd4dc; font-size:13px; }")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(combo, row, 1)

        layout.addLayout(grid)
        return card

    def _build_source_script_card(self):
        card, layout = self._card_frame("Source Script")

        hint = QLabel("Paste or load the source script for this project.")
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel { color:#c6ccd6; font-size:12px; }")
        layout.addWidget(hint)

        self.text_source_script = QTextEdit()
        self.text_source_script.setPlaceholderText("Paste or load a source script here...")
        self.text_source_script.setStyleSheet(
            "QTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
            "border-radius:6px; padding:10px; font-size:13px; selection-background-color:#e24a22; selection-color:#ffffff; }"
        )
        self.text_source_script.setMinimumHeight(220)
        self.text_source_script.textChanged.connect(self._update_shell_status)
        layout.addWidget(self.text_source_script, stretch=1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_paste_script = QPushButton("Paste")
        self.btn_load_txt_script = QPushButton("Load TXT")
        self.btn_clear_script = QPushButton("Clear Script")
        for btn in (self.btn_paste_script, self.btn_load_txt_script, self.btn_clear_script):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(30)
            btn.setStyleSheet(
                "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
                "QPushButton:hover { background:#f05a34; }"
            )
            row.addWidget(btn)
        self.btn_paste_script.clicked.connect(lambda: self._coming_soon("Paste"))
        self.btn_load_txt_script.clicked.connect(lambda: self._coming_soon("Load TXT"))
        self.btn_clear_script.clicked.connect(self.text_source_script.clear)
        row.addStretch()
        layout.addLayout(row)
        return card

    def _build_scene_workspace_card(self):
        card, layout = self._card_frame("Scene Workflow")

        hint = QLabel("Build scenes from plain scripts or Extract Structure output.")
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel { color:#c6ccd6; font-size:12px; }")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.btn_add_scene = self._small_action_button("Add Scene")
        self.btn_duplicate_scene = self._small_action_button("Duplicate")
        self.btn_remove_scene = self._small_action_button("Remove")
        self.btn_move_scene_up = self._small_action_button("Move Up")
        self.btn_move_scene_down = self._small_action_button("Move Down")
        toolbar.addWidget(self.btn_add_scene)
        toolbar.addWidget(self.btn_duplicate_scene)
        toolbar.addWidget(self.btn_remove_scene)
        toolbar.addWidget(self.btn_move_scene_up)
        toolbar.addWidget(self.btn_move_scene_down)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.btn_add_scene.clicked.connect(self._add_scene_row)
        self.btn_duplicate_scene.clicked.connect(self._duplicate_selected_scene)
        self.btn_remove_scene.clicked.connect(self._remove_selected_scene)
        self.btn_move_scene_up.clicked.connect(lambda: self._move_selected_scene(-1))
        self.btn_move_scene_down.clicked.connect(lambda: self._move_selected_scene(1))

        self.table_scenes = QTableWidget(0, 7)
        self.table_scenes.setHorizontalHeaderLabels(
            ["Scene", "Scene Title", "Duration", "Visual Goal", "Voiceover", "Status", "Clip"]
        )
        self.table_scenes.verticalHeader().setVisible(False)
        self.table_scenes.setAlternatingRowColors(False)
        self.table_scenes.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_scenes.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_scenes.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table_scenes.setStyleSheet(
            "QTableWidget { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; "
            "gridline-color:#e6e6e6; font-size:13px; }"
            "QTableWidget::item { padding:6px; }"
            "QTableWidget::item:selected { background:#f5d7d0; color:#111111; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:none; border-right:1px solid #d7d7d7; "
            "border-bottom:1px solid #d7d7d7; padding:8px 6px; font-weight:700; }"
        )
        self.table_scenes.setMinimumHeight(340)
        self.table_scenes.horizontalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        self.table_scenes.verticalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        header = self.table_scenes.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_scenes.setColumnWidth(0, 72)
        self.table_scenes.setColumnWidth(1, 190)
        self.table_scenes.setColumnWidth(2, 88)
        self.table_scenes.setColumnWidth(3, 230)
        self.table_scenes.setColumnWidth(4, 260)
        self.table_scenes.setColumnWidth(5, 92)
        self.table_scenes.setColumnWidth(6, 145)
        self.table_scenes.itemSelectionChanged.connect(self._handle_scene_selection_changed)
        self.table_scenes.itemChanged.connect(self._handle_scene_item_changed)

        table_frame = QFrame()
        table_frame.setObjectName("ttvSceneTableFrame")
        table_frame.setStyleSheet(
            "QFrame#ttvSceneTableFrame { background:#181b1f; border:1px solid #31363f; border-radius:8px; }"
        )
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self.table_scenes)

        self.lbl_selected_scene_title = QLabel("Selected scene: None")
        self.lbl_selected_scene_title.setStyleSheet("QLabel { color:#ffffff; font-size:13px; font-weight:600; }")
        self.lbl_selected_scene_title.hide()

        self.combo_shot_type = QComboBox()
        self.combo_shot_type.addItems(["Talking Head", "B-Roll", "Montage", "Product Shot", "UGC"])
        self.combo_shot_type.setStyleSheet(
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
            "border-radius:4px; padding:5px 8px; font-size:12px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; selection-background-color:#e24a22; selection-color:#ffffff; }"
        )
        self.combo_shot_type.setMinimumWidth(180)
        self.combo_shot_type.hide()

        self.text_scene_notes = QPlainTextEdit()
        self.text_scene_notes.setPlaceholderText("Local scene notes for this selected row...")
        self.text_scene_notes.setStyleSheet(
            "QPlainTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; padding:8px; font-size:12px; }"
        )
        self.text_scene_notes.setMinimumHeight(110)
        self.text_scene_notes.hide()

        layout.addWidget(table_frame, stretch=1)

        self._add_scene_row(
            title="Hook / Opening",
            duration="8 sec",
            visual_goal="Strong opening visual",
            voiceover="Opening hook line goes here",
            status="Draft",
            clip="Not Generated",
            refresh=False,
        )
        self._add_scene_row(
            title="Main Point 1",
            duration="8 sec",
            visual_goal="Explain the first key idea",
            voiceover="Main scene narration",
            status="Draft",
            clip="Not Generated",
            refresh=False,
        )
        self._add_scene_row(
            title="CTA / Closing",
            duration="6 sec",
            visual_goal="Closing visual or CTA shot",
            voiceover="Closing line or CTA",
            status="Draft",
            clip="Not Generated",
            refresh=False,
        )
        self.table_scenes.selectRow(0)
        self._refresh_scene_stats()
        return card

    def _small_action_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(28)
        btn.setStyleSheet(
            "QPushButton { background:#242424; color:#ffffff; border:1px solid #3a3a3a; border-radius:4px; padding:5px 10px; font-weight:600; }"
            "QPushButton:hover { background:#2f2f2f; border-color:#5a5a5a; }"
        )
        return btn

    def _build_workspace_card(self):
        card, layout = self._card_frame("Workspace")

        hint = QLabel("Open scene details, prompt editor, and project preview in separate popups.")
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel { color:#c6ccd6; font-size:12px; }")
        layout.addWidget(hint)

        self.lbl_prompt_scene = QLabel("Selected prompt scene: None")
        self.lbl_prompt_scene.setStyleSheet("QLabel { color:#ffffff; font-size:13px; font-weight:600; }")
        layout.addWidget(self.lbl_prompt_scene)

        top = QHBoxLayout()
        top.setSpacing(8)

        lbl_prompt_format = QLabel("Format")
        lbl_prompt_format.setStyleSheet("QLabel { color:#cfd4dc; font-size:12px; }")
        self.combo_prompt_format = QComboBox()
        self.combo_prompt_format.addItems(["Scene Prompt", "Detailed Prompt", "Veo Prompt"])
        self.combo_prompt_format.setStyleSheet(
            "QComboBox { background:#ffffff; color:#111111; border:1px solid #d4d7dc; "
            "border-radius:4px; padding:5px 8px; font-size:12px; }"
            "QComboBox QAbstractItemView { background:#ffffff; color:#111111; selection-background-color:#e24a22; selection-color:#ffffff; }"
        )
        self.combo_prompt_format.setMinimumWidth(160)
        self.combo_prompt_format.currentTextChanged.connect(self._handle_prompt_format_changed)
        top.addWidget(lbl_prompt_format)
        top.addWidget(self.combo_prompt_format)
        top.addStretch()
        layout.addLayout(top)

        row = QVBoxLayout()
        row.setSpacing(8)
        btn_scene_details = self._small_action_button("Scene Details")
        btn_prompt_editor = self._small_action_button("Prompt Editor")
        btn_preview_popup = self._small_action_button("Preview")
        btn_scene_details.clicked.connect(self._open_scene_details_dialog)
        btn_prompt_editor.clicked.connect(self._open_prompt_editor_dialog)
        btn_preview_popup.clicked.connect(self._open_preview_dialog)
        row.addWidget(btn_scene_details)
        row.addWidget(btn_prompt_editor)
        row.addWidget(btn_preview_popup)
        layout.addLayout(row)
        return card

    def _build_generation_card(self):
        card, layout = self._card_frame("Generation")
        card.setMinimumHeight(135)

        hint = QLabel("Manual controls now. Gemini prompt generation and Veo backend come next.")
        hint.setWordWrap(True)
        hint.setStyleSheet("QLabel { color:#c6ccd6; font-size:12px; }")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_generate_one = QPushButton("Generate One")
        self.btn_generate_all = QPushButton("Generate All")
        self.btn_browser_fallback = QPushButton("Browser Fallback")
        self.btn_clip_manager = QPushButton("Clip Manager")
        self.btn_export_package = QPushButton("Export Package")
        for btn in (
            self.btn_generate_one,
            self.btn_generate_all,
            self.btn_browser_fallback,
            self.btn_clip_manager,
            self.btn_export_package,
        ):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(30)
            btn.setStyleSheet(
                "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:6px 12px; font-weight:700; }"
                "QPushButton:hover { background:#f05a34; }"
            )
            row.addWidget(btn)
        self.btn_generate_one.clicked.connect(self._generate_single_scene)
        self.btn_generate_all.clicked.connect(self._generate_all_scenes)
        self.btn_browser_fallback.clicked.connect(self._open_browser_fallback_dialog)
        self.btn_clip_manager.clicked.connect(self._open_clip_manager_dialog)
        self.btn_export_package.clicked.connect(self._export_project_package)
        layout.addLayout(row)
        return card

    def _coming_soon(self, label: str):
        QMessageBox.information(self, label, f"{label} will be implemented in the next step.")

    def _default_veo_settings(self) -> dict:
        return {
            "model": "veo-3.1-generate-preview",
            "duration": "8 sec",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "variants": "1",
            "quality": "Balanced",
            "native_audio": True,
            "use_scene_prompt": True,
            "use_voiceover_guidance": True,
            "negative_prompt": "",
        }

    def _project_veo_settings(self) -> dict:
        settings = dict(self._default_veo_settings())
        settings.update(self._veo_settings or {})
        settings["aspect_ratio"] = self.combo_aspect_ratio.currentText() or settings["aspect_ratio"]
        settings["duration"] = self.combo_scene_duration.currentText() or settings["duration"]
        return settings

    def _create_veo_settings_dialog(self) -> tuple[QDialog, dict]:
        settings = self._project_veo_settings()

        dialog = QDialog(self)
        dialog.setWindowTitle("Veo Settings")
        dialog.resize(720, 520)
        dialog.setStyleSheet(
            "QDialog { background:#181b1f; color:#ffffff; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QComboBox, QPlainTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; padding:8px; }"
            "QCheckBox { color:#ffffff; font-size:13px; }"
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel("Configure Gemini Veo generation defaults for this project.")
        header.setWordWrap(True)
        header.setStyleSheet("QLabel { color:#cfd4dc; font-size:12px; }")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        def _label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("QLabel { color:#ffffff; font-size:13px; font-weight:600; }")
            return lbl

        combo_model = QComboBox()
        combo_model.addItems(
            [
                "veo-3.1-generate-preview",
                "veo-3.1-fast-generate-preview",
                "veo-3.1-lite-generate-preview",
                "veo-3.0-generate-001",
                "veo-3.0-fast-generate-001",
            ]
        )
        combo_model.setCurrentText(settings["model"])

        combo_duration = QComboBox()
        combo_duration.addItems(["5 sec", "6 sec", "8 sec", "10 sec"])
        combo_duration.setCurrentText(settings["duration"])

        combo_aspect = QComboBox()
        combo_aspect.addItems(["16:9", "9:16", "1:1"])
        combo_aspect.setCurrentText(settings["aspect_ratio"])

        combo_resolution = QComboBox()
        combo_resolution.addItems(["720p", "1080p"])
        combo_resolution.setCurrentText(settings["resolution"])

        combo_variants = QComboBox()
        combo_variants.addItems(["1", "2", "4"])
        combo_variants.setCurrentText(settings["variants"])

        combo_quality = QComboBox()
        combo_quality.addItems(["Balanced", "High"])
        combo_quality.setCurrentText(settings["quality"])

        grid.addWidget(_label("Model"), 0, 0)
        grid.addWidget(combo_model, 0, 1)
        grid.addWidget(_label("Clip Duration"), 0, 2)
        grid.addWidget(combo_duration, 0, 3)

        grid.addWidget(_label("Aspect Ratio"), 1, 0)
        grid.addWidget(combo_aspect, 1, 1)
        grid.addWidget(_label("Resolution"), 1, 2)
        grid.addWidget(combo_resolution, 1, 3)

        grid.addWidget(_label("Variants"), 2, 0)
        grid.addWidget(combo_variants, 2, 1)
        grid.addWidget(_label("Quality"), 2, 2)
        grid.addWidget(combo_quality, 2, 3)
        layout.addLayout(grid)

        check_native_audio = QCheckBox("Use native audio when available")
        check_native_audio.setChecked(bool(settings["native_audio"]))
        check_scene_prompt = QCheckBox("Use scene prompt draft")
        check_scene_prompt.setChecked(bool(settings["use_scene_prompt"]))
        check_voiceover = QCheckBox("Use voiceover guidance")
        check_voiceover.setChecked(bool(settings["use_voiceover_guidance"]))
        layout.addWidget(check_native_audio)
        layout.addWidget(check_scene_prompt)
        layout.addWidget(check_voiceover)

        negative_label = QLabel("Negative Prompt")
        negative_label.setStyleSheet("QLabel { color:#ffffff; font-size:13px; font-weight:600; }")
        layout.addWidget(negative_label)

        text_negative_prompt = QPlainTextEdit()
        text_negative_prompt.setPlaceholderText(
            "Optional. Describe what Veo should avoid: low detail, distorted hands, text overlays, flicker, bad anatomy..."
        )
        text_negative_prompt.setPlainText(str(settings.get("negative_prompt", "")))
        text_negative_prompt.setMinimumHeight(140)
        layout.addWidget(text_negative_prompt, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        btn_reset = QPushButton("Reset Defaults")
        btn_save = QPushButton("Save")
        btn_close = QPushButton("Close")
        button_row.addWidget(btn_reset)
        button_row.addWidget(btn_save)
        button_row.addWidget(btn_close)
        layout.addLayout(button_row)

        controls = {
            "model": combo_model,
            "duration": combo_duration,
            "aspect_ratio": combo_aspect,
            "resolution": combo_resolution,
            "variants": combo_variants,
            "quality": combo_quality,
            "native_audio": check_native_audio,
            "use_scene_prompt": check_scene_prompt,
            "use_voiceover_guidance": check_voiceover,
            "negative_prompt": text_negative_prompt,
            "reset": btn_reset,
            "save": btn_save,
            "close": btn_close,
        }
        return dialog, controls

    def _open_veo_settings_dialog(self):
        dialog, controls = self._create_veo_settings_dialog()

        def _apply_defaults():
            defaults = self._default_veo_settings()
            controls["model"].setCurrentText(defaults["model"])
            controls["duration"].setCurrentText(defaults["duration"])
            controls["aspect_ratio"].setCurrentText(defaults["aspect_ratio"])
            controls["resolution"].setCurrentText(defaults["resolution"])
            controls["variants"].setCurrentText(defaults["variants"])
            controls["quality"].setCurrentText(defaults["quality"])
            controls["native_audio"].setChecked(bool(defaults["native_audio"]))
            controls["use_scene_prompt"].setChecked(bool(defaults["use_scene_prompt"]))
            controls["use_voiceover_guidance"].setChecked(bool(defaults["use_voiceover_guidance"]))
            controls["negative_prompt"].setPlainText(str(defaults["negative_prompt"]))

        def _save_settings():
            self._veo_settings = {
                "model": controls["model"].currentText(),
                "duration": controls["duration"].currentText(),
                "aspect_ratio": controls["aspect_ratio"].currentText(),
                "resolution": controls["resolution"].currentText(),
                "variants": controls["variants"].currentText(),
                "quality": controls["quality"].currentText(),
                "native_audio": controls["native_audio"].isChecked(),
                "use_scene_prompt": controls["use_scene_prompt"].isChecked(),
                "use_voiceover_guidance": controls["use_voiceover_guidance"].isChecked(),
                "negative_prompt": controls["negative_prompt"].toPlainText().strip(),
            }
            if self.combo_aspect_ratio.findText(self._veo_settings["aspect_ratio"]) >= 0:
                self.combo_aspect_ratio.setCurrentText(self._veo_settings["aspect_ratio"])
            if self.combo_scene_duration.findText(self._veo_settings["duration"]) >= 0:
                self.combo_scene_duration.setCurrentText(self._veo_settings["duration"])
            self._set_project_status(
                f"Veo settings saved ({self._veo_settings['model']}, {self._veo_settings['duration']}, {self._veo_settings['aspect_ratio']})"
            )
            dialog.accept()

        controls["reset"].clicked.connect(_apply_defaults)
        controls["save"].clicked.connect(_save_settings)
        controls["close"].clicked.connect(dialog.reject)
        dialog.exec()

    def _set_project_status(self, text: str):
        self._project_status = str(text or "Shell ready").strip() or "Shell ready"
        self._update_shell_status()

    def _set_generate_prompts_busy(self, busy: bool):
        self._prompt_generation_active = bool(busy)
        self._refresh_interaction_state()

    def _set_generate_one_busy(self, busy: bool):
        self._single_generation_active = bool(busy)
        self._refresh_interaction_state()

    def _set_generate_all_busy(self, busy: bool):
        self._batch_generation_active = bool(busy)
        self._refresh_interaction_state()

    def _is_project_busy(self) -> bool:
        return bool(
            self._prompt_generation_active
            or self._single_generation_active
            or self._batch_generation_active
            or self._prompt_worker is not None
            or self._scene_worker is not None
        )

    def _refresh_interaction_state(self):
        busy = self._is_project_busy()

        if hasattr(self, "input_project_name"):
            self.input_project_name.setReadOnly(busy)
        if hasattr(self, "text_source_script"):
            self.text_source_script.setReadOnly(busy)
        for name in (
            "combo_aspect_ratio",
            "combo_scene_duration",
            "combo_prompt_style",
            "combo_output_goal",
            "combo_prompt_format",
            "btn_load_script",
            "btn_paste_script",
            "btn_load_txt_script",
            "btn_clear_script",
            "btn_create_scene_plan",
            "btn_veo_settings",
            "btn_render_project",
            "btn_add_scene",
            "btn_duplicate_scene",
            "btn_remove_scene",
            "btn_move_scene_up",
            "btn_move_scene_down",
            "btn_browser_fallback",
            "btn_export_package",
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setEnabled(not busy)

        if hasattr(self, "table_scenes"):
            self.table_scenes.setEditTriggers(
                QAbstractItemView.EditTrigger.NoEditTriggers
                if busy
                else (
                    QAbstractItemView.EditTrigger.DoubleClicked
                    | QAbstractItemView.EditTrigger.SelectedClicked
                    | QAbstractItemView.EditTrigger.EditKeyPressed
                )
            )

        if hasattr(self, "btn_generate_prompts"):
            self.btn_generate_prompts.setEnabled(not busy)
            self.btn_generate_prompts.setText("Generating..." if self._prompt_generation_active else "Generate Prompts")
        if hasattr(self, "btn_generate_one"):
            self.btn_generate_one.setEnabled(not busy)
            self.btn_generate_one.setText("Generating..." if self._single_generation_active else "Generate One")
        if hasattr(self, "btn_generate_all"):
            self.btn_generate_all.setEnabled(not busy)
            self.btn_generate_all.setText("Generating All..." if self._batch_generation_active else "Generate All")

    def _guard_busy_action(self, label: str) -> bool:
        if not self._is_project_busy():
            return False
        QMessageBox.information(
            self,
            label,
            "Please wait for the current prompt or scene generation job to finish, or use Clear to stop and reset the project state first.",
        )
        return True

    def _request_stop_prompt_worker(self):
        worker = self._prompt_worker
        if worker is None:
            return
        try:
            worker.request_stop()
        except Exception:
            pass

    def _cleanup_prompt_worker(self):
        worker = self._prompt_worker
        if worker is None:
            return
        self._prompt_worker = None
        try:
            worker.quit()
            worker.wait(1500)
        except Exception:
            pass
        try:
            worker.deleteLater()
        except Exception:
            pass

    def _request_stop_scene_worker(self):
        worker = self._scene_worker
        if worker is None:
            return
        try:
            worker.request_stop()
        except Exception:
            pass

    def _cleanup_scene_worker(self):
        worker = self._scene_worker
        if worker is None:
            return
        self._scene_worker = None
        try:
            worker.quit()
            worker.wait(1500)
        except Exception:
            pass
        try:
            worker.deleteLater()
        except Exception:
            pass

    def _scene_row_payload(self, row: int) -> dict:
        values = []
        for col in range(self.table_scenes.columnCount()):
            item = self.table_scenes.item(row, col)
            values.append(item.text() if item else "")
        return {"values": values, "meta": self._scene_row_meta(row)}

    def _scene_row_meta(self, row: int) -> dict:
        item = self.table_scenes.item(row, 1)
        if item is None:
            return {}
        meta = item.data(Qt.ItemDataRole.UserRole)
        return dict(meta) if isinstance(meta, dict) else {}

    def _set_scene_row_meta(self, row: int, meta: dict | None):
        item = self.table_scenes.item(row, 1)
        if item is None:
            item = QTableWidgetItem()
            self.table_scenes.setItem(row, 1, item)
        item.setData(Qt.ItemDataRole.UserRole, dict(meta or {}))

    def _set_scene_row_payload(self, row: int, payload):
        if isinstance(payload, dict):
            values = list(payload.get("values", []))
            meta = dict(payload.get("meta", {}) or {})
        else:
            values = list(payload or [])
            meta = {}
        while len(values) < self.table_scenes.columnCount():
            values.append("")
        self.table_scenes.blockSignals(True)
        for col, value in enumerate(values[: self.table_scenes.columnCount()]):
            item = self.table_scenes.item(row, col)
            if item is None:
                item = QTableWidgetItem()
                self.table_scenes.setItem(row, col, item)
            item.setText(str(value))
            if col == 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_scene_row_meta(row, meta)
        self.table_scenes.blockSignals(False)

    def _reindex_scene_numbers(self):
        self.table_scenes.blockSignals(True)
        for row in range(self.table_scenes.rowCount()):
            item = self.table_scenes.item(row, 0)
            if item is None:
                item = QTableWidgetItem()
                self.table_scenes.setItem(row, 0, item)
            item.setText(f"S{row + 1:02d}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_scenes.blockSignals(False)

    def _refresh_scene_stats(self):
        rows = self.table_scenes.rowCount()
        if hasattr(self, "lbl_scene_count"):
            self.lbl_scene_count.setText(f"Scenes: {rows}")
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        if hasattr(self, "lbl_selected_scene"):
            self.lbl_selected_scene.setText(f"Selected: {len(selected)}")
        self._update_shell_status()

    def _add_scene_row(
        self,
        *,
        title: str = "New Scene",
        duration: str = "8 sec",
        visual_goal: str = "Describe visual goal",
        voiceover: str = "",
        status: str = "Draft",
        clip: str = "Not Generated",
        refresh: bool = True,
    ):
        row = self.table_scenes.rowCount()
        self.table_scenes.insertRow(row)
        self._set_scene_row_payload(
            row,
            ["", title, duration, visual_goal, voiceover, status, clip],
        )
        self._reindex_scene_numbers()
        if refresh:
            self._refresh_scene_stats()

    def _duplicate_selected_scene(self):
        if self._guard_busy_action("Duplicate"):
            return
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        if not selected:
            QMessageBox.information(self, "Duplicate", "Please select a scene row first.")
            return
        row = selected[0].row()
        payload = self._scene_row_payload(row)
        new_row = row + 1
        self.table_scenes.insertRow(new_row)
        self._set_scene_row_payload(new_row, payload)
        title_item = self.table_scenes.item(new_row, 1)
        if title_item:
            title_item.setText(f"{title_item.text()} Copy")
        self._reindex_scene_numbers()
        self.table_scenes.selectRow(new_row)
        self._refresh_scene_stats()

    def _remove_selected_scene(self):
        if self._guard_busy_action("Remove"):
            return
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        if not selected:
            QMessageBox.information(self, "Remove", "Please select a scene row first.")
            return
        self.table_scenes.removeRow(selected[0].row())
        self._reindex_scene_numbers()
        if self.table_scenes.rowCount() > 0:
            self.table_scenes.selectRow(min(selected[0].row(), self.table_scenes.rowCount() - 1))
        else:
            self.lbl_selected_scene_title.setText("Selected scene: None")
            self.text_scene_notes.clear()
        self._refresh_scene_stats()

    def _move_selected_scene(self, direction: int):
        if self._guard_busy_action("Move Scene"):
            return
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        if not selected:
            QMessageBox.information(self, "Move Scene", "Please select a scene row first.")
            return
        row = selected[0].row()
        target = row + int(direction)
        if target < 0 or target >= self.table_scenes.rowCount():
            return
        current_payload = self._scene_row_payload(row)
        target_payload = self._scene_row_payload(target)
        self._set_scene_row_payload(row, target_payload)
        self._set_scene_row_payload(target, current_payload)
        self._reindex_scene_numbers()
        self.table_scenes.selectRow(target)
        self._refresh_scene_stats()

    def _handle_scene_selection_changed(self):
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        if not selected:
            if hasattr(self, "lbl_selected_scene_title"):
                self.lbl_selected_scene_title.setText("Selected scene: None")
            if hasattr(self, "lbl_prompt_scene"):
                self.lbl_prompt_scene.setText("Selected prompt scene: None")
            if hasattr(self, "lbl_selected_scene"):
                self.lbl_selected_scene.setText("Selected: 0")
            return
        row = selected[0].row()
        scene_no = self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else f"S{row + 1:02d}"
        title = self.table_scenes.item(row, 1).text() if self.table_scenes.item(row, 1) else "Untitled Scene"
        visual_goal = self.table_scenes.item(row, 3).text() if self.table_scenes.item(row, 3) else ""
        voiceover = self.table_scenes.item(row, 4).text() if self.table_scenes.item(row, 4) else ""
        if hasattr(self, "lbl_selected_scene_title"):
            self.lbl_selected_scene_title.setText(f"Selected scene: {scene_no} - {title}")
        if hasattr(self, "text_scene_notes"):
            self.text_scene_notes.blockSignals(True)
            self.text_scene_notes.setPlainText(
                f"Visual Goal:\n{visual_goal}\n\nVoiceover Draft:\n{voiceover}"
            )
            self.text_scene_notes.blockSignals(False)
        if hasattr(self, "lbl_prompt_scene"):
            self.lbl_prompt_scene.setText(f"Selected prompt scene: {scene_no} - {title}")
        if hasattr(self, "lbl_selected_scene"):
            self.lbl_selected_scene.setText(f"Selected: {len(selected)}")

    def _handle_scene_item_changed(self, item: QTableWidgetItem):
        if item is None:
            return
        self._refresh_scene_stats()
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        if selected and selected[0].row() == item.row():
            if item.column() in (1, 2, 3, 4):
                meta = self._scene_row_meta(item.row())
                if "prompt_draft" not in meta:
                    self._load_prompt_for_selected_scene(force_template=True)
            self._handle_scene_selection_changed()

    def _update_shell_status(self):
        script_text = self.text_source_script.toPlainText()
        word_count = len([part for part in script_text.split() if part.strip()])
        line_count = len([line for line in script_text.splitlines() if line.strip()])
        scene_count = self.table_scenes.rowCount() if hasattr(self, "table_scenes") else 0
        if hasattr(self, "lbl_project_status"):
            self.lbl_project_status.setText(
                f"Project Status: {self._project_status} | {scene_count:,} scenes | {line_count:,} lines | {word_count:,} words"
            )

    def _serialize_scene_rows(self) -> list[dict]:
        rows = []
        for row in range(self.table_scenes.rowCount()):
            meta = self._scene_row_meta(row)
            rows.append(
                {
                    "scene_no": self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else f"S{row + 1:02d}",
                    "title": self.table_scenes.item(row, 1).text() if self.table_scenes.item(row, 1) else "",
                    "duration": self.table_scenes.item(row, 2).text() if self.table_scenes.item(row, 2) else "",
                    "visual_goal": self.table_scenes.item(row, 3).text() if self.table_scenes.item(row, 3) else "",
                    "voiceover": self.table_scenes.item(row, 4).text() if self.table_scenes.item(row, 4) else "",
                    "status": self.table_scenes.item(row, 5).text() if self.table_scenes.item(row, 5) else "",
                    "clip": self.table_scenes.item(row, 6).text() if self.table_scenes.item(row, 6) else "",
                    "shot_type": str(meta.get("shot_type", self.combo_shot_type.currentText() or "Talking Head")),
                    "scene_notes": str(meta.get("scene_notes", "")).strip(),
                }
            )
        return rows

    def _find_scene_row_by_no(self, scene_no: str) -> int | None:
        target = str(scene_no or "").strip()
        if not target:
            return None
        for row in range(self.table_scenes.rowCount()):
            item = self.table_scenes.item(row, 0)
            if item and item.text().strip() == target:
                return row
        return None

    def _scene_numbers_for_batch(self) -> list[str]:
        scene_nos = []
        for row in range(self.table_scenes.rowCount()):
            item = self.table_scenes.item(row, 0)
            scene_no = item.text().strip() if item else ""
            if scene_no:
                scene_nos.append(scene_no)
        return scene_nos

    def _serialize_clip_rows(self) -> list[dict]:
        rows = []
        for row in range(self.table_scenes.rowCount()):
            meta = self._scene_row_meta(row)
            rows.append(
                {
                    "scene_no": self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else f"S{row + 1:02d}",
                    "title": self.table_scenes.item(row, 1).text() if self.table_scenes.item(row, 1) else "",
                    "status": self.table_scenes.item(row, 5).text() if self.table_scenes.item(row, 5) else "",
                    "clip": self.table_scenes.item(row, 6).text() if self.table_scenes.item(row, 6) else "",
                    "clip_path": str(meta.get("clip_path", "")).strip(),
                    "clip_file_name": str(meta.get("clip_file_name", "")).strip(),
                    "veo_model": str(meta.get("veo_model", "")).strip(),
                    "veo_operation_name": str(meta.get("veo_operation_name", "")).strip(),
                    "veo_video_uri": str(meta.get("veo_video_uri", "")).strip(),
                }
            )
        return rows

    def _serialize_export_scenes(self) -> list[dict]:
        scenes = self._serialize_scene_rows()
        for scene in scenes:
            row = self._find_scene_row_by_no(scene.get("scene_no", ""))
            if row is None:
                continue
            meta = self._scene_row_meta(row)
            scene["prompt_draft"] = str(meta.get("prompt_draft", "")).strip()
            scene["clip_path"] = str(meta.get("clip_path", "")).strip()
            scene["clip_file_name"] = str(meta.get("clip_file_name", "")).strip()
            scene["veo_model"] = str(meta.get("veo_model", "")).strip()
            scene["veo_operation_name"] = str(meta.get("veo_operation_name", "")).strip()
            scene["veo_video_uri"] = str(meta.get("veo_video_uri", "")).strip()
        return scenes

    def _project_prompt_settings(self) -> dict:
        return {
            "prompt_style": self.combo_prompt_style.currentText(),
            "aspect_ratio": self.combo_aspect_ratio.currentText(),
            "output_goal": self.combo_output_goal.currentText(),
        }

    def _export_project_package(self):
        if self._guard_busy_action("Export Package"):
            return
        if self.table_scenes.rowCount() == 0 and not self.text_source_script.toPlainText().strip():
            QMessageBox.information(self, "Export Package", "There is no project data to export yet.")
            return

        project_name = self.input_project_name.text().strip() or "My Veo Project"
        target_root = QFileDialog.getExistingDirectory(
            self,
            "Choose Export Folder",
            str(Path(__file__).resolve().parent.parent / "exports"),
        )
        if not target_root:
            return

        project_data = {
            "project_name": project_name,
            "source_script": self.text_source_script.toPlainText(),
            "scenes": self._serialize_export_scenes(),
            "veo_settings": self._project_veo_settings(),
            "prompt_format": self.combo_prompt_format.currentText(),
            "project_prompt_settings": self._project_prompt_settings(),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            result = export_project_package(project_data, target_root)
        except Exception as exc:
            QMessageBox.warning(self, "Export Package", f"Failed to export project package.\n\n{exc}")
            return

        self._set_project_status(
            f"Project package exported ({result.get('scene_count', 0)} scenes, {result.get('copied_clip_count', 0)} clips copied)"
        )
        if self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(str(result.get("package_dir", "")), 7000)
        QMessageBox.information(
            self,
            "Export Package",
            "\n".join(
                [
                    "Project package exported successfully.",
                    "",
                    f"Folder: {result.get('package_dir', '')}",
                    f"Scenes: {result.get('scene_count', 0)}",
                    f"Copied clips: {result.get('copied_clip_count', 0)}",
                ]
            ).strip(),
        )

    def _clear_shell(self):
        self._prompt_run_token += 1
        self._scene_run_token += 1
        self._request_stop_prompt_worker()
        self._request_stop_scene_worker()
        self._cleanup_prompt_worker()
        self._cleanup_scene_worker()
        self.text_source_script.clear()
        self.table_scenes.setRowCount(0)
        self.text_scene_notes.clear()
        self.lbl_selected_scene_title.setText("Selected scene: None")
        self.lbl_prompt_scene.setText("Selected prompt scene: None")
        self.lbl_scene_count.setText("Scenes: 0")
        self.lbl_selected_scene.setText("Selected: 0")
        self._project_status = "Shell ready"
        self._set_generate_prompts_busy(False)
        self._set_generate_one_busy(False)
        self._batch_scene_queue = []
        self._batch_results = []
        self._batch_failures = []
        self._set_generate_all_busy(False)
        self._update_shell_status()
        self._refresh_interaction_state()

    def _populate_scene_plan(self, scenes: list[dict[str, str]]):
        self.table_scenes.blockSignals(True)
        self.table_scenes.setRowCount(0)
        for scene in scenes:
            self._add_scene_row(
                title=str(scene.get("title", "New Scene")),
                duration=str(scene.get("duration", self.combo_scene_duration.currentText() or "8 sec")),
                visual_goal=str(scene.get("visual_goal", "Describe visual goal")),
                voiceover=str(scene.get("voiceover", "")),
                status=str(scene.get("status", "Draft")),
                clip=str(scene.get("clip", "Not Generated")),
                refresh=False,
            )
        self.table_scenes.blockSignals(False)
        if self.table_scenes.rowCount() > 0:
            self.table_scenes.selectRow(0)
            self._handle_scene_selection_changed()
        else:
            self.lbl_selected_scene_title.setText("Selected scene: None")
            self.lbl_prompt_scene.setText("Selected prompt scene: None")
            self.text_scene_notes.clear()
        self._refresh_scene_stats()

    def _create_scene_plan_from_source(self):
        if self._guard_busy_action("Create Scene Plan"):
            return
        source_text = self.text_source_script.toPlainText().strip()
        if not source_text:
            QMessageBox.information(self, "Create Scene Plan", "Please paste or load a source script first.")
            return
        scenes = create_scene_plan(
            source_text,
            default_duration=self.combo_scene_duration.currentText() or "8 sec",
        )
        if not scenes:
            QMessageBox.warning(self, "Create Scene Plan", "No usable scenes were generated from the current source script.")
            return
        self._populate_scene_plan(scenes)
        self._set_project_status(f"Scene plan generated ({len(scenes)} scenes)")

    def receive_payload(self, text, hint_text=""):
        self.text_source_script.setPlainText(str(text or "").strip())
        self._set_project_status("Source script loaded")
        if hint_text and self.main_window and self.main_window.statusBar():
            self.main_window.statusBar().showMessage(str(hint_text), 4000)

    def receive_script_payload(self, text, hint_text=""):
        self.receive_payload(text, hint_text=hint_text)

    def _build_prompt_template_for_row(self, row: int) -> str:
        scene = self._serialize_scene_rows()[row]
        return build_scene_prompt_template(
            scene,
            self._project_prompt_settings(),
            format_name=self.combo_prompt_format.currentText() or "Scene Prompt",
        )

    def _load_prompt_for_selected_scene(self, force_template: bool = False):
        if not hasattr(self, "lbl_prompt_scene"):
            return
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        if not selected:
            self.lbl_prompt_scene.setText("Selected prompt scene: None")
            return
        row = selected[0].row()
        scene_no = self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else f"S{row + 1:02d}"
        title = self.table_scenes.item(row, 1).text() if self.table_scenes.item(row, 1) else "Untitled Scene"
        self.lbl_prompt_scene.setText(f"Selected prompt scene: {scene_no} - {title}")

    def _selected_scene_row(self):
        selected = self.table_scenes.selectionModel().selectedRows() if self.table_scenes.selectionModel() else []
        return selected[0].row() if selected else None

    def _current_prompt_text_for_row(self, row: int, force_template: bool = False) -> str:
        meta = self._scene_row_meta(row)
        prompt_text = ""
        if not force_template:
            prompt_text = str(meta.get("prompt_draft", "")).strip()
        if not prompt_text:
            prompt_text = self._build_prompt_template_for_row(row)
        return prompt_text

    def _handle_prompt_format_changed(self):
        row = self._selected_scene_row()
        if row is None:
            return
        meta = self._scene_row_meta(row)
        if "prompt_draft" not in meta:
            return
        # Keep existing custom prompt. Only template generation changes for rows without saved drafts.

    def _generate_scene_prompts(self):
        if self._prompt_worker is not None or self._prompt_generation_active:
            QMessageBox.information(self, "Generate Prompts", "Prompt generation is already running.")
            return
        if self._scene_worker is not None or self._single_generation_active or self._batch_generation_active:
            QMessageBox.information(self, "Generate Prompts", "Scene generation is still running. Please wait for it to finish first.")
            return
        source = self.text_source_script.toPlainText().strip()
        if not source:
            QMessageBox.information(self, "Generate Prompts", "Please paste or load a source script first.")
            return
        scenes = self._serialize_scene_rows()
        if not scenes:
            QMessageBox.information(self, "Generate Prompts", "Please create a scene plan first.")
            return

        self._prompt_run_token += 1
        run_token = self._prompt_run_token
        self._set_generate_prompts_busy(True)
        self._set_project_status(f"Generating prompts for {len(scenes)} scenes")

        worker = AIGenerateScenePromptsWorker(
            source,
            scenes,
            self._project_prompt_settings(),
            format_name=self.combo_prompt_format.currentText() or "Scene Prompt",
        )
        self._prompt_worker = worker

        def _status(message: str):
            if run_token != self._prompt_run_token:
                return
            self._set_project_status(message)

        def _error(message: str):
            if run_token != self._prompt_run_token:
                return
            local_prompts = generate_local_scene_prompts(
                scenes,
                self._project_prompt_settings(),
                format_name=self.combo_prompt_format.currentText() or "Scene Prompt",
            )
            self._apply_generated_prompts(local_prompts)
            self._set_generate_prompts_busy(False)
            self._set_project_status("Gemini prompt generation failed. Local prompt templates applied.")
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(str(message), 6000)
            self._cleanup_prompt_worker()

        def _finished(items: list):
            if run_token != self._prompt_run_token:
                return
            self._apply_generated_prompts(items)
            self._set_generate_prompts_busy(False)
            self._set_project_status(f"Generated prompts for {len(items)} scenes")
            self._cleanup_prompt_worker()

        worker.status_signal.connect(_status)
        worker.error_signal.connect(_error)
        worker.finished_signal.connect(_finished)
        worker.start()

    def _apply_generated_prompts(self, items: list[dict]):
        prompt_map = {
            str(item.get("scene", "")).strip(): str(item.get("prompt", "")).strip()
            for item in (items or [])
            if str(item.get("scene", "")).strip() and str(item.get("prompt", "")).strip()
        }
        if not prompt_map:
            return
        for row in range(self.table_scenes.rowCount()):
            scene_no = self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else ""
            prompt_text = prompt_map.get(scene_no)
            if not prompt_text:
                continue
            meta = self._scene_row_meta(row)
            meta["prompt_draft"] = prompt_text
            self._set_scene_row_meta(row, meta)
        selected_row = self._selected_scene_row()
        if selected_row is not None:
            scene_no = self.table_scenes.item(selected_row, 0).text() if self.table_scenes.item(selected_row, 0) else ""
            if scene_no in prompt_map and self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(f"Prompt ready for {scene_no}", 4000)

    def _build_generation_output_root(self) -> str:
        return str(Path(__file__).resolve().parent.parent / "generated" / "text_to_video")

    def _should_abort_batch_for_error(self, message: str) -> bool:
        lower = str(message or "").lower()
        triggers = [
            "http 429",
            "quota",
            "rate limit",
            "billing",
            "permission denied",
            "authentication",
            "api key",
        ]
        return any(token in lower for token in triggers)

    def _mark_scene_row_generating(self, scene_no: str):
        current_row = self._find_scene_row_by_no(scene_no)
        if current_row is None:
            return
        status_item = self.table_scenes.item(current_row, 5) or QTableWidgetItem()
        clip_item = self.table_scenes.item(current_row, 6) or QTableWidgetItem()
        self.table_scenes.setItem(current_row, 5, status_item)
        self.table_scenes.setItem(current_row, 6, clip_item)
        status_item.setText("Generating")
        clip_item.setText("Waiting for Veo...")
        clip_item.setToolTip("")

    def _apply_scene_generation_success(self, scene_no: str, payload: dict):
        current_row = self._find_scene_row_by_no(scene_no)
        if current_row is None:
            return
        status_item = self.table_scenes.item(current_row, 5) or QTableWidgetItem()
        clip_item = self.table_scenes.item(current_row, 6) or QTableWidgetItem()
        self.table_scenes.setItem(current_row, 5, status_item)
        self.table_scenes.setItem(current_row, 6, clip_item)
        status_item.setText("Generated")
        clip_item.setText(str(payload.get("file_name", "")).strip() or "Generated Clip")
        clip_item.setToolTip(str(payload.get("file_path", "")).strip())
        meta = self._scene_row_meta(current_row)
        meta.update(
            {
                "clip_path": str(payload.get("file_path", "")).strip(),
                "clip_file_name": str(payload.get("file_name", "")).strip(),
                "veo_operation_name": str(payload.get("operation_name", "")).strip(),
                "veo_video_uri": str(payload.get("video_uri", "")).strip(),
                "veo_model": str(payload.get("model", "")).strip(),
            }
        )
        self._set_scene_row_meta(current_row, meta)

    def _apply_scene_generation_error(self, scene_no: str, message: str):
        current_row = self._find_scene_row_by_no(scene_no)
        if current_row is None:
            return
        status_item = self.table_scenes.item(current_row, 5) or QTableWidgetItem()
        clip_item = self.table_scenes.item(current_row, 6) or QTableWidgetItem()
        self.table_scenes.setItem(current_row, 5, status_item)
        self.table_scenes.setItem(current_row, 6, clip_item)
        status_item.setText("Error")
        clip_item.setText("Generation Failed")
        clip_item.setToolTip(str(message))

    def _start_scene_generation_worker(self, row: int, *, batch_mode: bool = False):
        if row < 0 or row >= self.table_scenes.rowCount():
            return
        scene = self._serialize_scene_rows()[row]
        scene_no = str(scene.get("scene_no", "")).strip() or f"S{row + 1:02d}"
        settings = self._project_veo_settings()
        prompt_text = self._current_prompt_text_for_row(
            row,
            force_template=not bool(settings.get("use_scene_prompt", True)),
        ).strip()
        if not prompt_text:
            raise ValueError("Prompt draft is empty for the selected scene.")

        self._scene_run_token += 1
        run_token = self._scene_run_token
        worker = GenerateSingleSceneWorker(
            scene=scene,
            prompt=prompt_text,
            settings=settings,
            project_name=self.input_project_name.text().strip() or "My Veo Project",
            output_root=self._build_generation_output_root(),
        )
        self._scene_worker = worker
        self._set_generate_one_busy(True)
        self._mark_scene_row_generating(scene_no)

        def _status(message: str):
            if run_token != self._scene_run_token:
                return
            prefix = f"[Batch] {message}" if batch_mode else message
            self._set_project_status(prefix)

        def _error(message: str):
            if run_token != self._scene_run_token:
                return
            self._apply_scene_generation_error(scene_no, message)
            self._cleanup_scene_worker()
            self._set_generate_one_busy(False)
            if batch_mode:
                self._batch_failures.append({"scene_no": scene_no, "message": str(message).strip()})
                if self._should_abort_batch_for_error(message):
                    self._batch_scene_queue = []
                self._start_next_batch_scene()
                return
            self._set_project_status(f"Scene generation failed for {scene_no}")
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(str(message), 7000)
            QMessageBox.warning(
                self,
                "Generate One",
                f"Scene generation failed for {scene_no}.\n\n{str(message).strip() or 'Unknown Veo error.'}",
            )

        def _finished(payload: dict):
            if run_token != self._scene_run_token:
                return
            self._apply_scene_generation_success(scene_no, payload)
            self._cleanup_scene_worker()
            self._set_generate_one_busy(False)
            if batch_mode:
                self._batch_results.append(dict(payload or {}))
                self._start_next_batch_scene()
                return
            self._set_project_status(f"Generated clip for {scene_no}")
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(
                    str(payload.get("file_path", "")).strip() or f"Generated clip for {scene_no}",
                    7000,
                )

        worker.status_signal.connect(_status)
        worker.error_signal.connect(_error)
        worker.finished_signal.connect(_finished)
        worker.start()

    def _generate_single_scene(self):
        if self._scene_worker is not None:
            QMessageBox.information(self, "Generate One", "A scene generation job is already running.")
            return
        if self._batch_generation_active:
            QMessageBox.information(self, "Generate One", "Batch generation is already running.")
            return
        if self._prompt_worker is not None:
            QMessageBox.information(self, "Generate One", "Prompt generation is still running. Please wait for it to finish first.")
            return
        row = self._selected_scene_row()
        if row is None:
            QMessageBox.information(self, "Generate One", "Please select a scene row first.")
            return
        try:
            self._start_scene_generation_worker(row, batch_mode=False)
        except Exception as exc:
            QMessageBox.warning(self, "Generate One", str(exc))

    def _finish_batch_generation(self):
        self._set_generate_all_busy(False)
        self._set_generate_one_busy(False)
        success_count = len(self._batch_results)
        failure_count = len(self._batch_failures)
        if failure_count == 0:
            self._set_project_status(f"Batch generation finished. Generated {success_count} scene(s).")
            if self.main_window and self.main_window.statusBar():
                self.main_window.statusBar().showMessage(
                    f"Batch generation finished. Generated {success_count} scene(s).",
                    7000,
                )
        else:
            first_error = self._batch_failures[0]["message"] if self._batch_failures else ""
            self._set_project_status(f"Batch generation finished with {failure_count} error(s).")
            QMessageBox.warning(
                self,
                "Generate All",
                f"Generated {success_count} scene(s).\nFailed: {failure_count}.\n\n{first_error}".strip(),
            )
        self._batch_scene_queue = []
        self._batch_results = []
        self._batch_failures = []

    def _start_next_batch_scene(self):
        if self._scene_worker is not None:
            return
        while self._batch_scene_queue:
            scene_no = self._batch_scene_queue.pop(0)
            row = self._find_scene_row_by_no(scene_no)
            if row is None:
                continue
            try:
                self._start_scene_generation_worker(row, batch_mode=True)
                return
            except Exception as exc:
                self._batch_failures.append({"scene_no": scene_no, "message": str(exc).strip()})
                if self._should_abort_batch_for_error(exc):
                    self._batch_scene_queue = []
                    break
                continue
        self._finish_batch_generation()

    def _generate_all_scenes(self):
        if self._batch_generation_active:
            QMessageBox.information(self, "Generate All", "Batch generation is already running.")
            return
        if self._scene_worker is not None:
            QMessageBox.information(self, "Generate All", "A scene generation job is already running.")
            return
        if self._prompt_worker is not None:
            QMessageBox.information(self, "Generate All", "Prompt generation is still running. Please wait for it to finish first.")
            return
        source = self.text_source_script.toPlainText().strip()
        if not source:
            QMessageBox.information(self, "Generate All", "Please paste or load a source script first.")
            return
        scene_nos = self._scene_numbers_for_batch()
        if not scene_nos:
            QMessageBox.information(self, "Generate All", "Please create a scene plan first.")
            return
        self._batch_scene_queue = list(scene_nos)
        self._batch_results = []
        self._batch_failures = []
        self._set_generate_all_busy(True)
        self._set_project_status(f"Batch generation started for {len(scene_nos)} scene(s)")
        self._start_next_batch_scene()

    def _open_scene_details_dialog(self):
        if self._guard_busy_action("Scene Details"):
            return
        row = self._selected_scene_row()
        if row is None:
            QMessageBox.information(self, "Scene Details", "Please select a scene row first.")
            return
        scene_no = self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else f"S{row + 1:02d}"
        title = self.table_scenes.item(row, 1).text() if self.table_scenes.item(row, 1) else "Untitled Scene"
        visual_goal = self.table_scenes.item(row, 3).text() if self.table_scenes.item(row, 3) else ""
        voiceover = self.table_scenes.item(row, 4).text() if self.table_scenes.item(row, 4) else ""
        meta = self._scene_row_meta(row)

        dialog = QDialog(self)
        dialog.setWindowTitle("Scene Details")
        dialog.resize(760, 520)
        dialog.setStyleSheet(
            "QDialog { background:#181b1f; color:#ffffff; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QComboBox, QPlainTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; padding:8px; }"
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = QLabel(f"{scene_no} - {title}")
        header.setStyleSheet("QLabel { color:#ffffff; font-size:16px; font-weight:700; }")
        layout.addWidget(header)

        shot_row = QHBoxLayout()
        shot_row.setSpacing(10)
        shot_row.addWidget(QLabel("Shot Type"))
        combo = QComboBox()
        combo.addItems(["Talking Head", "B-Roll", "Montage", "Product Shot", "UGC"])
        combo.setCurrentText(str(meta.get("shot_type", self.combo_shot_type.currentText() or "Talking Head")))
        combo.setMinimumWidth(220)
        shot_row.addWidget(combo)
        shot_row.addStretch()
        layout.addLayout(shot_row)

        layout.addWidget(QLabel("Scene Notes"))
        notes = QPlainTextEdit()
        notes.setPlainText(str(meta.get("scene_notes", f"Visual Goal:\n{visual_goal}\n\nVoiceover Draft:\n{voiceover}")))
        layout.addWidget(notes, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        btn_save = QPushButton("Save")
        btn_close = QPushButton("Close")
        button_row.addWidget(btn_save)
        button_row.addWidget(btn_close)
        layout.addLayout(button_row)

        def _save():
            meta_local = self._scene_row_meta(row)
            meta_local["shot_type"] = combo.currentText()
            meta_local["scene_notes"] = notes.toPlainText().strip()
            self._set_scene_row_meta(row, meta_local)
            self.combo_shot_type.setCurrentText(combo.currentText())
            self.text_scene_notes.setPlainText(notes.toPlainText().strip())
            self._set_project_status(f"Scene details saved for {scene_no}")
            dialog.accept()

        btn_save.clicked.connect(_save)
        btn_close.clicked.connect(dialog.reject)
        dialog.exec()

    def _open_prompt_editor_dialog(self):
        if self._guard_busy_action("Prompt Editor"):
            return
        row = self._selected_scene_row()
        if row is None:
            QMessageBox.information(self, "Prompt Editor", "Please select a scene row first.")
            return
        scene_no = self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else f"S{row + 1:02d}"
        title = self.table_scenes.item(row, 1).text() if self.table_scenes.item(row, 1) else "Untitled Scene"

        dialog = QDialog(self)
        dialog.setWindowTitle("Prompt Editor")
        dialog.resize(860, 620)
        dialog.setStyleSheet(
            "QDialog { background:#181b1f; color:#ffffff; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QComboBox, QTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; padding:8px; }"
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel(f"{scene_no} - {title}"))

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(QLabel("Format"))
        combo = QComboBox()
        combo.addItems(["Scene Prompt", "Detailed Prompt", "Veo Prompt"])
        combo.setCurrentText(self.combo_prompt_format.currentText())
        combo.setMinimumWidth(180)
        top.addWidget(combo)
        top.addStretch()
        layout.addLayout(top)

        editor = QTextEdit()
        editor.setPlainText(self._current_prompt_text_for_row(row))
        layout.addWidget(editor, stretch=1)

        button_row = QHBoxLayout()
        btn_reset = QPushButton("Reset to Template")
        btn_copy = QPushButton("Copy")
        btn_apply = QPushButton("Apply")
        btn_close = QPushButton("Close")
        button_row.addWidget(btn_reset)
        button_row.addWidget(btn_copy)
        button_row.addStretch()
        button_row.addWidget(btn_apply)
        button_row.addWidget(btn_close)
        layout.addLayout(button_row)

        def _reload_template():
            self.combo_prompt_format.setCurrentText(combo.currentText())
            editor.setPlainText(self._current_prompt_text_for_row(row, force_template=True))

        def _copy():
            text = editor.toPlainText().strip()
            if not text:
                QMessageBox.information(dialog, "Copy Prompt", "Prompt editor is empty.")
                return
            QApplication.clipboard().setText(text)

        def _apply():
            self.combo_prompt_format.setCurrentText(combo.currentText())
            meta = self._scene_row_meta(row)
            meta["prompt_draft"] = editor.toPlainText().strip()
            self._set_scene_row_meta(row, meta)
            self._set_project_status(f"Prompt draft saved for {scene_no}")
            dialog.accept()

        btn_reset.clicked.connect(_reload_template)
        btn_copy.clicked.connect(_copy)
        btn_apply.clicked.connect(_apply)
        btn_close.clicked.connect(dialog.reject)
        dialog.exec()

    def _open_preview_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Project Preview")
        dialog.resize(780, 560)
        dialog.setStyleSheet(
            "QDialog { background:#181b1f; color:#ffffff; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QPlainTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; padding:10px; font-size:13px; }"
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Project Preview"))

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        if self.table_scenes.rowCount() == 0:
            preview.setPlainText("No scenes yet. Create a scene plan first.")
        else:
            lines = []
            for row in range(self.table_scenes.rowCount()):
                scene_no = self.table_scenes.item(row, 0).text() if self.table_scenes.item(row, 0) else f"S{row + 1:02d}"
                title = self.table_scenes.item(row, 1).text() if self.table_scenes.item(row, 1) else ""
                duration = self.table_scenes.item(row, 2).text() if self.table_scenes.item(row, 2) else ""
                visual_goal = self.table_scenes.item(row, 3).text() if self.table_scenes.item(row, 3) else ""
                lines.append(f"{scene_no} | {title} | {duration}\n{visual_goal}")
            preview.setPlainText("\n\n".join(lines).strip())
        layout.addWidget(preview, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        button_row.addWidget(btn_close)
        layout.addLayout(button_row)
        dialog.exec()

    def _open_clip_manager_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Clip Manager")
        dialog.resize(980, 620)
        dialog.setStyleSheet(
            "QDialog { background:#181b1f; color:#ffffff; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QTableWidget { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; gridline-color:#e6e6e6; font-size:13px; }"
            "QTableWidget::item { padding:6px; }"
            "QTableWidget::item:selected { background:#f5d7d0; color:#111111; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:none; border-right:1px solid #d7d7d7; border-bottom:1px solid #d7d7d7; padding:8px 6px; font-weight:700; }"
            "QPlainTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; padding:10px; font-size:13px; }"
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        summary_label = QLabel("Clips generated in this project.")
        summary_label.setStyleSheet("QLabel { color:#cfd4dc; font-size:12px; }")
        layout.addWidget(summary_label)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Scene", "Title", "Status", "Clip File", "Model", "Output"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 72)
        table.setColumnWidth(1, 220)
        table.setColumnWidth(2, 100)
        table.setColumnWidth(3, 180)
        table.setColumnWidth(4, 170)
        table.setColumnWidth(5, 180)
        table.horizontalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        table.verticalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        layout.addWidget(table, stretch=1)

        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText("Selected clip details will appear here.")
        preview.setMinimumHeight(150)
        layout.addWidget(preview)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        btn_refresh = QPushButton("Refresh")
        btn_open_clip = QPushButton("Open Clip")
        btn_open_folder = QPushButton("Open Folder")
        btn_close = QPushButton("Close")
        button_row.addWidget(btn_refresh)
        button_row.addWidget(btn_open_clip)
        button_row.addWidget(btn_open_folder)
        button_row.addStretch()
        button_row.addWidget(btn_close)
        layout.addLayout(button_row)

        def _update_preview():
            selected = table.selectionModel().selectedRows() if table.selectionModel() else []
            if not selected:
                preview.setPlainText("Select a clip row to inspect clip metadata.")
                return
            row = selected[0].row()
            payload = table.item(row, 0).data(Qt.ItemDataRole.UserRole) if table.item(row, 0) else {}
            payload = dict(payload) if isinstance(payload, dict) else {}
            preview.setPlainText(
                "\n".join(
                    [
                        f"Scene: {payload.get('scene_no', '')}",
                        f"Title: {payload.get('title', '')}",
                        f"Status: {payload.get('status', '')}",
                        f"Clip File: {payload.get('clip_file_name', '') or payload.get('clip', '')}",
                        f"Clip Path: {payload.get('clip_path', '') or 'not-generated'}",
                        f"Model: {payload.get('veo_model', '') or 'not-given'}",
                        f"Operation: {payload.get('veo_operation_name', '') or 'not-given'}",
                        f"Video URI: {payload.get('veo_video_uri', '') or 'not-given'}",
                    ]
                ).strip()
            )

        def _reload():
            clip_rows = self._serialize_clip_rows()
            table.setRowCount(0)
            generated_count = 0
            for item in clip_rows:
                row = table.rowCount()
                table.insertRow(row)
                values = [
                    item.get("scene_no", ""),
                    item.get("title", ""),
                    item.get("status", ""),
                    item.get("clip_file_name", "") or item.get("clip", ""),
                    item.get("veo_model", "") or "-",
                    item.get("clip_path", "") or item.get("clip", ""),
                ]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value or ""))
                    if col == 0:
                        cell.setData(Qt.ItemDataRole.UserRole, dict(item))
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row, col, cell)
                if str(item.get("status", "")).strip().lower() == "generated":
                    generated_count += 1
            summary_label.setText(f"Clip rows: {len(clip_rows)} | Generated: {generated_count}")
            if table.rowCount() > 0:
                table.selectRow(0)
            else:
                preview.setPlainText("No clip rows yet. Generate one or more scenes first.")
            _update_preview()

        table.itemSelectionChanged.connect(_update_preview)
        btn_refresh.clicked.connect(_reload)
        btn_open_clip.clicked.connect(lambda: self._coming_soon("Open Clip"))
        btn_open_folder.clicked.connect(lambda: self._coming_soon("Open Folder"))
        btn_close.clicked.connect(dialog.accept)

        _reload()
        dialog.exec()

    def _open_browser_fallback_dialog(self):
        if self._guard_busy_action("Browser Fallback"):
            return
        if self.table_scenes.rowCount() == 0:
            QMessageBox.information(self, "Browser Fallback", "Please create a scene plan first.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Browser Fallback Queue")
        dialog.resize(1080, 680)
        dialog.setStyleSheet(
            "QDialog { background:#181b1f; color:#ffffff; }"
            "QLabel { color:#ffffff; font-size:13px; }"
            "QTableWidget { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; gridline-color:#e6e6e6; font-size:13px; }"
            "QTableWidget::item { padding:6px; }"
            "QTableWidget::item:selected { background:#f5d7d0; color:#111111; }"
            "QHeaderView::section { background:#f0f0f0; color:#111111; border:none; border-right:1px solid #d7d7d7; border-bottom:1px solid #d7d7d7; padding:8px 6px; font-weight:700; }"
            "QPlainTextEdit { background:#ffffff; color:#111111; border:1px solid #d4d7dc; border-radius:6px; padding:10px; font-size:13px; }"
            "QPushButton { background:#e24a22; color:#ffffff; border:none; border-radius:4px; padding:7px 14px; font-weight:700; }"
            "QPushButton:hover { background:#f05a34; }"
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro = QLabel(
            "Use this queue when Gemini Veo API is unavailable or out of quota. Copy each scene prompt, open the browser flow manually, generate the clip there, then import the rendered clip in a later step."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("QLabel { color:#cfd4dc; font-size:12px; }")
        layout.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, stretch=1)

        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        summary = QLabel("Scene queue")
        summary.setStyleSheet("QLabel { color:#ffffff; font-size:14px; font-weight:700; }")
        left_layout.addWidget(summary)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Scene", "Title", "Status", "Prompt"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 72)
        table.setColumnWidth(1, 220)
        table.setColumnWidth(2, 110)
        table.setColumnWidth(3, 160)
        table.horizontalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        table.verticalScrollBar().setStyleSheet(TABLE_SCROLLBAR_STYLE)
        left_layout.addWidget(table, stretch=1)

        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        lbl_scene = QLabel("Selected scene: None")
        lbl_scene.setStyleSheet("QLabel { color:#ffffff; font-size:14px; font-weight:700; }")
        right_layout.addWidget(lbl_scene)

        instruction_box = QLabel(
            "Manual flow: 1) copy the scene prompt, 2) open the browser render flow, 3) generate the clip manually, 4) import the clip back into this project in the next backend step."
        )
        instruction_box.setWordWrap(True)
        instruction_box.setStyleSheet("QLabel { color:#cfd4dc; font-size:12px; }")
        right_layout.addWidget(instruction_box)

        right_layout.addWidget(QLabel("Prompt"))
        text_prompt = QPlainTextEdit()
        text_prompt.setReadOnly(True)
        text_prompt.setMinimumHeight(220)
        right_layout.addWidget(text_prompt, stretch=1)

        right_layout.addWidget(QLabel("Voiceover"))
        text_voiceover = QPlainTextEdit()
        text_voiceover.setReadOnly(True)
        text_voiceover.setMinimumHeight(120)
        right_layout.addWidget(text_voiceover)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        btn_copy_prompt = QPushButton("Copy Prompt")
        btn_copy_voiceover = QPushButton("Copy Voiceover")
        btn_open_browser = QPushButton("Open Browser Flow")
        btn_mark_pending = QPushButton("Mark Pending")
        btn_import_clip = QPushButton("Import Clip")
        btn_next = QPushButton("Next Scene")
        btn_close = QPushButton("Close")
        for btn in (
            btn_copy_prompt,
            btn_copy_voiceover,
            btn_open_browser,
            btn_mark_pending,
            btn_import_clip,
            btn_next,
            btn_close,
        ):
            button_row.addWidget(btn)
        right_layout.addLayout(button_row)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([460, 560])

        def _reload():
            scene_rows = self._serialize_scene_rows()
            table.setRowCount(0)
            for row_idx, item in enumerate(scene_rows):
                prompt_text = self._current_prompt_text_for_row(row_idx)
                table.insertRow(row_idx)
                values = [
                    item.get("scene_no", ""),
                    item.get("title", ""),
                    item.get("status", ""),
                    "Ready" if prompt_text.strip() else "Missing",
                ]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value or ""))
                    if col == 0:
                        cell.setData(
                            Qt.ItemDataRole.UserRole,
                            {
                                "row": row_idx,
                                "scene_no": item.get("scene_no", ""),
                                "title": item.get("title", ""),
                                "status": item.get("status", ""),
                                "voiceover": item.get("voiceover", ""),
                                "prompt": prompt_text,
                            },
                        )
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row_idx, col, cell)

        def _update_preview():
            selected = table.selectionModel().selectedRows() if table.selectionModel() else []
            if not selected:
                lbl_scene.setText("Selected scene: None")
                text_prompt.setPlainText("")
                text_voiceover.setPlainText("")
                return
            row = selected[0].row()
            payload = table.item(row, 0).data(Qt.ItemDataRole.UserRole) if table.item(row, 0) else {}
            payload = dict(payload) if isinstance(payload, dict) else {}
            lbl_scene.setText(
                f"Selected scene: {payload.get('scene_no', '')} - {payload.get('title', '')}"
            )
            text_prompt.setPlainText(str(payload.get("prompt", "")).strip())
            text_voiceover.setPlainText(str(payload.get("voiceover", "")).strip())

        def _copy_prompt():
            text = text_prompt.toPlainText().strip()
            if not text:
                QMessageBox.information(dialog, "Copy Prompt", "Prompt is empty for the selected scene.")
                return
            QApplication.clipboard().setText(text)

        def _copy_voiceover():
            text = text_voiceover.toPlainText().strip()
            if not text:
                QMessageBox.information(dialog, "Copy Voiceover", "Voiceover is empty for the selected scene.")
                return
            QApplication.clipboard().setText(text)

        def _select_next():
            current = table.currentRow()
            if current < 0 and table.rowCount() > 0:
                table.selectRow(0)
                return
            next_row = current + 1
            if next_row < table.rowCount():
                table.selectRow(next_row)

        table.itemSelectionChanged.connect(_update_preview)
        btn_copy_prompt.clicked.connect(_copy_prompt)
        btn_copy_voiceover.clicked.connect(_copy_voiceover)
        btn_open_browser.clicked.connect(lambda: self._coming_soon("Open Browser Flow"))
        btn_mark_pending.clicked.connect(lambda: self._coming_soon("Mark Pending"))
        btn_import_clip.clicked.connect(lambda: self._coming_soon("Import Clip"))
        btn_next.clicked.connect(_select_next)
        btn_close.clicked.connect(dialog.accept)

        _reload()
        initial_row = self._selected_scene_row()
        if initial_row is not None and initial_row < table.rowCount():
            table.selectRow(initial_row)
        elif table.rowCount() > 0:
            table.selectRow(0)
        _update_preview()
        dialog.exec()

    def shutdown(self):
        self._request_stop_prompt_worker()
        self._request_stop_scene_worker()
        self._cleanup_prompt_worker()
        self._cleanup_scene_worker()
        self._prompt_generation_active = False
        self._single_generation_active = False
        self._batch_generation_active = False
        self._batch_scene_queue = []
        self._batch_results = []
        self._batch_failures = []
        self._refresh_interaction_state()
