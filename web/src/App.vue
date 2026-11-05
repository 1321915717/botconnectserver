<script setup>
import { ref, computed } from 'vue'
const url = ref(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.hostname || 'localhost'}:${import.meta.env.VITE_WS_PORT || '9101'}`)
const key = ref(''), me = ref(null), clients = ref([]), groups = ref([]), selected = ref(null), text = ref(''), error = ref(''), messages = ref({}), connected = ref(false), inviting = ref(false)
let ws
const current = computed(() => selected.value && (selected.value.kind === 'dm' ? clients.value.find(c => c.id === selected.value.id) : groups.value.find(g => g.id === selected.value.id)))
const conversation = computed(() => selected.value ? messages.value[`${selected.value.kind}:${selected.value.id}`] || [] : [])
const peers = computed(() => clients.value.filter(c => c.id !== me.value?.id))
const online = computed(() => peers.value.filter(c => c.online))
function send(frame) { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(frame)) }
function add(kind, id, from, payload) { const k = `${kind}:${id}`; (messages.value[k] ||= []).push({ from, payload, time: new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) }) }
function refresh() { send({type:'list_clients'}); send({type:'list_groups'}) }
function connect() {
  error.value = ''; me.value = null; clients.value = []; groups.value = []; selected.value = null; messages.value = {}
  try { ws = new WebSocket(url.value) } catch { error.value = 'WebSocket 地址无效'; return }
  ws.onopen = () => send({type:'auth', key:key.value})
  ws.onerror = () => { error.value = '连接失败，请检查地址与服务状态' }
  ws.onclose = () => { connected.value = false; if (!error.value) error.value = '连接已断开' }
  ws.onmessage = event => {
    let f; try { f = JSON.parse(event.data) } catch { return }
    if (f.type === 'auth_ok') { me.value = {id:f.client_id,name:f.name}; connected.value = true; key.value = ''; refresh() }
    else if (f.type === 'error') error.value = f.error
    else if (f.type === 'clients') clients.value = f.clients
    else if (f.type === 'groups') groups.value = f.groups
    else if (f.type === 'presence') send({type:'list_clients'})
    else if (['group_created','group_updated','invited'].includes(f.type)) { send({type:'list_groups'}); if (f.type === 'group_created') selected.value = {kind:'group',id:f.group_id} }
    else if (f.type === 'dm') add('dm', f.from === me.value.id ? f.to : f.from, f.from, f.payload)
    else if (f.type === 'group_message') add('group', f.group_id, f.from, f.payload)
    else if (f.type === 'message' && f.from && f.from !== me.value.id) add('dm', f.from, f.from, f.payload)
  }
}
function submit() { const value = text.value.trim(); if (!value || !selected.value) return; if (selected.value.kind === 'dm') send({type:'dm',to:selected.value.id,payload:value}); else { send({type:'group_message',group_id:selected.value.id,payload:value}); add('group',selected.value.id,me.value.id,value) } text.value = '' }
function createGroup() { const name = prompt('输入群聊名称'); if (name?.trim()) send({type:'create_group',name:name.trim()}) }
function invite(id) { if (!id) return; send({type:'invite',group_id:selected.value.id,client_id:id}); inviting.value = false }
function shortId(id) { return id.length > 12 ? `${id.slice(0, 8)}…` : id }
function display(id) { return id === me.value?.id ? '控制台' : `服务 · ${clients.value.find(c => c.id === id)?.name || id}` }
function content(v) { return typeof v === 'string' ? v : JSON.stringify(v) }
</script>
<template>
  <div v-if="!connected" class="login-wrap"><div class="glow"></div><section class="login card"><div class="brand-icon">✦</div><p class="eyebrow">BOTCONNECT / OPERATOR</p><h1>BotConnect 控制台</h1><p class="muted">使用 WebSocket 地址和控制台 key 连接管理端，查看并操作在线服务。</p><form @submit.prevent="connect"><label>WebSocket 地址<input v-model="url" required placeholder="ws://localhost:9001"></label><label>控制台 key<input v-model="key" required type="password" placeholder="输入控制台 key" autocomplete="current-password"></label><p v-if="error" class="error">{{ error }}</p><button class="primary" type="submit">连接管理端 <span>↗</span></button></form><p class="footnote">连接后可与在线服务私聊或创建群聊</p></section></div>
  <div v-else class="shell"><aside class="sidebar"><div class="brand"><div class="brand-icon small">✦</div><div><strong>botconnect</strong><div class="brand-sub">OPERATOR CONSOLE</div></div></div><div class="profile"><div class="avatar violet">{{ me.name[0]?.toUpperCase() }}</div><div class="grow"><strong>{{ me.name }}</strong><div class="muted tiny"><i class="dot"></i> 在线</div></div><button class="icon" title="断开连接" @click="ws.close()">⏻</button></div><div class="section-title">服务端 · 客户端 <span>{{ online.length }}/{{ peers.length }}</span></div><div v-if="!peers.length" class="empty-small">尚未配置任何客户端</div><button v-for="client in peers" :key="client.id" class="nav-item" :class="{active:selected?.kind === 'dm' && selected.id === client.id, offline:!client.online}" @click="selected={kind:'dm',id:client.id}; inviting=false"><div class="avatar">{{ client.name[0]?.toUpperCase() }}</div><span class="grow"><strong>{{ client.name }}</strong><span class="service-meta"><i class="dot"></i>{{ client.online ? '在线' : '离线' }} · {{ shortId(client.id) }}</span></span></button><div class="section-title">我的群聊 <button class="icon" title="创建群聊" @click="createGroup">＋</button></div><div v-if="!groups.length" class="empty-small">创建群聊以连接多个服务</div><button v-for="group in groups" :key="group.id" class="nav-item" :class="{active:selected?.kind === 'group' && selected.id === group.id}" @click="selected={kind:'group',id:group.id}; inviting=false"><div class="avatar group-avatar">#</div><span>{{ group.name }}</span></button><div class="sidebar-bottom">✦ &nbsp; 服务连接管理</div></aside><main class="chat"><header class="chat-header"><template v-if="selected"><div class="avatar" :class="{'group-avatar':selected.kind === 'group'}">{{ selected.kind === 'group' ? '#' : current?.name?.[0]?.toUpperCase() }}</div><div class="grow"><strong>{{ current?.name || selected.id }}</strong><div class="muted tiny">{{ selected.kind === 'group' ? `${current?.members?.length || 0} 位成员 · 群 ID: ${selected.id}` : `服务私聊 · ${current?.online ? '在线' : '离线'}` }}</div></div><button v-if="selected.kind === 'group'" class="outline" @click="inviting = !inviting">＋ 邀请服务</button></template><span v-else class="muted">选择在线服务或群聊</span></header><div v-if="inviting && selected?.kind === 'group'" class="invite-panel"><strong>邀请在线服务</strong><p v-if="!online.filter(c => !current?.members?.includes(c.id)).length" class="muted tiny">暂无可邀请的在线服务</p><button v-for="client in online.filter(c => !current?.members?.includes(c.id))" :key="client.id" class="invite-option" @click="invite(client.id)"><i class="dot"></i>{{ client.name }} <span>{{ shortId(client.id) }}</span></button></div><div v-if="error" class="notice" @click="error=''">{{ error }} <span>×</span></div><div v-if="selected" class="message-area"><div class="date-label">今天</div><div v-if="!conversation.length" class="welcome"><div>✧</div><strong>准备发送消息</strong><p>发送消息到所选服务或群聊。</p></div><div v-for="(msg,index) in conversation" :key="index" class="message" :class="{own:msg.from === me.id}"><div class="avatar mini">{{ display(msg.from)[0]?.toUpperCase() }}</div><div><div class="message-meta">{{ display(msg.from) }} <span>{{ msg.time }}</span></div><div class="bubble">{{ content(msg.payload) }}</div></div></div></div><div v-else class="welcome center"><div>✧</div><strong>欢迎使用控制台</strong><p>选择左侧在线服务进行私聊，或创建群聊并邀请服务。</p></div><form v-if="selected" class="composer" @submit.prevent="submit"><input v-model="text" placeholder="输入消息..." aria-label="消息"><button class="primary" :disabled="!text.trim()">发送 <span>↗</span></button></form><div v-if="selected" class="hint">ENTER 发送消息</div></main></div>
</template>
