package com.geirlifehub.companion.healthconnect

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant

/**
 * Thin wrapper around the Health Connect client SDK.
 *
 * This app never writes to Health Connect - it only reads data that Garmin
 * Connect, Vektklubb or the OS already wrote there. If Health Connect is not
 * installed/supported, or the user has not granted permissions, callers get
 * an explicit, non-throwing status back so a failed read never crashes the
 * rest of the app (see [com.geirlifehub.companion.sync.SyncManager]).
 */
class HealthConnectRepository(private val context: Context) {

    companion object {
        val REQUIRED_PERMISSIONS = setOf(
            HealthPermission.getReadPermission(ExerciseSessionRecord::class),
            HealthPermission.getReadPermission(SleepSessionRecord::class),
            HealthPermission.getReadPermission(HeartRateRecord::class),
        )
    }

    fun isAvailable(): Boolean =
        HealthConnectClient.getSdkStatus(context) == HealthConnectClient.SDK_AVAILABLE

    private val client: HealthConnectClient
        get() = HealthConnectClient.getOrCreate(context)

    fun permissionController(): PermissionController = client.permissionController

    suspend fun hasAllPermissions(): Boolean =
        client.permissionController.getGrantedPermissions().containsAll(REQUIRED_PERMISSIONS)

    /** Sleep sessions in the given window, one row per night. */
    suspend fun readSleepSessions(since: Instant, until: Instant): List<SleepSessionRecord> {
        val request = ReadRecordsRequest(
            recordType = SleepSessionRecord::class,
            timeRangeFilter = TimeRangeFilter.between(since, until),
        )
        return client.readRecords(request).records
    }

    /** Discrete workout/exercise sessions in the given window. */
    suspend fun readExerciseSessions(since: Instant, until: Instant): List<ExerciseSessionRecord> {
        val request = ReadRecordsRequest(
            recordType = ExerciseSessionRecord::class,
            timeRangeFilter = TimeRangeFilter.between(since, until),
        )
        return client.readRecords(request).records
    }

    /** Average/resting heart rate for a single day, or nulls if no data. */
    suspend fun readDailyHeartRateStats(dayStart: Instant, dayEnd: Instant): Pair<Int?, Int?> {
        val samples = client.readRecords(
            ReadRecordsRequest(
                recordType = HeartRateRecord::class,
                timeRangeFilter = TimeRangeFilter.between(dayStart, dayEnd),
            )
        ).records.flatMap { it.samples }

        if (samples.isEmpty()) return null to null
        val avg = samples.map { it.beatsPerMinute }.average().toInt()
        val resting = samples.minOf { it.beatsPerMinute }.toInt()
        return resting to avg
    }

    /** Average heart rate across a workout session's own time window. */
    suspend fun readWorkoutAverageHeartRate(start: Instant, end: Instant): Int? {
        val samples = client.readRecords(
            ReadRecordsRequest(
                recordType = HeartRateRecord::class,
                timeRangeFilter = TimeRangeFilter.between(start, end),
            )
        ).records.flatMap { it.samples }
        if (samples.isEmpty()) return null
        return samples.map { it.beatsPerMinute }.average().toInt()
    }
}
