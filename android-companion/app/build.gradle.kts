plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.amts.companion"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.amts.companion"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    kotlinOptions {
        jvmTarget = "11"
    }
}
