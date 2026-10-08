package com.geirlifehub.companion.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkRequest
import java.util.concurrent.TimeUnit

/**
 * Schedules/cancels the periodic background sync job ([SyncWorker]).
 *
 * Uses [WorkManager.enqueueUniquePeriodicWork] with
 * [ExistingPeriodicWorkPolicy.UPDATE] so changing the configured interval
 * re-plans the same job instead of creating a duplicate one running
 * alongside it.
 */
object SyncScheduler {

    private const val UNIQUE_WORK_NAME = "com.geirlifehub.companion.PERIODIC_SYNC"

    /**
     * (Re)schedules periodic sync to run roughly every [intervalHours] hours,
     * only while the device has network connectivity. [intervalHours] is
     * clamped via [coerceIntervalHours] so callers can't accidentally
     * schedule more often than this app supports.
     */
    fun schedule(context: Context, intervalHours: Long) {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val request = PeriodicWorkRequestBuilder<SyncWorker>(
            coerceIntervalHours(intervalHours), TimeUnit.HOURS,
        )
            .setConstraints(constraints)
            // A failed run already reports Result.success() (see SyncWorker),
            // so this backoff policy only matters for the rare case WorkManager
            // itself has to retry (e.g. the process was killed mid-run).
            .setBackoffCriteria(BackoffPolicy.LINEAR, WorkRequest.MIN_BACKOFF_MILLIS, TimeUnit.MILLISECONDS)
            .build()

        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            UNIQUE_WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }

    /** Cancels any scheduled periodic sync (e.g. on logout). */
    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(UNIQUE_WORK_NAME)
    }
}
