from playwright.sync_api import sync_playwright

BASE = "https://silentgoodbyelabs.github.io/revenueforge"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width":390,"height":844},
        record_video_dir="videos", record_video_size={"width":390,"height":844},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
    page = ctx.new_page()

    def go(url, ms): page.goto(url); page.wait_for_timeout(ms)
    def click(sel, ms=1000):
        try: page.click(sel, timeout=4000); page.wait_for_timeout(ms)
        except Exception: print("skip", sel)
    def nav(v, ms=1400):
        click("#burger", 500)
        click('.nav-i[data-view="%s"]' % v, ms)

    go(BASE+"/index.html", 1800)
    go(BASE+"/pricing.html", 1800)
    go(BASE+"/marketplace.html", 1800)

    go(BASE+"/portal.html?authed=admin@gmail.com", 3000)
    if "login" in page.url: go(BASE+"/portal.html?authed=admin@gmail.com", 3000)

    # Seed config LOCALLY only (so Run works) — does NOT touch your server data
    page.evaluate("localStorage.setItem('rf_cfg::admin@gmail.com', JSON.stringify({skills:'python automation, web scraping, data entry', target:'startups & agencies'}))")

    page.mouse.wheel(0,400); page.wait_for_timeout(700); page.mouse.wheel(0,-400); page.wait_for_timeout(400)

    nav("eng")
    try:
        page.fill("#skills","python automation, web scraping, data entry"); page.wait_for_timeout(400)
        page.fill("#target","startups & agencies"); page.wait_for_timeout(400)
    except Exception: pass
    click("#runBtn", 4000)      # engine runs -> jobs appear

    click("[data-j]", 1000); click("#closeM", 500)

    nav("serv"); page.mouse.wheel(0,300); page.wait_for_timeout(600)
    click("#servBody .plat", 800); click("#shareClose", 400)

    nav("social"); click("[data-spl]", 800); click("#shareClose", 400)

    nav("pros")
    try:
        page.fill("#pr_name","Demo Client"); page.fill("#pr_note","interested in automation")
        page.wait_for_timeout(300); click("#prBtn",800)
    except Exception: pass

    nav("ana",1300); nav("plan",1600); nav("set",1000); nav("help",1000); nav("ov",1300)

    vid = page.video.path(); ctx.close(); browser.close()
    print("VIDEO SAVED:", vid)
