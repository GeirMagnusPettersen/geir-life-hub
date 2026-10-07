package com.geirlifehub.companion.sync

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate
import java.time.format.DateTimeFormatter

/** One day's rollup, matching `HealthConnectSyncItem` in the backend schema. */
data class SleepActivityEntry(
    val summaryDate: LocalDate,
    val sleepMinutes: Int?,
    val steps: Int?,
    val restingHeartRate: Int?,
    val avgHeartRate: Int?,
)

/** One workout/exercise session, matching `WorkoutSyncItem` in the backend schema. */
data class WorkoutEntry(
    val externalId: String,
    val activityType: String,
    val startTimeIso: String,
    val endTimeIso: String,
    val durationMinutes: Int?,
    val calories: Double?,
    val avgHeartRate: Int?,
    val distanceMeters: Double?,
)

/**
 * Minimal client for the two Health Connect sync endpoints on the existing
 * FastAPI backend. Auth is a device-token bearer header (see
 * [com.geirlifehub.companion.auth.SessionManager]) - the same credential the
 * backend already issues for sync clients via `POST /devices`.
 */
class BackendApiClient(private val baseUrl: String, private val deviceToken: String) {

    private val httpClient = OkHttpClient()
    private val jsonMediaType = "application/json".toMediaType()

    private fun authorizedRequest(path: String, jsonBody: String): Request {
        val bearer = "Bearer "
        return Request.Builder()
            .url("$baseUrl$path")
            .addHeader("Authorization", bearer + deviceToken)
            .post(jsonBody.toRequestBody(jsonMediaType))
            .build()
    }

    /** POSTs to `/sleep-activity/sync`. Returns the number of entries the backend accepted. */
    fun syncSleepActivity(entries: List<SleepActivityEntry>): Int {
        val body = JSONObject().put("entries", JSONArray().apply {
            entries.forEach { entry ->
                put(
                    JSONObject().apply {
                        put("summary_date", entry.summaryDate.format(DateTimeFormatter.ISO_LOCAL_DATE))
                        putOpt("sleep_minutes", entry.sleepMinutes)
                        putOpt("steps", entry.steps)
                        putOpt("resting_heart_rate", entry.restingHeartRate)
                        putOpt("avg_heart_rate", entry.avgHeartRate)
                    }
                )
            }
        })

        val request = authorizedRequest("/sleep-activity/sync", body.toString())
        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw java.io.IOException("Sleep/activity sync failed: HTTP ${response.code}")
            }
            return JSONObject(response.body?.string().orEmpty()).getInt("synced")
        }
    }

    /** POSTs to `/workouts/sync`. Returns the number of sessions the backend accepted. */
    fun syncWorkouts(sessions: List<WorkoutEntry>): Int {
        val body = JSONObject().put("sessions", JSONArray().apply {
            sessions.forEach { session ->
                put(
                    JSONObject().apply {
                        put("external_id", session.externalId)
                        put("activity_type", session.activityType)
                        put("start_time", session.startTimeIso)
                        put("end_time", session.endTimeIso)
                        putOpt("duration_minutes", session.durationMinutes)
                        putOpt("calories", session.calories)
                        putOpt("avg_heart_rate", session.avgHeartRate)
                        putOpt("distance_meters", session.distanceMeters)
                    }
                )
            }
        })

        val request = authorizedRequest("/workouts/sync", body.toString())
        httpClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw java.io.IOException("Workout sync failed: HTTP ${response.code}")
            }
            return JSONObject(response.body?.string().orEmpty()).getInt("synced")
        }
    }
}
