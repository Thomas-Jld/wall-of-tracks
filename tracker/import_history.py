"""Import Spotify "Extended streaming history" exports into listening.db.

    python import_history.py path/to/export_dir_or_files... [--include-incognito]

Safe to re-run with a newer export: identical plays are ignored, and API plays
(`recently_played`, `observed`) that the export also contains are replaced by the richer export row.
Afterwards, run enrich.py to fetch covers and artist ids for the imported tracks.
"""

import argparse
import json
from pathlib import Path

from tracker import open_db

# An API play and an export play of the same track this close together are the same listen.
SAME_PLAY_TOLERANCE_S = 60


def export_files(paths):
    for path in map(Path, paths):
        if path.is_dir():
            yield from sorted(path.glob("Streaming_History_Audio_*.json"))
        else:
            yield path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--include-incognito", action="store_true")
    args = parser.parse_args()

    db = open_db()
    plays_before = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    skipped = {"not a track": 0, "incognito": 0}

    for file in export_files(args.paths):
        rows = json.loads(file.read_text())
        for r in rows:
            uri = r.get("spotify_track_uri")
            if not uri:
                skipped["not a track"] += 1
                continue
            if r.get("incognito_mode") and not args.include_incognito:
                skipped["incognito"] += 1
                continue
            track_id = uri.rsplit(":", 1)[-1]
            # Placeholder until enrich.py fetches the real track. Never overwrites API data,
            # except the blank names an earlier enrich.py copied from removed tracks' stubs.
            db.execute(
                """INSERT INTO tracks (id, name, artists, album_name) VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name, artists = excluded.artists,
                     album_name = excluded.album_name
                   WHERE tracks.name = '' AND excluded.name != ''""",
                (
                    track_id,
                    r["master_metadata_track_name"] or "",
                    json.dumps([{"id": None, "name": r["master_metadata_album_artist_name"]}]),
                    r["master_metadata_album_album_name"],
                ),
            )
            db.execute(
                """INSERT OR IGNORE INTO plays
                   (played_at, track_id, ms_played, source, skipped, reason_start, reason_end, shuffle, platform)
                   VALUES (?, ?, ?, 'history_export', ?, ?, ?, ?, ?)""",
                (
                    r["ts"],
                    track_id,
                    r["ms_played"],
                    None if r.get("skipped") is None else int(r["skipped"]),
                    r.get("reason_start"),
                    r.get("reason_end"),
                    None if r.get("shuffle") is None else int(r["shuffle"]),
                    r.get("platform"),
                ),
            )
        print(f"{file.name}: {len(rows)} rows")

    replaced = db.execute(
        """DELETE FROM plays WHERE source IN ('recently_played', 'observed') AND EXISTS (
             SELECT 1 FROM plays h
             WHERE h.source = 'history_export' AND h.track_id = plays.track_id
               AND abs(julianday(h.played_at) - julianday(plays.played_at)) * 86400 < ?)""",
        (SAME_PLAY_TOLERANCE_S,),
    ).rowcount
    db.commit()

    plays_after = db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    print(f"plays: {plays_before} -> {plays_after} "
          f"({replaced} API plays superseded by export rows; skipped {skipped})")
    pending = db.execute("SELECT COUNT(*) FROM tracks WHERE fetched_at IS NULL").fetchone()[0]
    print(f"{pending} tracks need metadata: run enrich.py")


if __name__ == "__main__":
    main()
