import os, sys, time, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app.core.hiring_search as hs

API = os.environ.get("RF_API", "https://revenueforge-api.onrender.com")
TOKEN = os.environ.get("HOME_WORKER_TOKEN", "rf-home-1")
CAND = ["search_more","search_reddit_subs","search_rss_all","search_indeed","search_reddit","search_remotive_cats","search_hn"]
FNS = [getattr(hs, n) for n in CAND if callable(getattr(hs, n, None))]
print("home worker sources:", [f.__name__ for f in FNS], flush=True)

def fetch(q):
    out=[]
    for fn in FNS:
        try: out += fn(query=q, limit=3)
        except Exception: pass
    seen=set(); ded=[]
    for r in out:
        if r.get("url") and r["url"] not in seen: seen.add(r["url"]); ded.append(r)
    return ded

print("🏠 Home worker running on YOUR home IP. Ctrl-C to stop.", flush=True)
while True:
    try:
        r = requests.get(API+"/api/home/poll", params={"token":TOKEN}, timeout=15).json()
        q = r.get("query")
        if q:
            items = fetch(q)
            requests.post(API+"/api/home/results", params={"token":TOKEN}, json={"query":q,"results":items}, timeout=15)
            print(f"[home] {q}: {len(items)} blocked-source jobs sent", flush=True)
    except Exception as e:
        print("poll error:", e, flush=True)
    time.sleep(5)
