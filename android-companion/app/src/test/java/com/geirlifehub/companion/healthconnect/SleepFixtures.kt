package com.geirlifehub.companion.healthconnect

import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.metadata.Metadata
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneOffset

/**
 * Seed/fixture data for the sleep side of the Health Connect adapter, expressed
 * in Health Connect's own schema ([SleepSessionRecord] + [SleepSessionRecord.Stage],
 * [HeartRateRecord]) rather than any Garmin-internal field layout - this is the
 * shape [HealthConnectRepository.readSleepSessions] actually returns.
 *
 * ## Provenance and why the stage data here is synthetic
 *
 * The *envelope* of each night below (bedtime, wake time, total sleep duration) is
 * inspired by real sleep sessions pulled from a Garmin Connect account for 2022.
 * The *stage breakdown and heart rate* for that real 2022 data was not usable as-is:
 *
 * - 2022-03-19: real total sleep was 8h43m (22:31 -> 07:19), but the real stage
 *   split was Deep 8h35m / Light 8m / REM missing ("--") / Awake 5m - i.e. almost
 *   the entire night recorded as "Deep", which is not physiologically plausible.
 *   The real resting heart rate for that night (141 bpm) is also not a plausible
 *   *sleeping* resting heart rate - most likely a sensor/sync error on an old device.
 * - 2022-02-19: real total sleep was 10h34m, but Deep was recorded as equal to the
 *   total (10h33m) with Light/REM/Awake all missing ("--"), and resting heart rate
 *   was 130 bpm - again not usable as a real per-stage/HR reference.
 * - A third week of real data (15-21 May 2022, e.g. 11h59m / 22:57->10:56 repeated
 *   on four separate days) was excluded entirely: identical values repeated across
 *   consecutive days strongly suggest placeholder/manually-entered data rather than
 *   real sensor readings, so it is not used as an "inspiration" source at all.
 *
 * Because of that, the stage proportions and heart rate samples below are
 * **synthetic**: constructed to be internally consistent (stage minutes sum exactly
 * to the real total sleep duration) and physiologically realistic (roughly
 * 50-55% Light, 18-23% Deep, 22-26% REM, a few percent Awake; resting heart rate in
 * the normal 45-65 bpm sleeping range), not copied from the real per-stage/HR
 * readings, which were unreliable for this period.
 */
object SleepFixtures {

    /** Oslo was on winter time (CET, UTC+1) for both reference dates below. */
    private val OSLO_WINTER_OFFSET = ZoneOffset.ofHours(1)

    /**
     * 2022-03-19 night, synthetic stages. Envelope (bedtime 22:31 on 2022-03-18,
     * wake 07:19 on 2022-03-19, total 8h43m = 523 minutes) is inspired by the real
     * Garmin export; the stage breakdown and heart rate are synthetic (see class doc).
     */
    fun sleepSessionMar19_2022(): SleepSessionRecord {
        val start = instantAt(LocalDate.of(2022, 3, 18), LocalTime.of(22, 31))
        return buildSession(
            start = start,
            stageMinutes = listOf(
                SleepSessionRecord.STAGE_TYPE_AWAKE to 4L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 70L,
                SleepSessionRecord.STAGE_TYPE_DEEP to 55L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 65L,
                SleepSessionRecord.STAGE_TYPE_REM to 60L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 68L,
                SleepSessionRecord.STAGE_TYPE_DEEP to 50L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 59L,
                SleepSessionRecord.STAGE_TYPE_REM to 73L,
                SleepSessionRecord.STAGE_TYPE_AWAKE to 19L,
            ),
        )
    }

    /** Synthetic resting heart rate samples for [sleepSessionMar19_2022] (45-65 bpm). */
    fun heartRateMar19_2022(): HeartRateRecord {
        val start = instantAt(LocalDate.of(2022, 3, 18), LocalTime.of(22, 31))
        return buildHeartRateSamples(start, totalMinutes = 523, restingBpm = 48, peakBpm = 62)
    }

    /**
     * 2022-02-19 night, synthetic stages. Envelope (total 10h34m = 634 minutes) is
     * inspired by the real Garmin export; the real data had no usable bedtime
     * (Deep was wrongly equal to the total, Light/REM/Awake all missing), so a
     * plausible bedtime/wake pair is assumed here. Stage breakdown and heart rate
     * are synthetic (see class doc).
     */
    fun sleepSessionFeb19_2022(): SleepSessionRecord {
        val start = instantAt(LocalDate.of(2022, 2, 18), LocalTime.of(23, 50))
        return buildSession(
            start = start,
            stageMinutes = listOf(
                SleepSessionRecord.STAGE_TYPE_AWAKE to 5L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 65L,
                SleepSessionRecord.STAGE_TYPE_DEEP to 48L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 60L,
                SleepSessionRecord.STAGE_TYPE_REM to 55L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 62L,
                SleepSessionRecord.STAGE_TYPE_DEEP to 46L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 58L,
                SleepSessionRecord.STAGE_TYPE_REM to 56L,
                SleepSessionRecord.STAGE_TYPE_LIGHT to 98L,
                SleepSessionRecord.STAGE_TYPE_DEEP to 22L,
                SleepSessionRecord.STAGE_TYPE_REM to 48L,
                SleepSessionRecord.STAGE_TYPE_AWAKE to 11L,
            ),
        )
    }

    /** Synthetic resting heart rate samples for [sleepSessionFeb19_2022] (45-65 bpm). */
    fun heartRateFeb19_2022(): HeartRateRecord {
        val start = instantAt(LocalDate.of(2022, 2, 18), LocalTime.of(23, 50))
        return buildHeartRateSamples(start, totalMinutes = 634, restingBpm = 50, peakBpm = 64)
    }

    /** Both reference nights, for adapter/mapping tests that want a small batch. */
    fun allSleepSessions(): List<SleepSessionRecord> =
        listOf(sleepSessionMar19_2022(), sleepSessionFeb19_2022())

    fun allHeartRateRecords(): List<HeartRateRecord> =
        listOf(heartRateMar19_2022(), heartRateFeb19_2022())

    private fun instantAt(date: LocalDate, time: LocalTime): Instant =
        date.atTime(time).toInstant(OSLO_WINTER_OFFSET)

    private fun buildSession(
        start: Instant,
        stageMinutes: List<Pair<Int, Long>>,
    ): SleepSessionRecord {
        var cursor = start
        val stages = stageMinutes.map { (stageType, minutes) ->
            val stageStart = cursor
            val stageEnd = stageStart.plusSeconds(minutes * 60)
            cursor = stageEnd
            SleepSessionRecord.Stage(stageStart, stageEnd, stageType)
        }
        return SleepSessionRecord(
            startTime = start,
            startZoneOffset = OSLO_WINTER_OFFSET,
            endTime = cursor,
            endZoneOffset = OSLO_WINTER_OFFSET,
            stages = stages,
            metadata = Metadata(recordingMethod = Metadata.RECORDING_METHOD_MANUAL_ENTRY),
        )
    }

    /** One heart rate sample every 15 minutes, dipping to [restingBpm] mid-session. */
    private fun buildHeartRateSamples(
        start: Instant,
        totalMinutes: Long,
        restingBpm: Long,
        peakBpm: Long,
    ): HeartRateRecord {
        val sampleIntervalMinutes = 15L
        val sampleCount = (totalMinutes / sampleIntervalMinutes).coerceAtLeast(1)
        val samples = (0 until sampleCount).map { index ->
            val time = start.plusSeconds(index * sampleIntervalMinutes * 60)
            // Simple synthetic envelope: higher near sleep onset/wake, lowest mid-session.
            val midpoint = sampleCount / 2.0
            val distanceFromMid = kotlin.math.abs(index - midpoint) / midpoint
            val bpm = restingBpm + ((peakBpm - restingBpm) * distanceFromMid).toLong()
            HeartRateRecord.Sample(time, bpm)
        }
        return HeartRateRecord(
            startTime = start,
            startZoneOffset = OSLO_WINTER_OFFSET,
            endTime = start.plusSeconds(totalMinutes * 60),
            endZoneOffset = OSLO_WINTER_OFFSET,
            samples = samples,
            metadata = Metadata(recordingMethod = Metadata.RECORDING_METHOD_MANUAL_ENTRY),
        )
    }
}
