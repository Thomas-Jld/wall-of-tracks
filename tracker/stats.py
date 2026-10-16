"""Aggregates the listening history into stats.json for the past-listening page (web/past/).

Run daily by wall-of-tracks-stats.timer. Cover colours are cached between runs, so only
albums new to the export need their cover downloaded.
"""

import colorsys
import io
import json
import logging
import re
import sqlite3
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from tracker import DATA_DIR, DB_PATH, PUBLIC_DIR, utcnow, write_public

TZ = ZoneInfo("Europe/Paris")
TOP_N = 240        # albums in Eras and Groove
YEAR_TOP_N = 24    # albums per year: the slices of Records, and a year's top 10
COLOR_CACHE = DATA_DIR / "cover_colors.json"

# Spotify cover URLs differ only by a size prefix
LARGE, MEDIUM, SMALL = "ab67616d0000b273", "ab67616d00001e02", "ab67616d00004851"

log = logging.getLogger("stats")


def album_key(artist, album):
    """Editions of one album share a key: "Album (Deluxe)", "Album - Remastered 2011" -> "album"."""
    album = re.sub(r"\s*[\(\[][^)\]]*[\)\]]\s*", " ", album)
    album = re.sub(r"\s+-\s+.*(edition|version|remaster|deluxe|expanded|anniversary).*$", "", album, flags=re.I)
    album = re.sub(r"\s+", " ", album).strip().lower()
    return f"{artist.lower()}|{album}"


def aggregate(db):
    albums, year_totals = {}, defaultdict(int)
    rows = db.execute(
        """SELECT p.played_at, coalesce(p.ms_played, t.duration_ms, 0), t.album_name, t.artists, t.album_image
           FROM plays p JOIN tracks t ON t.id = p.track_id
           WHERE coalesce(t.album_name, '') != ''"""
    )
    for played_at, ms, album_name, artists, image in rows:
        artist = json.loads(artists)[0]["name"] or ""
        key = album_key(artist, album_name)
        a = albums.get(key)
        if a is None:
            a = albums[key] = {"key": key, "name": album_name, "artist": artist, "ms": 0, "years": defaultdict(int),
                               "hours": [0] * 24, "images": defaultdict(int), "weighted_day": 0.0}
        local = datetime.fromisoformat(played_at.replace("Z", "+00:00")).astimezone(TZ)
        a["ms"] += ms
        a["years"][local.year] += ms
        a["hours"][local.hour] += ms
        a["weighted_day"] += ms * local.timestamp() / 86400
        if image:
            a["images"][image] += ms  # editions differ in cover; keep the most listened one
        year_totals[local.year] += ms
    for a in albums.values():
        a["img"] = max(a["images"], key=a["images"].get) if a["images"] else None
    return albums, year_totals


def dominant_color(url):
    """Most frequent colour of the cover, nudged toward saturated ones so a white border doesn't win."""
    try:
        data = requests.get(url.replace(LARGE, SMALL), timeout=15).content
        q = Image.open(io.BytesIO(data)).convert("RGB").resize((48, 48)).quantize(5)
        pal = q.getpalette()
        rgb = lambda i: pal[i * 3:i * 3 + 3]
        counts = sorted(q.getcolors(), reverse=True)[:3]
        best = max(counts, key=lambda c: c[0] * (0.35 + colorsys.rgb_to_hsv(*[x / 255 for x in rgb(c[1])])[1]))
        return rgb(best[1])
    except Exception as e:
        log.warning("no colour for %s: %s", url, e)
        return None


def main():
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    albums, year_totals = aggregate(db)

    with_cover = sorted((a for a in albums.values() if a["img"]), key=lambda a: -a["ms"])
    year_tops = {
        y: [a["key"] for a in sorted((a for a in with_cover if a["years"].get(y)), key=lambda a: -a["years"][y])[:YEAR_TOP_N]]
        for y in sorted(year_totals)
    }
    wanted = {a["key"] for a in with_cover[:TOP_N]} | {k for keys in year_tops.values() for k in keys}

    colors = json.loads(COLOR_CACHE.read_text()) if COLOR_CACHE.exists() else {}
    missing = [albums[k]["img"] for k in wanted if albums[k]["img"] not in colors]
    with ThreadPoolExecutor(8) as pool:
        for url, color in zip(missing, pool.map(dominant_color, missing)):
            if color:
                colors[url] = color
    COLOR_CACHE.write_text(json.dumps(colors))

    out = []
    for a in with_cover:
        if a["key"] not in wanted:
            continue
        mean_day = a["weighted_day"] / a["ms"] if a["ms"] else 0
        out.append({
            "key": a["key"], "name": a["name"], "artist": a["artist"], "ms": a["ms"],
            "years": {str(y): ms for y, ms in a["years"].items()}, "hours": a["hours"],
            "img": a["img"].replace(LARGE, MEDIUM), "color": colors.get(a["img"]),
            "tmean": datetime.fromtimestamp(mean_day * 86400, TZ).date().isoformat(),  # listening-weighted date
        })
    write_public(PUBLIC_DIR / "stats.json", {
        "updated_at": utcnow(),
        "albums": out,
        "year_tops": {str(y): keys for y, keys in year_tops.items()},
        "year_totals": {str(y): ms for y, ms in year_totals.items()},
    })
    log.info("stats.json: %d albums (%d new colours), %d years", len(out), len(missing), len(year_totals))


if __name__ == "__main__":
    main()
