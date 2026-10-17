package com.thomasjuldo.walloftracks;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.util.Log;
import android.util.LruCache;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Album covers, kept in memory and on disk. get() never blocks: it returns null and loads in the background. */
final class Covers {
    // Spotify serves each cover at 64, 300 and 640px under different URL prefixes
    private static final String LARGE = "ab67616d0000b273", MEDIUM = "ab67616d00001e02", SMALL = "ab67616d00004851";

    static String medium(String url) { return url == null ? null : url.replace(LARGE, MEDIUM).replace(SMALL, MEDIUM); }
    static String small(String url) { return url == null ? null : url.replace(LARGE, SMALL).replace(MEDIUM, SMALL); }

    private final LruCache<String, Bitmap> memory = new LruCache<String, Bitmap>(32 * 1024 * 1024) {
        @Override protected int sizeOf(String key, Bitmap b) { return b.getByteCount(); }
    };
    private final Set<String> loading = ConcurrentHashMap.newKeySet();
    private final ExecutorService pool = Executors.newFixedThreadPool(4);
    private final File dir;
    private final Runnable onLoaded;

    Covers(File cacheDir, Runnable onLoaded) {
        this.dir = new File(cacheDir, "covers");
        this.dir.mkdirs();
        this.onLoaded = onLoaded;
    }

    Bitmap get(String url) {
        if (url == null) return null;
        Bitmap b = memory.get(url);
        if (b == null && loading.add(url)) pool.execute(() -> load(url));
        return b;
    }

    private void load(String url) {
        try {
            File file = new File(dir, sha1(url));
            byte[] data = file.exists() ? Files.readAllBytes(file.toPath()) : download(url);
            if (!file.exists()) try (FileOutputStream out = new FileOutputStream(file)) { out.write(data); }
            Bitmap b = BitmapFactory.decodeByteArray(data, 0, data.length);
            if (b != null) {
                memory.put(url, b);
                onLoaded.run();
            }
        } catch (Exception e) {
            Log.w("WallOfTracks", "cover " + url + ": " + e);
        } finally {
            loading.remove(url);
        }
    }

    private static byte[] download(String url) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(10_000);
        c.setReadTimeout(15_000);
        try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[16 * 1024];
            for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
            return out.toByteArray();
        } finally {
            c.disconnect();
        }
    }

    private static String sha1(String s) throws Exception {
        StringBuilder hex = new StringBuilder();
        for (byte b : MessageDigest.getInstance("SHA-1").digest(s.getBytes("UTF-8"))) hex.append(String.format("%02x", b));
        return hex.toString();
    }

    void shutdown() { pool.shutdownNow(); }
}
