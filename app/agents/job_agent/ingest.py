import json
import xml.etree.ElementTree as ET

import requests

from app.core.config import CONFIG_DIR


def load_sources():
    p = CONFIG_DIR / "sources.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("sources", [])


def fetch_feed(url, timeout=20):
    headers = {"User-Agent": "RevenueForge/1.0 (local research tool)"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.content


def parse_rss(xml_bytes):
    items = []
    root = ET.fromstring(xml_bytes)
    for item in root.iter("item"):
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "description": (item.findtext("description") or "").strip(),
        })
    if not items:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("a:entry", ns):
            link_el = entry.find("a:link", ns)
            items.append({
                "title": (entry.findtext("a:title", namespaces=ns) or "").strip(),
                "link": (link_el.get("href") if link_el is not None else ""),
                "description": (entry.findtext("a:summary", namespaces=ns) or entry.findtext("a:content", namespaces=ns) or "").strip(),
            })
    return items
