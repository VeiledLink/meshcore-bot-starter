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

long = fa.fit("x" * 300)
check("posts cut to fit one mesh message", len(long.encode()) <= fa.MAX_POST_BYTES and long.endswith("..."))

sys.exit(0 if ok else 1)
