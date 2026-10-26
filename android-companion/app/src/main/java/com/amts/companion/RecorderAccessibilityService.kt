package com.amts.companion

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityWindowInfo
import org.json.JSONArray
import org.json.JSONObject

/**
 * Observes accessibility events and writes them (contract v1) to logcat tag AMTS_EVT.
 * The Recorder Agent reads them over USB via `adb logcat`. Nothing is sent over the network.
 * Password fields are never logged with values. This service does not perform any actions.
 */
class RecorderAccessibilityService : AccessibilityService() {

    private var lastImeBounds: String? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        ServiceStatus.connected = true
        emit(JSONObject().put("v", 1).put("type", "SERVICE_CONNECTED").put("ts", System.currentTimeMillis())
            .put("version", BuildConfig.VERSION_NAME))
    }

    override fun onDestroy() {
        ServiceStatus.connected = false
        super.onDestroy()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        val type = when (event.eventType) {
            AccessibilityEvent.TYPE_VIEW_CLICKED -> "CLICK"
            AccessibilityEvent.TYPE_VIEW_LONG_CLICKED -> "LONG_CLICK"
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED -> "TEXT_CHANGED"
            AccessibilityEvent.TYPE_VIEW_SCROLLED -> "SCROLL"
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED -> "WINDOW_CHANGE"
            AccessibilityEvent.TYPE_WINDOWS_CHANGED -> { emitImeState(); return }
            else -> return
        }
        val pkg = event.packageName?.toString()
        if (pkg == packageName) return
        val source = event.source
        val json = JSONObject()
            .put("v", 1)
            .put("type", type)
            .put("ts", System.currentTimeMillis())
            .put("pkg", pkg)
            .put("cls", event.className?.toString())
        if (source != null) json.put("node", EventSerializer.node(source))
        if (type == "TEXT_CHANGED") {
            val password = event.isPassword || source?.isPassword == true
            val showingHint = source?.isShowingHintText == true
            val text = if (showingHint) "" else event.text.joinToString("")
            val masked = password || EventSerializer.isSensitive(source) || EventSerializer.looksLikeOtp(text)
            json.put("textLength", text.length)
            json.put("masked", masked)
            json.put("textValue", if (masked) JSONObject.NULL else EventSerializer.clip(text))
        }
        emit(json)
    }

    private fun emitImeState() {
        val ime = try {
            windows.firstOrNull { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
        } catch (e: Exception) {
            null
        }
        val bounds = ime?.let { Rect().also { r -> it.getBoundsInScreen(r) } }
        val key = bounds?.flattenToString()
        if (key == lastImeBounds) return
        lastImeBounds = key
        val json = JSONObject().put("v", 1).put("type", "IME").put("ts", System.currentTimeMillis())
        json.put("imeBounds", bounds?.let { JSONArray(listOf(it.left, it.top, it.right, it.bottom)) } ?: JSONObject.NULL)
        emit(json)
    }

    private fun emit(json: JSONObject) {
        Log.i(TAG, json.toString())
        ServiceStatus.recordEmit(json.optString("type"))
    }

    override fun onInterrupt() = Unit

    companion object {
        const val TAG = "AMTS_EVT"
    }
}
