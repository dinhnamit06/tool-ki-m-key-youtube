import webbrowser
import urllib.parse

def web_search(engine, keyword):
    if not keyword:
        return
        
    encoded_kw = urllib.parse.quote_plus(keyword)
    url = ""
    
    if engine == "Google Trends":
        encoded_kw_trends = urllib.parse.quote(keyword)
        url = f"https://trends.google.com/trends/explore?q={encoded_kw_trends}"
    elif engine == "Google Search":
        url = f"https://www.google.com/search?q={encoded_kw}"
    elif engine == "YouTube Search":
        url = f"https://www.youtube.com/results?search_query={encoded_kw}"
    elif engine == "Bing Search":
        url = f"https://www.bing.com/search?q={encoded_kw}"
    elif engine == "Amazon":
        url = f"https://www.amazon.com/s?k={encoded_kw}"
    elif engine == "eBay":
        url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_kw}"
        
    if url:
        webbrowser.open(url)
