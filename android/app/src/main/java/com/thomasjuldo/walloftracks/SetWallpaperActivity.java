package com.thomasjuldo.walloftracks;

import android.app.Activity;
import android.app.WallpaperManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.os.Bundle;

/** The launcher icon: opens the system preview of this live wallpaper, where it can be set. */
public final class SetWallpaperActivity extends Activity {
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        Intent preview = new Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER)
                .putExtra(WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT, new ComponentName(this, RecordWallpaper.class));
        try {
            startActivity(preview);
        } catch (ActivityNotFoundException e) {
            startActivity(new Intent(WallpaperManager.ACTION_LIVE_WALLPAPER_CHOOSER));
        }
        finish();
    }
}
