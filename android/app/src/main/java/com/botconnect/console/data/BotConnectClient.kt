package com.botconnect.console.data

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class BotConnectClient {
    private val http = OkHttpClient.Builder().pingInterval(30, TimeUnit.SECONDS).build()
    private var socket: WebSocket? = null

    fun connect(url: String, onOpen: () -> Unit, onFrame: (JSONObject) -> Unit, onClosed: (String) -> Unit) {
        val request = Request.Builder().url(url).build()
        socket = http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) = onOpen()
            override fun onMessage(webSocket: WebSocket, text: String) {
                try { onFrame(JSONObject(text)) } catch (_: org.json.JSONException) { }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) { webSocket.close(code, reason) }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = onClosed(reason)
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) = onClosed(t.message ?: "连接失败")
        })
    }
    fun send(frame: JSONObject): Boolean = socket?.send(frame.toString()) == true
    fun close() { socket?.cancel(); socket = null }
    fun shutdown() { close(); http.dispatcher.executorService.shutdown(); http.connectionPool.evictAll() }
}
