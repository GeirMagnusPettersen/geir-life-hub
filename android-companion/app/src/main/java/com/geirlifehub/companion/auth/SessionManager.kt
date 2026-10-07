package com.geirlifehub.companion.auth

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

private const val PREFS_NAME = "companion_session"
private const val KEY_BACKEND_URL = "backend_url"
private const val KEY_DEVICE_TOKEN = "device_token"
private const val KEY_USERNAME = "username"

sealed class LoginOutcome {
    data class Success(val username: String) : LoginOutcome()
    data class Failure(val message: String) : LoginOutcome()
}

/**
 * Reuses the backend's existing two-user, session-cookie auth: logs in with
 * username/password to obtain a session cookie, then immediately mints a
 * device token via `POST /devices` using that cookie. Only the device token
 * (a long-lived bearer credential meant for background sync clients) is kept
 * afterwards; the session cookie itself is discarded once the device token
 * has been minted.
 */
class SessionManager(context: Context) {

    private val prefs: SharedPreferences = try {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            PREFS_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    } catch (error: Exception) {
        // Fall back to plain prefs rather than crash the app if the
        // keystore is unavailable (e.g. on some emulators).
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    private val httpClient = OkHttpClient()

    var backendUrl: String
        get() = prefs.getString(KEY_BACKEND_URL, "") ?: ""
        set(value) = prefs.edit().putString(KEY_BACKEND_URL, value.trimEnd('/')).apply()

    var deviceToken: String?
        get() = prefs.getString(KEY_DEVICE_TOKEN, null)
        private set(value) = prefs.edit().putString(KEY_DEVICE_TOKEN, value).apply()

    var username: String?
        get() = prefs.getString(KEY_USERNAME, null)
        private set(value) = prefs.edit().putString(KEY_USERNAME, value).apply()

    val isLoggedIn: Boolean
        get() = !deviceToken.isNullOrBlank()

    fun logout() {
        deviceToken = null
        username = null
    }

    /**
     * Logs in and provisions a device token in one go. Any failure (network,
     * bad credentials, unexpected response) is returned as [LoginOutcome.Failure]
     * instead of throwing, so the caller can show it inline without crashing.
     */
    fun login(username: String, password: String): LoginOutcome {
        return try {
            val base = backendUrl
            if (base.isBlank()) {
                return LoginOutcome.Failure("Backend-URL er ikke satt")
            }

            val loginBody = JSONObject()
                .put("username", username)
                .put("password", password)
                .toString()
                .toRequestBody("application/json".toMediaType())

            val loginRequest = Request.Builder()
                .url("$base/auth/login")
                .post(loginBody)
                .build()

            val loginResponse = httpClient.newCall(loginRequest).execute()
            loginResponse.use {
                if (!it.isSuccessful) {
                    return LoginOutcome.Failure("Innlogging feilet (HTTP ${it.code})")
                }
            }

            val sessionCookie = loginResponse.headers("Set-Cookie")
                .firstOrNull()
                ?.substringBefore(";")
                ?: return LoginOutcome.Failure("Fant ingen sesjonscookie i svaret")

            val deviceBody = JSONObject()
                .put("label", "Health Connect companion")
                .toString()
                .toRequestBody("application/json".toMediaType())

            val deviceRequest = Request.Builder()
                .url("$base/devices")
                .addHeader("Cookie", sessionCookie)
                .post(deviceBody)
                .build()

            val deviceResponse = httpClient.newCall(deviceRequest).execute()
            deviceResponse.use {
                if (!it.isSuccessful) {
                    return LoginOutcome.Failure("Kunne ikke registrere enhet (HTTP ${it.code})")
                }
                val json = JSONObject(it.body?.string().orEmpty())
                val token = json.getString("token")
                this.deviceToken = token
                this.username = username
            }

            LoginOutcome.Success(username)
        } catch (error: Exception) {
            LoginOutcome.Failure(error.message ?: "Ukjent feil under innlogging")
        }
    }
}
