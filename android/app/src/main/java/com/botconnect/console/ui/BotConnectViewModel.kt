package com.botconnect.console.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.botconnect.console.data.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class BotConnectViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("botconnect", 0)
    var url by mutableStateOf(prefs.getString("url", "ws://43.173.102.253:8320") ?: "ws://43.173.102.253:8320")
    var key by mutableStateOf("")
    var connection by mutableStateOf(Connection.DISCONNECTED); private set
    var me by mutableStateOf<Identity?>(null); private set
    var clients by mutableStateOf<List<Client>>(emptyList()); private set
    var groups by mutableStateOf<List<Group>>(emptyList()); private set
    var messages by mutableStateOf<Map<String, List<ChatMessage>>>(emptyMap()); private set
    var error by mutableStateOf(""); private set
    var openGroup by mutableStateOf<String?>(null); private set
    private val client = BotConnectClient()
    private var secret = ""
    private var generation = 0
    private var retry: Job? = null
    private var attempt = 0
    private var authenticated = false
    private var reconnecting = false
    private val delays = longArrayOf(1, 2, 5, 10, 30)

    fun connect() {
        if (url.isBlank() || key.isBlank()) { error = "请输入 WebSocket 地址和控制台 key"; return }
        val enteredKey = key
        disconnect(false)
        key = enteredKey; secret = enteredKey
        me = null; clients = emptyList(); groups = emptyList(); messages = emptyMap(); error = ""
        attempt = 0; reconnecting = false
        startConnection()
    }
    private fun startConnection() {
        val token = ++generation
        connection = if (reconnecting) Connection.RECONNECTING else Connection.CONNECTING
        authenticated = false
        try {
            client.close()
            client.connect(url.trim(),
                onOpen = { viewModelScope.launch(Dispatchers.Main) { if (token == generation) send("auth", "key" to secret) } },
                onFrame = { frame -> viewModelScope.launch(Dispatchers.Main) { if (token == generation) handle(frame) } },
                onClosed = { reason -> viewModelScope.launch(Dispatchers.Main) { if (token == generation) closed(reason) } })
        } catch (_: IllegalArgumentException) {
            connection = Connection.DISCONNECTED; secret = ""; error = "WebSocket 地址无效"
        }
    }
    private fun closed(reason: String) {
        if (secret.isEmpty()) return
        if (!authenticated && !reconnecting) {
            connection = Connection.DISCONNECTED; secret = ""; error = "连接失败，请检查地址与服务状态"; return
        }
        reconnecting = true; connection = Connection.RECONNECTING
        val seconds = delays[attempt.coerceAtMost(delays.lastIndex)]; attempt++
        retry?.cancel(); retry = viewModelScope.launch { delay(seconds * 1000); startConnection() }
    }
    fun disconnect(clearError: Boolean = true) {
        generation++; retry?.cancel(); retry = null; client.close(); secret = ""; key = ""
        reconnecting = false; authenticated = false; connection = Connection.DISCONNECTED
        me = null; clients = emptyList(); groups = emptyList(); messages = emptyMap(); openGroup = null
        if (clearError) error = ""
    }
    private fun send(type: String, vararg fields: Pair<String, String>): Boolean {
        val obj = JSONObject().put("type", type); fields.forEach { obj.put(it.first, it.second) }
        return client.send(obj)
    }
    private fun handle(f: JSONObject) {
        when (f.optString("type")) {
            "auth_ok" -> {
                me = Identity(f.optString("client_id"), f.optString("name")); authenticated = true
                connection = Connection.CONNECTED; reconnecting = false; attempt = 0; key = ""; error = ""
                prefs.edit().putString("url", url.trim()).apply(); send("list_clients"); send("list_groups")
            }
            "error" -> {
                val message = f.optString("error")
                if (message == "authentication failed") { disconnect(false); error = message } else error = message
            }
            "clients" -> {
                val a = f.optJSONArray("clients"); clients = (0 until (a?.length() ?: 0)).mapNotNull { i -> a?.optJSONObject(i)?.let { Client(it.optString("id"), it.optString("name"), it.optBoolean("online")) } }
            }
            "groups" -> {
                val a = f.optJSONArray("groups"); groups = (0 until (a?.length() ?: 0)).mapNotNull { i -> a?.optJSONObject(i)?.let { g -> val m = g.optJSONArray("members"); Group(g.optString("id"), g.optString("name"), (0 until (m?.length() ?: 0)).map { m!!.optString(it) }) } }
            }
            "presence" -> send("list_clients")
            "group_created", "group_updated", "invited" -> {
                send("list_groups")
                if (f.optString("type") == "group_created") {
                    val id = f.optString("group_id"); val members = f.optJSONArray("members")
                    groups = groups.filterNot { it.id == id } + Group(id, f.optString("name"), (0 until (members?.length() ?: 0)).map { members!!.optString(it) })
                    openGroup = id
                }
            }
            "dm" -> { val from = f.optString("from"); add("dm", if (from == me?.id) f.optString("to") else from, from, payload(f)) }
            "group_message" -> add("group", f.optString("group_id"), f.optString("from"), payload(f))
            "message" -> { val from = f.optString("from"); if (from.isNotEmpty() && from != me?.id) add("dm", from, from, payload(f)) }
        }
    }
    private fun payload(f: JSONObject): String { val v = f.opt("payload"); return if (v == null || v == JSONObject.NULL) "null" else v.toString() }
    private fun add(kind: String, id: String, from: String, payload: String) {
        val k = "$kind:$id"; val msg = ChatMessage(from, payload, SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date()))
        messages = messages + (k to (messages[k].orEmpty() + msg))
    }
    fun sendMessage(kind: String, id: String, text: String) {
        val value = text.trim(); if (value.isEmpty()) return
        if (connection != Connection.CONNECTED) { error = "连接尚未恢复"; return }
        val sent = if (kind == "dm") send("dm", "to" to id, "payload" to value) else send("group_message", "group_id" to id, "payload" to value)
        if (!sent) error = "发送失败，请检查连接" else if (kind == "group") add(kind, id, me?.id.orEmpty(), value)
    }
    fun createGroup(name: String) { if (name.isNotBlank() && !send("create_group", "name" to name.trim())) error = "发送失败，请检查连接" }
    fun invite(group: String, id: String) { if (!send("invite", "group_id" to group, "client_id" to id)) error = "发送失败，请检查连接" }
    fun clearError() { error = "" }
    fun groupOpened() { openGroup = null }
    fun display(id: String) = if (id == me?.id) "控制台" else clients.find { it.id == id }?.name ?: id
    override fun onCleared() { disconnect(); client.shutdown(); super.onCleared() }
}
