"""Polls Spotify for what is being listened to and logs it to SQLite.

One loop, two sources:
  - /me/player is polled every few seconds while music is active. Successive snapshots
    are turned into finished plays as soon as a track ends (source 'observed'), and a
    sample is kept every SAMPLE_INTERVAL seconds for time-of-day detail.
  - /me/player/recently-played is fetched every RECENT_INTERVAL seconds. It is Spotify's
    canonical list of plays but lags by minutes; its rows replace the observed ones.

State for the web page in web/ is pushed live (live.py) and also written as
now_playing.json and day.json (the last 24h of plays) into PUBLIC_DIR.

Run `auth.py` once beforehand to create the token cache.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

import live

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("WOT_DATA_DIR", HERE / "data"))
DB_PATH = DATA_DIR / "listening.db"
TOKEN_CACHE_PATH = DATA_DIR / ".spotify_token"
# Served as-is by the web server: only put things here that are fine to be public.
PUBLIC_DIR = Path(os.environ.get("WOT_PUBLIC_DIR", DATA_DIR / "public"))
NOW_PLAYING_PATH = PUBLIC_DIR / "now_playing.json"
DAY_PATH = PUBLIC_DIR / "day.json"

ACTIVE_INTERVAL = float(os.environ.get("WOT_ACTIVE_INTERVAL", 3))  # playing, or was recently
IDLE_INTERVAL = float(os.environ.get("WOT_IDLE_INTERVAL", 10))
ACTIVE_FOR = 600       # seconds after the last playback during which we keep polling fast
SAMPLE_INTERVAL = 15   # seconds between rows in `samples`
RECENT_INTERVAL = int(os.environ.get("WOT_RECENT_INTERVAL", 600))
LIVE_PORT = int(os.environ.get("WOT_LIVE_PORT", 8790))

MIN_PLAY_MS = 30_000   # Spotify only counts a play after 30s
GONE_GRACE = 300       # seconds the player may vanish before the loaded track counts as finished
SAME_PLAY_EARLY_S = 120   # Spotify may date a play slightly before the tracker saw it end...
SAME_PLAY_LATE_S = 7200   # ...or long after, when it only logs it once the session closes

SCOPE = "user-read-currently-playing user-read-playback-state user-read-recently-played"
# Already registered on the Spotify app for the old Flask login flow.
DEFAULT_REDIRECT_URI = "http://127.0.0.1:27150/walloftrack/spotify/callback/"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    artists      TEXT NOT NULL,  -- JSON list of {id, name}
    album_id     TEXT,
    album_name   TEXT,
    album_image  TEXT,           -- largest cover URL
    release_date TEXT,
    duration_ms  INTEGER,
    fetched_at   TEXT            -- NULL until full metadata came from the API (see enrich.py)
);

-- One row per play. `played_at` is when the play ended (UTC).
-- History-export rows also carry how long and why the track played. API rows only
-- include plays Spotify counted (>= 30s); their ms_played comes from a matching
-- observed play when the tracker saw it, else stays NULL.
CREATE TABLE IF NOT EXISTS plays (
    played_at    TEXT NOT NULL,
    track_id     TEXT NOT NULL REFERENCES tracks(id),
    context_uri  TEXT,
    ms_played    INTEGER,
    source       TEXT NOT NULL,  -- 'recently_played' | 'observed' | 'history_export'
    skipped      INTEGER,
    reason_start TEXT,
    reason_end   TEXT,
    shuffle      INTEGER,
    platform     TEXT,
    PRIMARY KEY (played_at, track_id)
);
CREATE INDEX IF NOT EXISTS plays_track ON plays(track_id);

-- Periodic snapshots of the player while something is playing.
CREATE TABLE IF NOT EXISTS samples (
    ts          TEXT PRIMARY KEY,
    item_type   TEXT,            -- 'track' | 'episode' | 'ad' | 'unknown'
    track_id    TEXT,
    progress_ms INTEGER,
    context_uri TEXT,
    device      TEXT,
    shuffle     INTEGER
);
"""

log = logging.getLogger("tracker")


def client_credentials():
    """Env vars first, then the repo's conf.json used by the rest of the project."""
    client_id = os.environ.get("SPOTIPY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    if client_id and client_secret:
        return client_id, client_secret
    conf = json.loads((HERE.parent / "conf.json").read_text())["spotify"]
    return conf["id"], conf["secret"]


def make_auth_manager(open_browser=False):
    client_id, client_secret = client_credentials()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=os.environ.get("SPOTIPY_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        scope=SCOPE,
        cache_handler=CacheFileHandler(cache_path=str(TOKEN_CACHE_PATH)),
        open_browser=open_browser,
    )


def open_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert_track(db, track, track_id=None):
    """Store an API track object. `track_id` overrides the id when Spotify relinked the track."""
    album = track.get("album") or {}
    images = album.get("images") or []
    biggest = max(images, key=lambda i: i.get("width") or 0)["url"] if images else None
    db.execute(
        """INSERT INTO tracks (id, name, artists, album_id, album_name, album_image, release_date, duration_ms, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, artists=excluded.artists, album_id=excluded.album_id,
             album_name=excluded.album_name, album_image=excluded.album_image,
             release_date=excluded.release_date, duration_ms=excluded.duration_ms,
             fetched_at=excluded.fetched_at""",
        (
            track_id or track["id"],
            track["name"],
            json.dumps([{"id": a.get("id"), "name": a["name"]} for a in track["artists"]]),
            album.get("id"),
            album.get("name"),
            biggest,
            album.get("release_date"),
            track.get("duration_ms"),
            utcnow(),
        ),
    )


def write_public(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


def iso_z(dt):
    """Same shape as Spotify's played_at, so plays from every source sort together."""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def day_state(db, hours=25):
    """Recent plays with their start times; the page trims to exactly 24h itself."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = db.execute(
        """SELECT p.played_at, coalesce(p.ms_played, t.duration_ms), t.id, t.name, t.artists,
                  coalesce(t.album_id, t.id), t.album_name, t.album_image
           FROM plays p JOIN tracks t ON t.id = p.track_id
           WHERE p.played_at >= ? AND coalesce(p.ms_played, 30000) >= 30000
           ORDER BY p.played_at""",
        (since,),
    ).fetchall()
    plays, prev_end = [], None
    for played_at, ms, track_id, name, artists, album_id, album_name, image in rows:
        end = datetime.fromisoformat(played_at.replace("Z", "+00:00"))
        # played_at is when the play ended; don't let a start overlap the previous play
        start = end - timedelta(milliseconds=ms or 180_000)
        if prev_end and start < prev_end:
            start = prev_end
        prev_end = end
        plays.append({
            "t0": start.isoformat(), "t1": end.isoformat(), "track_id": track_id, "track": name,
            "artist": json.loads(artists)[0]["name"], "album": album_id, "album_name": album_name, "img": image,
        })
    return {"updated_at": utcnow(), "plays": plays}


class Observer:
    """Turns successive player snapshots into finished plays, ahead of Spotify's own log.

    A track counts as finished when a different track (or a replay of it) is loaded, or
    when the player has been gone for GONE_GRACE. Pausing, even for hours, is not an end.
    """

    def __init__(self):
        self.cur = None
        self.gone_since = None

    def update(self, track, progress, playing, now, player_present):
        if not player_present:
            self.gone_since = self.gone_since or now
            if self.cur and (now - self.gone_since).total_seconds() > GONE_GRACE:
                return self._finish()
            return None
        self.gone_since = None

        finished = None
        if self.cur:
            replay = (track and track["id"] == self.cur["id"] and progress + 5000 < self.cur["progress"]
                      and self.cur["progress"] > self.cur["duration"] - 10_000)
            if not track or track["id"] != self.cur["id"] or replay:
                finished = self._finish()
        if track:
            if self.cur is None:
                self.cur = {"id": track["id"], "duration": track["duration_ms"], "max": progress,
                            "last_playing": None, "progress_then": progress}
            self.cur["progress"] = progress
            self.cur["max"] = max(self.cur["max"], progress)
            if playing:
                self.cur["last_playing"], self.cur["progress_then"] = now, progress
        return finished

    def _finish(self):
        cur, self.cur = self.cur, None
        if cur["last_playing"] is None:  # loaded but never played
            return None
        near_end = cur["max"] >= cur["duration"] - (2 * ACTIVE_INTERVAL + 1) * 1000
        ms = cur["duration"] if near_end else cur["max"]
        if ms < MIN_PLAY_MS:
            return None
        ended = cur["last_playing"]
        if near_end:  # it ran out between two polls
            ended += timedelta(milliseconds=max(0, cur["duration"] - cur["progress_then"]))
        return {"track_id": cur["id"], "played_at": iso_z(ended), "ms_played": ms}


def poll_recently_played(sp, db):
    items = sp.current_user_recently_played(limit=50)["items"]
    new = 0
    for entry in items:
        track = entry["track"]
        if not track.get("id"):  # local files have no Spotify id
            continue
        upsert_track(db, track)
        new += db.execute(
            "INSERT OR IGNORE INTO plays (played_at, track_id, context_uri, source) VALUES (?, ?, ?, 'recently_played')",
            (entry["played_at"], track["id"], (entry.get("context") or {}).get("uri")),
        ).rowcount

    # The same listen seen both ways: keep Spotify's row, with the duration the tracker observed.
    # Spotify dates a play around when it ended, or much later when it only logs it as the session
    # closes, so pair each observed play with the first Spotify row of that track in that window,
    # unless another observed play of the track comes in between (that one is the better match).
    merged = 0
    for played_at, track_id, ms in db.execute(
        "SELECT played_at, track_id, ms_played FROM plays WHERE source = 'observed' ORDER BY played_at"
    ).fetchall():
        match = db.execute(
            """SELECT a.played_at FROM plays a
               WHERE a.source = 'recently_played' AND a.track_id = :track AND a.ms_played IS NULL
                 AND (julianday(a.played_at) - julianday(:at)) * 86400 BETWEEN -:early AND :late
                 AND NOT EXISTS (
                   SELECT 1 FROM plays o
                   WHERE o.source = 'observed' AND o.track_id = :track
                     AND julianday(o.played_at) > julianday(:at) AND julianday(o.played_at) <= julianday(a.played_at))
               ORDER BY a.played_at LIMIT 1""",
            {"track": track_id, "at": played_at, "early": SAME_PLAY_EARLY_S, "late": SAME_PLAY_LATE_S},
        ).fetchone()
        if match:
            db.execute("UPDATE plays SET ms_played = ? WHERE played_at = ? AND track_id = ?", (ms, match[0], track_id))
            db.execute("DELETE FROM plays WHERE played_at = ? AND track_id = ? AND source = 'observed'", (played_at, track_id))
            merged += 1
    db.commit()
    log.info("recently-played synced: %d new, %d merged with observed plays", new, merged)


class Tracker:
    def __init__(self, sp, db, hub):
        self.sp, self.db, self.hub = sp, db, hub
        self.observer = Observer()
        self.last_track = None
        self.last_sample = self.last_active = -1e9

    def publish(self, event, path, data):
        write_public(path, data)
        self.hub.publish(event, data)

    def publish_day(self):
        self.publish("day", DAY_PATH, day_state(self.db))

    def poll_player(self):
        """One /me/player snapshot. Returns how long to wait before the next one."""
        now = datetime.now(timezone.utc)
        playback = self.sp.current_playback()  # None when no device is active
        item = (playback or {}).get("item")
        track = item if item and item.get("type") == "track" and item.get("id") else None
        playing = bool(playback and playback.get("is_playing"))
        progress = (playback or {}).get("progress_ms") or 0

        if track and track["id"] != self.last_track:
            upsert_track(self.db, track)
        self.last_track = track["id"] if track else None

        finished = self.observer.update(track, progress, playing, now, player_present=playback is not None)
        if finished:
            self.db.execute(
                "INSERT OR IGNORE INTO plays (played_at, track_id, ms_played, source) VALUES (?, ?, ?, 'observed')",
                (finished["played_at"], finished["track_id"], finished["ms_played"]),
            )
            self.db.commit()
            log.info("finished: %s (%ds)", finished["track_id"], finished["ms_played"] // 1000)
            self.publish_day()  # before "now", so the page never shows a gap

        if playing:
            self.last_active = time.monotonic()
            if time.monotonic() - self.last_sample >= SAMPLE_INTERVAL:
                self.last_sample = time.monotonic()
                self.db.execute(
                    "INSERT OR IGNORE INTO samples VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        now.isoformat(timespec="seconds"),
                        playback.get("currently_playing_type", "unknown"),
                        track["id"] if track else None,
                        progress,
                        (playback.get("context") or {}).get("uri"),
                        (playback.get("device") or {}).get("name"),
                        int(bool(playback.get("shuffle_state"))),
                    ),
                )
        self.db.commit()

        self.publish("now", NOW_PLAYING_PATH, {
            "updated_at": now.isoformat(timespec="seconds"),
            "is_playing": playing,
            "progress_ms": progress if track else None,
            "track": {
                "id": track["id"],
                "name": track["name"],
                "artists": [a["name"] for a in track["artists"]],
                "album": track["album"]["id"] or track["id"],
                "album_name": track["album"]["name"],
                "album_image": (track["album"]["images"] or [{}])[0].get("url"),
                "duration_ms": track["duration_ms"],
            } if track else None,
        })

        if playing and track:
            # look again right after the track should end, so the next one shows up at once
            remaining = (track["duration_ms"] - progress) / 1000
            return max(0.5, min(ACTIVE_INTERVAL, remaining + 0.5))
        recently_active = time.monotonic() - self.last_active < ACTIVE_FOR
        return ACTIVE_INTERVAL if recently_active else IDLE_INTERVAL

    def run(self):
        next_recent, failures = 0.0, 0
        while True:
            started = time.monotonic()
            try:
                wait = self.poll_player()
                failures = 0
            except Exception as e:
                failures += 1
                wait = min(60, ACTIVE_INTERVAL * 2 ** failures)
                if isinstance(e, SpotifyException):
                    log.warning("player poll failed (%s %s), retrying in %.0fs", e.http_status, e.msg, wait)
                else:
                    log.exception("player poll failed, retrying in %.0fs", wait)
            if started >= next_recent:
                try:
                    poll_recently_played(self.sp, self.db)
                    self.publish_day()
                    next_recent = started + RECENT_INTERVAL
                except Exception:
                    log.exception("recently-played poll failed")
                    next_recent = started + 60
            time.sleep(max(0.2, wait - (time.monotonic() - started)))


def main():
    logging.basicConfig(
        level=os.environ.get("WOT_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    auth = make_auth_manager()
    if not auth.cache_handler.get_cached_token():
        raise SystemExit(f"No Spotify token at {TOKEN_CACHE_PATH}; run auth.py first.")

    # no automatic retries: the loop polls again in seconds anyway, and backs off on its own
    sp = spotipy.Spotify(auth_manager=auth, requests_timeout=10, retries=0, status_retries=0)
    hub = live.Hub()
    live.serve(hub, LIVE_PORT)
    log.info("tracking into %s (player every %ss active / %ss idle, recent every %ss)",
             DB_PATH, ACTIVE_INTERVAL, IDLE_INTERVAL, RECENT_INTERVAL)
    Tracker(sp, open_db(), hub).run()


if __name__ == "__main__":
    main()
