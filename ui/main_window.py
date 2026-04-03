import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QStackedWidget, QSizePolicy, QTextEdit
)
from PyQt6.QtCore import Qt

from ui.keywords_tab import KeywordsTab
from ui.trends_tab import TrendsTab
from ui.videos_tab import VideosTab
from utils.constants import MAIN_STYLE
from utils.proxy_utils import normalize_proxy


class ToolInboxPage(QWidget):
    def __init__(self, title, hint_text=""):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(16)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("QLabel { color:#ffffff; font-size:28px; font-weight:700; }")
        root.addWidget(lbl_title)

        self.lbl_hint = QLabel(hint_text)
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("QLabel { color:#cbd5e1; font-size:14px; }")
        root.addWidget(self.lbl_hint)

        self.text_payload = QTextEdit()
        self.text_payload.setReadOnly(True)
        self.text_payload.setPlaceholderText("Incoming data will appear here.")
        self.text_payload.setStyleSheet(
            "QTextEdit { background:#11151f; color:#f8fafc; border:1px solid #2f3444; "
            "border-radius:8px; padding:12px; font-size:14px; }"
        )
        root.addWidget(self.text_payload, stretch=1)

    def receive_payload(self, text, hint_text=""):
        self.text_payload.setPlainText(str(text or "").strip())
        if hint_text:
            self.lbl_hint.setText(str(hint_text))

class TubeVibeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.proxy_settings = {
            "enabled": False,
            "proxies": [],
        }
        self.proxy_runtime_settings = {
            "max_proxies_per_run": 30,
        }
        self.setWindowTitle("TubeVibe - YouTube Research Pro")
        self.resize(1280, 800)
        self.setup_ui()
        self.setStyleSheet(MAIN_STYLE)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # MAIN AREA
        right_area = QWidget()
        r_layout = QVBoxLayout(right_area)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(0)
        
        # Navbar
        navbar = QFrame(); navbar.setObjectName("navbar"); navbar.setFixedHeight(60)
        n_layout = QHBoxLayout(navbar); n_layout.setContentsMargins(20, 0, 20, 0)
        
        self.nav_labels = []
        tabs_names = ["Welcome", "Keywords", "Trends", "Videos", "Channels", "Video to Text", "Comments"]
        for i, name in enumerate(tabs_names):
            lbl = QLabel(name)
            lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            lbl.setObjectName("active_tab" if name == "Keywords" else "inactive_tab")
            lbl.mousePressEvent = lambda e, idx=i: self.switch_tab(idx)
            self.nav_labels.append(lbl)
            n_layout.addWidget(lbl)
        n_layout.addStretch()
        
        self.main_stack = QStackedWidget()
        self.tab_welcome = QWidget()
        self.tab_keywords = KeywordsTab(self)
        self.tab_trends = TrendsTab(self)
        self.tab_videos = VideosTab(self)
        self.tab_channels = ToolInboxPage("Channels Tool", "Videos or channel seeds sent from other tools will appear here.")
        self.tab_video_to_text = ToolInboxPage("Video to Text", "Selected video links sent for transcription will appear here.")
        self.tab_comments = ToolInboxPage("Comments Tool", "Selected video links sent for comment extraction will appear here.")
        
        # Connect signal: Keywords -> Trends data transfer
        self.tab_keywords.send_to_trends_signal.connect(self.handle_send_to_trends)
        
        self.main_stack.addWidget(self.tab_welcome)
        self.main_stack.addWidget(self.tab_keywords)
        self.main_stack.addWidget(self.tab_trends)
        self.main_stack.addWidget(self.tab_videos)
        self.main_stack.addWidget(self.tab_channels)
        self.main_stack.addWidget(self.tab_video_to_text)
        self.main_stack.addWidget(self.tab_comments)
        
        self.main_stack.setCurrentIndex(1)
        
        r_layout.addWidget(navbar)
        r_layout.addWidget(self.main_stack, stretch=1)
        main_layout.addWidget(right_area, stretch=1)

    def switch_tab(self, index):
        self.main_stack.setCurrentIndex(index)
        for i, lbl in enumerate(self.nav_labels):
            if i == index:
                lbl.setObjectName("active_tab")
                lbl.setStyleSheet("color: #ffffff; background-color: #2a2a2a; padding: 20px 15px; border-bottom: 3px solid #e50914; font-weight: bold; font-size: 15px;")
            else:
                lbl.setObjectName("inactive_tab")
                lbl.setStyleSheet("color: #aaaaaa; padding: 20px 15px; font-size: 15px; border-bottom: none; background-color: transparent;")

    def handle_send_to_trends(self, keywords):
        self.tab_trends.trends_input.setText("\n".join(keywords))
        self.switch_tab(2)
        self.statusBar().showMessage(f"Sent {len(keywords)} keywords to Trends tool.", 4000)

    def handle_send_to_videos(self, keywords, source_tool=""):
        if not keywords:
            return
        accepted = self.tab_videos.receive_keywords_for_video_search(
            keywords, source_tool=source_tool
        )
        if not accepted:
            return
        self.switch_tab(3)
        src = source_tool or "another tool"
        self.statusBar().showMessage(
            f"Sent {len(keywords)} keywords to Videos tool from {src}.", 4000
        )

    def handle_send_videos_to_comments(self, video_links):
        links = [str(link).strip() for link in (video_links or []) if str(link).strip()]
        if not links:
            return False
        self.tab_comments.receive_payload(
            "\n".join(links),
            f"Received {len(links)} video link(s) from Videos tool.",
        )
        self.switch_tab(6)
        self.statusBar().showMessage(
            f"Sent {len(links)} video link(s) to Comments tool.", 4000
        )
        return True

    def handle_send_videos_to_channels(self, items, source_label="Videos tool"):
        rows = [dict(row) for row in (items or []) if isinstance(row, dict)]
        if not rows:
            return False
        lines = []
        for idx, row in enumerate(rows, start=1):
            lines.append(f"{idx}. {row.get('Title', '').strip()}")
            lines.append(f"Video Link: {row.get('Video Link', '').strip()}")
            lines.append(f"Search Phrase: {row.get('Search Phrase', '').strip()}")
            lines.append("")
        self.tab_channels.receive_payload(
            "\n".join(lines).strip(),
            f"Received {len(rows)} item(s) from {source_label}.",
        )
        self.switch_tab(4)
        self.statusBar().showMessage(
            f"Sent {len(rows)} item(s) to Channel tool.", 4000
        )
        return True

    def handle_send_videos_to_text(self, video_links):
        links = [str(link).strip() for link in (video_links or []) if str(link).strip()]
        if not links:
            return False
        self.tab_video_to_text.receive_payload(
            "\n".join(links),
            f"Received {len(links)} video link(s) from Videos tool.",
        )
        self.switch_tab(5)
        self.statusBar().showMessage(
            f"Sent {len(links)} video link(s) to Video to Text.", 4000
        )
        return True

    def get_proxy_settings(self):
        return {
            "enabled": bool(self.proxy_settings.get("enabled", False)),
            "proxies": list(self.proxy_settings.get("proxies", [])),
        }

    def set_proxy_settings(self, enabled=False, proxies=None):
        clean_proxies = []
        seen = set()
        for proxy in proxies or []:
            text = normalize_proxy(proxy)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            clean_proxies.append(text)

        self.proxy_settings = {
            "enabled": bool(enabled),
            "proxies": clean_proxies,
        }

        if self.proxy_settings["enabled"] and self.proxy_settings["proxies"]:
            first_proxy = self.proxy_settings["proxies"][0]
            os.environ["HTTP_PROXY"] = first_proxy
            os.environ["HTTPS_PROXY"] = first_proxy
            os.environ["http_proxy"] = first_proxy
            os.environ["https_proxy"] = first_proxy
        else:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)

    def get_proxy_runtime_settings(self):
        return {
            "max_proxies_per_run": max(1, int(self.proxy_runtime_settings.get("max_proxies_per_run", 30))),
        }

    def set_proxy_runtime_settings(self, max_proxies_per_run=30):
        self.proxy_runtime_settings = {
            "max_proxies_per_run": max(1, int(max_proxies_per_run)),
        }
