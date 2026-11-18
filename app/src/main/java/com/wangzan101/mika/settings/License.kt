package com.wangzan101.mika.settings

import android.content.Context
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** 会员档位。付费档位决定「能不能自己选模型」。 */
enum class LicensePlan(val code: String) {
    Trial("T"),
    Monthly("M"),
    Pro("P"),
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
    /** 这枚码是发给另一台设备的。 */
    data object WrongDevice : LicenseResult
}

/**
 * 本地授权:激活码方案,不需要服务器。
 *
 * 码格式:`{档位}{yyyyMMdd}{随机4位}{设备指纹6位}-{签名前8位}`
 * 例:`P20261218ZS917A3F21-9F3C7D21`
 * 设备指纹 = SHA-256(ANDROID_ID + 密钥) 的前 6 位,做到一码一设备。
 * 签名 = HMAC-SHA256(密钥, 前半段) 的前 8 位。
 */
object LicenseCode {
    /**
     * 和 tools/make-license.ps1 里保持一致。
     * 保存形式是 XOR 混淆过的字节,避免 `strings` 直接搜到明文;
     * 这只提高门槛,不是真正的防护(见 MOD-NOTES 里的安全边界)。
     */
    private val SECRET_MASK = intArrayOf(
        59, 57, 41, 119, 54, 51, 57, 63, 52, 41, 63, 119, 44, 107, 119,
        111, 60, 106, 57, 99, 63, 104, 59, 109, 107, 56, 98, 110, 62, 105, 57,
    )

    /** 运行时拼回密钥,用一次就丢,不常驻字符串常量池。 */
    private fun secret(): String {
        val chars = CharArray(SECRET_MASK.size)
        for (i in SECRET_MASK.indices) chars[i] = (SECRET_MASK[i] xor 0x5A).toChar()
        return String(chars)
    }

    private val PATTERN = Regex("^([TMP])(\\d{8})([A-Z0-9]{4})([0-9A-F]{6})-([0-9A-F]{8})$")

    /** 本机指纹:6 位十六进制,激活码里带着它。 */
    fun deviceFingerprint(context: Context): String {
        val id = android.provider.Settings.Secure.getString(
            context.contentResolver,
            android.provider.Settings.Secure.ANDROID_ID,
        ) ?: ""
        val digest = MessageDigest.getInstance("SHA-256").digest((id + secret()).toByteArray())
        return digest.joinToString("") { "%02x".format(it) }.uppercase().take(6)
    }

    fun sign(payload: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(secret().toByteArray(), "HmacSHA256"))
        val out = mac.doFinal(payload.toByteArray())
        return out.joinToString("") { "%02x".format(it) }.uppercase().take(8)
    }

    /**
     * 管理员在本机生成激活码(和 tools/make-license.ps1 用同一套算法)。
     * [device] 是目标设备的 6 位指纹。
     */
    fun generate(device: String, plan: LicensePlan, days: Int, now: Long = System.currentTimeMillis()): String {
        val dev = device.trim().uppercase()
        val expiry = java.text.SimpleDateFormat("yyyyMMdd", java.util.Locale.US)
            .format(java.util.Date(now + days * 86_400_000L))
        val alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        val rand = (1..4).map { alphabet.random() }.joinToString("")
        val payload = "${plan.code}$expiry$rand$dev"
        return "$payload-${sign(payload)}"
    }

    fun verify(raw: String, context: Context, now: Long = System.currentTimeMillis()): LicenseResult {
        val code = raw.trim().uppercase().replace(" ", "")
        val m = PATTERN.matchEntire(code) ?: return LicenseResult.BadFormat
        val planChar = m.groupValues[1]
        val date = m.groupValues[2]
        val rand = m.groupValues[3]
        val dev = m.groupValues[4]
        val sig = m.groupValues[5]
        val payload = "$planChar$date$rand$dev"
        if (sign(payload) != sig) return LicenseResult.BadSignature
        if (deviceFingerprint(context) != dev) return LicenseResult.WrongDevice
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
        return when (val r = LicenseCode.verify(code, context)) {
            is LicenseResult.Ok -> r.license
            else -> null
        }
    }

    /** 激活:验签 + 验设备通过才写入。 */
    fun activate(raw: String): LicenseResult {
        val r = LicenseCode.verify(raw, context)
        if (r is LicenseResult.Ok) prefs.edit().putString("code", r.license.code).apply()
        return r
    }

    fun clear() = prefs.edit().remove("code").apply()
}

/**
 * 防逆向与防重打包的最基础一层:记录首次安装时签名证书的 SHA-256,之后每次比对。
 * 别人改包重签后签名变了,这里就会判为「被改动过」,管理员入口直接消失。
 * 局限:清数据可重置,查不到更早的证书。
 */
object Integrity {
    private const val PREFS = "acs-integrity"
    private const val KEY = "cert"

    /** 当前签名的 SHA-256;取不到就返回空串。 */
    fun certSha256(context: android.content.Context): String {
        return try {
            val info = context.packageManager.getPackageInfo(
                context.packageName,
                android.content.pm.PackageManager.GET_SIGNING_CERTIFICATES,
            )
            val signers = info.signingInfo?.apkContentsSigners ?: return ""
            if (signers.isEmpty()) return ""
            val digest = MessageDigest.getInstance("SHA-256").digest(signers[0].toByteArray())
            digest.joinToString("") { "%02x".format(it) }
        } catch (e: Exception) {
            ""
        }
    }

    /** 首次运行记下证书指纹;之后不一致就说明包被改过。 */
    fun trusted(context: android.content.Context): Boolean {
        val now = certSha256(context)
        if (now.isEmpty()) return false
        val prefs = context.getSharedPreferences(PREFS, android.content.Context.MODE_PRIVATE)
        val known = prefs.getString(KEY, null)
        if (known == null) {
            prefs.edit().putString(KEY, now).apply()
            return true
        }
        return known == now
    }
}