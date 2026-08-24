import json, re, time, urllib.parse
import requests
from bs4 import BeautifulSoup

HIRING_RE = re.compile(
    r"(hiring|looking for|need|seeking|wanted|help needed|job opening|position available)",
    re.I
)

BAD_RE = re.compile(
    r"(for hire|available for work|seeking work|hire me|my resume|i am a|freelancer available)",
    re.I
)

def search_remotive(query="", limit=10):
    """Search Remotive API (free, no key needed, real remote jobs)."""
    results = []
    
    url = "https://remotive.com/api/remote-jobs"
    params = {}
    if query:
        params["search"] = query
    params["limit"] = limit
    
    try:
        r = requests.get(url, params=params, timeout=10, headers={
            "User-Agent": "RevenueForge/1.0"
        })
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", [])
            
            for job in jobs[:limit]:
                title = job.get("title", "")
                if title:
                    results.append({
                        "title": title[:180],
                        "platform": "Remotive",
                        "url": job.get("url", ""),
                        "score": 90,
                        "company": job.get("company_name", "")
                    })
    except Exception as e:
        pass
    
    return results[:limit]

def search_arbeitnow(query="", limit=10):
    """Search Arbeitnow API (free, European jobs)."""
    results = []
    
    url = "https://www.arbeitnow.com/api/job-board-api"
    
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "RevenueForge/1.0"
        })
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("data", [])
            
            for job in jobs:
                title = job.get("title", "")
                description = job.get("description", "")
                text = (title + " " + description).lower()
                
                # Filter by query if provided
                if query:
                    qwords = [w.lower() for w in re.split(r"[,\s]+", query) if len(w) > 2]
                    if qwords and not any(w in text for w in qwords):
                        continue
                
                if title:
                    results.append({
                        "title": title[:180],
                        "platform": "Arbeitnow",
                        "url": job.get("url", ""),
                        "score": 85,
                        "company": job.get("company_name", "")
                    })
    except:
        pass
    
    return results[:limit]

def search_reed(query="", limit=10):
    """Search Reed API (free UK jobs, no key for basic)."""
    results = []
    
    if not query:
        query = "hiring"
    
    url = f"https://www.reed.co.uk/api/1.0/search?keywords={urllib.parse.quote(query)}&minimumSalary=0&maximumSalary=100000&permanent=true&contract=true&temporary=true&partTime=true&fullTime=true&graduate=true&apprenticeship=true&resultsToTake=20"
    
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "RevenueForge/1.0"
        })
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("results", [])
            
            for job in jobs[:limit]:
                title = job.get("jobTitle", "")
                if title:
                    results.append({
                        "title": title[:180],
                        "platform": "Reed",
                        "url": job.get("jobUrl", ""),
                        "score": 80,
                        "company": job.get("employerName", "")
                    })
    except:
        pass
    
    return results[:limit]

def search_reddit(query="", limit=15):
    """Search Reddit r/forhire and job subreddits."""
    results = []
    
    # Multiple subreddits
    subs = ["forhire", "Jobs", "WorkOnline", "slavelabour", "HireAFreelancer"]
    
    for sub in subs:
        url = f"https://www.reddit.com/r/{sub}/new.json"
        params = {"limit": 25, "raw_json": 1}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            r = requests.get(url, params=params, headers=headers, timeout=8)
            if r.status_code != 200:
                continue
                
            data = r.json()
            children = data.get("data", {}).get("children", [])
            
            for c in children:
                v = c.get("data", {})
                title = v.get("title", "")
                body = v.get("selftext", "")
                text = title + " " + body
                
                # Must be hiring
                if not HIRING_RE.search(text):
                    continue
                
                # Skip "for hire" freelancers
                if BAD_RE.search(title):
                    continue
                
                # Filter by query
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
            continue
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def search_remoteok(query="", limit=10):
    results = []
    try:
        r = requests.get("https://remoteok.com/api", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        items = data[1:] if isinstance(data, list) else []
        for job in items:
            title = job.get("position") or ""
            url = job.get("url") or ""
            if url and not url.startswith("http"): url = "https://remoteok.com/" + url
            desc = job.get("description") or ""
            text = (title + " " + desc).lower()
            if query:
                ws = [w.lower() for w in re.split(r"[,\s]+", query) if len(w) > 2]
                if ws and not any(w in text for w in ws): continue
            if title and url: results.append({"title": title[:180], "platform": "RemoteOK", "url": url, "score": 85})
    except Exception: pass
    return results[:limit]

def search_hn(query="", limit=8):
    results = []
    try:
        ts = int(time.time()) - 30*86400
        q = urllib.parse.quote((query + " hiring").strip())
        r = requests.get(f"https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&numericFilters=created_at_i>{ts}", timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        for h in r.json().get("hits", []):
            t2 = h.get("title") or ""; u2 = h.get("url") or ""
            if t2 and u2 and HIRING_RE.search(t2) and not BAD_RE.search(t2):
                results.append({"title": t2[:180], "platform": "HackerNews", "url": u2, "score": 75})
    except Exception: pass
    return results[:limit]

def search_indeed(query="", limit=10):
    results = []
    try:
        r = requests.get("https://www.indeed.com/rss?q=" + urllib.parse.quote(query or "hiring"), timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.content, "html.parser")
        for item in soup.find_all("item")[:limit]:
            t2 = item.find("title").text if item.find("title") else ""
            u2 = item.find("link").text if item.find("link") else ""
            if t2 and u2: results.append({"title": t2[:180], "platform": "Indeed", "url": u2, "score": 80})
    except Exception: pass
    return results[:limit]

def search_hiring(query="", limit=25):
    """Main search: combines multiple sources."""
    results = []
    
    # Try each source
    results.extend(search_remotive(query, limit=10))
    results.extend(search_arbeitnow(query, limit=10))
    results.extend(search_reed(query, limit=10))
    results.extend(search_reddit(query, limit=15))
    results.extend(search_remoteok(query, limit=10))
    results.extend(search_hn(query, limit=8))
    results.extend(search_indeed(query, limit=10))
    
    # Deduplicate by URL
    seen = set()
    clean = []
    for r in results:
        key = r.get("url", "")
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append(r)
    
    clean.sort(key=lambda x: x["score"], reverse=True)
    return clean[:limit]
