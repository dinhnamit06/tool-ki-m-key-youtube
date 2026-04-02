import random
import threading
import time
from urllib.parse import urlencode

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from utils.constants import CAT_MAP, GEO_MAP, PROP_MAP, TIME_MAP


class TrendsFetcherWorker(QThread):
    progress_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)

    def __init__(
        self,
        keywords,
        geo,
        timeframe,
        category,
        gprop,
        pause_after_connections=20,
        pause_min_seconds=10,
        pause_max_seconds=60,
        max_workers=1,
    ):
        super().__init__()
        self.keywords = list(keywords)
        self.geo = geo
        self.timeframe = timeframe
        self.category = category
        self.gprop = gprop
        self.is_running = True

        # Keep sequential processing for stable pytrends requests.
        self.max_workers = 1

        # Kept for API compatibility with previous settings dialog.
        self.pause_after_connections = int(pause_after_connections)
        self.pause_min_seconds = int(pause_min_seconds)
        self.pause_max_seconds = int(pause_max_seconds)

        self._thread_local = threading.local()
        self.total_requests_made = 0
        self._recent_request_seconds = []
        self._delay_min_seconds = 2.0
        self._delay_max_seconds = 3.4
        self._burst_keywords = 3
        self._burst_delay_min = 0.9
        self._burst_delay_max = 1.6
        self._slow_request_threshold_seconds = 8.0
        self._rate_limit_events = 0

    @staticmethod
    def _build_google_trends_url(keyword, timeframe, geo, gprop):
        params = {"q": keyword, "date": timeframe}
        if geo:
            params["geo"] = geo
        if gprop:
            params["gprop"] = gprop
        return f"https://trends.google.com/trends/explore?{urlencode(params)}"

    @staticmethod
    def _is_rate_limit_error(error_text):
        err = error_text.lower()
        return (
            "429" in err
            or "rate limit" in err
            or "too many requests" in err
            or "quota" in err
        )

    def _record_request_time(self, seconds):
        self._recent_request_seconds.append(float(seconds))
        if len(self._recent_request_seconds) > 12:
            self._recent_request_seconds.pop(0)

    def _clamp(self, value, min_value, max_value):
        return max(min_value, min(max_value, value))

    def _recent_average_request_seconds(self, window=5):
        if not self._recent_request_seconds:
            return 0.0
        points = self._recent_request_seconds[-window:]
        return float(sum(points)) / float(len(points))

    def _update_dynamic_delay(self, last_request_seconds, rate_limited=False):
        avg_recent = self._recent_average_request_seconds(window=5)

        if rate_limited:
            self._delay_min_seconds = self._clamp(self._delay_min_seconds + 0.7, 1.2, 6.5)
            self._delay_max_seconds = self._clamp(self._delay_max_seconds + 1.0, 2.0, 8.5)
            return

        if last_request_seconds >= self._slow_request_threshold_seconds or avg_recent >= 7.0:
            self._delay_min_seconds = self._clamp(self._delay_min_seconds + 0.35, 1.2, 6.5)
            self._delay_max_seconds = self._clamp(self._delay_max_seconds + 0.5, 2.0, 8.5)
            return

        if last_request_seconds <= 3.0 and avg_recent <= 4.0:
            self._delay_min_seconds = self._clamp(self._delay_min_seconds - 0.15, 1.2, 6.5)
            self._delay_max_seconds = self._clamp(self._delay_max_seconds - 0.2, 2.0, 8.5)

    def _next_inter_keyword_delay(self, keyword_index):
        if keyword_index <= self._burst_keywords:
            return random.uniform(self._burst_delay_min, self._burst_delay_max)

        lo = min(self._delay_min_seconds, self._delay_max_seconds - 0.2)
        hi = max(lo + 0.2, self._delay_max_seconds)
        return random.uniform(lo, hi)

    def _format_waiting_status(self, keyword, index, total, remaining_seconds, suffix=""):
        message = f"Processing '{keyword}' ({index}/{total}) \u2022 Waiting {remaining_seconds}s..."
        if suffix:
            message = f"{message} {suffix}"
        return message

    def _sleep_with_status(self, seconds, keyword, index, total, suffix=""):
        if seconds <= 0:
            return

        deadline = time.time() + float(seconds)
        last_shown = None
        while self.is_running:
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            remaining_whole = max(1, int(round(remaining)))
            if remaining_whole != last_shown:
                self.status_signal.emit(
                    self._format_waiting_status(
                        keyword,
                        index,
                        total,
                        remaining_whole,
                        suffix=suffix,
                    )
                )
                last_shown = remaining_whole

            time.sleep(min(0.2, max(0.05, remaining)))

    def _get_thread_pytrends(self):
        if not hasattr(self._thread_local, "client"):
            from pytrends.request import TrendReq

            self._thread_local.client = TrendReq(hl="en-US", tz=360)
        return self._thread_local.client

    def _build_payload_for_keyword(self, kw, cat_code, tf_code, geo_code, gprop_code):
        pytrends = self._get_thread_pytrends()
        pytrends.build_payload([kw], cat=cat_code, timeframe=tf_code, geo=geo_code, gprop=gprop_code)
        df = pytrends.interest_over_time()
        trends_url = self._build_google_trends_url(kw, tf_code, geo_code, gprop_code)

        if df.empty or kw not in df.columns:
            values = np.array([], dtype=float)
            raw_points = []
        else:
            series = df[kw].astype(float)
            values = series.values
            raw_points = [{"date": d.strftime("%Y-%m-%d"), "value": float(v)} for d, v in series.items()]

        total_avg = round(float(np.mean(values)), 2) if len(values) > 0 else 0.0
        x = np.arange(len(values), dtype=float)
        try:
            slope = round(float(np.polyfit(x, values, 1)[0]), 3) if len(values) > 1 else 0.0
        except Exception:
            slope = 0.0

        if len(values) >= 30:
            last_30_avg = float(np.mean(values[-30:]))
            last_7_max = float(np.max(values[-7:]))
            spike = round(last_7_max - last_30_avg, 2)
        elif len(values) > 0:
            last_7_max = float(np.max(values[-min(7, len(values)) :]))
            spike = round(last_7_max - float(np.mean(values)), 2)
        else:
            spike = 0.0

        return {
            "Keyword": kw,
            "Country": self.geo,
            "Time Period": self.timeframe,
            "Category": self.category,
            "Property": self.gprop,
            "Word Count": len(kw.split()),
            "Character Count": len(kw),
            "Total Average": total_avg,
            "Trend Slope": slope,
            "Trending Spike": max(0.0, spike),
            "RawData": raw_points,
            "GoogleTrendsUrl": trends_url,
        }

    def run(self):
        try:
            from pytrends.request import TrendReq  # noqa: F401
        except ImportError:
            self.error_signal.emit("Dependency Error: 'pytrends' is missing. Run: pip install pytrends")
            self.finished_signal.emit()
            return

        cat_code = CAT_MAP.get(self.category, 0)
        gprop_code = PROP_MAP.get(self.gprop, "youtube")
        geo_code = GEO_MAP.get(self.geo, "")
        tf_code = TIME_MAP.get(self.timeframe, "today 1-m")

        total_keywords = len(self.keywords)
        successful_keywords = 0

        for keyword_index, kw in enumerate(self.keywords, start=1):
            if not self.is_running:
                break

            self.status_signal.emit(
                f"Processing '{kw}' ({keyword_index}/{total_keywords})..."
            )

            keyword_success = False
            keyword_rate_limited = False
            latest_request_seconds = 0.0

            for attempt in range(1, 4):
                if not self.is_running or keyword_success:
                    break

                start_ts = time.time()
                try:
                    payload = self._build_payload_for_keyword(kw, cat_code, tf_code, geo_code, gprop_code)
                    duration_seconds = time.time() - start_ts
                    self.total_requests_made += 1
                    self._record_request_time(duration_seconds)
                    latest_request_seconds = duration_seconds

                    successful_keywords += 1
                    keyword_success = True
                    self._update_dynamic_delay(duration_seconds, rate_limited=False)

                    payload["ProcessedIndex"] = successful_keywords
                    payload["TotalKeywords"] = total_keywords
                    payload["KeywordIndex"] = keyword_index
                    payload["RequestSeconds"] = round(duration_seconds, 2)
                    self.progress_signal.emit(payload)
                except Exception as exc:
                    duration_seconds = time.time() - start_ts
                    self.total_requests_made += 1
                    self._record_request_time(duration_seconds)
                    latest_request_seconds = duration_seconds
                    err_text = str(exc)

                    if self._is_rate_limit_error(err_text):
                        keyword_rate_limited = True
                        self._rate_limit_events += 1
                        self._update_dynamic_delay(duration_seconds, rate_limited=True)
                        if attempt == 1:
                            wait_seconds = random.uniform(20.0, 35.0)
                            self._sleep_with_status(
                                wait_seconds,
                                kw,
                                keyword_index,
                                total_keywords,
                                suffix="(rate limit retry 1/3)",
                            )
                            continue
                        if attempt == 2:
                            wait_seconds = random.uniform(45.0, 70.0)
                            self._sleep_with_status(
                                wait_seconds,
                                kw,
                                keyword_index,
                                total_keywords,
                                suffix="(rate limit retry 2/3)",
                            )
                            continue

                        self.status_signal.emit(f"Skipped '{kw}' after 3 failed attempts due to rate limit")
                        break

                    self.status_signal.emit(f"Error fetching '{kw}': {err_text}. Skipping keyword.")
                    break

            if self.is_running and keyword_index < total_keywords:
                inter_delay = self._next_inter_keyword_delay(keyword_index)
                if keyword_rate_limited:
                    inter_delay += random.uniform(0.6, 1.4)
                if latest_request_seconds >= self._slow_request_threshold_seconds:
                    inter_delay += random.uniform(0.4, 1.0)
                self._sleep_with_status(inter_delay, kw, keyword_index, total_keywords, suffix="(adaptive delay)")

            self.status_signal.emit(
                f"Processed {keyword_index}/{total_keywords} keyword(s) \u2022 Added {successful_keywords} row(s)"
            )

        self.finished_signal.emit()
