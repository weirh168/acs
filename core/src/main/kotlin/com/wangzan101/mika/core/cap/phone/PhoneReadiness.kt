package com.wangzan101.mika.core.cap.phone

/**
 * "手机操作这会儿为什么用不了"的判断，独立出来好测。
 *
 * 三种情况要给出不同的话：
 * - 助手连上了：没问题，用不上这个；
 * - 助手没连上，但无障碍在、用户还没同意读主屏：**告诉他打开哪个开关就能继续**，比"去设置一次"更有用；
 * - 其余：就是没准备好，让用户去走一遍设置。
 */
object PhoneReadiness {

    enum class Unavailable {
        /** 助手没连上，这时什么也做不了，让用户去设置。 */
        HelperMissing,

        /** 助手没连上，但只差用户点开「没有内置助手时读我的主屏」——直接把开关指出来。 */
        HelperMissingCanDegrade,
    }

    fun unavailable(helperConnected: Boolean, degradedApproved: Boolean, accessibilityOn: Boolean): Unavailable? =
        when {
            helperConnected -> null
            accessibilityOn && !degradedApproved -> Unavailable.HelperMissingCanDegrade
            else -> Unavailable.HelperMissing
        }
}
