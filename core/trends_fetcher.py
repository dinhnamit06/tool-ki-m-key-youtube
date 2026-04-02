import time
import random
import numpy as np
from urllib.parse import urlencode
from PyQt6.QtCore import QThread, pyqtSignal
from utils.constants import CAT_MAP, PROP_MAP, GEO_MAP, TIME_MAP

class TrendsFetcherWorker(QThread):
    progress_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    
    def __init__(self, keywords, geo, timeframe, category, gprop):
        super().__init__()
        self.keywords = keywords
        self.geo = geo
        self.timeframe = timeframe
        self.category = category
        self.gprop = gprop
        self.is_running = True

    @staticmethod
    def _build_google_trends_url(keyword, timeframe, geo, gprop):
        params = {
            "q": keyword,
            "date": timeframe,
        }
        if geo:
            params["geo"] = geo
        if gprop:
            params["gprop"] = gprop
        return f"https://trends.google.com/trends/explore?{urlencode(params)}"
        
    def run(self):
        try:
            from pytrends.request import TrendReq
        except ImportError:
            self.error_signal.emit("Dependency Error: 'pytrends' is missing. Run: pip install pytrends")
            return
            
        pytrends = TrendReq(hl='en-US', tz=360)
        
        cat_code = CAT_MAP.get(self.category, 0)
        gprop_code = PROP_MAP.get(self.gprop, "youtube")
        geo_code = GEO_MAP.get(self.geo, "")
        tf_code = TIME_MAP.get(self.timeframe, "today 1-m")

        idx = 0
        while idx < len(self.keywords):
            if not self.is_running:
                break
                
            kw = self.keywords[idx]
            
            if hasattr(self, 'status_signal'):
                self.status_signal.emit(f"Processing keyword {idx+1}/{len(self.keywords)}: {kw}...")
                
            try:
                pytrends.build_payload([kw], cat=cat_code, timeframe=tf_code, geo=geo_code, gprop=gprop_code)
                df = pytrends.interest_over_time()
                trends_url = self._build_google_trends_url(kw, tf_code, geo_code, gprop_code)
                
                if df.empty:
                    self.progress_signal.emit({
                        "Keyword": kw, "Country": self.geo, "Time Period": self.timeframe,
                        "Category": self.category, "Property": self.gprop, "Word Count": len(kw.split()),
                        "Character Count": len(kw), "Total Average": 0, "Trend Slope": 0, "Trending Spike": 0,
                        "RawData": [],
                        "GoogleTrendsUrl": trends_url
                    })
                else:
                    if kw not in df.columns:
                        values = np.array([], dtype=float)
                        raw_points = []
                    else:
                        series = df[kw].astype(float)
                        values = series.values
                        raw_points = [
                            {
                                "date": point_date.strftime("%Y-%m-%d"),
                                "value": float(val)
                            }
                            for point_date, val in series.items()
                        ]

                    total_avg = round(np.mean(values), 2) if len(values) > 0 else 0.0
                    
                    x = np.arange(len(values))
                    try:
                        slope = np.polyfit(x, values, 1)[0]
                        slope = round(slope, 3)
                    except Exception:
                        slope = 0.0
                        
                    if len(values) >= 30:
                        last_30_avg = np.mean(values[-30:])
                        last_7_max = np.max(values[-7:])
                        spike = round(last_7_max - last_30_avg, 2)
                    elif len(values) > 0:
                        last_7_max = np.max(values[-min(7, len(values)):])
                        spike = round(last_7_max - np.mean(values), 2)
                    else:
                        spike = 0.0
                        
                    if spike < 0:
                        spike = 0.0
                        
                    self.progress_signal.emit({
                        "Keyword": kw, "Country": self.geo, "Time Period": self.timeframe,
                        "Category": self.category, "Property": self.gprop, "Word Count": len(kw.split()),
                        "Character Count": len(kw), "Total Average": total_avg, "Trend Slope": slope, "Trending Spike": spike,
                        "RawData": raw_points,
                        "GoogleTrendsUrl": trends_url
                    })
                    
                idx += 1 
                
                if idx < len(self.keywords) and self.is_running:
                    time.sleep(0.01) 
                        
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate limit" in err_str or "too many requests" in err_str:
                    wait_time = random.randint(15, 25)
                    if hasattr(self, 'status_signal'):
                        self.status_signal.emit(f"Rate limit reached! Waiting {wait_time}s before retrying '{kw}'...")
                    for _ in range(wait_time * 10):
                        if not self.is_running:
                            break
                        time.sleep(0.1)
                else:
                    self.error_signal.emit(f"Error fetching '{kw}': {str(e)}")
                    idx += 1 
                
        self.finished_signal.emit()
