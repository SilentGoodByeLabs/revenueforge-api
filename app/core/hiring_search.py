import json, re, time, urllib.parse
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)

HIRING_RE = re.compile(r"(hiring|looking for|need|seeking|wanted|help needed|job opening|position available|vacancy)", re.I)
BAD_RE = re.compile(r"(for hire|available for work|seeking work|hire me|my resume|i am a|freelancer available)", re.I)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def search_remotive(query="", limit=10):
    out = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs", timeout=10, headers=UA)
        for job in r.json().get("jobs", [])[:limit]:
            t = job.get("title", "")
            if t: out.append({"title": t[:180], "platform": "Remotive", "url": job.get("url", ""), "score": 90})
    except Exception: pass
    return out[:limit]

def search_arbeitnow(query="", limit=10):
    out = []
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=10, headers=UA)
        for job in r.json().get("data", []):
            t = job.get("title", ""); text = (t + " " + (job.get("description") or "")).lower()
            if query:
                ws = [w.lower() for w in re.split(r"[,\s]+", query) if len(w) > 2]
                if ws and not any(w in text for w in ws): continue
            if t: out.append({"title": t[:180], "platform": "Arbeitnow", "url": job.get("url", ""), "score": 85})
    except Exception: pass
    return out[:limit]

def search_reed(query="", limit=10):
    out = []
    try:
        r = requests.get("https://www.reed.co.uk/api/1.0/search?keywords=" + urllib.parse.quote(query or "hiring"), timeout=10, headers=UA)
        for job in r.json().get("results", [])[:limit]:
            t = job.get("jobTitle", "")
            if t: out.append({"title": t[:180], "platform": "Reed", "url": job.get("jobUrl", ""), "score": 80})
    except Exception: pass
    return out[:limit]

def search_reddit(query="", limit=15):
    out = []
    for sub in ["forhire", "Jobs", "WorkOnline", "slavelabour", "freelance", "HireAFreelancer"]:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/new.json", params={"limit": 25, "raw_json": 1}, headers=UA, timeout=8)
            if r.status_code != 200: continue
            for c in r.json().get("data", {}).get("children", []):
                v = c.get("data", {}); title = v.get("title", ""); body = v.get("selftext", "")
                text = title + " " + body
                if not HIRING_RE.search(text) or BAD_RE.search(title): continue
                if query:
                    ws = [w.lower() for w in re.split(r"[,\s]+", query) if len(w) > 2]
                    if ws and not any(w in text.lower() for w in ws): continue
                out.append({"title": title[:180], "platform": "Reddit", "url": "https://reddit.com" + v.get("permalink", ""), "score": 75, "author": v.get("author", "")})
        except Exception: continue
    return out[:limit]

def search_remoteok(query="", limit=10):
    out = []
    try:
        r = requests.get("https://remoteok.com/api", timeout=10, headers=UA)
        data = r.json(); items = data[1:] if isinstance(data, list) else []
        for job in items:
            t = job.get("position") or ""; u = job.get("url") or ""
            if u and not u.startswith("http"): u = "https://remoteok.com/" + u
            text = (t + " " + (job.get("description") or "")).lower()
            if query:
                ws = [w.lower() for w in re.split(r"[,\s]+", query) if len(w) > 2]
                if ws and not any(w in text for w in ws): continue
            if t and u: out.append({"title": t[:180], "platform": "RemoteOK", "url": u, "score": 85})
    except Exception: pass
    return out[:limit]

def search_hn(query="", limit=8):
    out = []
    try:
        ts = int(time.time()) - 30*86400
        q = urllib.parse.quote((query + " hiring").strip())
        r = requests.get(f"https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&numericFilters=created_at_i>{ts}", timeout=10, headers=UA)
        for h in r.json().get("hits", []):
            t = h.get("title") or ""; u = h.get("url") or ""
            if t and u and HIRING_RE.search(t) and not BAD_RE.search(t):
                out.append({"title": t[:180], "platform": "HackerNews", "url": u, "score": 75})
    except Exception: pass
    return out[:limit]

FEEDS = [
 ("WeWorkRemotely-Programming","https://weworkremotely.com/categories/remote-programming-jobs.rss"),
 ("WeWorkRemotely-Design","https://weworkremotely.com/categories/remote-design-jobs.rss"),
 ("WeWorkRemotely-Marketing","https://weworkremotely.com/categories/remote-marketing-jobs.rss"),
 ("WeWorkRemotely-Support","https://weworkremotely.com/categories/remote-customer-support-jobs.rss"),
 ("WeWorkRemotely-Sales","https://weworkremotely.com/categories/remote-sales-jobs.rss"),
 ("WeWorkRemotely-Product","https://weworkremotely.com/categories/remote-product-jobs.rss"),
 ("WeWorkRemotely-Management","https://weworkremotely.com/categories/remote-management-jobs.rss"),
 ("WeWorkRemotely-Finance","https://weworkremotely.com/categories/remote-finance-jobs.rss"),
 ("Jobspresso","https://jobspresso.co/jobs/feed/"),
 ("WorkingNomads","https://www.workingnomads.com/feed/jobs"),
 ("RemoteCo","https://remote.co/jobs/feed/"),
 ("Indeed-Hiring","https://www.indeed.com/rss?q=hiring"),
 ("Indeed-Remote","https://www.indeed.com/rss?q=remote+work"),
]
FEEDS2 = [
 ("Indeed-Cleaning","https://www.indeed.com/rss?q=cleaning"),
 ("Indeed-Design","https://www.indeed.com/rss?q=graphic+design"),
 ("Indeed-Writing","https://www.indeed.com/rss?q=content+writing"),
 ("Indeed-Assistant","https://www.indeed.com/rss?q=virtual+assistant"),
 ("Indeed-Developer","https://www.indeed.com/rss?q=developer"),
 ("Indeed-Data","https://www.indeed.com/rss?q=data+entry"),
 ("Indeed-Driver","https://www.indeed.com/rss?q=driver"),
 ("Indeed-Teacher","https://www.indeed.com/rss?q=teacher"),
]
ALL_FEEDS = FEEDS + FEEDS2
SOURCE_NAMES = [n for n,_ in ALL_FEEDS] + ["Remotive","RemoteOK","Arbeitnow","Reed","HackerNews","Reddit-forhire","Reddit-Jobs","Reddit-WorkOnline","Reddit-SlaveLabour","Reddit-freelance","Reddit-HireAFreelancer"]

def parse_rss(name, url, query="", limit=3):
    out = []
    try:
        r = requests.get(url, timeout=8, headers=UA)
        soup = BeautifulSoup(r.content, "html.parser")
        for item in soup.find_all("item")[:limit]:
            t = item.find("title").text if item.find("title") else ""
            u = item.find("link").text if item.find("link") else ""
            if not t or not u: continue
            if query:
                ws = [w.lower() for w in re.split(r"[,\s]+", query) if len(w) > 2]
                if ws and not any(w in t.lower() for w in ws): continue
            out.append({"title": t[:180], "platform": name, "url": u, "score": 80})
    except Exception: pass
    return out

def search_feeds(query="", limit=30):
    out = []
    for name, url in ALL_FEEDS:
        out.extend(parse_rss(name, url, query, 2))
    return out[:limit]


MORE_SOURCES = [
    ("Indeed US","https://www.indeed.com/rss?q={q}"),("Indeed UK","https://www.indeed.co.uk/rss?q={q}"),
    ("Indeed CA","https://ca.indeed.com/rss?q={q}"),("Indeed AU","https://au.indeed.com/rss?q={q}"),
    ("Indeed IN","https://www.indeed.co.in/rss?q={q}"),("Indeed DE","https://de.indeed.com/rss?q={q}"),
    ("Indeed FR","https://fr.indeed.com/rss?q={q}"),("Indeed ES","https://es.indeed.com/rss?q={q}"),
    ("Indeed IT","https://it.indeed.com/rss?q={q}"),("Indeed BR","https://br.indeed.com/rss?q={q}"),
    ("Indeed MX","https://mx.indeed.com/rss?q={q}"),("Indeed ZA","https://za.indeed.com/rss?q={q}"),
    ("Indeed PH","https://ph.indeed.com/rss?q={q}"),("Indeed SG","https://sg.indeed.com/rss?q={q}"),
    ("Indeed NL","https://nl.indeed.com/rss?q={q}"),("Indeed AE","https://ae.indeed.com/rss?q={q}"),
    ("Craigslist SF","https://sfbay.craigslist.org/search/cpg?format=rss"),("Craigslist NY","https://newyork.craigslist.org/search/cpg?format=rss"),
    ("Craigslist London","https://london.craigslist.org/search/cpg?format=rss"),("Craigslist Toronto","https://toronto.craigslist.org/search/cpg?format=rss"),
    ("Python Jobs","https://www.python.org/community/jobs/feed/"),
    ("WWR Programming","https://weworkremotely.com/categories/remote-programming-jobs/feed"),
    ("WWR Design","https://weworkremotely.com/categories/remote-design-jobs/feed"),
    ("WWR Marketing","https://weworkremotely.com/categories/remote-marketing-jobs/feed"),
]
def search_more(query="", limit=1):
    out=[]
    for name,url in MORE_SOURCES:
        try:
            r=requests.get(url.format(q=urllib.parse.quote(query or "hiring")), timeout=4, headers=UA)
            soup=BeautifulSoup(r.content,"html.parser"); n=0
            for item in soup.find_all("item"):
                if n>=limit: break
                t2=item.find("title"); l2=item.find("link")
                if t2 and l2: out.append({"title":t2.get_text()[:180],"platform":name,"url":l2.get_text(),"score":76}); n+=1
        except Exception: continue
    return out

REDDIT_SUBS=["forhire","Jobs","WorkOnline","slavelabour","freelance","designjobs","Hiring","remotejobs","webdev","marketing"]
def search_reddit_subs(query="", limit=1):
    out=[]
    for sub in REDDIT_SUBS:
        try:
            r=requests.get("https://www.reddit.com/r/"+sub+"/new.json?limit=5", timeout=4, headers=UA)
            for ch in r.json()["data"]["children"][:limit]:
                d=ch["data"]; t2=d.get("title","")
                if t2 and HIRING_RE.search(t2):
                    out.append({"title":t2[:180],"platform":"Reddit r/"+sub,"url":"https://reddit.com"+d.get("permalink",""),"score":74,"profile":"https://reddit.com/user/"+str(d.get("author",""))})
        except Exception: continue
    return out

def search_remotive_cats(query="", limit=3):
    out=[]
    for cat in ["software-development","design","marketing"]:
        try:
            r=requests.get("https://remotive.com/api/remote-jobs?category="+cat, timeout=5, headers=UA)
            for j in r.json().get("jobs",[])[:limit]:
                t2=j.get("title") or ""; u2=j.get("url") or ""
                if t2 and u2: out.append({"title":t2[:180],"platform":"Remotive "+cat,"url":u2,"score":80})
        except Exception: continue
    return out


def search_jobicy(query="", limit=8):
    out=[]
    try:
        r=requests.get("https://jobicy.com/api/v2/jobs?count=30", timeout=6, headers=UA)
        for j in r.json().get("jobs",[])[:limit]:
            t2=j.get("jobTitle") or j.get("title") or ""; u2=j.get("url") or j.get("jobLink") or ""
            if t2 and u2: out.append({"title":t2[:180],"platform":"Jobicy","url":u2,"score":78})
    except Exception: pass
    return out

def search_adzuna(query="", limit=10):
    import os
    app=os.environ.get("ADZUNA_APP_ID") or ""; key=os.environ.get("ADZUNA_APP_KEY") or ""
    if not app or not key: return []
    out=[]
    try:
        r=requests.get("https://api.adzuna.com/v1/api/jobs/us/search?app_id="+app+"&app_key="+key+"&results_per_page="+str(limit)+"&what="+urllib.parse.quote(query or ""), timeout=6, headers=UA)
        for j in r.json().get("results",[]):
            t2=j.get("title") or ""; u2=j.get("redirect_url") or ""
            if t2 and u2: out.append({"title":t2[:180],"platform":"Adzuna","url":u2,"score":80})
    except Exception: pass
    return out

def search_jooble(query="", limit=10):
    import os
    key=os.environ.get("JOOBLE_KEY") or ""
    if not key: return []
    out=[]
    try:
        r=requests.post("https://jooble.org/api/"+key, json={"keywords":query or "hiring"}, timeout=6, headers=UA)
        for j in r.json().get("jobs",[]):
            t2=j.get("title") or ""; u2=j.get("link") or ""
            if t2 and u2: out.append({"title":t2[:180],"platform":"Jooble","url":u2,"score":79})
    except Exception: pass
    return out

def search_hiring(query="", limit=25):
    results = []
    results.extend(search_remotive(query, 10))
    results.extend(search_arbeitnow(query, 8))
    results.extend(search_reed(query, 8))
    results.extend(search_reddit(query, 15))
    results.extend(search_remoteok(query, 8))
    results.extend(search_hn(query, 6))
    results.extend(search_feeds(query, 30))
    seen = set(); clean = []
    for r in results:
        k = r.get("url", "")
        if not k or k in seen: continue
        seen.add(k); clean.append(r)
    clean.sort(key=lambda x: x["score"], reverse=True)
    return clean[:limit]
