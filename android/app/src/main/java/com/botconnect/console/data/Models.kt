package com.botconnect.console.data

data class Client(val id: String, val name: String, val online: Boolean)
data class Group(val id: String, val name: String, val members: List<String>)
data class ChatMessage(val from: String, val payload: String, val time: String)
data class Identity(val id: String, val name: String)
enum class Connection { DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING }
