"""Offline tests for alerts/feed_alerts.py - made-up feed data, no network.
    python3 tests/test_alerts.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "alerts"))
import feed_alerts as fa

S = dict(fa.DEFAULTS, lat=37.30, lon=-120.48, radius_mi=100, min_magnitude=2.5)
ok = True


def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name)


def quake(qid, mag, lat, lon, place="somewhere"):
    return {"id": qid, "geometry": {"coordinates": [lon, lat, 5.0]},
            "properties": {"mag": mag, "place": place, "time": 1_760_000_000_000}}


feed = {"features": [
    quake("near", 3.1, 37.0, -120.3, "10 km E of Chowchilla, CA"),
    quake("small", 1.4, 37.0, -120.3),
    quake("far", 5.0, 34.0, -118.2),
    quake("nomag", None, 37.0, -120.3),
]}
posts = dict(fa.quake_posts(feed, S))
check("close quake above min magnitude is posted", "near" in posts and "M3.1" in posts["near"])
check("  shows distance", "mi away" in posts["near"])
check("small quake skipped", "small" not in posts)
check("far quake skipped (Los Angeles is ~230 mi)", "far" not in posts)
check("quake without magnitude skipped", "nomag" not in posts)
check("Merced to Fresno ~55 mi", 50 < fa.miles(37.30, -120.48, 36.74, -119.79) < 60)

wx = {"features": [
    {"properties": {"id": "a1", "status": "Actual", "messageType": "Alert", "event": "Heat Advisory",
                    "areaDesc": "Merced; Madera", "ends": "2026-07-01T20:00:00-07:00"}},
    {"properties": {"id": "t1", "status": "Test", "messageType": "Alert", "event": "Test Message"}},
    {"properties": {"id": "c1", "status": "Actual", "messageType": "Cancel", "event": "Wind Advisory"}},
]}
w = dict(fa.weather_posts(wx))
check("active alert posted", w.get("a1", "").startswith("⚠️ Heat Advisory: Merced until"))
check("test messages skipped", "t1" not in w)
check("cancellations skipped", "c1" not in w)

# ---- fires
fires = {"features": [
    {"attributes": {"UniqueFireIdentifier": "F1", "IncidentName": "OAK", "IncidentSize": 1200.0,
                    "PercentContained": 20.0, "POOCounty": "Mariposa"}, "geometry": {"x": -120.0, "y": 37.5}},
    {"attributes": {"UniqueFireIdentifier": "F2", "IncidentName": "TINY", "IncidentSize": 0.1},
     "geometry": {"x": -120.4, "y": 37.3}},
    {"attributes": {"UniqueFireIdentifier": "F3", "IncidentName": "OUT", "IncidentSize": 5000.0,
                    "PercentContained": 100.0}, "geometry": {"x": -120.4, "y": 37.3}},
]}
fp = dict(fa.fire_posts(fires, S))
check("fire posted with name, county, acres", fp.get("fire|F1", "").startswith("🔥 Oak Fire, Mariposa Co: 1,200 acres, 20% contained"))
check("tiny fire skipped", "fire|F2" not in fp)
check("fully contained fire skipped", "fire|F3" not in fp)

# ---- air quality (AirNow file: | separated)
dat = "\n".join([
    "10/20/26|10/20/26|19:00|PDT|0|O|Y|Merced|CA|37.30|-120.48|PM2.5|162|Unhealthy|No||APCD",
    "10/20/26|10/20/26|19:00|PDT|0|O|N|Merced|CA|37.30|-120.48|OZONE|40|Good|No||APCD",
    "10/20/26|10/21/26||PDT|1|F|Y|Merced|CA|37.30|-120.48|PM2.5|180|Unhealthy|No||APCD",
    "10/20/26|10/20/26|19:00|PDT|0|O|Y|Fresno|CA|36.78|-119.79|PM2.5|30|Good|No||APCD",
])
ap = fa.air_posts(dat, S)
check("unhealthy air at the nearest area posted", len(ap) == 1 and "AQI 162 (PM2.5) in Merced" in ap[0][1])
check("forecast rows ignored, only observed", "180" not in ap[0][1])
check("good air not posted", fa.air_posts(dat.replace("|162|Unhealthy", "|62|Moderate"), S) == [])

# ---- rivers
gauges = {"gauges": [
    {"lid": "A1", "name": "Bear Creek at Merced", "latitude": 37.3, "longitude": -120.4,
     "status": {"observed": {"floodCategory": "minor", "primary": 12.5, "primaryUnit": "ft"}}},
    {"lid": "B2", "name": "Dry Creek", "latitude": 37.3, "longitude": -120.4,
     "status": {"observed": {"floodCategory": "no_flooding", "primary": 3.0, "primaryUnit": "ft"}}},
]}
rp = fa.river_posts(gauges, S)
check("gauge at flood stage posted", len(rp) == 1 and "Bear Creek at Merced: minor flooding, 12.5 ft" in rp[0][1])

# ---- space weather
kp = [{"time_tag": "2026-10-20T18:00:00", "Kp": 2.0}, {"time_tag": "2026-10-20T21:00:00", "Kp": 7.33}]
kpp = fa.kp_posts(kp, S)
check("strong storm posted as G3", len(kpp) == 1 and "G3 (Kp 7)" in kpp[0][1])
check("quiet Kp not posted", fa.kp_posts(kp[:1], S) == [])

long = fa.fit("x" * 300)
check("posts cut to fit one mesh message", len(long.encode()) <= fa.MAX_POST_BYTES and long.endswith("..."))

sys.exit(0 if ok else 1)
