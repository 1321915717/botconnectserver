package com.botconnect.console

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import android.net.Uri
import com.botconnect.console.data.Connection
import com.botconnect.console.ui.*
import com.botconnect.console.ui.theme.BotConnectTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { BotConnectTheme { ConsoleApp() } }
    }
}
@Composable fun ConsoleApp(vm: BotConnectViewModel = viewModel()) {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    LaunchedEffect(vm.connection, vm.me, route) {
        if (vm.me != null && route == "login") nav.navigate("home") { popUpTo("login") { inclusive = true }; launchSingleTop = true }
        if (vm.me == null && vm.connection == Connection.DISCONNECTED && route != null && route != "login") nav.navigate("login") { popUpTo(nav.graph.id) { inclusive = true }; launchSingleTop = true }
    }
    LaunchedEffect(vm.openGroup) {
        vm.openGroup?.let { id -> nav.navigate("chat/group/${Uri.encode(id)}"); vm.groupOpened() }
    }
    NavHost(navController = nav, startDestination = "login") {
        composable("login") { LoginScreen(vm) }
        composable("home") { HomeScreen(vm) { kind, id -> nav.navigate("chat/$kind/${Uri.encode(id)}") } }
        composable("chat/{kind}/{id}", arguments = listOf(navArgument("kind") { type = NavType.StringType }, navArgument("id") { type = NavType.StringType })) { e ->
            ChatScreen(vm, e.arguments?.getString("kind").orEmpty(), e.arguments?.getString("id").orEmpty()) { nav.popBackStack() }
        }
    }
}
