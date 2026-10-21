#!/usr/bin/env python3
"""Optional add-on: post new alerts near you to a channel.

Every few minutes (alerts/feed-alerts.timer) this checks free public feeds and
posts anything new for your area through RemoteTerm. Each can be turned off in
settings:

  earthquakes    USGS, last hour - within radius_mi and at least min_magnitude
  weather        National Weather Service - active alerts for your lat/lon (US)
  fires          National wildfire map (WFIGS) - new wildfires within fire_radius_mi
                 of at least min_fire_acres
  air_quality    AirNow - the nearest reporting area reaching min_aqi (US)
  rivers         NOAA river gauges within river_radius_mi at flood stage or above
  space_weather  NOAA - geomagnetic storms of at least min_kp (aurora, GPS/HF trouble)

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
FIRE_URL = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
            "WFIGS_Incident_Locations_Current/FeatureServer/0/query")
AIRNOW_URL = "https://files.airnowtech.org/airnow/today/reportingarea.dat"
RIVER_URL = "https://api.water.noaa.gov/nwps/v1/gauges"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
MAX_POST_BYTES = 130
FORGET_AFTER_DAYS = 7           # an alert not in any feed for this long can be posted again

DEFAULTS = {
    "channel": "#alerts",
    "lat": 37.30,
    "lon": -120.48,
    "earthquakes": True,
    "radius_mi": 100,
    "min_magnitude": 2.5,
    "weather": True,
    "fires": True,
    "fire_radius_mi": 75,
    "min_fire_acres": 10,
    "air_quality": True,
    "min_aqi": 151,             # 151+ = "Unhealthy"; 101+ = "Unhealthy for Sensitive Groups"
    "rivers": True,
    "river_radius_mi": 50,
    "space_weather": True,
    "min_kp": 7,                # Kp 7 = strong (G3) storm; 5 = minor (G1)
    # NWS asks every app to identify itself; put a way to reach you here
    "contact": "meshcore-bot-starter",
}


def load_settings():
    s = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        s.update(json.loads(SETTINGS_FILE.read_text()))
    return s


def fetch(url, contact, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": f"meshcore-bot-starter ({contact})",
                                               "Accept": "application/geo+json, application/json, */*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode("utf-8", "replace")
    return body if raw else json.loads(body)


def miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def box(lat, lon, radius_mi):
    """(west, south, east, north) around a point - feeds that want a map box."""
    dlat = radius_mi / 69.0
    dlon = radius_mi / (69.0 * max(math.cos(math.radians(lat)), 0.1))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def fit(text, limit=MAX_POST_BYTES):
    raw = text.encode()
    return text if len(raw) <= limit else raw[: limit - 3].decode("utf-8", "ignore").rstrip() + "..."


def today():
    return time.strftime("%Y-%m-%d")


# ---------------------------------------------------------------- feeds
# Each returns [(id, text)]. The id decides "new": the same id is posted once.

def quake_posts(feed, s):
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
    """Updates to an alert get a new id, so an upgraded warning is posted again."""
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


def fire_url(s):
    w, so, e, n = box(s["lat"], s["lon"], s["fire_radius_mi"])
    q = {"where": "IncidentTypeCategory='WF'", "geometry": f"{w},{so},{e},{n}",
         "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326, "f": "json",
         "outFields": "UniqueFireIdentifier,IncidentName,IncidentSize,PercentContained,POOCounty"}
    return FIRE_URL + "?" + urllib.parse.urlencode(q)


def fire_posts(feed, s):
    """One post per fire, the first time it's at least min_fire_acres (not once it's fully contained)."""
    out = []
    for f in feed.get("features", []):
        a, g = f.get("attributes", {}), f.get("geometry") or {}
        acres = a.get("IncidentSize") or 0
        if acres < s["min_fire_acres"] or "x" not in g or (a.get("PercentContained") or 0) >= 100:
            continue
        d = miles(s["lat"], s["lon"], g["y"], g["x"])
        if d > s["fire_radius_mi"]:
            continue
        name = (a.get("IncidentName") or "").strip().title()
        county = f", {a['POOCounty']} Co" if a.get("POOCounty") else ""
        cont = f", {a['PercentContained']:.0f}% contained" if a.get("PercentContained") is not None else ""
        out.append((f"fire|{a.get('UniqueFireIdentifier')}",
                     fit(f"🔥 {name} Fire{county}: {acres:,.0f} acres{cont} ({d:.0f} mi away)")))
    return out


def air_posts(text, s):
    """AirNow's daily file, one line per area and pollutant (| separated). Uses the
    nearest area's current readings; posts once per day per level reached."""
    rows = []
    for line in text.splitlines():
        f = line.split("|")
        if len(f) < 14 or f[5] != "O":          # O = observed now (F = forecast)
            continue
        try:
            rows.append((miles(s["lat"], s["lon"], float(f[9]), float(f[10])), f[7], f[8], f[11], int(f[12]), f[13]))
        except ValueError:
            continue
    if not rows:
        return []
    nearest = min(rows)[0]
    if nearest > 60:
        return []
    worst = max((r for r in rows if r[0] == nearest), key=lambda r: r[4])
    _, area, state, pollutant, aqi, category = worst
    if aqi < s["min_aqi"]:
        return []
    return [(f"aqi|{area}|{today()}|{category}",
             fit(f"😷 Air quality {category}: AQI {aqi} ({pollutant}) in {area}, {state}"))]


FLOOD_LEVELS = {"action": "near flood stage", "minor": "minor flooding",
                "moderate": "moderate flooding", "major": "major flooding"}


def river_url(s):
    w, so, e, n = box(s["lat"], s["lon"], s["river_radius_mi"])
    return RIVER_URL + "?" + urllib.parse.urlencode({"bbox.xmin": w, "bbox.ymin": so, "bbox.xmax": e,
                                                     "bbox.ymax": n, "srid": "EPSG_4326"})


def river_posts(feed, s):
    """Gauges at flood stage now (observed); posted again if it gets worse."""
    out = []
    for g in feed.get("gauges", []):
        obs = ((g.get("status") or {}).get("observed") or {})
        level = obs.get("floodCategory")
        if level not in FLOOD_LEVELS:
            continue
        if miles(s["lat"], s["lon"], g["latitude"], g["longitude"]) > s["river_radius_mi"]:
            continue
        out.append((f"river|{g['lid']}|{level}|{today()}",
                    fit(f"🌊 {g['name']}: {FLOOD_LEVELS[level]}, {obs.get('primary')} {obs.get('primaryUnit', '')}")))
    return out


def kp_posts(rows, s):
    """NOAA's planetary K-index, every 3 hours. One post per day per storm level."""
    if not rows:
        return []
    last = rows[-1]
    kp = float(last["Kp"] if isinstance(last, dict) else last[1])
    if kp < s["min_kp"]:
        return []
    level = f"G{min(int(kp) - 4, 5)} " if kp >= 5 else ""     # Kp 5 = G1 ... Kp 9 = G5
    return [(f"kp|{today()}|{int(kp)}",
             fit(f"🌌 Geomagnetic storm {level}(Kp {kp:.0f}): aurora possible, GPS/HF may be off"))]


def check_all(s):
    """[(id, text)] from every feed that's turned on. A feed that fails is skipped."""
    feeds = [
        ("earthquakes", lambda: quake_posts(fetch(USGS_URL, s["contact"]), s)),
        ("weather", lambda: weather_posts(fetch(NWS_URL.format(lat=s["lat"], lon=s["lon"]), s["contact"]))),
        ("fires", lambda: fire_posts(fetch(fire_url(s), s["contact"]), s)),
        ("air_quality", lambda: air_posts(fetch(AIRNOW_URL, s["contact"], raw=True), s)),
        ("rivers", lambda: river_posts(fetch(river_url(s), s["contact"]), s)),
        ("space_weather", lambda: kp_posts(fetch(KP_URL, s["contact"]), s)),
    ]
    found = []
    for name, run in feeds:
        if not s.get(name):
            continue
        try:
            found += run()
        except Exception as e:
            print(f"{name} feed failed: {e}")
    return found


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
    cutoff = time.time() - FORGET_AFTER_DAYS * 86400
    STATE_FILE.write_text(json.dumps({k: t for k, t in seen.items() if t > cutoff}))


def main():
    dry = "--dry-run" in sys.argv
    s = load_settings()
    found = check_all(s)

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
    if not dry:
        now = time.time()
        for i, _ in found:              # still in a feed: keep remembering it (a fire can last weeks)
            seen[i] = now
        save_seen(seen)
    if not new:
        print("nothing new")


if __name__ == "__main__":
    main()
