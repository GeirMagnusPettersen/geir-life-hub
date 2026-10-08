package com.geirlifehub.companion.sync

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Pure-JVM tests for the interval-clamping logic used by [SyncPreferences]
 * and [SyncScheduler]. Deliberately scoped to [coerceIntervalHours] alone so
 * these tests need no Android framework / Robolectric / instrumentation.
 */
class SyncPreferencesTest {

    @Test
    fun `values at or above the minimum are returned unchanged`() {
        assertEquals(MIN_SYNC_INTERVAL_HOURS, coerceIntervalHours(MIN_SYNC_INTERVAL_HOURS))
        assertEquals(3L, coerceIntervalHours(3L))
        assertEquals(24L, coerceIntervalHours(24L))
    }

    @Test
    fun `values below the minimum are clamped up to it`() {
        assertEquals(MIN_SYNC_INTERVAL_HOURS, coerceIntervalHours(0L))
        assertEquals(MIN_SYNC_INTERVAL_HOURS, coerceIntervalHours(-5L))
    }

    @Test
    fun `default interval is at least the minimum`() {
        assertEquals(DEFAULT_SYNC_INTERVAL_HOURS, coerceIntervalHours(DEFAULT_SYNC_INTERVAL_HOURS))
    }
}
