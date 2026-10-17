package com.thomasjuldo.walloftracks;

import android.app.WallpaperManager;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapShader;
import android.graphics.BlendMode;
import android.graphics.BlurMaskFilter;
import android.graphics.Canvas;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.RuntimeShader;
import android.graphics.Shader;
import android.graphics.SweepGradient;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.Settings;
import android.service.wallpaper.WallpaperService;
import android.util.Log;
import android.view.SurfaceHolder;

import java.util.List;

/** The live record from walloftrack.thomasjuldo.com as a live wallpaper. */
public final class RecordWallpaper extends WallpaperService {
    private static final float RPM = 2.5f;      // slow on purpose: it's a wall piece, not a turntable
    private static final int BG = 0xFF0C0C0F;
    private static final long FRAME_MS = 33;    // ~30 fps is plenty for this slow motion

    // the drawn record, slowly marbled; the label and the rim stay still (same as the web page's flow)
    private static final String FLOW = """
            uniform shader tex;
            uniform float t;
            uniform float2 size;
            float hash(float2 p) { return fract(sin(dot(p, float2(127.1, 311.7))) * 43758.5453); }
            float noise(float2 p) {
                float2 i = floor(p);
                float2 f = fract(p);
                float2 u = f * f * (3.0 - 2.0 * f);
                return mix(mix(hash(i), hash(i + float2(1.0, 0.0)), u.x),
                           mix(hash(i + float2(0.0, 1.0)), hash(i + float2(1.0, 1.0)), u.x), u.y);
            }
            float fbm(float2 p) {
                float s = 0.0;
                float a = 0.5;
                for (int k = 0; k < 4; k++) { s += a * noise(p); p *= 2.03; a *= 0.5; }
                return s;
            }
            half4 main(float2 fc) {
                float2 p = fc / size * 2.0 - 1.0;
                float r = length(p);
                float a = atan(p.y, p.x);
                if (r > 1.0) { return half4(0.0); }
                float w = smoothstep(0.31, 0.42, r) * (1.0 - smoothstep(0.93, 0.975, r));
                float2 q = p * 2.0 + float2(t * 0.02, -t * 0.015);
                a += w * 0.14 * (fbm(q) - 0.5);
                r += w * 0.012 * (fbm(q * 1.3 + 7.0) - 0.5);
                return tex.eval((float2(cos(a), sin(a)) * r * 0.5 + 0.5) * size);
            }
            """;

    @Override public Engine onCreateEngine() { return new RecordEngine(); }

    private final class RecordEngine extends Engine implements LiveFeed.Listener {
        private final Handler main = new Handler(Looper.getMainLooper());
        private final Runnable frameRunnable = this::frame;
        private final Record record = new Record();
        private Covers covers;
        private LiveFeed feed;
        private SharedPreferences prefs;

        private boolean visible, frameQueued, motion = true;
        private int width, height, D;
        private float cx, cy;

        // the record is drawn into one of two bitmaps (the other may still be on screen), then spun on the GPU
        private final Bitmap[] discs = new Bitmap[2];
        private int front;
        private boolean discDirty = true;
        private long renderedAt, renderedUptime;
        private Bitmap grooves, shadow;

        private RuntimeShader flow;
        private boolean organicFlow = true;  // the style: organic + flow, or classic; a double tap switches
        private final Paint flowPaint = new Paint();
        private final Paint plain = new Paint(Paint.FILTER_BITMAP_FLAG);
        private final Paint sheen = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint rim = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF dst = new RectF();

        // spin: eases up when playing, coasts down when paused, like a turntable; the flow moves with it
        private float angle, speed, flowTime;
        private long lastFrame;

        // background: the label's cover, blurred, cross-fading when it changes; drifts with home-screen pages
        private String backdropUrl;
        private Bitmap backdrop, previousBackdrop;
        private float fade = 1, parallax = 0.5f;

        private long lastTap;
        private int tapX, tapY;

        @Override public void onCreate(SurfaceHolder holder) {
            super.onCreate(holder);
            prefs = getSharedPreferences("wall-of-tracks", MODE_PRIVATE);
            organicFlow = !"classic".equals(prefs.getString("style", "flow"));
            covers = new Covers(getCacheDir(), () -> main.post(this::invalidateDisc));
            feed = new LiveFeed(this);
            try {
                flow = new RuntimeShader(FLOW);
                flowPaint.setShader(flow);
            } catch (RuntimeException e) {  // no flow then: the organic record still turns
                Log.w("WallOfTracks", "flow shader: " + e);
                flow = null;
            }
            rim.setStyle(Paint.Style.STROKE);
            rim.setColor(0x14FFFFFF);
        }

        @Override public void onSurfaceChanged(SurfaceHolder holder, int format, int w, int h) {
            super.onSurfaceChanged(holder, format, w, h);
            width = w;
            height = h;
            D = Math.round(Math.min(w, h) * 0.86f);
            cx = w / 2f;
            cy = h / 2f;
            grooves = makeGrooves(D);
            shadow = makeShadow(D);
            float R = D / 2f;
            // the web page's masks are sized from the page corner (R * sqrt 2): the reflection spans 0.27R..R
            SweepGradient sweep = new SweepGradient(cx, cy,
                    new int[]{0x00FFFFFF, 0x42FFFFFF, 0x00FFFFFF, 0x00FFFFFF, 0x33FFFFFF, 0x00FFFFFF, 0x00FFFFFF},
                    new float[]{0f, 30 / 360f, 62 / 360f, 180 / 360f, 210 / 360f, 242 / 360f, 1f});
            Matrix m = new Matrix();
            m.setRotate(-90, cx, cy);  // start at 12 o'clock like the CSS conic gradient
            sweep.setLocalMatrix(m);
            sheen.setShader(sweep);
            sheen.setStyle(Paint.Style.STROKE);
            sheen.setStrokeWidth(R * (1 - 0.27f));
            sheen.setBlendMode(BlendMode.SCREEN);
            rim.setStrokeWidth(Math.max(1, R * 0.003f));
            discs[0] = discs[1] = null;
            invalidateDisc();
        }

        @Override public void onVisibilityChanged(boolean v) {
            visible = v;
            if (v) {
                motion = motionAllowed();
                lastFrame = SystemClock.uptimeMillis();
                feed.start();
                requestFrame();
            } else {
                feed.stop();  // nothing to show, nothing to fetch
                main.removeCallbacks(frameRunnable);
                frameQueued = false;
            }
        }

        @Override public void onSurfaceDestroyed(SurfaceHolder holder) {
            visible = false;
            main.removeCallbacks(frameRunnable);
            frameQueued = false;
            super.onSurfaceDestroyed(holder);
        }

        @Override public void onDestroy() {
            feed.shutdown();
            covers.shutdown();
            main.removeCallbacksAndMessages(null);
            super.onDestroy();
        }

        @Override public void onOffsetsChanged(float xOffset, float yOffset, float xStep, float yStep, int xPx, int yPx) {
            parallax = xOffset;
            requestFrame();
        }

        // the launcher forwards taps on empty space; two close together switch the style
        @Override public Bundle onCommand(String action, int x, int y, int z, Bundle extras, boolean resultRequested) {
            if (WallpaperManager.COMMAND_TAP.equals(action)) {
                long t = SystemClock.uptimeMillis();
                float slop = 80 * getResources().getDisplayMetrics().density;
                if (t - lastTap < 400 && Math.hypot(x - tapX, y - tapY) < slop) {
                    lastTap = 0;
                    organicFlow = !organicFlow;
                    prefs.edit().putString("style", organicFlow ? "flow" : "classic").apply();
                    invalidateDisc();
                } else {
                    lastTap = t;
                    tapX = x;
                    tapY = y;
                }
            }
            return null;
        }

        // ---------- data (arrives on background threads) ----------
        @Override public void onDay(List<Record.Play> plays) { main.post(() -> { record.setDay(plays); invalidateDisc(); }); }
        @Override public void onNow(Record.NowPlaying now) { main.post(() -> { record.setNow(now); invalidateDisc(); }); }

        private void invalidateDisc() {
            discDirty = true;
            requestFrame();
        }

        private void requestFrame() {
            if (visible && !frameQueued) {
                frameQueued = true;
                main.post(frameRunnable);
            }
        }

        private boolean motionAllowed() {  // honour "remove animations" and battery saver
            float scale = Settings.Global.getFloat(getContentResolver(), Settings.Global.ANIMATOR_DURATION_SCALE, 1f);
            PowerManager pm = getSystemService(PowerManager.class);
            return scale > 0 && !(pm != null && pm.isPowerSaveMode());
        }

        // ---------- the loop: ~30 fps while something moves, a redraw every 2s while a paused-motion song plays, else idle ----------
        private void frame() {
            frameQueued = false;
            if (!visible || D == 0) return;
            long up = SystemClock.uptimeMillis(), wall = System.currentTimeMillis();
            float dt = Math.min(0.1f, (up - lastFrame) / 1000f);
            lastFrame = up;

            boolean playing = record.isPlaying(wall);
            float full = RPM * 6, target = playing && motion ? full : 0;
            speed += (target - speed) * (float) (1 - Math.exp(-dt / (playing ? 0.9 : 2.2)));
            if (target == 0 && speed < 0.01f) speed = 0;
            angle = (angle + speed * dt) % 360;
            flowTime += dt * speed / full;

            // the playing album's slice keeps growing; slices that are easing redraw at ~15 fps
            if (playing && wall - renderedAt > 2000) discDirty = true;
            if (discDirty || (record.easing && up - renderedUptime > 66)) renderDisc(wall, up);
            updateBackdrop(wall);
            if (fade < 1) fade = Math.min(1, fade + dt / 2.5f);

            draw();

            boolean moving = speed > 0 || record.easing || fade < 1;
            long next = moving ? FRAME_MS : playing ? 2000 : -1;
            if (next >= 0) {
                frameQueued = true;
                main.postDelayed(frameRunnable, next);
            }
        }

        private void renderDisc(long wall, long up) {
            int i = front ^ 1;
            if (discs[i] == null || discs[i].getWidth() != D) discs[i] = Bitmap.createBitmap(D, D, Bitmap.Config.ARGB_8888);
            discs[i].eraseColor(0);
            record.render(new Canvas(discs[i]), D, organicFlow, covers, wall, up);
            front = i;
            discDirty = false;
            renderedAt = wall;
            renderedUptime = up;
            if (flow != null) flow.setInputShader("tex", new BitmapShader(discs[front], Shader.TileMode.CLAMP, Shader.TileMode.CLAMP));
        }

        private void updateBackdrop(long wall) {
            String url = Covers.small(record.labelImage(wall));
            if (url == null || url.equals(backdropUrl)) return;
            Bitmap cover = covers.get(url);
            if (cover == null) return;  // comes back here once it has loaded
            backdropUrl = url;
            previousBackdrop = backdrop;
            backdrop = blurred(cover);
            fade = previousBackdrop == null ? 1 : 0;
        }

        private void draw() {
            SurfaceHolder holder = getSurfaceHolder();
            Canvas c;
            try { c = holder.lockHardwareCanvas(); } catch (RuntimeException e) { return; }
            if (c == null) return;
            try {
                c.drawColor(BG);
                // 20% larger than the screen, like the web page, which leaves room for the parallax drift
                float side = Math.max(width, height) * 1.2f, shift = (parallax - 0.5f) * width * 0.12f;
                dst.set(cx - side / 2 - shift, cy - side / 2, cx + side / 2 - shift, cy + side / 2);
                plain.setAlpha(255);
                if (previousBackdrop != null && fade < 1) c.drawBitmap(previousBackdrop, null, dst, plain);
                if (backdrop != null) {
                    plain.setAlpha(Math.round(255 * fade));
                    c.drawBitmap(backdrop, null, dst, plain);
                    plain.setAlpha(255);
                }
                c.drawBitmap(shadow, cx - shadow.getWidth() / 2f, cy - shadow.getHeight() / 2f, null);

                Bitmap disc = discs[front];
                if (disc != null) {
                    c.save();
                    c.rotate(angle, cx, cy);
                    c.translate(cx - D / 2f, cy - D / 2f);
                    if (organicFlow && flow != null) {
                        flow.setFloatUniform("t", flowTime);
                        flow.setFloatUniform("size", D, D);
                        c.drawRect(0, 0, D, D, flowPaint);
                    } else {
                        c.drawBitmap(disc, 0, 0, plain);
                    }
                    c.restore();
                }
                c.drawBitmap(grooves, cx - D / 2f, cy - D / 2f, null);
                float R = D / 2f;
                c.drawCircle(cx, cy, R * (1 + 0.27f) / 2, sheen);  // stays put while the record turns underneath
                c.drawCircle(cx, cy, R - rim.getStrokeWidth() / 2, rim);
            } finally {
                holder.unlockCanvasAndPost(c);
            }
        }
    }

    // ---------- static layers, drawn once per size ----------

    /** Fine grooves from 0.43R to the edge (the web page's mask, sized from the page corner). */
    private static Bitmap makeGrooves(int D) {
        Bitmap b = Bitmap.createBitmap(D, D, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        Paint dark = new Paint(Paint.ANTI_ALIAS_FLAG), light = new Paint(Paint.ANTI_ALIAS_FLAG);
        dark.setStyle(Paint.Style.STROKE);
        light.setStyle(Paint.Style.STROKE);
        dark.setColor(0x38000000);
        light.setColor(0x08FFFFFF);
        float R = D / 2f, period = Math.max(3, D / 200f), w = period / 4;
        dark.setStrokeWidth(w);
        light.setStrokeWidth(w);
        for (float r = R * 0.43f; r < R; r += period) {
            c.drawCircle(R, R, r, dark);
            c.drawCircle(R, R, r + w, light);
        }
        return b;
    }

    /** The record's soft drop shadow, like the web page's two box-shadows. */
    private static Bitmap makeShadow(int D) {
        int S = Math.round(D * 1.4f);
        Bitmap b = Bitmap.createBitmap(S, S, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(0xB3000000);
        p.setMaskFilter(new BlurMaskFilter(D * 0.1f, BlurMaskFilter.Blur.NORMAL));
        c.drawCircle(S / 2f, S / 2f + D * 0.037f, D / 2f, p);
        p.setColor(0x80000000);
        p.setMaskFilter(new BlurMaskFilter(D * 0.03f, BlurMaskFilter.Blur.NORMAL));
        c.drawCircle(S / 2f, S / 2f + D * 0.01f, D / 2f, p);
        return b;
    }

    /**
     * A small blurred, darkened and slightly saturated copy of a cover, scaled up when drawn. The blur is
     * light on purpose: scaled up to the screen it keeps about the contrast of the web page's 70px blur,
     * where a stronger one averages the bright patches away and the background looks flat and dark.
     */
    private static Bitmap blurred(Bitmap cover) {
        int n = 64;
        Bitmap b = Bitmap.createScaledBitmap(cover, n, n, true).copy(Bitmap.Config.ARGB_8888, true);
        int[] px = new int[n * n];
        b.getPixels(px, 0, n, 0, 0, n, n);
        for (int pass = 0; pass < 2; pass++) {
            px = boxBlur(px, n, n, 2, true);
            px = boxBlur(px, n, n, 2, false);
        }
        for (int i = 0; i < px.length; i++) {  // saturate x1.3, then darken to 40%, like the web page's filter
            int r = (px[i] >> 16) & 255, g = (px[i] >> 8) & 255, bl = px[i] & 255;
            float gray = 0.2126f * r + 0.7152f * g + 0.0722f * bl;
            px[i] = 0xFF000000 | channel(gray + (r - gray) * 1.3f) << 16 | channel(gray + (g - gray) * 1.3f) << 8 | channel(gray + (bl - gray) * 1.3f);
        }
        b.setPixels(px, 0, n, 0, 0, n, n);
        return b;
    }

    private static int channel(float v) { return Math.max(0, Math.min(255, Math.round(v * 0.4f))); }

    private static int[] boxBlur(int[] src, int w, int h, int radius, boolean horizontal) {
        int[] out = new int[src.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int r = 0, g = 0, b = 0, count = 0;
                for (int k = -radius; k <= radius; k++) {
                    int sx = horizontal ? Math.max(0, Math.min(w - 1, x + k)) : x;
                    int sy = horizontal ? y : Math.max(0, Math.min(h - 1, y + k));
                    int c = src[sy * w + sx];
                    r += (c >> 16) & 255; g += (c >> 8) & 255; b += c & 255; count++;
                }
                out[y * w + x] = 0xFF000000 | (r / count) << 16 | (g / count) << 8 | (b / count);
            }
        }
        return out;
    }
}
