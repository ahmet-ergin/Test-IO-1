package com.amts.companion

import android.graphics.Rect
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject

object EventSerializer {
    private const val MAX_TEXT = 300

    fun clip(s: String?): String? = s?.let { if (it.length > MAX_TEXT) it.substring(0, MAX_TEXT) else it }

    fun node(n: AccessibilityNodeInfo): JSONObject {
        val r = Rect()
        n.getBoundsInScreen(r)
        val password = n.isPassword
        return JSONObject()
            .put("resourceId", n.viewIdResourceName ?: JSONObject.NULL)
            .put("text", if (password) JSONObject.NULL else (clip(n.text?.toString()) ?: JSONObject.NULL))
            .put("contentDesc", clip(n.contentDescription?.toString()) ?: JSONObject.NULL)
            .put("hint", clip(n.hintText?.toString()) ?: JSONObject.NULL)
            .put("className", n.className?.toString() ?: JSONObject.NULL)
            .put("bounds", JSONArray(listOf(r.left, r.top, r.right, r.bottom)))
            .put("clickable", n.isClickable)
            .put("enabled", n.isEnabled)
            .put("password", password)
    }
}
