package com.botconnect.console.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.botconnect.console.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun ChatScreen(vm: BotConnectViewModel, kind: String, id: String, back: () -> Unit) {
    val group = vm.groups.find { it.id == id }; val peer = vm.clients.find { it.id == id }
    val title = if (kind == "group") group?.name ?: id else peer?.name ?: id
    val subtitle = if (kind == "group") "${group?.members?.size ?: 0} 位成员 · 群 ID: $id" else "服务私聊 · ${if (peer?.online == true) "在线" else "离线"}"
    var inviting by remember { mutableStateOf(false) }; var text by remember(id, kind) { mutableStateOf("") }
    val conversation = vm.messages["$kind:$id"].orEmpty(); val listState = rememberLazyListState()
    LaunchedEffect(conversation.size) { if (conversation.isNotEmpty()) listState.animateScrollToItem(conversation.lastIndex) }
    Scaffold(topBar = {
        Column {
            Row(Modifier.fillMaxWidth().statusBarsPadding().padding(end = 8.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = back) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
                Avatar(if (kind == "group") "#" else title, id, if (kind == "dm") peer?.online else null)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) { Text(title, fontWeight = FontWeight.Bold, maxLines = 1); Text(subtitle, style = MaterialTheme.typography.bodySmall, color = Muted, maxLines = 1) }
                if (kind == "group") TextButton(onClick = { inviting = true }) { Text("＋ 邀请服务") }
            }
            ErrorNotice(vm)
        }
    }, bottomBar = {
        Row(Modifier.fillMaxWidth().navigationBarsPadding().imePadding().padding(12.dp), verticalAlignment = Alignment.Bottom) {
            OutlinedTextField(text, { text = it }, modifier = Modifier.weight(1f), placeholder = { Text("输入消息…") }, maxLines = 4, shape = RoundedCornerShape(20.dp))
            Spacer(Modifier.width(8.dp)); FilledIconButton(onClick = { vm.sendMessage(kind, id, text); text = "" }, enabled = text.isNotBlank(), modifier = Modifier.size(56.dp)) { Icon(Icons.AutoMirrored.Filled.Send, "发送") }
        }
    }) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            if (conversation.isEmpty()) Column(Modifier.align(Alignment.Center), horizontalAlignment = Alignment.CenterHorizontally) { Text("✧", fontSize = 48.sp, color = Purple); Text("准备发送消息", fontWeight = FontWeight.Bold); Spacer(Modifier.height(8.dp)); Text("发送消息到所选服务或群聊。", color = Muted) }
            else LazyColumn(state = listState, contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp), modifier = Modifier.fillMaxSize()) {
                items(conversation) { msg ->
                    val own = msg.from == vm.me?.id
                    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (own) Alignment.End else Alignment.Start) {
                        Text("${vm.display(msg.from)}  ${msg.time}", style = MaterialTheme.typography.labelSmall, color = Muted)
                        Spacer(Modifier.height(5.dp))
                        Text(msg.payload, Modifier.widthIn(max = 300.dp).background(if (own) Purple else MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(18.dp)).padding(horizontal = 16.dp, vertical = 12.dp), color = if (own) androidx.compose.ui.graphics.Color.White else MaterialTheme.colorScheme.onSurface)
                    }
                }
            }
        }
    }
    if (inviting) ModalBottomSheet(onDismissRequest = { inviting = false }) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 24.dp)) {
            Text("邀请在线服务", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(16.dp))
            val available = vm.clients.filter { it.online && it.id != vm.me?.id && it.id !in group?.members.orEmpty() }
            if (available.isEmpty()) Text("暂无可邀请的在线服务", color = Muted, modifier = Modifier.padding(vertical = 20.dp))
            else LazyColumn { items(available, key = { it.id }) { c -> ListItem(headlineContent = { Text(c.name) }, supportingContent = { Text(shortId(c.id)) }, leadingContent = { Avatar(c.name, c.id, true) }, trailingContent = { TextButton(onClick = { vm.invite(id, c.id); inviting = false }) { Text("邀请") } }) } }
            Spacer(Modifier.height(24.dp))
        }
    }
}
