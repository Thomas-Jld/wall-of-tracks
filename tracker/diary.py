"""Per-day listening for the Diary view on /past/: one file per year (diary/<year>.json) and an index.

Each day lists its albums with the seconds played, so the page can draw that day's record the same way
as the live one. Plays count from 30 seconds, like the live record. Run nightly by
wall-of-tracks-stats.service, after stats.py.
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from tracker import DB_PATH, PUBLIC_DIR, utcnow, write_public

TZ = ZoneInfo("Europe/Paris")
LARGE, MEDIUM = "ab67616d0000b273", "ab67616d00001e02"  # Spotify cover sizes: the page picks its own

log = logging.getLogger("diary")


def main():
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    rows = db.execute(
        """SELECT p.played_at, coalesce(p.ms_played, t.duration_ms, 0), coalesce(t.album_id, t.id),
                  t.album_name, t.artists, t.album_image
           FROM plays p JOIN tracks t ON t.id = p.track_id
           WHERE coalesce(p.ms_played, 30000) >= 30000"""
    )
    # year -> album id -> [name, artist, cover]; year -> day -> album id -> ms
    albums = defaultdict(dict)
    days = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for played_at, ms, album, name, artists, image in rows:
        day = datetime.fromisoformat(played_at.replace("Z", "+00:00")).astimezone(TZ).date()
        if album not in albums[day.year]:
            artist = json.loads(artists)[0]["name"] if artists else ""
            albums[day.year][album] = [name or "", artist or "", image.replace(LARGE, MEDIUM) if image else None]
        days[day.year][day.isoformat()][album] += ms

    index = {}
    for year in sorted(days):
        ids = list(albums[year])
        position = {a: i for i, a in enumerate(ids)}
        out_days = {
            day: [[position[a], round(ms / 1000)] for a, ms in sorted(per.items(), key=lambda kv: -kv[1])]
            for day, per in sorted(days[year].items())
        }
        write_public(PUBLIC_DIR / "diary" / f"{year}.json", {
            "year": year,
            "updated_at": utcnow(),
            "albums": [albums[year][a] for a in ids],  # [name, artist, cover url]
            "days": out_days,                            # day -> [[album index, seconds], ...], most played first
        })
        index[year] = {"days": len(out_days), "first": min(out_days), "last": max(out_days),
                       "hours": round(sum(s for d in out_days.values() for _, s in d) / 3600)}
        log.info("diary/%d.json: %d days, %d albums", year, len(out_days), len(ids))
    write_public(PUBLIC_DIR / "diary" / "index.json", {"updated_at": utcnow(), "years": index})


if __name__ == "__main__":
    main()
