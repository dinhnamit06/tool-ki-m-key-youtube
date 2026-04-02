import random
import threading
import time
from collections import deque
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

        # Step 2.18 requirement: keep sequential processing for stability.
        self.max_workers = 1

        self._thread_local = threading.local()
        self.total_requests_made = 0
        self._burst_keywords = 4
        self._delay_offset = 0.0
        self._recent_request_seconds = deque(maxlen=8)
        self._recent_inter_delays = deque(maxlen=8)

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
        return "429" in err or "rate limit" in err or "too many requests" in err

    def _sleep_with_stop(self, seconds):
        ticks = max(1, int(seconds * 10))
        for _ in range(ticks):
            if not self.is_running:
                return
            time.sleep(0.1)

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

    def _preview_delay_for_estimate(self, finalized_keywords):
        if finalized_keywords < self._burst_keywords:
            return 1.5
        return 3.5 + self._delay_offset

    def _compute_inter_keyword_delay(self, finalized_keywords):
        # Burst mode for first 4 keywords.
        if finalized_keywords < self._burst_keywords:
            delay_seconds = random.uniform(1.0, 2.0)
        else:
            # Base dynamic delay.
            delay_seconds = random.uniform(2.5, 4.5) + self._delay_offset
            delay_seconds = max(2.5, min(14.0, delay_seconds))

        # Gradual adaptive tuning based on recent response times.
        if len(self._recent_request_seconds) >= 3:
            recent = list(self._recent_request_seconds)[-3:]
            avg_recent = sum(recent) / len(recent)
            if avg_recent > 6.5:
                self._delay_offset = min(10.0, self._delay_offset + 0.35)
            elif avg_recent < 4.0 and self._delay_offset > 0:
                self._delay_offset = max(0.0, self._delay_offset - 0.2)

        return delay_seconds

    def _estimate_remaining_seconds(self, total_keywords, finalized_keywords):
        remaining = max(0, total_keywords - finalized_keywords)
        if remaining == 0:
            return 0

        avg_request = (
            sum(self._recent_request_seconds) / len(self._recent_request_seconds)
            if self._recent_request_seconds
            else 4.0
        )
        avg_delay = (
            sum(self._recent_inter_delays) / len(self._recent_inter_delays)
            if self._recent_inter_delays
            else self._preview_delay_for_estimate(finalized_keywords)
        )
        return int(round(remaining * (avg_request + avg_delay)))

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
        finalized_keywords = 0
        successful_keywords = 0
        retry_wait_schedule = {1: 15, 2: 30, 3: 60}
        max_retry_attempts = 3

        for kw in self.keywords:
            if not self.is_running:
                break

            eta_seconds = self._estimate_remaining_seconds(total_keywords, finalized_keywords)
            self.status_signal.emit(
                f"Processing '{kw}' ({finalized_keywords + 1}/{total_keywords}) • Estimated remaining: {eta_seconds}s"
            )

            keyword_success = False
            attempts = 0

            while self.is_running and attempts <= max_retry_attempts and not keyword_success:
                start_ts = time.time()
                try:
                    payload = self._build_payload_for_keyword(kw, cat_code, tf_code, geo_code, gprop_code)
                    duration_seconds = time.time() - start_ts
                    self.total_requests_made += 1
                    self._recent_request_seconds.append(duration_seconds)

                    # Early sign of rate limit: very slow request.
                    if duration_seconds > 8.0:
                        self._delay_offset = min(12.0, self._delay_offset + 2.0)
                        self.status_signal.emit(
                            f"Slow response detected for '{kw}' ({duration_seconds:.1f}s). "
                            "Increasing delay by 2s for next keywords."
                        )

                    successful_keywords += 1
                    keyword_success = True

                    # Include progress metadata so UI can update row counter/status in real time.
                    payload["ProcessedIndex"] = successful_keywords
                    payload["TotalKeywords"] = total_keywords
                    self.progress_signal.emit(payload)
                except Exception as exc:
                    duration_seconds = time.time() - start_ts
                    self.total_requests_made += 1
                    self._recent_request_seconds.append(duration_seconds)
                    err_text = str(exc)

                    if self._is_rate_limit_error(err_text):
                        attempts += 1
                        if attempts <= max_retry_attempts and self.is_running:
                            wait_seconds = retry_wait_schedule.get(attempts, 60)
                            self._delay_offset = min(12.0, self._delay_offset + 2.0)
                            self.status_signal.emit(
                                f"Rate limit on '{kw}'. Waiting {wait_seconds}s before retry ({attempts}/{max_retry_attempts} attempts)..."
                            )
                            self._sleep_with_stop(wait_seconds)
                            continue

                        self.status_signal.emit(
                            f"Skipped '{kw}' after 3 failed attempts due to rate limit"
                        )
                        break

                    # Non-rate-limit errors: skip this keyword after first failure.
                    self.error_signal.emit(f"Error fetching '{kw}': {err_text}")
                    break

            finalized_keywords += 1
            self.status_signal.emit(
                f"Processed {successful_keywords}/{total_keywords} keywords "
                f"(requests={self.total_requests_made})"
            )

            if self.is_running and finalized_keywords < total_keywords:
                inter_delay = self._compute_inter_keyword_delay(finalized_keywords)
                self._recent_inter_delays.append(inter_delay)
                self.status_signal.emit(
                    f"Stabilizing speed: waiting {inter_delay:.1f}s before next keyword..."
                )
                self._sleep_with_stop(inter_delay)

        self.finished_signal.emit()
