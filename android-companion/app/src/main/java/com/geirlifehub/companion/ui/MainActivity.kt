package com.geirlifehub.companion.ui

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.health.connect.client.PermissionController
import androidx.lifecycle.lifecycleScope
import com.geirlifehub.companion.R
import com.geirlifehub.companion.auth.LoginOutcome
import com.geirlifehub.companion.auth.SessionManager
import com.geirlifehub.companion.databinding.ActivityMainBinding
import com.geirlifehub.companion.healthconnect.HealthConnectRepository
import com.geirlifehub.companion.sync.SyncManager
import com.geirlifehub.companion.sync.SyncResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Single-screen companion UI: connect an account, grant Health Connect
 * access, and trigger a manual sync. There is intentionally no background
 * scheduling in this first iteration - the brief only asks for a working,
 * isolated sync path that cannot take down the rest of the app.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var sessionManager: SessionManager
    private lateinit var healthConnectRepository: HealthConnectRepository

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

        binding.backendUrlInput.setText(sessionManager.backendUrl.ifBlank { binding.backendUrlInput.text.toString() })
        updateStatusForCurrentSession()

        binding.loginButton.setOnClickListener { onLoginClicked() }
        binding.requestPermissionsButton.setOnClickListener { onRequestPermissionsClicked() }
        binding.syncButton.setOnClickListener { onSyncClicked() }
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
                is LoginOutcome.Success -> getString(R.string.status_logged_in, outcome.username)
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
        }
    }
}
