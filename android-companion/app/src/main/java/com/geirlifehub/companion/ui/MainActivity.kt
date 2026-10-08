package com.geirlifehub.companion.ui

import android.os.Bundle
import android.view.View
import android.widget.AdapterView
import androidx.appcompat.app.AppCompatActivity
import androidx.health.connect.client.PermissionController
import androidx.lifecycle.lifecycleScope
import com.geirlifehub.companion.R
import com.geirlifehub.companion.auth.LoginOutcome
import com.geirlifehub.companion.auth.SessionManager
import com.geirlifehub.companion.databinding.ActivityMainBinding
import com.geirlifehub.companion.healthconnect.HealthConnectRepository
import com.geirlifehub.companion.sync.SyncManager
import com.geirlifehub.companion.sync.SyncPreferences
import com.geirlifehub.companion.sync.SyncResult
import com.geirlifehub.companion.sync.SyncScheduler
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.util.Date

/**
 * Single-screen companion UI: connect an account, grant Health Connect
 * access, trigger a manual sync, and configure/observe periodic background
 * sync (issue #14). Background sync delegates to the same [SyncManager]
 * used by the manual "Synkroniser nå" button via [com.geirlifehub.companion.sync.SyncWorker],
 * so this screen only needs to manage the interval preference and the
 * WorkManager schedule, plus display the last sync outcome.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var sessionManager: SessionManager
    private lateinit var healthConnectRepository: HealthConnectRepository
    private lateinit var syncPreferences: SyncPreferences

    /** Hour values aligned by index with R.array.sync_interval_labels. */
    private val intervalHoursOptions by lazy {
        resources.getIntArray(R.array.sync_interval_hours_values)
    }

    private val requestPermissionsLauncher = registerForActivityResult(
        PermissionController.createRequestPermissionResultContract()
    ) { granted ->
        if (granted.containsAll(HealthConnectRepository.REQUIRED_PERMISSIONS)) {
            binding.statusText.text = getString(R.string.status_logged_in, sessionManager.username ?: "")
        } else {
            binding.statusText.text = getString(R.string.status_permissions_missing)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        sessionManager = SessionManager(applicationContext)
        healthConnectRepository = HealthConnectRepository(applicationContext)
        syncPreferences = SyncPreferences(applicationContext)

        binding.backendUrlInput.setText(sessionManager.backendUrl.ifBlank { binding.backendUrlInput.text.toString() })
        updateStatusForCurrentSession()
        setUpSyncIntervalSpinner()
        updateLastSyncText()

        binding.loginButton.setOnClickListener { onLoginClicked() }
        binding.requestPermissionsButton.setOnClickListener { onRequestPermissionsClicked() }
        binding.syncButton.setOnClickListener { onSyncClicked() }

        // Only schedule background sync for users who are already logged in;
        // SyncWorker itself also no-ops safely if credentials are missing.
        if (sessionManager.isLoggedIn) {
            SyncScheduler.schedule(applicationContext, syncPreferences.intervalHours)
        }
    }

    private fun setUpSyncIntervalSpinner() {
        val selectedIndex = intervalHoursOptions.indexOf(syncPreferences.intervalHours.toInt())
            .takeIf { it >= 0 } ?: 0
        binding.syncIntervalSpinner.setSelection(selectedIndex, false)

        binding.syncIntervalSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val hours = intervalHoursOptions[position].toLong()
                if (hours == syncPreferences.intervalHours) return
                syncPreferences.intervalHours = hours
                SyncScheduler.schedule(applicationContext, syncPreferences.intervalHours)
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
    }

    private fun updateLastSyncText() {
        val timestamp = syncPreferences.lastSyncTimestamp
        val success = syncPreferences.lastSyncSuccess
        binding.lastSyncText.text = if (timestamp == null || success == null) {
            getString(R.string.status_last_sync_never)
        } else {
            val formattedTime = DateFormat.getDateTimeInstance().format(Date(timestamp))
            val statusLabel = if (success) {
                getString(R.string.status_last_sync_success)
            } else {
                getString(R.string.status_last_sync_failure)
            }
            getString(R.string.status_last_sync, statusLabel, formattedTime)
        }
    }

    private fun updateStatusForCurrentSession() {
        binding.statusText.text = if (sessionManager.isLoggedIn) {
            getString(R.string.status_logged_in, sessionManager.username ?: "")
        } else {
            getString(R.string.status_not_logged_in)
        }
    }

    private fun onLoginClicked() {
        val backendUrl = binding.backendUrlInput.text.toString().trim()
        val username = binding.usernameInput.text.toString().trim()
        val password = binding.passwordInput.text.toString()

        sessionManager.backendUrl = backendUrl
        binding.statusText.text = getString(R.string.status_syncing)

        lifecycleScope.launch {
            // Network I/O must not run on the main thread; failures here are
            // caught inside SessionManager.login and returned as a value, so
            // this coroutine itself never throws.
            val outcome = withContext(Dispatchers.IO) {
                sessionManager.login(username, password)
            }
            binding.statusText.text = when (outcome) {
                is LoginOutcome.Success -> {
                    // Now that we have credentials, (re)schedule background
                    // sync at the currently configured interval.
                    SyncScheduler.schedule(applicationContext, syncPreferences.intervalHours)
                    getString(R.string.status_logged_in, outcome.username)
                }
                is LoginOutcome.Failure -> getString(R.string.status_sync_failed, outcome.message)
            }
        }
    }

    private fun onRequestPermissionsClicked() {
        if (!healthConnectRepository.isAvailable()) {
            binding.statusText.text = getString(R.string.status_health_connect_unavailable)
            return
        }
        requestPermissionsLauncher.launch(HealthConnectRepository.REQUIRED_PERMISSIONS)
    }

    private fun onSyncClicked() {
        val backendUrl = sessionManager.backendUrl
        val deviceToken = sessionManager.deviceToken

        if (backendUrl.isBlank() || deviceToken.isNullOrBlank()) {
            binding.statusText.text = getString(R.string.status_not_logged_in)
            return
        }

        binding.statusText.text = getString(R.string.status_syncing)
        val syncManager = SyncManager(healthConnectRepository, backendUrl, deviceToken)

        lifecycleScope.launch {
            // SyncManager.runSync() already wraps every failure mode (Health
            // Connect, network, backend) into SyncResult.Failure, so a bad
            // sync only ever updates the status text - it cannot crash the
            // activity or affect anything else in the app.
            val result = withContext(Dispatchers.IO) { syncManager.runSync() }
            binding.statusText.text = when (result) {
                is SyncResult.Success ->
                    getString(R.string.status_sync_success, result.sleepEntriesSynced, result.workoutsSynced)
                is SyncResult.Failure ->
                    getString(R.string.status_sync_failed, result.message)
            }
            val successMessage = when (result) {
                is SyncResult.Success -> binding.statusText.text.toString()
                is SyncResult.Failure -> result.message
            }
            syncPreferences.recordSyncResult(
                timestampMillis = System.currentTimeMillis(),
                success = result is SyncResult.Success,
                message = successMessage,
            )
            updateLastSyncText()
        }
    }
}
