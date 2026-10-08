# Geir Life Hub – Health Connect Companion

A minimal Android app that reads **workouts, sleep sessions and heart rate**
from [Android Health Connect](https://developer.android.com/health-and-fitness/guides/health-connect)
and pushes them to the existing Geir Life Hub FastAPI backend.

This is the companion app for GitHub issue
[`#5 – Journey: Android Health Connect-companion for automatisk Garmin-sync`](https://github.com/GeirMagnusPettersen/geir-life-hub/issues/5).

## What this app does (and does not do)

- ✅ Reads exercise sessions, sleep sessions and heart-rate samples that are
  already present in Health Connect — typically written there by Garmin
  Connect, Google Fit, or any other app the user has installed.
- ✅ Pushes that data to the backend's existing `/sleep-activity/sync` and
  `/workouts/sync` endpoints, using the same two-user household model and
  session-based auth the rest of Geir Life Hub uses (via a device token, see
  below).
- ✅ Fails in isolation: every sync run is wrapped in a single try/catch
  boundary (`SyncManager.runSync()`). A failed sync (no network, revoked
  Health Connect permission, backend error, ...) is reported in the UI as
  plain text and never crashes the app or affects anything else.
- ✅ Syncs automatically in the background on a user-configurable interval
  (via `WorkManager`/`PeriodicWorkRequest`), in addition to the manual
  "Sync now" button — see "Periodic background sync" below.
- ❌ Does **not** talk to the Garmin Connect API or scrape Vektklubb. It only
  reads what the user already exposed via Health Connect.
- ❌ Does **not** introduce a new/parallel data model. It maps Health Connect
  records onto the backend's existing `SleepActivitySummary` and (new, but
  backend-owned) `WorkoutSession` models.
- ❌ No push notifications and no new retry/backoff strategy: a failed
  scheduled sync is simply reported as "last sync failed" status in the UI —
  the next periodic run is the natural retry.

## How authentication works

The backend already has two auth mechanisms:

1. **Session cookie auth** (`POST /auth/login`) — used by the PWA/browser.
2. **Device token auth** (`POST /devices`, then `Authorization: Bearer <token>`)
   — meant for exactly this kind of sync client.

Rather than asking the user to manually copy a device token out of the PWA,
this app automates both steps behind one "Log in" button:

1. `POST /auth/login` with username + password → capture the `Set-Cookie`
   session cookie from the response.
2. `POST /devices` with that cookie (label: `Health Connect companion`) →
   receive a device token (shown once, exactly like the PWA's "Connect my
   phone" flow).
3. Store only the device token (in `EncryptedSharedPreferences`, falling back
   to plain `SharedPreferences` if the Android keystore is unavailable) and
   discard the session cookie.

All subsequent sync calls use `Authorization: Bearer <device token>`. This is
the same household model (Geir/Kristin) and the same credential type the
backend already issues — no parallel auth system.

## Project layout

```
android-companion/
├── app/
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/geirlifehub/companion/
│       │   ├── auth/SessionManager.kt         # login + device-token provisioning
│       │   ├── healthconnect/HealthConnectRepository.kt  # read-only HC wrapper
│       │   ├── sync/BackendApiClient.kt       # OkHttp calls to the backend
│       │   ├── sync/SyncManager.kt            # orchestrates read → map → push
│       │   ├── sync/SyncPreferences.kt        # persisted interval + last-sync status
│       │   ├── sync/SyncWorker.kt             # WorkManager CoroutineWorker, runs SyncManager
│       │   ├── sync/SyncScheduler.kt          # (re)schedules the periodic WorkManager job
│       │   └── ui/MainActivity.kt             # single-screen UI
│       └── res/                               # layout, strings, icons
├── build.gradle.kts / settings.gradle.kts / gradle.properties
└── gradlew, gradlew.bat, gradle/wrapper/      # Gradle 8.7 wrapper
```

## Requirements

- Android Studio Koala (2024.1) or newer, or a standalone JDK 17 + Android
  SDK (API 34) command-line setup.
- A device or emulator running **Android 9 (API 28) or newer** with the
  [Health Connect app](https://play.google.com/store/apps/details?id=com.google.android.apps.healthdata)
  installed (on Android 14+, Health Connect is built into the OS settings).
  `minSdk` for this module is 26, matching the Health Connect client library's
  own minimum, but the Health Connect *app/service* itself needs API 28+.
- A running instance of the Geir Life Hub backend (`../backend`) reachable
  from the device/emulator. The default backend URL in the app
  (`http://10.0.2.2:8000`) is the standard Android emulator alias for your
  host machine's `localhost:8000` — change it to a LAN IP (e.g.
  `http://192.168.1.50:8000`) when testing on a physical phone.

## Building

> **Verified:** `./gradlew assembleDebug` has been run end-to-end (portable
> JDK 17 + Android SDK API 34, no Android Studio) and produces a working
> debug APK with zero compile errors. The Gradle wrapper (`gradlew`/
> `gradlew.bat` + `gradle-wrapper.jar`, Gradle 8.7) is included, along with
> Android Gradle Plugin 8.5.2 and Kotlin 1.9.24, which are a known-compatible
> combination. The full login → device-token → Health-Connect-sync →
> idempotent-re-sync flow has also been exercised directly against a live
> instance of the backend (see "Backend contract" below) to confirm the
> request/response shapes match exactly what `BackendApiClient.kt` sends.
> What remains unverified from a development sandbox is the actual on-device
> Health Connect permission prompt and real Garmin-synced data — that last
> mile needs a physical Android phone or emulator.

From the `android-companion/` directory, with Android Studio or the
command line:

```bash
# Command line (requires JDK 17 and ANDROID_HOME/ANDROID_SDK_ROOT set):
./gradlew assembleDebug

# Or open android-companion/ as a project in Android Studio and hit Run.
```

If `local.properties` (SDK path) is missing, Android Studio will create it
for you on first open; it's intentionally not committed since the SDK path
is machine-specific.

## Using the app

1. Launch the app, fill in **Backend-URL**, **Brukernavn** and **Passord**
   (the same credentials used for the Geir Life Hub PWA), and tap
   **"Logg inn og registrer enhet"**.
2. Tap **"Be om Health Connect-tilgang"** and grant read access to exercise,
   sleep and heart rate when prompted by the Health Connect permission
   screen.
3. Tap **"Synkroniser nå"**. The app reads the last 14 days of sleep sessions
   and workouts from Health Connect and POSTs them to the backend. The
   status line reports how many sleep entries and workouts were synced, or a
   plain-language error if something went wrong — a failed sync never
   crashes the app.
4. Pick a **synk-intervall** (1/3/6/12/24 timer) from the dropdown. Once
   logged in, the app schedules a background sync job at that interval and
   displays the last automatic-or-manual sync's time and status below it.

## Periodic background sync

Starting with [issue #14](https://github.com/GeirMagnusPettersen/geir-life-hub/issues/14),
the app no longer depends solely on the user remembering to tap "Sync now":

- A `WorkManager` `PeriodicWorkRequest` (`SyncScheduler` + `SyncWorker`) runs
  `SyncManager.runSync()` in the background on the interval chosen in the UI
  (1, 3, 6, 12 or 24 hours — WorkManager's own floor is 15 minutes, but the
  UI only offers whole-hour choices down to 1 hour).
- The job only runs when the device has network connectivity
  (`Constraints(NetworkType.CONNECTED)`), and only while the user is logged
  in; it is (re)scheduled automatically after login and whenever the
  interval selection changes, using `enqueueUniquePeriodicWork(...,
  ExistingPeriodicWorkPolicy.UPDATE, ...)` so changing the interval replaces
  the existing job instead of running two in parallel.
- The chosen interval and the outcome (success/failure + message/timestamp)
  of the most recent sync — scheduled or manual — are persisted in
  `SyncPreferences` (plain `SharedPreferences`) and shown on the main screen.
- A failed background sync is recorded as status only; it never throws,
  crashes, or triggers a push notification. There is still no new
  retry/backoff strategy beyond "the next periodic run will try again" — the
  backend contract and `SyncManager`'s own error handling are unchanged.

## Backend contract

This app only talks to two existing/extended backend endpoints
(see `../backend/app/routers/sleep_activity.py` and
`../backend/app/routers/workouts.py`):

- `POST /sleep-activity/sync` — batch of `{summary_date, sleep_minutes,
  steps, resting_heart_rate, avg_heart_rate}`, upserted per
  `(user, summary_date)`.
- `POST /workouts/sync` — batch of `{external_id, activity_type, start_time,
  end_time, duration_minutes, calories, avg_heart_rate, distance_meters}`,
  idempotent per `(user, source="health_connect", external_id)` using Health
  Connect's own stable record id as `external_id`.

Both endpoints require `Authorization: Bearer <device token>` and are
documented further in the backend's own code/tests
(`backend/tests/test_core_logs.py`, `backend/tests/test_workouts.py`).
