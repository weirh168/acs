package com.wangzan101.mika.cap.phone.setup

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.wangzan101.mika.cap.phone.PhoneServices
import com.wangzan101.mika.core.shell.BuiltinShellStatus
import com.wangzan101.mika.core.shell.RestoreOutcome
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * 开机广播。只有用户打开了「重启后自动恢复」、并且 Mika 还拿着修改系统设置的授权时才动手,
 * 其余情况什么都不做(判断在 [BuiltinShellRecovery.restoreAfterBoot])。
 */
open class BootRestoreHandler : BroadcastReceiver() {

    /** 开机恢复没成功时的补追:每轮先看重试有没有用,连上或用户关掉就退出。 */
    private suspend fun followUp(phone: PhoneServices) {
        val control = phone.shellControl
        for (waitMs in FOLLOW_UP_MS) {
            delay(waitMs)
            if (control.status.value == BuiltinShellStatus.Running) return
            if (!control.paired) return
            runCatching { control.retry() }
        }
    }

    private companion object {
        /** 逐渐拉长:开机后 20 秒、1 分、3 分、8 分各追一次。 */
        val FOLLOW_UP_MS = longArrayOf(20_000, 40_000, 120_000, 300_000)
    }
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val pending = goAsync()
        val phone = PhoneServices.of(context)
        phone.pairing.scope.launch {
            try {
                val outcome = runCatching { phone.recovery.restoreAfterBoot() }.getOrNull()
                // 开机那一下常常来不及:Wi-Fi 还没连上、系统还没把开关拨回来。
                // 恢复没成功就自己再追几次,连上就停,省得用户开机后还要手动点「重试」。
                if (outcome == RestoreOutcome.NotRecovered) followUp(phone)
            } finally {
                pending.finish()
            }
        }
    }
}
