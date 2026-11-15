package com.wangzan101.mika.core.cap.phone

/**
 * 手机工具的调试探针开关。
 *
 * 只在调试包里由 App 打开（`BuildConfig.DEBUG`）。打开后有两种方式触发等待循环的探针：
 *
 * 1. 调用参数 `_forceWaitMs`（模型一般不会主动带，够用但不稳）；
 * 2. App 私有目录里存在 `debug-force-wait` 文件（`adb shell run-as ... touch` 即可），
 *    此时**每一次** `phone_tap_ocr` 都会先故意忽略第一次读到的结果，模拟"首帧还没渲染"。
 *
 * 探针只影响"是否跳过第一次读"，把 `waitedMs` 逼出来用于验证等待循环本身。
 * 正式包里 [allowForceWait] 恒为 false，上面两条都不生效。
 */
object PhoneDebug {
    @Volatile
    var allowForceWait: Boolean = false

    /** 由 App 注入：调试标记文件是否存在。null 表示不支持文件开关。 */
    @Volatile
    var forceSkipProbe: (() -> Boolean)? = null
}
