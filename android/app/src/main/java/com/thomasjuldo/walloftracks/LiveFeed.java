package com.thomasjuldo.walloftracks;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * The same data as the web page: the JSON files once, then the live event stream, only while the
 * wallpaper is visible. A stream that goes quiet for 30s is treated as dead and reopened (the tracker
 * sends player state at least every 10s, and a keepalive every 15s).
 */
final class LiveFeed {
    interface Listener {
        void onDay(List<Record.Play> plays);
        void onNow(Record.NowPlaying now);
    }

    private static final String BASE = "https://walloftrack.thomasjuldo.com/";
    private static final String TAG = "WallOfTracks";

    private final Listener listener;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private volatile Thread streamThread;
    private volatile HttpURLConnection streamConnection;

    LiveFeed(Listener listener) { this.listener = listener; }

    void start() {
        if (streamThread != null) return;
        io.execute(this::poll);  // the first picture shouldn't wait for the stream
        Thread t = new Thread(this::stream, "wot-events");
        streamThread = t;
        t.start();
    }

    void stop() {
        Thread t = streamThread;
        streamThread = null;
        HttpURLConnection c = streamConnection;
        if (c != null) io.execute(c::disconnect);  // unblocks the reading thread
        if (t != null) t.interrupt();
    }

    void shutdown() { stop(); io.shutdownNow(); }

    private void poll() {
        try {
            listener.onDay(parseDay(new JSONObject(get("data/day.json"))));
            listener.onNow(parseNow(new JSONObject(get("data/now_playing.json"))));
        } catch (Exception e) {
            Log.w(TAG, "poll: " + e);
        }
    }

    private void stream() {
        Thread me = Thread.currentThread();
        while (streamThread == me) {
            HttpURLConnection c = null;
            try {
                c = open("events", 30_000);
                streamConnection = c;
                BufferedReader in = new BufferedReader(new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8));
                String event = null;
                StringBuilder data = new StringBuilder();
                for (String line; streamThread == me && (line = in.readLine()) != null; ) {
                    if (line.startsWith("event:")) event = line.substring(6).trim();
                    else if (line.startsWith("data:")) data.append(line.substring(5).trim());
                    else if (line.isEmpty()) {
                        if (event != null && data.length() > 0) dispatch(event, data.toString());
                        event = null;
                        data.setLength(0);
                    }
                }
            } catch (Exception e) {
                if (streamThread == me) Log.w(TAG, "stream: " + e);
            } finally {
                if (c != null) c.disconnect();
                streamConnection = null;
            }
            if (streamThread != me) break;
            poll();  // catch up on whatever happened while disconnected
            try { Thread.sleep(3000); } catch (InterruptedException e) { break; }
        }
    }

    private void dispatch(String event, String data) throws Exception {
        if (event.equals("day")) listener.onDay(parseDay(new JSONObject(data)));
        else if (event.equals("now")) listener.onNow(parseNow(new JSONObject(data)));
    }

    private static List<Record.Play> parseDay(JSONObject d) throws Exception {
        JSONArray plays = d.getJSONArray("plays");
        List<Record.Play> out = new ArrayList<>(plays.length());
        for (int i = 0; i < plays.length(); i++) {
            JSONObject p = plays.getJSONObject(i);
            out.add(new Record.Play(time(p.getString("t0")), time(p.getString("t1")), p.getString("album"), str(p, "img")));
        }
        return out;
    }

    private static Record.NowPlaying parseNow(JSONObject n) {
        JSONObject track = n.optJSONObject("track");
        long received = System.currentTimeMillis();
        if (track == null) return new Record.NowPlaying(false, 0, 0, null, null, received);
        return new Record.NowPlaying(n.optBoolean("is_playing"), n.optLong("progress_ms", 0), track.optLong("duration_ms", 0),
                str(track, "album"), str(track, "album_image"), received);
    }

    // org.json turns a JSON null into the string "null"; we want a real null
    private static String str(JSONObject o, String key) { return o.isNull(key) ? null : o.optString(key); }

    private static long time(String iso) { return OffsetDateTime.parse(iso).toInstant().toEpochMilli(); }

    private static HttpURLConnection open(String path, int readTimeoutMs) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(BASE + path).openConnection();
        c.setConnectTimeout(10_000);
        c.setReadTimeout(readTimeoutMs);
        c.setUseCaches(false);
        return c;
    }

    private static String get(String path) throws IOException {
        HttpURLConnection c = open(path, 15_000);
        try (InputStream in = c.getInputStream()) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } finally {
            c.disconnect();
        }
    }
}
