"""Fetch full metadata (cover, album/artist ids, duration) for tracks that only have
names, e.g. those created by import_history.py. Resumable: progress is committed per batch."""

import logging

import spotipy

from tracker import make_auth_manager, open_db, upsert_track, utcnow

BATCH = 50  # max ids per GET /tracks

log = logging.getLogger("enrich")


def main():
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
    sp = spotipy.Spotify(auth_manager=make_auth_manager(), requests_timeout=15, retries=5)
    db = open_db()
    # Most-listened first, so an interrupted run has already covered what matters.
    ids = [r[0] for r in db.execute(
        """SELECT t.id FROM tracks t LEFT JOIN plays p ON p.track_id = t.id
           WHERE t.fetched_at IS NULL GROUP BY t.id ORDER BY SUM(p.ms_played) DESC"""
    )]
    log.info("%d tracks to enrich", len(ids))

    missing = 0
    for start in range(0, len(ids), BATCH):
        batch = ids[start:start + BATCH]
        for track_id, track in zip(batch, sp.tracks(batch)["tracks"]):
            if track:
                upsert_track(db, track, track_id=track_id)
            else:  # removed from Spotify; mark so it isn't retried every run
                db.execute("UPDATE tracks SET fetched_at = ? WHERE id = ?", (utcnow(), track_id))
                missing += 1
        db.commit()
        if (start // BATCH) % 20 == 0:
            log.info("%d / %d", start + len(batch), len(ids))
    log.info("done (%d no longer on Spotify)", missing)


if __name__ == "__main__":
    main()
