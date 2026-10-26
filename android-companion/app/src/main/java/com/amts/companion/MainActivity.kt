package com.amts.companion

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 96, 48, 48)
        }
        layout.addView(TextView(this).apply { text = getString(R.string.explanation); textSize = 16f })
        layout.addView(Button(this).apply {
            text = getString(R.string.open_settings)
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })
        setContentView(layout)
    }
}
