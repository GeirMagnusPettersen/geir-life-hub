package com.geirlifehub.companion.sync

import android.content.Context
import android.content.SharedPreferences

private const val PREFS_NAME = "companion_sync_prefs"
private const val KEY_INTERVAL_HOURS = "sync_interval_hours"
private const val KEY_LAST_SYNC_TIMESTAMP = "last_sync_timestamp"
private const val KEY_LAST_SYNC_SUCCESS = "last_sync_success"
private const val KEY_LAST_SYNC_MESSAGE = "last_sync_message"

/** The interval offered by default before the user picks one explicitly. */
const val DEFAULT_SYNC_INTERVAL_HOURS = 6L

/**
 * The lowest interval (in hours) this app's UI allows. WorkManager itself
 * enforces an even lower floor of 15 minutes for [androidx.work.PeriodicWorkRequest],
 * but we only expose whole-hour choices in the UI, so 1 hour is the
 * practical minimum here.
 */
const val MIN_SYNC_INTERVAL_HOURS = 1L

/**
 * Persists the user-configurable background sync interval and the outcome of
 * the most recent sync run (manual or scheduled), so the UI can show
 * "last synced" status without re-running a sync.
 *
 * Unlike [com.geirlifehub.companion.auth.SessionManager], nothing stored here
 * is sensitive, so plain (unencrypted) SharedPreferences is sufficient.
 */
class SyncPreferences(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var intervalHours: Long
        get() = prefs.getLong(KEY_INTERVAL_HOURS, DEFAULT_SYNC_INTERVAL_HOURS)
        set(value) = prefs.edit().putLong(KEY_INTERVAL_HOURS, coerceIntervalHours(value)).apply()

    val lastSyncTimestamp: Long?
        get() = prefs.getLong(KEY_LAST_SYNC_TIMESTAMP, -1L).takeIf { it >= 0 }

    val lastSyncSuccess: Boolean?
        get() = if (prefs.contains(KEY_LAST_SYNC_SUCCESS)) prefs.getBoolean(KEY_LAST_SYNC_SUCCESS, false) else null

    val lastSyncMessage: String?
        get() = prefs.getString(KEY_LAST_SYNC_MESSAGE, null)

    /** Records the outcome of a sync run (manual or background-scheduled). */
    fun recordSyncResult(timestampMillis: Long, success: Boolean, message: String) {
        prefs.edit()
            .putLong(KEY_LAST_SYNC_TIMESTAMP, timestampMillis)
            .putBoolean(KEY_LAST_SYNC_SUCCESS, success)
            .putString(KEY_LAST_SYNC_MESSAGE, message)
            .apply()
    }
}

/**
 * Clamps a user-requested interval (in hours) to this app's supported range.
 * Pulled out as a pure function so it can be unit-tested without an Android
 * context (see `SyncPreferencesTest`).
 */
fun coerceIntervalHours(hours: Long): Long = hours.coerceAtLeast(MIN_SYNC_INTERVAL_HOURS)
