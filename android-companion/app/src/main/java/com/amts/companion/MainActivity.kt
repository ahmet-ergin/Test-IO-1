package com.amts.companion

import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.format.DateFormat
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** Setup screen: shows whether the AccessibilityService is enabled in Settings and actually connected. */
class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var enabledView: TextView
    private lateinit var connectedView: TextView
    private lateinit var eventsView: TextView
    private val refresher = object : Runnable {
        override fun run() {
            refresh()
            handler.postDelayed(this, 1000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 96, 48, 48)
        }
        layout.addView(TextView(this).apply { text = getString(R.string.explanation); textSize = 15f })
        enabledView = statusLine(layout)
        connectedView = statusLine(layout)
        eventsView = statusLine(layout)
        layout.addView(TextView(this).apply { text = getString(R.string.transport_note); textSize = 13f; setPadding(0, 24, 0, 24) })
        layout.addView(Button(this).apply {
            text = getString(R.string.open_settings)
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })
        setContentView(layout)
    }

    private fun statusLine(parent: LinearLayout) = TextView(this).apply {
        textSize = 16f
        setPadding(0, 24, 0, 0)
        parent.addView(this)
    }

    override fun onResume() {
        super.onResume()
        handler.post(refresher)
    }

    override fun onPause() {
        handler.removeCallbacks(refresher)
        super.onPause()
    }

    private fun isEnabledInSettings(): Boolean {
        val expected = ComponentName(this, RecorderAccessibilityService::class.java)
        val enabled = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
        return enabled.split(':').mapNotNull { ComponentName.unflattenFromString(it) }.any { it == expected }
    }

    private fun refresh() {
        val enabled = isEnabledInSettings()
        val connected = ServiceStatus.connected
        enabledView.text = getString(R.string.status_enabled, yesNo(enabled))
        enabledView.setTextColor(if (enabled) GREEN else RED)
        connectedView.text = getString(R.string.status_connected, yesNo(connected))
        connectedView.setTextColor(if (connected) GREEN else RED)
        val last = if (ServiceStatus.lastEventAt == 0L) "-" else
            "${ServiceStatus.lastEventType} @ ${DateFormat.format("HH:mm:ss", ServiceStatus.lastEventAt)}"
        eventsView.text = getString(R.string.status_events, ServiceStatus.eventCount, last)
    }

    private fun yesNo(b: Boolean) = getString(if (b) R.string.yes else R.string.no)

    companion object {
        private val GREEN = Color.rgb(16, 150, 100)
        private val RED = Color.rgb(200, 40, 40)
    }
}
