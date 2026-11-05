package com.botconnect.console.ui.theme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp
private val colors = darkColorScheme(primary = Purple, background = Background, surface = Surface, surfaceVariant = androidx.compose.ui.graphics.Color(0xFF292936), onSurfaceVariant = Muted)
@Composable fun BotConnectTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors, typography = AppTypography, shapes = Shapes(small = RoundedCornerShape(12.dp), medium = RoundedCornerShape(18.dp), large = RoundedCornerShape(20.dp)), content = content)
}
