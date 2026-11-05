package com.botconnect.console.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.botconnect.console.data.Connection
import com.botconnect.console.ui.theme.*

fun shortId(id: String) = if (id.length > 12) id.take(8) + "…" else id
@Composable fun Avatar(name: String, id: String, online: Boolean? = null) {
    val shades = listOf(Color(0xFF514777), Color(0xFF365D68), Color(0xFF70505F), Color(0xFF465D52), Color(0xFF62573E))
    Box(Modifier.size(48.dp), contentAlignment = Alignment.Center) {
        Box(Modifier.fillMaxSize().background(shades[(id.hashCode().toLong().let { kotlin.math.abs(it) } % shades.size).toInt()], CircleShape), contentAlignment = Alignment.Center) { Text(name.take(1).uppercase().ifEmpty { "?" }, fontWeight = FontWeight.Bold) }
        if (online != null) Box(Modifier.align(Alignment.BottomEnd).size(12.dp).background(Background, CircleShape).padding(2.dp).background(if (online) Online else Muted, CircleShape))
    }
}
@Composable fun ErrorNotice(vm: BotConnectViewModel) {
    if (vm.error.isNotEmpty()) Surface(color = MaterialTheme.colorScheme.errorContainer, modifier = Modifier.fillMaxWidth().clickable { vm.clearError() }) { Text(vm.error + "   ×", Modifier.padding(12.dp), color = MaterialTheme.colorScheme.onErrorContainer) }
    if (vm.connection == Connection.RECONNECTING) Surface(color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.fillMaxWidth()) { Text("重连中…", Modifier.padding(12.dp), color = Purple) }
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable fun HomeScreen(vm: BotConnectViewModel, open: (String, String) -> Unit) {
    var tab by remember { mutableIntStateOf(0) }
    var create by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    Scaffold(floatingActionButton = { if (tab == 1) FloatingActionButton(onClick = { create = true }) { Icon(Icons.Default.Add, "创建群聊") } }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 18.dp), verticalAlignment = Alignment.CenterVertically) {
                Avatar(vm.me?.name.orEmpty(), vm.me?.id.orEmpty(), vm.connection == Connection.CONNECTED)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) { Text(vm.me?.name.orEmpty(), fontWeight = FontWeight.Bold); Text(if (vm.connection == Connection.RECONNECTING) "重连中…" else "在线", color = if (vm.connection == Connection.CONNECTED) Online else Muted, style = MaterialTheme.typography.bodySmall) }
                IconButton(onClick = { vm.disconnect() }) { Icon(Icons.Default.PowerSettingsNew, "断开连接") }
            }
            ErrorNotice(vm)
            PrimaryTabRow(selectedTabIndex = tab) { listOf("服务", "群聊").forEachIndexed { index, title -> Tab(selected = tab == index, onClick = { tab = index }, text = { Text(title) }) } }
            if (tab == 0) {
                val peers = vm.clients.filter { it.id != vm.me?.id }.distinctBy { it.id }
                if (peers.isEmpty()) EmptyList("尚未配置任何客户端") else LazyColumn(contentPadding = PaddingValues(vertical = 8.dp)) {
                    items(peers, key = { it.id }) { c -> ConversationRow(c.name, c.id, "${if (c.online) "在线" else "离线"} · ${shortId(c.id)}", c.online, vm.messages["dm:${c.id}"].orEmpty().lastOrNull()) { open("dm", c.id) } }
                }
            } else {
                if (vm.groups.isEmpty()) EmptyList("创建群聊以连接多个服务") else LazyColumn(contentPadding = PaddingValues(bottom = 88.dp, top = 8.dp)) {
                    items(vm.groups, key = { it.id }) { g -> ConversationRow(g.name, g.id, "${g.members.size} 位成员", null, vm.messages["group:${g.id}"].orEmpty().lastOrNull(), "#") { open("group", g.id) } }
                }
            }
        }
    }
    if (create) AlertDialog(onDismissRequest = { create = false }, title = { Text("创建群聊") }, text = { OutlinedTextField(name, { name = it }, label = { Text("群聊名称") }, singleLine = true) }, confirmButton = { TextButton(onClick = { vm.createGroup(name); name = ""; create = false }, enabled = name.isNotBlank()) { Text("创建") } }, dismissButton = { TextButton(onClick = { create = false }) { Text("取消") } })
}
@Composable private fun EmptyList(text: String) { Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(text, color = Muted) } }
@Composable private fun ConversationRow(name: String, id: String, subtitle: String, online: Boolean?, last: com.botconnect.console.data.ChatMessage?, avatar: String = name, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 20.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Avatar(avatar, id, online); Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Row { Text(name, Modifier.weight(1f), fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis); if (last != null) Text(last.time, color = Muted, style = MaterialTheme.typography.labelSmall) }
            Spacer(Modifier.height(4.dp)); Text(subtitle, color = Muted, style = MaterialTheme.typography.bodySmall)
            if (last != null) Text(last.payload, color = Muted, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = Muted)
    }
}
