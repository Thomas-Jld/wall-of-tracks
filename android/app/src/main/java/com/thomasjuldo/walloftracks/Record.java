package com.thomasjuldo.walloftracks;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** The last 24h of listening and how it is drawn as a picture disc. Mirrors tracker/web/index.html. */
final class Record {
    static final long DAY_MS = 24 * 3600_000L;
    static final long STALE_MS = 60_000;  // the tracker reports at least every 10s; silence longer means it's down

    static final class Play {
        final long t0, t1;
        final String album, img;
        Play(long t0, long t1, String album, String img) { this.t0 = t0; this.t1 = t1; this.album = album; this.img = img; }
    }

    static final class NowPlaying {
        final boolean playing;
        final long progressMs, durationMs, receivedAt;  // receivedAt: this phone's clock, so a skewed clock doesn't matter
        final String album, img;
        NowPlaying(boolean playing, long progressMs, long durationMs, String album, String img, long receivedAt) {
            this.playing = playing; this.progressMs = progressMs; this.durationMs = durationMs;
            this.album = album; this.img = img; this.receivedAt = receivedAt;
        }
    }

    static final class Slice {
        final String album, img;
        double sec, share;
        Slice(String album, String img) { this.album = album; this.img = img; }
    }

    private List<Play> day = new ArrayList<>();
    private NowPlaying now;
    private boolean dayLoaded;

    void setDay(List<Play> plays) { day = plays; dayLoaded = true; }
    void setNow(NowPlaying n) { now = n; }
    List<Play> dayPlays() { return day; }

    boolean isPlaying(long t) { return now != null && now.playing && t - now.receivedAt < STALE_MS; }

    /** The last 24h of finished plays, plus the track in the player as a growing slice. */
    List<Play> composed(long t) {
        long cutoff = t - DAY_MS;
        List<Play> list = new ArrayList<>();
        for (Play p : day) if (p.t1 > cutoff) list.add(new Play(Math.max(p.t0, cutoff), p.t1, p.album, p.img));
        if (now != null && now.album != null) {
            boolean playing = isPlaying(t);
            long progress = Math.min(now.durationMs, now.progressMs + (playing ? t - now.receivedAt : 0));
            long t1 = playing ? t : now.receivedAt;
            long last = list.isEmpty() ? cutoff : list.get(list.size() - 1).t1;
            long t0 = Math.max(t1 - progress, Math.max(last, cutoff));
            if (t1 > t0) list.add(new Play(t0, t1, now.album, now.img));
        }
        return list;
    }

    /** One slice per album, sized by its listening, in the order albums first appeared. */
    static List<Slice> albumSlices(List<Play> plays) {
        LinkedHashMap<String, Slice> byAlbum = new LinkedHashMap<>();
        for (Play p : plays) {
            Slice s = byAlbum.get(p.album);
            if (s == null) byAlbum.put(p.album, s = new Slice(p.album, p.img));
            s.sec += (p.t1 - p.t0) / 1000.0;
        }
        return new ArrayList<>(byAlbum.values());
    }

    // What the record shows: each album keeps the place it got when first seen (so slices never swap),
    // and its share of the disc eases toward the real one (so growing, shrinking and arriving slide).
    private final LinkedHashMap<String, Slice> shown = new LinkedHashMap<>();
    private long easedAt;
    boolean easing;

    private List<Slice> eased(List<Slice> slices, long uptime) {
        // a long gap between draws (nothing was changing) must not count as time already spent easing
        double k = easedAt == 0 ? 1 : 1 - Math.exp(-Math.min(uptime - easedAt, 100) / 1000.0);
        easedAt = uptime;
        double total = 0;
        for (Slice s : slices) total += s.sec;
        if (total == 0) total = 1;
        Map<String, Double> goal = new HashMap<>();
        for (Slice s : slices) {
            goal.put(s.album, s.sec / total);
            if (!shown.containsKey(s.album)) shown.put(s.album, new Slice(s.album, s.img));
        }
        easing = false;
        double sum = 0;
        for (Iterator<Slice> it = shown.values().iterator(); it.hasNext(); ) {
            Slice d = it.next();
            double g = goal.getOrDefault(d.album, 0.0);
            d.share += (g - d.share) * k;
            // steps under 0.1% of the disc (the playing album's steady growth) aren't visible as jumps: snap them,
            // so the easing only runs for real changes instead of redrawing all the time
            if (Math.abs(g - d.share) > 1e-3) easing = true; else d.share = g;
            if (g == 0 && d.share == 0) it.remove();  // aged out of the window
            else sum += d.share;
        }
        List<Slice> out = new ArrayList<>();
        for (Slice d : shown.values()) {
            Slice s = new Slice(d.album, d.img);
            s.share = d.share / (sum == 0 ? 1 : sum);
            out.add(s);
        }
        return out;
    }

    /** The album of the day: the one with the most listening in the window. */
    static Slice topAlbum(List<Play> plays) {
        Slice best = null;
        for (Slice s : albumSlices(plays)) if (s.img != null && (best == null || s.sec > best.sec)) best = s;
        return best;
    }

    /** What the label (and the blurred background) shows: the playing album, else the album of the day. */
    String labelImage(long t) {
        if (isPlaying(t) && now.img != null) return now.img;
        Slice top = topAlbum(composed(t));
        return top == null ? null : top.img;
    }

    // Every slice edge waves outward; the waves' rhythm, phase and strength drift smoothly around the disc,
    // smooth enough that neighbouring edges stay near-parallel and thin slices never tear.
    private static double wave(double k1, double p1, double k2, double p2, double a) {
        return 0.5 + 0.3 * Math.sin(k1 * a + p1) + 0.2 * Math.sin(k2 * a + p2);  // periodic, 0..1
    }
    static double organicOffset(double d, double a) {
        double freq = 2.0 + 1.6 * wave(1, 0.3, 3, 2.1, a), phase = 2 * Math.PI * wave(2, 1.7, 1, 4.2, a);
        double amp = 0.03 + 0.033 * wave(3, 0.9, 2, 5.5, a);
        return amp * (Math.sin(d * Math.PI * freq + phase) + 0.35 * Math.sin(d * Math.PI * 5.3 + 2 * phase)) * Math.min(1, d * 4);
    }

    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint image = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final RectF dst = new RectF();
    { stroke.setStyle(Paint.Style.STROKE); }

    /** Draws the record, D pixels across, onto a cleared canvas. */
    void render(Canvas c, int D, boolean organic, Covers covers, long t, long uptime) {
        float R = D / 2f, rOut = R * 0.985f, rArt = R * 0.97f, rWax = R * 0.31f, rLabel = R * 0.3f, span = rArt - rWax;
        float groove = Math.max(1, R * 0.006f);
        fill.setShader(null);
        fill.setColor(0xFF0A0A0C);
        c.drawCircle(R, R, rOut, fill);

        // wait for the day's plays, so the first albums placed are the oldest rather than whatever plays now
        List<Play> plays = composed(t);
        List<Slice> slices = dayLoaded ? eased(albumSlices(plays), uptime) : new ArrayList<>();
        double acc = 0;
        for (Slice run : slices) {
            double a0 = -Math.PI / 2 + 2 * Math.PI * acc, a1 = a0 + 2 * Math.PI * run.share;
            acc += run.share;
            int nU = Math.max(8, (int) Math.ceil((a1 - a0) * 60)), nD = 40;
            // positions inside a slice: u across it (0..1), d from its inner edge to its outer edge (0..1)
            Path outline = new Path();
            for (int i = 0; i <= nU; i++) point(outline, i == 0, R, rWax, span, a0, a1, i / (double) nU, 0, organic);
            for (int i = 0; i <= nD; i++) point(outline, false, R, rWax, span, a0, a1, 1, i / (double) nD, organic);
            for (int i = nU; i >= 0; i--) point(outline, false, R, rWax, span, a0, a1, i / (double) nU, 1, organic);
            for (int i = nD; i >= 0; i--) point(outline, false, R, rWax, span, a0, a1, 0, i / (double) nD, organic);
            outline.close();

            c.save();
            c.clipPath(outline);
            // the cover is printed with its top facing outward, centred on the slice
            double am = angle(a0, a1, 0.5, 0.5, organic);
            float rm = rWax + span / 2, s = (float) Math.max(span, rm * (a1 - a0)) * 1.15f;
            Bitmap im = covers.get(Covers.medium(run.img));
            if (im != null) {
                c.save();
                c.rotate((float) Math.toDegrees(am + Math.PI / 2), R, R);
                dst.set(R - s / 2, R - rm - s / 2, R + s / 2, R - rm + s / 2);
                c.drawBitmap(im, null, dst, image);
                c.restore();
            }
            c.restore();
            if (slices.size() > 1) {
                Path edge = new Path();
                for (int i = 0; i <= nD; i++) point(edge, i == 0, R, rWax, span, a0, a1, 0, i / (double) nD, organic);
                stroke.setColor(0xD9060608);
                stroke.setStrokeWidth(groove * 0.6f);
                c.drawPath(edge, stroke);
            }
        }

        // soften the art toward the edges so it sits in the vinyl
        float p0 = rWax / rArt, span01 = span / rArt;
        stroke.setColor(0xFF000000);
        stroke.setShader(new RadialGradient(R, R, rArt,
                new int[]{0x59000000, 0x00000000, 0x00000000, 0x73000000},
                new float[]{p0, p0 + 0.12f * span01, p0 + 0.9f * span01, 1f}, Shader.TileMode.CLAMP));
        stroke.setStrokeWidth(span);
        c.drawCircle(R, R, rWax + span / 2, stroke);
        stroke.setShader(null);

        // label: what's playing, else the album of the day; then the spindle hole
        c.save();
        Path label = new Path();
        label.addCircle(R, R, rLabel, Path.Direction.CW);
        c.clipPath(label);
        fill.setColor(0xFF15151A);
        c.drawCircle(R, R, rLabel, fill);
        Bitmap lim = covers.get(Covers.medium(labelImage(t)));
        if (lim != null) {
            dst.set(R - rLabel, R - rLabel, R + rLabel, R + rLabel);
            c.drawBitmap(lim, null, dst, image);
        }
        fill.setShader(new RadialGradient(R, R, rLabel, new int[]{0, 0, 0x59000000}, new float[]{0, 0.75f, 1}, Shader.TileMode.CLAMP));
        c.drawCircle(R, R, rLabel, fill);
        fill.setShader(null);
        c.restore();
        fill.setColor(0xFF0C0C0F);
        c.drawCircle(R, R, R * 0.022f, fill);
    }

    private static double angle(double a0, double a1, double u, double d, boolean organic) {
        double base = a0 + u * (a1 - a0);
        return organic ? base + organicOffset(d, base) : base;
    }

    private static void point(Path path, boolean first, float R, float rWax, float span,
                              double a0, double a1, double u, double d, boolean organic) {
        double a = angle(a0, a1, u, d, organic), r = rWax + span * d;
        float x = (float) (R + r * Math.cos(a)), y = (float) (R + r * Math.sin(a));
        if (first) path.moveTo(x, y); else path.lineTo(x, y);
    }
}
