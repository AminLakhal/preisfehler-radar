#!/usr/bin/env python3
"""Preisfehler-Radar: liest öffentliche Deal-Feeds, erkennt Preisfehler
(Schwerpunkt Amazon), speichert sie in docs/deals.json und schickt eine
Push-Nachricht (ntfy.sh und/oder Telegram) für jeden neuen Treffer.

Nur Standardbibliothek, läuft lokal und in GitHub Actions.
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "tracker" / "config.json").read_text(encoding="utf-8"))
DEALS_FILE = ROOT / "docs" / "deals.json"
UA = "Mozilla/5.0 (compatible; Preisfehler-Radar/1.0; +https://github.com)"

KEYWORDS = re.compile(
    r"preis\s*-?\s*fehler|fehler\s*-?\s*preis|price\s*(mistake|error)|pricing\s*error|"
    r"fehlerhafte[rn]?\s+preis|preisirrtum|preis\s*glitch",
    re.I,
)
PRICE_RE = re.compile(r"(\d{1,6}(?:[.,]\d{1,2})?)\s*€")


def fetch(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,*/*"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    print(f"! Feed nicht erreichbar: {url} ({last})", file=sys.stderr)
    return None


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_price(s):
    if not s:
        return None
    m = PRICE_RE.search(s if "€" in s else s + "€")
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", ".")) if "," in m.group(1) else float(m.group(1))


def find_outlink(desc_html):
    """Direktlink zum Händler, falls im Beitrag vorhanden (z. B. amazon.de/dp/...)."""
    for m in re.finditer(r'href="(https?://[^"]+)"', desc_html or ""):
        u = html.unescape(m.group(1))
        if re.search(r"amazon\.[a-z.]+/", u) or "amzn." in u:
            return u
    return None


def parse_feed(feed, raw):
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"! Feed defekt: {feed['url']} ({e})", file=sys.stderr)
        return out
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        if not link or link.rstrip("/").count("/") < 3:
            continue
        title = clean(it.findtext("title"))
        desc_html = it.findtext("description") or ""
        merchant, price_txt = "", ""
        for child in it:
            if child.tag.endswith("}merchant") or child.tag == "merchant":
                merchant = html.unescape(child.attrib.get("name", ""))
                price_txt = child.attrib.get("price", "")
        cats = [clean(c.text) for c in it.findall("category") if c.text]
        try:
            ts = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:  # noqa: BLE001
            ts = datetime.now(timezone.utc)
        img = ""
        im = re.search(r'<img[^>]+src="([^"]+)"', desc_html)
        if im:
            img = html.unescape(im.group(1))
        text = f"{title} {clean(desc_html)}"
        is_error = feed.get("all_are_errors", False) or bool(KEYWORDS.search(text))
        if not is_error:
            continue
        outlink = find_outlink(desc_html)
        is_amazon = bool(
            re.search(r"amazon|amzn", merchant, re.I)
            or re.search(r"amazon|amzn", title, re.I)
            or (outlink and re.search(r"amazon|amzn", outlink, re.I))
        )
        price = parse_price(price_txt) or parse_price(title)
        out.append(
            {
                "id": link,
                "title": title,
                "url": link,
                "outlink": outlink,
                "merchant": merchant or ("Amazon" if is_amazon else ""),
                "amazon": is_amazon,
                "price": price,
                "price_text": price_txt or (f"{price:.2f}".replace(".", ",") + "€" if price is not None else ""),
                "category": cats[0] if cats else "",
                "image": img,
                "published": ts.isoformat(),
                "source": feed["name"],
            }
        )
    return out


def load_state():
    if DEALS_FILE.exists():
        try:
            return json.loads(DEALS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"updated": None, "deals": []}


def notify_ntfy(deal):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    price = f" für {deal['price_text']}" if deal["price_text"] else ""
    shop = deal["merchant"] or "Shop"
    headers = {
        "Title": _hdr(f"Preisfehler bei {shop}{price}"),
        "Priority": "5" if deal["amazon"] else "4",
        "Tags": "rotating_light,moneybag",
        "Click": deal["outlink"] or deal["url"],
        "Actions": _hdr(f"view, Deal ansehen, {deal['url']}"),
    }
    req = urllib.request.Request(f"{server}/{topic}", data=deal["title"].encode("utf-8"), headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=20).read()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"! ntfy fehlgeschlagen: {e}", file=sys.stderr)
        return False


def _hdr(s):
    # ntfy akzeptiert RFC-2047-codierte Header, damit Umlaute/€ erhalten bleiben
    try:
        s.encode("ascii")
        return s
    except UnicodeEncodeError:
        import base64

        return "=?UTF-8?B?" + base64.b64encode(s.encode("utf-8")).decode() + "?="


def notify_telegram(deal):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    price = f" – {deal['price_text']}" if deal["price_text"] else ""
    text = (
        f"🚨 <b>Preisfehler{' (Amazon)' if deal['amazon'] else ''}</b>{html.escape(price)}\n"
        f"{html.escape(deal['title'])}\n"
        f"Shop: {html.escape(deal['merchant'] or '?')}\n{deal['outlink'] or deal['url']}"
    )
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20).read()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"! Telegram fehlgeschlagen: {e}", file=sys.stderr)
        return False


def should_notify(deal, first_run):
    if first_run:
        return False
    age = datetime.now(timezone.utc) - datetime.fromisoformat(deal["published"])
    if age > timedelta(hours=CONFIG.get("max_age_hours_for_push", 6)):
        return False
    if CONFIG.get("notify_only_amazon", True) and not deal["amazon"]:
        return False
    return True


def main():
    state = load_state()
    first_run = not state["deals"]
    known = {d["id"]: d for d in state["deals"]}
    fresh = []
    for feed in CONFIG["feeds"]:
        raw = fetch(feed["url"])
        if raw:
            fresh.extend(parse_feed(feed, raw))

    new = []
    for d in fresh:
        if d["id"] not in known:
            known[d["id"]] = d
            new.append(d)

    # älteste zuerst, damit Pushes in richtiger Reihenfolge ankommen
    new.sort(key=lambda d: d["published"])
    sent = 0
    for d in new:
        if should_notify(d, first_run):
            ok = notify_ntfy(d) | notify_telegram(d)
            d["notified"] = bool(ok)
            sent += int(bool(ok))
        else:
            d["notified"] = False

    keep_days = CONFIG.get("keep_days", 14)
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    deals = [d for d in known.values() if datetime.fromisoformat(d["published"]) >= cutoff]
    deals.sort(key=lambda d: d["published"], reverse=True)
    deals = deals[: CONFIG.get("max_deals", 300)]

    # updated nur ändern, wenn sich Inhalt ändert -> keine unnötigen Commits
    changed = bool(new) or len(deals) != len(state["deals"])
    out = {"updated": datetime.now(timezone.utc).isoformat() if changed else state["updated"], "deals": deals}
    DEALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEALS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(fresh)} Treffer in Feeds, {len(new)} neu, {sent} Push gesendet" + (" (Erstlauf: kein Push)" if first_run else ""))


if __name__ == "__main__":
    main()
