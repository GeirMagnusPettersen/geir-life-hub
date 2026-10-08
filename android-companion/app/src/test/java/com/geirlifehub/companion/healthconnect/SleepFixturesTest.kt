package com.geirlifehub.companion.healthconnect

import androidx.health.connect.client.records.SleepSessionRecord
import java.time.Duration
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Sanity checks for [SleepFixtures]: the synthetic stage/heart-rate data must stay
 * internally consistent (stage minutes summing to the real-inspired total duration)
 * and physiologically plausible (realistic stage proportions, resting HR in a normal
 * sleeping range) - see [SleepFixtures] for why the stage/HR values are synthetic
 * rather than copied from the real 2022 Garmin export.
 */
class SleepFixturesTest {

    @Test
    fun `mar19 session stages sum to the real-inspired total duration`() {
        val session = SleepFixtures.sleepSessionMar19_2022()
        assertStagesSumToSessionDuration(session)
        assertEquals(Duration.ofHours(8).plusMinutes(43), sessionDuration(session))
    }

    @Test
    fun `feb19 session stages sum to the real-inspired total duration`() {
        val session = SleepFixtures.sleepSessionFeb19_2022()
        assertStagesSumToSessionDuration(session)
        assertEquals(Duration.ofHours(10).plusMinutes(34), sessionDuration(session))
    }

    @Test
    fun `mar19 stage proportions are physiologically realistic`() {
        assertRealisticProportions(SleepFixtures.sleepSessionMar19_2022())
    }

    @Test
    fun `feb19 stage proportions are physiologically realistic`() {
        assertRealisticProportions(SleepFixtures.sleepSessionFeb19_2022())
    }

    @Test
    fun `heart rate samples stay within normal resting sleep range`() {
        val records = SleepFixtures.allHeartRateRecords()
        for (record in records) {
            assertTrue("expected at least one HR sample", record.samples.isNotEmpty())
            for (sample in record.samples) {
                assertTrue(
                    "bpm ${sample.beatsPerMinute} outside plausible 45-65 sleeping range",
                    sample.beatsPerMinute in 45..65,
                )
            }
        }
    }

    @Test
    fun `fixtures exclude the suspected placeholder may 2022 week`() {
        // The 15-21 May 2022 week was flagged as suspected placeholder/manual data
        // (identical values repeated across consecutive days) and must never be used
        // as a fixture source - only the two legitimate real-inspired dates exist.
        val sessions = SleepFixtures.allSleepSessions()
        assertEquals(2, sessions.size)
        val months = sessions.map { it.startTime.toString().substring(0, 7) }
        assertTrue(months.none { it == "2022-05" })
    }

    private fun sessionDuration(session: SleepSessionRecord): Duration =
        Duration.between(session.startTime, session.endTime)

    private fun assertStagesSumToSessionDuration(session: SleepSessionRecord) {
        val stageTotal = session.stages.fold(Duration.ZERO) { acc, stage ->
            acc.plus(Duration.between(stage.startTime, stage.endTime))
        }
        assertEquals(sessionDuration(session), stageTotal)
    }

    private fun assertRealisticProportions(session: SleepSessionRecord) {
        val totalMinutes = sessionDuration(session).toMinutes().toDouble()
        val minutesByStage = session.stages
            .groupBy { it.stage }
            .mapValues { (_, stages) ->
                stages.sumOf { Duration.between(it.startTime, it.endTime).toMinutes() }
            }

        fun proportion(stageType: Int): Double =
            (minutesByStage[stageType] ?: 0L) / totalMinutes

        val light = proportion(SleepSessionRecord.STAGE_TYPE_LIGHT)
        val deep = proportion(SleepSessionRecord.STAGE_TYPE_DEEP)
        val rem = proportion(SleepSessionRecord.STAGE_TYPE_REM)
        val awake = proportion(SleepSessionRecord.STAGE_TYPE_AWAKE)

        assertTrue("light=$light out of [0.40, 0.60]", light in 0.40..0.60)
        assertTrue("deep=$deep out of [0.10, 0.30]", deep in 0.10..0.30)
        assertTrue("rem=$rem out of [0.15, 0.35]", rem in 0.15..0.35)
        assertTrue("awake=$awake out of [0.0, 0.10]", awake in 0.0..0.10)
    }
}
