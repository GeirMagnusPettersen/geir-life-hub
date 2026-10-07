plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.geirlifehub.companion"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.geirlifehub.companion"
        // Health Connect's permission APIs require API 26+; the Health Connect
        // app itself targets Android 9+ devices but the client library handles
        // older OS versions gracefully by reporting the SDK as unavailable.
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.4")

    // Health Connect client SDK: reads workouts, sleep sessions and heart rate
    // that Garmin Connect / Vektklubb (or any other app) already writes.
    implementation("androidx.health.connect:connect-client:1.1.0-alpha07")

    // Lightweight HTTP client for talking to the existing FastAPI backend.
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // Encrypted local storage for the session cookie / device token.
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
}
