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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.wangzan101.mika.ui.theme.MikaTheme
import com.wangzan101.mika.settings.LicenseCode
import com.wangzan101.mika.settings.LicensePlan
import com.wangzan101.mika.settings.LicenseResult
import com.wangzan101.mika.settings.LicenseStore

/** 会员弹窗:当前授权、本机设备码、激活码输入。 */
@Composable
fun MembershipDialog(forced: Boolean = false, onDismiss: () -> Unit) {
    val c = MikaTheme.colors
    val context = LocalContext.current
    val store = remember(context) { LicenseStore(context) }
    var license by remember { mutableStateOf(store.load()) }
    var input by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    val device = remember(context) { LicenseCode.deviceFingerprint(context) }

    androidx.compose.ui.window.Dialog(onDismissRequest = { if (!forced) onDismiss() }) {
        androidx.compose.material3.Surface(shape = RoundedCornerShape(18.dp), color = c.surface) {
            Column(Modifier.padding(18.dp)) {
                Text(if (forced) "需要激活才能使用" else "会员", fontSize = 16.sp, color = c.ink, fontWeight = FontWeight.Medium)
                if (forced) {
                    Text(
                        "试用已结束或还没有激活。把下面的设备码发给作者，拿到激活码后填入即可继续使用。",
                        fontSize = 12.sp, color = c.ink2, modifier = Modifier.padding(top = 6.dp),
                    )
                }

                val lic = license
                val statusText = when {
                    lic == null -> "未激活"
                    !lic.active() -> "已过期"
                    lic.plan == LicensePlan.Trial -> "试用中"
                    lic.plan == LicensePlan.Monthly -> "已开通 10 元版"
                    else -> "已开通 30 元订阅"
                }
                Text(
                    statusText,
                    fontSize = 13.sp,
                    color = if (lic?.active() == true) c.ok else c.ink2,
                    modifier = Modifier.padding(top = 8.dp).testTag("license-status"),
                )
                if (lic?.active() == true) {
                    Text(
                        "剩余 " + lic.daysLeft() + " 天 · " + if (lic.canPickModel()) "可自选模型" else "仅 AGNES 模型",
                        fontSize = 11.sp, color = c.ink3, modifier = Modifier.padding(top = 2.dp),
                    )
                }

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
                        modifier = Modifier.padding(start = 10.dp).testTag("device-code"),
                    )
                    Text(
                        "（发给作者换激活码）",
                        fontSize = 10.sp, color = c.ink3, modifier = Modifier.padding(start = 6.dp),
                    )
                }

                Text("激活码", fontSize = 12.sp, color = c.ink2, modifier = Modifier.padding(top = 14.dp))
                androidx.compose.material3.OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    singleLine = true,
                    placeholder = { Text("例如 P20261218VWZ47A3F21-BB326843", fontSize = 11.sp) },
                    modifier = Modifier.fillMaxWidth().padding(top = 6.dp).testTag("license-input"),
                )
                androidx.compose.material3.Button(
                    onClick = {
                        val r = store.activate(input)
                        message = when (r) {
                            is LicenseResult.Ok -> "激活成功"
                            LicenseResult.BadFormat -> "激活码格式不对"
                            LicenseResult.BadSignature -> "激活码无效"
                            LicenseResult.WrongDevice -> "这枚码属于另一台设备"
                            LicenseResult.Expired -> "这枚码已过期"
                        }
                        if (r is LicenseResult.Ok) license = r.license
                    },
                    modifier = Modifier.padding(top = 10.dp).testTag("activate-button"),
                ) { Text("激活", fontSize = 13.sp) }
                message?.let {
                    Text(it, fontSize = 11.sp, color = c.ink2, modifier = Modifier.padding(top = 8.dp).testTag("license-message"))
                }

                Text(
                    "15 天免费试用 · 10 元/月（仅 AGNES）· 30 元/月订阅（可自选模型）",
                    fontSize = 10.sp, color = c.ink3, modifier = Modifier.padding(top = 14.dp),
                )

                if (!forced) {
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
}

/** 当前能不能自己选模型:没授权或试用/10 元档都只能留在 AGNES。 */
fun canPickModelNow(context: android.content.Context): Boolean {
    val lic = LicenseStore(context).load() ?: return false
    return lic.active() && lic.canPickModel()
}

/** 是不是 AGNES 系的模型(低档位唯一可用)。 */
fun isAgnesModel(providerId: String, model: String): Boolean {
    val t = (providerId + " " + model).lowercase()
    return t.contains("agnes")
}

/** 只有这台手机(管理员机)显示「管理员 · 生成激活码」。换机时改这里。 */
const val ADMIN_DEVICE = "BE1CF3"

/** 当前设备是不是管理员机。 */
fun isAdminDevice(context: android.content.Context): Boolean =
    LicenseCode.deviceFingerprint(context) == ADMIN_DEVICE

/** 管理员口令。改这里即可换口令(明文写在 APK 内,只能挡住普通用户)。 */
private const val ADMIN_PASSWORD = "acs-admin-2026"

/** 管理员:在本机按目标设备码生成激活码。 */
@Composable
fun AdminCodeDialog(isAdmin: Boolean, onDismiss: () -> Unit) {
    val c = MikaTheme.colors
    val context = LocalContext.current
    var pwd by remember { mutableStateOf("") }
    var unlocked by remember { mutableStateOf(isAdmin) }
    var device by remember { mutableStateOf("") }
    var plan by remember { mutableStateOf(LicensePlan.Monthly) }
    var days by remember { mutableStateOf("30") }
    var result by remember { mutableStateOf<String?>(null) }

    androidx.compose.ui.window.Dialog(onDismissRequest = onDismiss) {
        androidx.compose.material3.Surface(shape = RoundedCornerShape(18.dp), color = c.surface) {
            Column(Modifier.padding(18.dp)) {
                Text("管理员 · 生成激活码", fontSize = 16.sp, color = c.ink, fontWeight = FontWeight.Medium)

                if (!unlocked) {
                    Text("输入管理员口令", fontSize = 12.sp, color = c.ink2, modifier = Modifier.padding(top = 10.dp))
                    androidx.compose.material3.OutlinedTextField(
                        value = pwd, onValueChange = { pwd = it }, singleLine = true,
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp).testTag("admin-pwd"),
                    )
                    androidx.compose.material3.Button(
                        onClick = { if (pwd == ADMIN_PASSWORD) unlocked = true else result = "口令不对" },
                        modifier = Modifier.padding(top = 8.dp).testTag("admin-unlock"),
                    ) { Text("进入", fontSize = 13.sp) }
                } else {
                    Text("会员发来的设备码（他会员页里的 6 位）", fontSize = 12.sp, color = c.ink2, modifier = Modifier.padding(top = 10.dp))
                    androidx.compose.material3.OutlinedTextField(
                        value = device, onValueChange = { device = it.uppercase() }, singleLine = true,
                        placeholder = { Text("例如 BE1CF3", fontSize = 11.sp) },
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp).testTag("admin-device"),
                    )
                    Row(Modifier.padding(top = 12.dp)) {
                        listOf(LicensePlan.Monthly, LicensePlan.Pro).forEach { p ->
                            val label = when (p) {
                                LicensePlan.Trial -> "试用"
                                LicensePlan.Monthly -> "10元/月"
                                LicensePlan.Pro -> "30元/月"
                            }
                            Text(
                                label,
                                fontSize = 12.sp,
                                color = if (plan == p) c.surface else c.ink2,
                                modifier = Modifier
                                    .padding(end = 8.dp)
                                    .background(if (plan == p) c.accent else c.greySoft, RoundedCornerShape(8.dp))
                                    .clickable { plan = p; days = if (p == LicensePlan.Trial) "15" else "30" }
                                    .padding(horizontal = 10.dp, vertical = 6.dp),
                            )
                        }
                    }
                    Text("天数", fontSize = 12.sp, color = c.ink2, modifier = Modifier.padding(top = 10.dp))
                    androidx.compose.material3.OutlinedTextField(
                        value = days, onValueChange = { days = it.filter { ch -> ch.isDigit() } }, singleLine = true,
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp).testTag("admin-days"),
                    )
                    androidx.compose.material3.Button(
                        onClick = {
                            val d = days.toIntOrNull() ?: 0
                            result = if (device.length != 6 || d <= 0) {
                                "设备码要 6 位，天数要大于 0"
                            } else {
                                LicenseCode.generate(device, plan, d)
                            }
                        },
                        modifier = Modifier.padding(top = 10.dp).testTag("admin-generate"),
                    ) { Text("生成", fontSize = 13.sp) }
                }

                result?.let {
                    Text(it, fontSize = 12.sp, color = c.ink, modifier = Modifier.padding(top = 10.dp).testTag("admin-result"))
                    if (it.length > 20) {
                        Text(
                            "复制", fontSize = 12.sp, color = c.accent,
                            modifier = Modifier.padding(top = 4.dp).clickable {
                                val cm = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                                cm.setPrimaryClip(android.content.ClipData.newPlainText("code", it))
                                android.widget.Toast.makeText(context, "已复制", android.widget.Toast.LENGTH_SHORT).show()
                            }.padding(vertical = 4.dp),
                        )
                    }
                }

                Text(
                    "关闭", fontSize = 13.sp, color = c.accent,
                    modifier = Modifier.align(Alignment.End).padding(top = 12.dp)
                        .clickable { onDismiss() }.padding(horizontal = 10.dp, vertical = 6.dp),
                )
            }
        }
    }
}