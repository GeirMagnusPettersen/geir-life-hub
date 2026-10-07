package com.geirlifehub.companion.sync

import com.geirlifehub.companion.healthconnect.HealthConnectRepository
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

sealed class SyncResult {
    data class Success(val sleepEntriesSynced: Int, val workoutsSynced: Int) : SyncResult()
    data class Failure(val message: String) : SyncResult()
}

/**
 * Ties the Health Connect read-side together with the backend push-side.
 *
 * This is the isolation boundary the project brief calls for: any exception
 * anywhere in this flow (Health Connect unavailable, permission revoked,
 * network error, unexpected backend response, ...) is caught here and
 * reported as [SyncResult.Failure] instead of propagating - a failed sync
 * must never crash the app or block any other feature.
 */
class SyncManager(
    private val healthConnectRepository: HealthConnectRepository,
    private val backendUrl: String,
    private val deviceToken: String,
    private val lookbackDays: Long = 14,
) {

    suspend fun runSync(): SyncResult {
        return try {
            if (!healthConnectRepository.isAvailable()) {
                return SyncResult.Failure("Health Connect er ikke tilgjengelig på denne enheten")
            }
            if (!healthConnectRepository.hasAllPermissions()) {
                return SyncResult.Failure("Mangler Health Connect-tillatelser")
            }

            val now = Instant.now()
            val since = now.minus(lookbackDays, ChronoUnit.DAYS)
            val apiClient = BackendApiClient(backendUrl, deviceToken)

            val sleepSynced = syncSleep(since, now, apiClient)
            val workoutsSynced = syncWorkouts(since, now, apiClient)

            SyncResult.Success(sleepSynced, workoutsSynced)
        } catch (error: Exception) {
            SyncResult.Failure(error.message ?: "Ukjent feil under synkronisering")
        }
    }

    private suspend fun syncSleep(since: Instant, until: Instant, apiClient: BackendApiClient): Int {
        val sessions = healthConnectRepository.readSleepSessions(since, until)
        if (sessions.isEmpty()) return 0

        val zone = ZoneId.systemDefault()
        val entries = sessions.map { session ->
            val durationMinutes = ChronoUnit.MINUTES.between(session.startTime, session.endTime).toInt()
            val summaryDate = session.endTime.atZone(zone).toLocalDate()
            val (resting, avg) = healthConnectRepository.readDailyHeartRateStats(session.startTime, session.endTime)
            SleepActivityEntry(
                summaryDate = summaryDate,
                sleepMinutes = durationMinutes,
                steps = null,
                restingHeartRate = resting,
                avgHeartRate = avg,
            )
        }
        return apiClient.syncSleepActivity(entries)
    }

    private suspend fun syncWorkouts(since: Instant, until: Instant, apiClient: BackendApiClient): Int {
        val sessions = healthConnectRepository.readExerciseSessions(since, until)
        if (sessions.isEmpty()) return 0

        val entries = sessions.map { session ->
            val durationMinutes = ChronoUnit.MINUTES.between(session.startTime, session.endTime).toInt()
            val avgHeartRate = healthConnectRepository.readWorkoutAverageHeartRate(session.startTime, session.endTime)
            WorkoutEntry(
                // Health Connect's record id is stable per record and is the
                // natural idempotency key the backend's (user, source,
                // external_id) uniqueness constraint expects.
                externalId = session.metadata.id,
                activityType = session.exerciseType.toString(),
                startTimeIso = DateTimeFormatter.ISO_INSTANT.format(session.startTime.atZone(ZoneOffset.UTC)),
                endTimeIso = DateTimeFormatter.ISO_INSTANT.format(session.endTime.atZone(ZoneOffset.UTC)),
                durationMinutes = durationMinutes,
                calories = null,
                avgHeartRate = avgHeartRate,
                distanceMeters = null,
            )
        }
        return apiClient.syncWorkouts(entries)
    }
}
