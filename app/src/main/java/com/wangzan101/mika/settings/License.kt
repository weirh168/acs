package com.wangzan101.mika.settings

import android.content.Context
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** 会员档位。付费档位决定「能不能自己选模型」。 */
enum class LicensePlan(val code: String) {
    Trial("T"),      // 15 天免费
    Monthly("M"),    // 10 元/月,只能用 AGNES
    Pro("P"),        // 30 元/月,可自选模型
}

/** 一个已激活的授权。 */
data class License(
    val plan: LicensePlan,
    val expiresAtMs: Long,
    val code: String,
) {
    fun active(now: Long = System.currentTimeMillis()) = now < expiresAtMs
    fun daysLeft(now: Long = System.currentTimeMillis()): Int {
        val ms = expiresAtMs - now
        return if (ms <= 0) 0 else (ms / 86_400_000L).toInt() + 1
    }
    /** 能不能自己挑模型:只有 Pro 可以。 */
    fun canPickModel() = plan == LicensePlan.Pro
}

/** 校验结果。 */
sealed interface LicenseResult {
    data class Ok(val license: License) : LicenseResult
    data object BadFormat : LicenseResult
    data object BadSignature : LicenseResult
    data object Expired : LicenseResult
}

/**
 * 本地授权:**激活码**方案,不需要服务器。
 *
 * 码的格式:`{plan}{yyyyMMdd}{随机4位}-{签名前8位}`,例如 `P20261231A1B2-9F3C7D21`。
 * 签名 = HMAC-SHA256(secret, 前半段) 的前 8 个十六进制字符。
 * 说明:密钥编译进 APK,能挡住随手编造,但挡不住逆向。要真正防破解必须上服务端。
 */
object LicenseCode {
    /** 和 tools/make-license.ps1 里保持一致。改这里要同步改脚本。 */
    private const val SECRET = "acs-license-v1-5f0c9e2a71b84d3c"

    private val PATTERN = Regex("^([TMP])(\\d{8})([A-Z0-9]{4})-([0-9A-F]{8})$")

    fun sign(payload: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(SECRET.toByteArray(), "HmacSHA256"))
        val out = mac.doFinal(payload.toByteArray())
        return out.joinToString("") { "%02x".format(it) }.uppercase().take(8)
    }

    fun verify(raw: String, now: Long = System.currentTimeMillis()): LicenseResult {
        val code = raw.trim().uppercase().replace(" ", "")
        val m = PATTERN.matchEntire(code) ?: return LicenseResult.BadFormat
        val planChar = m.groupValues[1]
        val date = m.groupValues[2]
        val rand = m.groupValues[3]
        val sig = m.groupValues[4]
        val payload = "$planChar$date$rand"
        if (sign(payload) != sig) return LicenseResult.BadSignature
        val plan = when (planChar) {
            "T" -> LicensePlan.Trial
            "M" -> LicensePlan.Monthly
            else -> LicensePlan.Pro
        }
        val calendar = java.util.Calendar.getInstance().apply {
            set(date.substring(0, 4).toInt(), date.substring(4, 6).toInt() - 1, date.substring(6, 8).toInt(), 23, 59, 59)
            set(java.util.Calendar.MILLISECOND, 999)
        }
        val expires = calendar.timeInMillis
        if (now >= expires) return LicenseResult.Expired
        return LicenseResult.Ok(License(plan, expires, code))
    }
}

/** 授权状态的本地存储:一台设备只记一份,换码即覆盖。 */
class LicenseStore(private val context: Context) {
    private val prefs = context.getSharedPreferences("acs-license", Context.MODE_PRIVATE)

    fun load(): License? {
        val code = prefs.getString("code", null) ?: return null
        return when (val r = LicenseCode.verify(code)) {
            is LicenseResult.Ok -> r.license
            LicenseResult.Expired -> LicenseCode.verify(code, 0L).let { old ->
                if (old is LicenseResult.Ok) old.license else null
            }
            else -> null
        }
    }

    /** 激活:验签通过才写入。返回结果给界面显示原因。 */
    fun activate(raw: String): LicenseResult {
        val r = LicenseCode.verify(raw)
        if (r is LicenseResult.Ok) prefs.edit().putString("code", r.license.code).apply()
        return r
    }

    fun clear() = prefs.edit().remove("code").apply()
}
