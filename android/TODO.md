# 安卓控制台 TODO

> 状态：待开发。2026-11-05 先把功能描述落下来提交，代码等 Codex 恢复后按本文档写。
> 当前卡点：Codex 调用网关三个模型（gpt-6.1-luna、gpt-6-luna、gpt-5.6-luna）均零输出卡住，
> 网关本身可达、Codex 程序正常，疑似网关侧很慢或排队，等 Mark 确认网关状态与 6.1 模型的准确 id。
> 本地编译环境已就绪：JDK 17 + Gradle 8.10.2 + Android SDK（API 34、build-tools 34.0.0）。

## 目标

给 BotConnect 服务端控制台做一个**原生安卓版 App**。注意：是**前端页面（操作员控制台）的安卓版**，
不是把服务端跑在安卓上。服务端保持 Python 不变。

对标对象：现有 Vue 3 网页控制台（`web/src/App.vue`，单文件），功能一比一，但界面按手机重新设计，
不要照搬网页。

## 技术选型

- 语言：Kotlin，Jetpack Compose 写界面（Material 3）
- 网络：OkHttp 连 WebSocket（安卓标准做法）
- 版本：Kotlin 2.0.21、AGP 8.7.3、Gradle 8.10.2、Compose BOM 2024.09.00、OkHttp 4.12.0
- minSdk 26、targetSdk 34、compileSdk 34、Java 17
- 包名 `com.botconnect.console`，应用名「BotConnect 控制台」
- 依赖越少越好：JSON 用 Android 内置 `org.json`，不另引序列化库
- 权限：INTERNET；`android:usesCleartextTraffic="true"`（`ws://` 是明文，安卓 9+ 默认禁明文流量）

## 协议（与网页版完全一致，服务端不用改）

服务端地址（已部署、可直接用）：WS `ws://43.173.102.253:8320`，控制台 `http://43.173.102.253:8319`，
TCP `43.173.102.253:8317`。App 内默认 WS 地址填 `ws://43.173.102.253:8320`，用户可改。

- 鉴权：首帧 `{"type":"auth","key":<控制台 key>}` → `{"type":"auth_ok","client_id","name"}`；
  key 错 → `{"type":"error","error":"authentication failed"}`，留在登录页显示错误。
- `list_clients` → `clients`：`[{"id","name","online"}]`（全部已配置身份，含在线标志）
- `list_groups` → `groups`：`[{"id","name","members":[client_id]}]`（仅我加入的群）
- `dm`：`{"type":"dm","to":<client_id>,"payload":<文本>}`，服务端会同时发给发送方和接收方
  `{"type":"dm","from","to","payload"}`；错误 `unknown client` / `client offline`
- `group_message`：`{"type":"group_message","group_id","payload"}`，服务端只发给其他成员
  `{"type":"group_message","group_id","from","payload"}`（不回显给发送方，发送方自己本地补一条）
- `create_group`：`{"type":"create_group","name"}` → `{"type":"group_created","group_id","name","members"}`（只发给创建者）
- `invite`：`{"type":"invite","group_id","client_id"}` → `{"type":"group_updated","group_id","name","members"}`（发给全体成员）
- 广播 `{"type":"message","payload"}`：操作员发给所有客户端；网页版没有广播入口，App 也不做。
- 推送帧：
  - `presence`（`{"type":"presence","client_id","name","online"}`）→ 重新请求 `list_clients`
  - `group_created` / `group_updated` / `invited` → 重新请求 `list_groups`；收到 `group_created` 直接打开该群
  - `dm` → 追加到与对方的私聊（`from` 是我则对方是 `to`，否则对方是 `from`）
  - `group_message` → 追加到对应群聊
  - `message`（别的客户端上报给操作员）→ 追加到与 `from` 的私聊（`from` 不是我才加）
  - `error` → 界面显示错误文本；除鉴权失败外不断开
- 断线重连：意外断开按 1/2/5/10/30 秒退避自动重连，显示“重连中…”；手动断开则停止重连。
- 消息只存内存（按会话 `dm:<client_id>` / `group:<group_id>` 分组，每条 `{from, payload, time}`，时间 `HH:mm`），
  退出即丢，和网页版一致；每个会话记最后一条消息，用于列表预览。

## 界面（好看、手机原生、不要照搬网页）

- Material 3 深色主题：深炭底色（#0E0E13 左右）、紫色主色（#8B7CFF）、大圆角（16–20dp）、间距宽松、触摸目标大。
- 品牌：BotConnect + ✦ 标记。
- 三个界面（单 Activity + Compose Navigation：`login → home → chat/{kind}/{id}`）：
  1. **登录页**：大 Logo +「BotConnect 控制台」，副标题说明；WS 地址输入框（默认填上次用过的地址，
     首次默认 `ws://43.173.102.253:8320`）、控制台 key 密码框、大号「连接管理端」按钮、表单下显示错误、
     脚注「连接后可与在线服务私聊或创建群聊」。
  2. **主页**：顶栏（我的头像 + 名字 +「在线」+ 断开按钮）；Tab 分「服务」「群聊」两栏；
     服务行：首字母头像（背景色按 id 哈希取）、名字、「在线/离线 · 短 id」（超过 12 位取前 8 位 + …）、
     绿色在线圆点、箭头；群聊行：「#」头像、群名、「N 位成员」；每行显示最后一条消息预览 + 时间；
     「群聊」页右下角「+」悬浮按钮，点开建群对话框（输入群名 + 创建/取消）。
  3. **聊天页**：顶栏（头像、名字；私聊副标题「服务私聊 · 在线/离线」，群聊副标题「N 位成员 · 群 ID: xxx」，
     群聊有「+ 邀请服务」按钮，打开底部面板列出未入群的在线服务）；消息区：自己的消息右对齐紫色气泡，
     别人的左对齐浅色气泡，带发送者显示名 + 时间；底部输入框圆角 + 圆形发送按钮；空会话显示 ✧「准备发送消息」。
- 显示名规则：用 `clients` 列表里的 `name`；自己的 id 显示为「控制台」。
- 只记住 WS 地址（SharedPreferences），**不存 key**（登录成功后清空，和网页版一致）。

## 目录结构（待建）

```
android/
  TODO.md                  ← 本文件
  README.md                ← 说明 + Android Studio 编译步骤 + 云打包说明
  settings.gradle.kts
  build.gradle.kts         ← 根工程
  gradle.properties
  gradlew / gradlew.bat / gradle/wrapper/
  app/build.gradle.kts
  app/proguard-rules.pro
  app/src/main/AndroidManifest.xml
  app/src/main/java/com/botconnect/console/MainActivity.kt
  app/src/main/java/com/botconnect/console/data/Models.kt
  app/src/main/java/com/botconnect/console/data/BotConnectClient.kt   ← OkHttp WebSocket 封装
  app/src/main/java/com/botconnect/console/ui/BotConnectViewModel.kt  ← 状态 + 帧处理
  app/src/main/java/com/botconnect/console/ui/theme/Color.kt
  app/src/main/java/com/botconnect/console/ui/theme/Theme.kt
  app/src/main/java/com/botconnect/console/ui/theme/Type.kt
  app/src/main/java/com/botconnect/console/ui/LoginScreen.kt
  app/src/main/java/com/botconnect/console/ui/HomeScreen.kt
  app/src/main/java/com/botconnect/console/ui/ChatScreen.kt
  app/src/main/res/values/strings.xml
  app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml (+ round)
  app/src/main/res/drawable/ic_launcher_foreground.xml   ← ✦ 矢量图标
.github/workflows/android.yml   ← 云打包：push 到 main 触发，checkout + JDK 17 + Gradle，
                                  ./gradlew assembleDebug，上传 debug APK 为 artifact（30 天）
```

## 云打包

- 首选 **GitHub Actions**（仓库已在 GitHub，公开仓免费）：push 触发，跑 `assembleDebug`，
  APK 作为 artifact 可下载安装；后续要发正式版再加签名（keystore 放 GitHub Secrets）。
- 备选：Codemagic / Appcircle 等第三方云打包（要另接账号，不首选）。
- 本地编包：Android Studio 打开 `android/` 即可；或命令行 `./gradlew assembleDebug`。

## 验收标准

- [ ] 登录：填 WS 地址 + key 能连上，错 key 显示 `authentication failed`，不闪退
- [ ] 服务列表：在线/离线状态对，短 id 显示对，点开能私聊
- [ ] 私聊：双向收发正常，对方离线时服务端报 `client offline`，界面有提示
- [ ] 群聊：建群、邀请、群内收发都正常；建群后自动打开新群
- [ ] 断线重连：杀掉服务端再启动，App 自动重连回来（1/2/5/10/30 秒退避）
- [ ] GitHub Actions 能出 debug APK，可下载安装
- [ ] 不照搬网页：界面是手机原生的 Material 3 形态（评审时肉眼确认）
