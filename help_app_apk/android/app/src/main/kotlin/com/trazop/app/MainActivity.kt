package com.trazop.app

import android.os.Bundle
import com.chaquo.python.Python
import io.flutter.embedding.android.FlutterActivity
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
    private val backendExecutor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        backendExecutor.execute {
            Python.getInstance()
                .getModule("mobile_server")
                .callAttr("start_server", filesDir.absolutePath)
        }
    }

    override fun onDestroy() {
        backendExecutor.shutdown()
        super.onDestroy()
    }
}
