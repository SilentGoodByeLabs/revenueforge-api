from playwright.sync_api import sync_playwright
BASE="https://silentgoodbyelabs.github.io/revenueforge"
R=[]
def ok(n,c): R.append((n,c)); print(("PASS " if c else "FAIL ")+n)
with sync_playwright() as p:
    b=p.chromium.launch(headless=True); ctx=b.new_context(); pg=ctx.new_page()
    pg.goto(BASE+"/login.html"); ok("login loads w/ email+password", pg.locator("input[type=email]").count()>0 and pg.locator("input[type=password]").count()>0)
    pg.goto(BASE+"/signup.html"); ok("signup loads w/ captcha or form", pg.locator("form").count()>0)
    pg.goto(BASE+"/contact.html"); ok("contact page 200 + form", pg.locator("#ms").count()>0)
    pg.goto(BASE+"/audit.html"); pg.fill("#sk","test"); pg.click("#go"); pg.wait_for_timeout(2500)
    ok("audit shows results without redirect", pg.locator("#out").inner_text()!="")
    pg.goto(BASE+"/portal.html?authed=admin@gmail.com"); pg.wait_for_timeout(2500)
    ok("portal logged in (sidebar)", pg.locator(".nav-i").count()>=10)
    pg.click("#supBtn"); pg.fill("#supIn","how do I use it"); pg.click("#supSend"); pg.wait_for_timeout(600)
    txt=pg.locator("#supMsgs").inner_text(); ok("bot answers 'how do I use it' specifically", "Quick start" in txt)
    
    # Navigate to a view, then use back button
    pg.click("#burger"); pg.wait_for_timeout(300); pg.click('.nav-i[data-view="eng"]'); pg.wait_for_timeout(500)
    ok("nav -> eng", pg.locator("#view-eng").is_visible())
    
    # Go to another view
    pg.click("#burger"); pg.wait_for_timeout(300); pg.click('.nav-i[data-view="jobs"]'); pg.wait_for_timeout(500)
    ok("nav -> jobs", pg.locator("#view-jobs").is_visible())
    
    # Use browser back button - should go back to eng (or stay in portal)
    pg.go_back(); pg.wait_for_timeout(1000)
    # Check we're still in portal (not logged out)
    still_in_portal = "portal" in pg.url and "login" not in pg.url
    ok("back button keeps you in portal (doesn't log out)", still_in_portal)
    
    # Test other navigation
    for v in ["serv","social","pros","ana","plan","set","help"]:
        pg.click("#burger"); pg.wait_for_timeout(300); pg.click('.nav-i[data-view="%s"]'%v); pg.wait_for_timeout(500)
        ok("nav -> "+v, pg.locator("#view-"+v).is_visible())
    
    b.close()
print("\nSUMMARY:", sum(1 for _,c in R if c), "passed /", len(R))
