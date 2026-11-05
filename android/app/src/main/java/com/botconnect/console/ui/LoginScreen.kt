package com.botconnect.console.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.botconnect.console.data.Connection
import com.botconnect.console.ui.theme.Muted
import com.botconnect.console.ui.theme.Purple

@Composable fun LoginScreen(vm: BotConnectViewModel) {
    Column(Modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 28.dp, vertical = 36.dp), verticalArrangement = Arrangement.Center) {
        Text("✦", color = Purple, fontSize = 70.sp)
        Spacer(Modifier.height(20.dp))
        Text("BOTCONNECT / OPERATOR", color = Purple, style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.height(12.dp))
        Text("BotConnect 控制台", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(12.dp))
        Text("连接管理端，随时查看和操作你的服务。", color = Muted)
        Spacer(Modifier.height(36.dp))
        OutlinedTextField(vm.url, { vm.url = it }, label = { Text("WebSocket 地址") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(vm.key, { vm.key = it }, label = { Text("控制台 key") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
        if (vm.error.isNotEmpty()) { Spacer(Modifier.height(12.dp)); Text(vm.error, color = MaterialTheme.colorScheme.error) }
        Spacer(Modifier.height(24.dp))
        Button(onClick = vm::connect, enabled = vm.connection == Connection.DISCONNECTED, modifier = Modifier.fillMaxWidth().height(56.dp)) { Text(if (vm.connection == Connection.CONNECTING) "连接中…" else "连接管理端") }
        Spacer(Modifier.height(32.dp))
        Text("连接后可与在线服务私聊或创建群聊", color = Muted, style = MaterialTheme.typography.bodySmall, modifier = Modifier.align(Alignment.CenterHorizontally))
    }
}
