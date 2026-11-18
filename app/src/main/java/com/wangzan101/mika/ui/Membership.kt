package com.wangzan101.mika.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.wangzan101.mika.ui.theme.MikaTheme
import com.wangzan101.mika.settings.LicensePlan
import com.wangzan101.mika.settings.LicenseResult
import com.wangzan101.mika.settings.LicenseStore
import com.wangzan101.mika.settings.LicenseCode

/**
 * 会员弹窗:显示当前授权、本机设备码,并提供激活码输入。
 * 用弹窗而不是新页面,是为了不改路由表。
 */
@Composable
fun MembershipDialog(onDismiss: () -> Unit) {
    val c = MikaTheme.colors
    val context = LocalContext.current
    val store = remember(context) { LicenseStore(context) }
    var license by remember { mutableStateOf(store.load()) }
    var input by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    val device = remember(context) { LicenseCode.deviceFingerprint(context) }

    androidx.compose.ui.window.Dialog(onDismissRequest = onDismiss) {
        androidx.compose.material3.Surface(shape = RoundedCornerShape(18.dp), color = c.surface) {
            Column(Modifier.padding(18.dp)) {
                Text("会员", fontSize = 16.sp, color = c.ink, fontWeight = FontWeight.Medium)

                // 当前状态
                val lic = license
                val statusText = when {
                    lic == null -> "未激活"
                    !lic.active() -> "已过期"
                    else -> when (lic.plan) {
                        LicensePlan.Trial -> "试用中"
                        LicensePlan.Monthly -> "已开通 10 元版"
                        LicensePlan.Pro -> "已开通 30 元订阅"
                    }
                }
                Text(
                    statusText,
                    fontSize = 13.sp, color = if (lic?.active() == true) c.ok else c.ink2,
                    modifier = Modifier.padding(top = 8.dp),
                )
                if (lic?.active() == true) {
                    Text(
                        "剩余 ${lic.daysLeft()} 天 · " + if (lic.canPickModel()) "可自选模型" else "仅 AGNES 模型",
                        fontSize = 11.sp, color = c.ink3, modifier = Modifier.padding(top = 2.dp),
                    )
                }

                // 本机设备码
                Row(
                    Modifier.fillMaxWidth().padding(top = 12.dp)
                        .background(c.greySoft, RoundedCornerShape(10.dp))
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("本机设备码", fontSize = 12.sp, color = c.ink2)
                    Text(
                        device,
                        fontSize = 15.sp, color = c.ink, fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(start = 10.dp),
                    )
                    Text(
                        "（发给作者换激活码）",
                        fontSize = 10.sp, color = c.ink3, modifier = Modifier.padding(start = 6.dp),
                    )
                }

                // 输入激活码
                Text(
                    "激活码",
                    fontSize = 12.sp, color = c.ink2, modifier = Modifier.padding(top = 14.dp),
                )
                androidx.compose.material3.OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    singleLine = true,
                    placeholder = { Text("例如 P20261218VWZ47A3F21-BB326843", fontSize = 11.sp) },
                    modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                )
                Text(
                    "激活",
                    fontSize = 13.sp, color = c.accent, fontWeight = FontWeight.Medium,
                    modifier = Modifier
                        .padding(top = 10.dp)
                        .background(c.greySoft, RoundedCornerShape(8.dp))
                        .clickable {
                            val r = store.activate(input)
                            message = when (r) {
                                is LicenseResult.Ok -> "激活成功"
                                LicenseResult.BadFormat -> "激活码格式不对"
                                LicenseResult.BadSignature -> "激活码无效"
                                LicenseResult.WrongDevice -> "这枚码属于另一台设备"
                                LicenseResult.Expired -> "这枚码已过期"
                            }
                            if (r is LicenseResult.Ok) license = r.license
                        }
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                )
                message?.let {
                    Text(it, fontSize = 11.sp, color = c.ink2, modifier = Modifier.padding(top = 8.dp))
                }

                // 价目
                Text(
                    "15 天免费试用 · 10 元/月（仅 AGNES）· 30 元/月订阅（可自选模型）",
                    fontSize = 10.sp, color = c.ink3, modifier = Modifier.padding(top = 14.dp),
                )

                Text(
                    "关闭",
                    fontSize = 13.sp, color = c.accent,
                    modifier = Modifier
                        .align(Alignment.End)
                        .padding(top = 12.dp)
                        .clickable { onDismiss() }
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                )
            }
        }
    }
}