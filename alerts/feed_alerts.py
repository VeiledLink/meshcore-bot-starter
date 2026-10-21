#!/usr/bin/env python3
"""Optional add-on: post new earthquakes and weather alerts near you to a channel.

Every few minutes (alerts/feed-alerts.timer) this checks two free public feeds
and posts anything new for your area through RemoteTerm:

  earthquakes     USGS, last hour - within radius_mi and at least min_magnitude
  weather alerts  National Weather Service, active alerts for your lat/lon

Settings: alerts/settings.json (copy settings.example.json). Nothing is posted
the first time it runs - it only notes what's already out there, so a fresh
install doesn't dump a pile of old alerts on the channel.

    python3 alerts/feed_alerts.py            check once and post what's new
    python3 alerts/feed_alerts.py --dry-run  print what it would post, send nothing

RemoteTerm address: REMOTETERM_URL (default http://127.0.0.1:8000).
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SETTINGS_FILE = HERE / "settings.json"
STATE_FILE = HERE / "seen.json"
API = os.environ.get("REMOTETERM_URL", "http://127.0.0.1:8000").rstrip("/") + "/api"

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
NWS_URL = "https://api.weather.gov/alerts/active?point={lat},{lon}"
MAX_POST_BYTES = 130
KEEP_SEEN_DAYS = 7

DEFAULTS = {
    "channel": "#alerts",
    "lat": 37.30,
    "lon": -120.48,
    "radius_mi": 100,
    "min_magnitude": 2.5,
    "earthquakes": True,
    "weather": True,
    # NWS asks every app to identify itself; put a way to reach you here
    "contact": "meshcore-bot-starter",
}


def load_settings():
    s = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        s.update(json.loads(SETTINGS_FILE.read_text()))
    return s


def get_json(url, contact):
    req = urllib.request.Request(url, headers={"User-Agent": f"meshcore-bot-starter ({contact})",
                                               "Accept": "application/geo+json, application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def fit(text, limit=MAX_POST_BYTES):
    raw = text.encode()
    return text if len(raw) <= limit else raw[: limit - 3].decode("utf-8", "ignore").rstrip() + "..."


# ---------------------------------------------------------------- feeds

def quake_posts(feed, s):
    """[(id, text)] for quakes in the USGS feed that are close and big enough."""
    out = []
    for f in feed.get("features", []):
        p, (lon, lat, *_) = f.get("properties", {}), f["geometry"]["coordinates"]
        mag = p.get("mag")
        if mag is None or mag < s["min_magnitude"]:
            continue
        d = miles(s["lat"], s["lon"], lat, lon)
        if d > s["radius_mi"]:
            continue
        when = time.strftime("%-I:%M %p", time.localtime(p["time"] / 1000))
        out.append((f["id"], fit(f"🌎 Earthquake M{mag:.1f} {p.get('place', '')} ({d:.0f} mi away) {when}")))
    return out


def weather_posts(feed):
    """[(id, text)] for active NWS alerts at your point. Updates to an alert get
    a new id, so an upgraded warning is posted again."""
    out = []
    for f in feed.get("features", []):
        p = f.get("properties", {})
        if p.get("status") != "Actual" or p.get("messageType") == "Cancel":
            continue
        area = (p.get("areaDesc") or "").split(";")[0].strip()
        ends = p.get("ends") or p.get("expires")
        until = ""
        if ends:
            try:
                t = time.strptime(ends[:19], "%Y-%m-%dT%H:%M:%S")
                until = " until " + time.strftime("%a %-I %p", t)
            except ValueError:
                pass
        out.append((p.get("id") or f.get("id"), fit(f"⚠️ {p.get('event', 'Weather alert')}: {area}{until}")))
    return out


# ---------------------------------------------------------------- posting

def channel_key(name):
    with urllib.request.urlopen(f"{API}/channels", timeout=15) as r:
        channels = json.loads(r.read().decode())
    want = name.lstrip("#").lower()
    for c in channels:
        if str(c.get("name", "")).lstrip("#").lower() == want:
            return c["key"]
    raise SystemExit(f"channel {name} not found in RemoteTerm - add it there first")


def post(key, text):
    req = urllib.request.Request(f"{API}/messages/channel", method="POST",
                                 data=json.dumps({"channel_key": key, "text": text}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def load_seen():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None                     # first run


def save_seen(seen):
    cutoff = time.time() - KEEP_SEEN_DAYS * 86400
    STATE_FILE.write_text(json.dumps({k: t for k, t in seen.items() if t > cutoff}))


def main():
    dry = "--dry-run" in sys.argv
    s = load_settings()
    found = []
    if s["earthquakes"]:
        try:
            found += quake_posts(get_json(USGS_URL, s["contact"]), s)
        except Exception as e:
            print("earthquake feed failed:", e)
    if s["weather"]:
        try:
            found += weather_posts(get_json(NWS_URL.format(lat=s["lat"], lon=s["lon"]), s["contact"]))
        except Exception as e:
            print("weather feed failed:", e)

    seen = load_seen()
    first_run = seen is None
    seen = seen or {}
    new = [(i, t) for i, t in found if i not in seen]
    if first_run and not dry:
        print(f"first run: noted {len(new)} current alert(s), posting only new ones from now on")
    key = None
    for i, text in new:
        if dry:
            print("WOULD POST:", text)
            continue
        if not first_run:
            key = key or channel_key(s["channel"])
            post(key, text)
            print("posted:", text)
            time.sleep(5)               # give the mesh room between posts
        seen[i] = time.time()
    if not dry:
        save_seen(seen)
    if not new:
        print("nothing new")


if __name__ == "__main__":
    main()
