import json, re, time, urllib.parse
import requests
from bs4 import BeautifulSoup

HIRING_RE = re.compile(
    r"(hiring|looking for|need|seeking|wanted|help needed)",
    re.I
)

BAD_RE = re.compile(
    r"(for hire|available for work|seeking work|hire me)",
    re.I
)

def _clean_title(title):
    """Clean and validate job title."""
    if not title:
        return None
    title = title.strip()
    if len(title) < 10:
        return None
    if BAD_RE.search(title):
        return None
    return title[:180]

def search_adzuna(query="", limit=10):
    """Search Adzuna API (free, real jobs)."""
    results = []
    if not query:
        query = "hiring"
    
    # Adzuna free API
    url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
    params = {
        "app_id": "test",
        "app_key": "test", 
        "what": query,
        "results_per_page": limit,
        "content-type": "application/json"
    }
    
    try:
        r = requests.get(url, params=params, timeout=8)
        if r.status_code == 200:
            data = r.json()
            for job in data.get("results", []):
                title = job.get("title", "")
                if title and HIRING_RE.search(title):
                    results.append({
                        "title": title,
                        "platform": "Adzuna",
                        "url": job.get("redirect_url", ""),
                        "score": 85,
                        "description": job.get("description", "")[:200]
                    })
    except:
        pass
    
    return results[:limit]

def search_indeed_rss(query="", limit=10):
    """Search Indeed via RSS feed."""
    results = []
    if not query:
        query = "hiring"
    
    url = f"https://www.indeed.com/rss?q={urllib.parse.quote(query)}&l="
    
    try:
        r = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "html.parser")
            items = soup.find_all("item")[:limit]
            
            for item in items:
                title = item.find("title").text if item.find("title") else ""
                link = item.find("link").text if item.find("link") else ""
                
                if title and link and HIRING_RE.search(title):
                    results.append({
                        "title": title,
                        "platform": "Indeed",
                        "url": link,
                        "score": 80
                    })
    except:
        pass
    
    return results[:limit]

def search_reddit(query="", limit=15):
    """Search Reddit with proper headers."""
    results = []
    
    url = "https://www.reddit.com/r/forhire+Jobs+WorkOnline+slavelabour/new.json"
    params = {"limit": 50, "raw_json": 1}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            children = data.get("data", {}).get("children", [])
            
            for c in children:
                v = c.get("data", {})
                title = v.get("title", "")
                body = v.get("selftext", "")
                text = title + " " + body
                
                if not HIRING_RE.search(text):
                    continue
                if BAD_RE.search(title):
                    continue
                
                # If query specified, prefer matches
                if query:
                    qwords = [w.lower() for w in re.split(r"[,\s]+", query) if len(w) > 2]
                    if qwords and not any(w in text.lower() for w in qwords):
                        continue
                
                permalink = v.get("permalink", "")
                results.append({
                    "title": title[:180],
                    "platform": "Reddit",
                    "url": "https://reddit.com" + permalink,
                    "score": 75
                })
    except:
        pass
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

def search_hn(query="", limit=8):
    """Search HackerNews."""
    results = []
    
    ts = int(time.time()) - 30 * 86400
    search_q = urllib.parse.quote((query + " hiring").strip() if query else "hiring")
    url = f"https://hn.algolia.com/api/v1/search_by_date?query={search_q}&tags=story&numericFilters=created_at_i>{ts}"
    
    try:
        r = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        if r.status_code == 200:
            data = r.json()
            for h in data.get("hits", []):
                title = h.get("title", "")
                url2 = h.get("url", "")
                
                if not title or not url2:
                    continue
                if not HIRING_RE.search(title):
                    continue
                if BAD_RE.search(title):
                    continue
                
                results.append({
                    "title": title[:180],
                    "platform": "HackerNews",
                    "url": url2,
                    "score": 70
                })
    except:
        pass
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

def search_hiring(query="", limit=25):
    """Main search: finds hiring posts for ANY work."""
    results = []
    
    # Try multiple sources
    results.extend(search_adzuna(query, limit=10))
    results.extend(search_indeed_rss(query, limit=10))
    results.extend(search_reddit(query, limit=15))
    results.extend(search_hn(query, limit=8))
    
    # Deduplicate
    seen = set()
    clean = []
    for r in results:
        key = r.get("url", "")
        if key in seen or not key:
            continue
        seen.add(key)
        clean.append(r)
    
    clean.sort(key=lambda x: x["score"], reverse=True)
    return clean[:limit]
