package com.geirlifehub.companion.sync

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.geirlifehub.companion.auth.SessionManager
import com.geirlifehub.companion.healthconnect.HealthConnectRepository

/**
 * Background entry point for periodic sync, scheduled by [SyncScheduler].
 *
 * This worker intentionally contains no sync logic of its own: it builds the
 * same [SessionManager] / [HealthConnectRepository] / [SyncManager] trio that
 * [com.geirlifehub.companion.ui.MainActivity]'s manual "Synkroniser nå" button
 * uses, and delegates to the existing [SyncManager.runSync] isolation
 * boundary. A failed run is recorded as status (via [SyncPreferences]) and
 * never thrown further - per the project's "no retry/backoff" scope, this
 * worker always reports [Result.success] so WorkManager neither retries nor
 * backs off; the next periodic run is the natural retry.
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val syncPreferences = SyncPreferences(applicationContext)
        val sessionManager = SessionManager(applicationContext)
        val backendUrl = sessionManager.backendUrl
        val deviceToken = sessionManager.deviceToken

        if (backendUrl.isBlank() || deviceToken.isNullOrBlank()) {
            syncPreferences.recordSyncResult(
                timestampMillis = System.currentTimeMillis(),
                success = false,
                message = "Ikke logget inn - hopper over planlagt synk",
            )
            return Result.success()
        }

        val healthConnectRepository = HealthConnectRepository(applicationContext)
        val syncManager = SyncManager(healthConnectRepository, backendUrl, deviceToken)

        val outcome = try {
            syncManager.runSync()
        } catch (error: Exception) {
            // SyncManager.runSync() already catches its own failures and
            // returns SyncResult.Failure; this is an extra safety net so an
            // unexpected exception still can't crash the worker/app.
            SyncResult.Failure(error.message ?: "Ukjent feil under planlagt synk")
        }

        when (outcome) {
            is SyncResult.Success -> syncPreferences.recordSyncResult(
                timestampMillis = System.currentTimeMillis(),
                success = true,
                message = "Synk fullført: ${outcome.sleepEntriesSynced} søvn, ${outcome.workoutsSynced} treningsøkter.",
            )
            is SyncResult.Failure -> syncPreferences.recordSyncResult(
                timestampMillis = System.currentTimeMillis(),
                success = false,
                message = outcome.message,
            )
        }

        return Result.success()
    }
}
