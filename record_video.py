from playwright.sync_api import sync_playwright
import os
os.makedirs('videos', exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={'width':1280,'height':800},
                        record_video_dir='videos', record_video_size={'width':1280,'height':800})
    page = ctx.new_page()
    page.goto('https://silentgoodbyelabs.github.io/revenueforge/live.html')
    page.wait_for_timeout(60000)   # let the full tour play
    ctx.close(); b.close()
print("✅ video saved in videos/")
