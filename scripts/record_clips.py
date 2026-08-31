import shutil
from playwright.sync_api import sync_playwright

BASE = "https://silentgoodbyelabs.github.io/revenueforge"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    def make_clip(name, fn):
        ctx = browser.new_context(viewport={"width":390,"height":844},
            record_video_dir="videos", record_video_size={"width":390,"height":844}, user_agent=UA)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        def go(u,ms): page.goto(u); page.wait_for_timeout(ms)
        def click(sel,ms=900):
            try: page.click(sel,timeout=4000); page.wait_for_timeout(ms)
            except Exception: print("skip",sel)
        def nav(v,ms=1200): click("#burger",400); click('.nav-i[data-view="%s"]'%v,ms)
        def login():
            go(BASE+"/portal.html?authed=admin@gmail.com",2500)
            if "login" in page.url: go(BASE+"/portal.html?authed=admin@gmail.com",2500)
        fn(go,click,nav,login,page)
        v = page.video.path(); ctx.close()
        shutil.copy(v, "videos/clip_%s.webm"%name)
        print("clip", name, "saved")

    # 1) ENGINE: finds hiring jobs + writes proposal
    def clip_engine(go,click,nav,login,page):
        login()
        page.evaluate("localStorage.setItem('rf_cfg::admin@gmail.com',JSON.stringify({skills:'python automation, web scraping',target:'startups & agencies'}))")
        nav("eng"); 
        try: page.fill("#skills","python automation, web scraping"); page.fill("#target","startups & agencies"); page.wait_for_timeout(400)
        except Exception: pass
        click("#runBtn",3500); click("[data-j]",900); click("#closeM",400)
    make_clip("engine", clip_engine)

    # 2) SELL: publish -> live + advertise + share -> delete (cleanup)
    def clip_sell(go,click,nav,login,page):
        login(); nav("serv")
        try:
            page.fill("#sv_name","Demo Automation Service"); page.fill("#sv_price","150")
            page.fill("#sv_desc","I automate your busywork."); page.wait_for_timeout(300)
        except Exception: pass
        click("#pubBtn",1500)
        click("#servBody [data-ad]",1200)          # Advertise
        click("#servBody .plat",800); click("#shareClose",400)
        click("#servBody [data-del]",1000)          # delete (cleanup)
    make_clip("sell", clip_sell)

    # 3) PLANS: billing + pricing
    def clip_plans(go,click,nav,login,page):
        login(); nav("plan",1600); page.mouse.wheel(0,400); page.wait_for_timeout(700)
        go(BASE+"/pricing.html",2000); page.mouse.wheel(0,500); page.wait_for_timeout(800)
    make_clip("plans", clip_plans)

    # 4) TRACK: prospects + analytics
    def clip_track(go,click,nav,login,page):
        login(); nav("pros")
        try: page.fill("#pr_name","Demo Client"); page.fill("#pr_note","wants automation"); page.wait_for_timeout(300); click("#prBtn",800)
        except Exception: pass
        nav("ana",1500); page.mouse.wheel(0,300); page.wait_for_timeout(600)
    make_clip("track", clip_track)

    browser.close()
print("ALL CLIPS DONE")
