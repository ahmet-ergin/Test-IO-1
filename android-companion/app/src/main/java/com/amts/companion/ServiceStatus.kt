package com.amts.companion

/** In-process status shared between the service and the setup screen (same app process). */
object ServiceStatus {
    @Volatile var connected: Boolean = false
    @Volatile var eventCount: Long = 0
    @Volatile var lastEventAt: Long = 0
    @Volatile var lastEventType: String? = null

    fun recordEmit(type: String) {
        eventCount++
        lastEventAt = System.currentTimeMillis()
        lastEventType = type
    }
}
