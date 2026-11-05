# BotConnect 安卓控制台

原生 Material 3 操作员控制台，使用 WebSocket 连接现有 BotConnect 服务端。默认地址为 `ws://43.173.102.253:8320`，可在登录页修改。只持久化地址，key 不写入磁盘；登录成功后清空输入框，连接期间仅在内存中保留以便自动重连。手动断开会清除凭据和会话消息。

## Android Studio

使用支持 AGP 8.7.3 的 Android Studio，打开本目录，安装 JDK 17、Android SDK Platform 34 和 Build Tools 34，等待 Gradle 同步后运行 `app`，或通过 Build 菜单生成 debug APK。

## 命令行

安装 JDK 17 和 Android SDK（API 34），设置 `ANDROID_HOME`，然后在本目录运行：

```sh
./gradlew assembleDebug
```

APK 位于 `app/build/outputs/apk/debug/app-debug.apk`。首次运行 wrapper 会下载 Gradle 8.10.2。

## 云打包

向 `main` 推送 `android/` 或 Android workflow 的变更后，GitHub Actions 自动构建 debug APK，在 Actions 对应运行的 artifacts 中下载，保留 30 天。debug APK 仅供测试；正式发布需要另行配置签名，切勿将 keystore 或密钥提交到仓库。
