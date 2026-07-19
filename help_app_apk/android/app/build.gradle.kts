plugins {
    id("com.android.application")
    id("kotlin-android")
    id("com.chaquo.python")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val trazopBackendRoot = rootProject.projectDir.resolve("../..")
val generatedPythonBackend = layout.buildDirectory.dir("generated/trazop_python")
val syncTrazopBackend by tasks.registering(Sync::class) {
    from(trazopBackendRoot) {
        include("app.py")
        include("admin/**")
        include("core/**")
        include("usuario/**")
        include("templates/**")
        include("static/**")
        exclude("**/__pycache__/**")
        exclude("**/*.pyc")
        exclude("**/*.db")
    }
    into(generatedPythonBackend)
}

android {
    namespace = "com.trazop.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.trazop.app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
    }

    buildTypes {
        release {
            // TODO: Add your own signing config for the release build.
            // Signing with the debug keys for now, so `flutter run --release` works.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.13"
        buildPython(
            "C:/Users/Jason/AppData/Local/Programs/Python/Python313/python.exe",
        )
        pip {
            install("Flask==3.1.2")
            install("Werkzeug==3.1.4")
            install("openpyxl==3.1.5")
            install("tzdata==2025.3")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir(generatedPythonBackend)
        }
    }
}

tasks.configureEach {
    if (name.contains("Python", ignoreCase = true)) {
        dependsOn(syncTrazopBackend)
    }
}

flutter {
    source = "../.."
}
