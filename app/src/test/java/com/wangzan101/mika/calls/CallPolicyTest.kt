package com.wangzan101.mika.calls

import org.junit.Assert.*
import org.junit.Test

class CallPolicyTest {
    @Test fun blocksControlCodesAndNeverStripsDialingSyntax() {
        listOf("112", "911", "*#06#", "**21*123456789#", "123456789,22", "123456789;22", "tel:123456789",
            "123456789p1", "%2a123456789", "+1+5551234567").forEach {
            assertNull(it, CallPolicy.outgoingNumber(it))
        }
        assertEquals("+15551234567", CallPolicy.outgoingNumber(" +1 (555) 123-4567 "))
    }

    @Test fun listOnlyFailsClosedAndAllModeAnswersHiddenCallers() {
        val listOnly = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.LIST)
        // 只接名单:名单外一律不接,隐藏号码也没有号码可比,不接
        assertFalse(CallPolicy.callerAllowed(listOnly, "15551234567"))
        assertFalse(CallPolicy.callerAllowed(listOnly, null))
        val listed = listOnly.copy(allowedIncomingNumbers = setOf("+15551234567"))
        assertTrue(CallPolicy.callerAllowed(listed, "+1 (555) 123-4567"))
        assertFalse(CallPolicy.callerAllowed(listed, "5551234567"))
        // 全部交给 AI:连隐藏号码也接
        val all = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.ALL)
        assertTrue(CallPolicy.callerAllowed(all, null))
        // 四道门缺一不可
        assertFalse(CallPolicy.callerAllowed(all.copy(autoAnswer = false), null))
        assertFalse(CallPolicy.callerAllowed(all.copy(credentialsConfigured = false), null))
        assertFalse(CallPolicy.callerAllowed(all.copy(audioVerified = false), null))
        assertFalse(CallPolicy.callerAllowed(all.copy(enabled = false), null))
        // 认不出来的串不接
        assertFalse(CallPolicy.callerAllowed(all, "*#06#"))
    }

    @Test fun smartPresetFollowsTheSourceSwitches() {
        val smart = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.SMART)
        // 默认:通讯录不接、陌生号码接、隐藏/国际不接、重复来电接
        assertFalse(CallPolicy.callerAllowed(smart, "15551234567", inContacts = true))
        assertTrue(CallPolicy.callerAllowed(smart, "15551234567", inContacts = false))
        assertFalse(CallPolicy.callerAllowed(smart, null))
        assertFalse(CallPolicy.callerAllowed(smart, "+15551234567", facts = CallerFacts(international = true)))
        assertTrue(CallPolicy.callerAllowed(smart, "15551234567", facts = CallerFacts(repeated = true)))
        // 把通讯录开关打开后,通讯录里的人改由 AI 接
        assertTrue(CallPolicy.callerAllowed(smart.copy(answerContacts = true), "15551234567", inContacts = true))
        // 隐藏 / 国际 各自的开关独立生效
        assertTrue(CallPolicy.callerAllowed(smart.copy(answerHidden = true), null))
        assertTrue(CallPolicy.callerAllowed(smart.copy(answerInternational = true), "+15551234567",
            facts = CallerFacts(international = true)))
        // 白名单优先:名单里说必须 AI 接,通讯录开关关着也接
        val listed = smart.copy(allowedIncomingNumbers = setOf("15551234567"))
        assertTrue(CallPolicy.callerAllowed(listed, "15551234567", inContacts = true))
        // 黑名单最优先:说不接就不接,哪怕在来源开关里是接的
        val blocked = smart.copy(blockedIncomingNumbers = setOf("15551234567"))
        assertFalse(CallPolicy.callerAllowed(blocked, "15551234567", inContacts = false))
        // 自动开始的判断同样尊重这整套
        assertFalse(CallPolicy.canStartAutoAnswer(smart, smart, "15551234567", 1_000, inContacts = true))
        assertTrue(CallPolicy.canStartAutoAnswer(smart, smart, "15551234567", 1_000, inContacts = false))
    }

    @Test fun prefixesAndActiveWindowNarrowTheDecision() {
        val all = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.ALL)
        // 号段:不接的号段优先,命中的一概不接
        assertFalse(CallPolicy.callerAllowed(all.copy(blockedPrefixes = setOf("400")), "4008001234"))
        assertTrue(CallPolicy.callerAllowed(all.copy(blockedPrefixes = setOf("400")), "13800138000"))
        // 必须接的号段:连「只接名单」模式也接
        val listOnly = all.copy(preset = CallPreset.LIST, allowedPrefixes = setOf("0571"))
        assertTrue(CallPolicy.callerAllowed(listOnly, "057188886666"))
        assertFalse(CallPolicy.callerAllowed(listOnly, "13800138000"))
        // 号段写法宽松:带 * 号、带横线都能归一
        assertEquals("400", CallPolicy.normalisePrefix("400*"))
        assertEquals("0571", CallPolicy.normalisePrefix(" 0571-"))
        assertNull(CallPolicy.normalisePrefix("1"))
        // 生效时段:窗口外不接,窗口内接;跨零点也对
        val noon = java.util.Calendar.getInstance().apply {
            set(java.util.Calendar.HOUR_OF_DAY, 12); set(java.util.Calendar.MINUTE, 0); set(java.util.Calendar.SECOND, 0)
        }.timeInMillis
        val night = noon + 12 * 60 * 60 * 1000L
        val dayWindow = all.copy(activeStartMinute = 9 * 60, activeEndMinute = 18 * 60)
        assertTrue(CallPolicy.callerAllowed(dayWindow, "13800138000", noon))
        assertFalse(CallPolicy.callerAllowed(dayWindow, "13800138000", night))
        val acrossMidnight = all.copy(activeStartMinute = 22 * 60, activeEndMinute = 8 * 60)
        assertTrue(CallPolicy.callerAllowed(acrossMidnight, "13800138000", night))
        assertFalse(CallPolicy.callerAllowed(acrossMidnight, "13800138000", noon))
        // 没设时段就是全天
        assertTrue(CallPolicy.inActiveWindow(all, noon))
    }
    @Test fun obviouslyIncompleteNumbersAreRejected() {
        // 兜底:名单里半截号码不许进来;完整号码不受影响
        assertTrue(CallPolicy.isIncompleteNumber("+86181"))
        assertTrue(CallPolicy.isIncompleteNumber("1234"))
        assertTrue(CallPolicy.isIncompleteNumber("+86 181"))
        assertFalse(CallPolicy.isIncompleteNumber("13800138000"))
        assertFalse(CallPolicy.isIncompleteNumber("+8613800138000"))
        assertFalse(CallPolicy.isIncompleteNumber("057188886666"))
    }
    @Test fun institutionNumbersGoToTheOwnerByDefault() {
        val all = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.ALL)
        // 400/955xx/100xx 这类机构号:默认不交给 AI
        for (number in listOf("4008001234", "95588", "10086", "12345", "+864008001234")) {
            assertTrue(CallPolicy.isInstitutionNumber(number))
            assertFalse(CallPolicy.callerAllowed(all, number))
        }
        // 普通手机号不受影响
        assertFalse(CallPolicy.isInstitutionNumber("13800138000"))
        assertTrue(CallPolicy.callerAllowed(all, "13800138000"))
        // 关掉这个策略后,机构号也交给 AI
        assertTrue(CallPolicy.callerAllowed(all.copy(institutionTransfer = false), "4008001234"))
        // 白名单显式要求 AI 接的,优先于机构号策略
        val listed = all.copy(allowedIncomingNumbers = setOf("4008001234"))
        assertTrue(CallPolicy.callerAllowed(listed, "4008001234"))
    }
    @Test fun quickFixTurnsOnTheMatchingSource() {
        val base = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.SMART, answerContacts = false, answerStrangers = false)
        // 陌生号码:只打开陌生号码来源
        val stranger = CallPolicy.quickFixAnswerCategory(base, "15551234567", inContacts = false)
        assertTrue(stranger.answerStrangers)
        assertFalse(stranger.answerContacts)
        // 通讯录里的人:打开通讯录来源
        val contact = CallPolicy.quickFixAnswerCategory(base, "15551234567", inContacts = true)
        assertTrue(contact.answerContacts)
        assertFalse(contact.answerStrangers)
        // 国际号码:+ 开头走国际开关
        assertTrue(CallPolicy.quickFixAnswerCategory(base, "+15551234567", inContacts = false).answerInternational)
        // 隐藏号码:走隐藏开关
        assertTrue(CallPolicy.quickFixAnswerCategory(base, null, inContacts = false).answerHidden)
        // 只接名单模式:顺手切回智能接听,否则开关不生效
        assertEquals(CallPreset.SMART,
            CallPolicy.quickFixAnswerCategory(base.copy(preset = CallPreset.LIST), "15551234567", false).preset)
        // 机构号:顺手关掉「机构号转本人」,否则打开了也接不起来
        assertFalse(CallPolicy.quickFixAnswerCategory(base, "4008001234", false).institutionTransfer)
    }
    @Test fun selectedSimsLimitAutoAnswer() {
        val all = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.ALL)
        // 没选 SIM:所有卡都接
        assertTrue(CallPolicy.callerAllowed(all, "13800138000", simKey = "sim-1"))
        // 只选了 sim-2:sim-1 上的来电不接,sim-2 照常
        val only2 = all.copy(autoAnswerSimIds = setOf("sim-2"))
        assertFalse(CallPolicy.callerAllowed(only2, "13800138000", simKey = "sim-1"))
        assertTrue(CallPolicy.callerAllowed(only2, "13800138000", simKey = "sim-2"))
        // 不知道走哪张卡时不拦(不能因为查不到就误杀)
        assertTrue(CallPolicy.callerAllowed(only2, "13800138000", simKey = null))
    }
    @Test fun requiresExplicitSelectionOnMultiSimDevices() {
        val sim1 = CallSim("1", "SIM 1", true)
        val sim2 = CallSim("2", "SIM 2", false)
        assertEquals(sim1, CallPolicy.chooseSim(listOf(sim1), null))
        assertNull(CallPolicy.chooseSim(listOf(sim1, sim2), null))
        assertEquals(sim1, CallPolicy.chooseSim(listOf(sim1, sim2), "default"))
        assertEquals(sim2, CallPolicy.chooseSim(listOf(sim1, sim2), "2"))
        assertNull(CallPolicy.chooseSim(listOf(sim1.copy(isDefault = false), sim2), "default"))
        assertNull(CallPolicy.chooseSim(listOf(sim1), "missing"))
    }

    @Test fun mainlandMobileAllowlistAcceptsOnlyCompleteEquivalentNumbers() {
        val local = "13800138000"
        val enabled = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true, audioVerified = true)
        for (allowed in listOf(local, "+8613800138000", "008613800138000")) {
            val config = enabled.copy(preset = CallPreset.LIST, allowedIncomingNumbers = setOf(allowed))
            assertTrue(CallPolicy.callerAllowed(config, local))
            assertTrue(CallPolicy.callerAllowed(config, "+86 138 0013 8000"))
            assertTrue(CallPolicy.callerAllowed(config, "0086-138-0013-8000"))
            assertFalse(CallPolicy.callerAllowed(config, "800138000"))
            assertFalse(CallPolicy.callerAllowed(config, "8613800138000"))
            assertFalse(CallPolicy.callerAllowed(config, "+113800138000"))
            assertFalse(CallPolicy.callerAllowed(config, "13800138001"))
        }
        val all = enabled.copy(preset = CallPreset.ALL)
        assertFalse(CallPolicy.callerAllowed(all, "*#06#"))
        assertFalse(CallPolicy.callerAllowed(all, "13800138000;22"))
    }

    @Test fun delayedStartupCannotAuthorizeAnExistingCallOrBroadenItsPolicy() {
        val number = "13800138000"
        val ready = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true,
            audioVerified = true, preset = CallPreset.LIST, allowedIncomingNumbers = setOf("+8613800138000"))
        assertTrue(CallPolicy.canStartAutoAnswer(ready, ready, number, CallPolicy.AUTO_START_WINDOW_MS))
        assertFalse(CallPolicy.canStartAutoAnswer(ready, ready, number, CallPolicy.AUTO_START_WINDOW_MS + 1))
        assertFalse(CallPolicy.canStartAutoAnswer(ready.copy(autoAnswer = false), ready, number, 100L))
        assertFalse(CallPolicy.canStartAutoAnswer(ready.copy(allowedIncomingNumbers = emptySet()), ready, number, 100L))
        assertFalse(CallPolicy.canStartAutoAnswer(ready, ready.copy(allowedIncomingNumbers = emptySet()), number, 100L))
        assertFalse(CallPolicy.canStartAutoAnswer(ready, ready.copy(audioMode = CallAudioMode.REDIRECT), number, 100L))
    }

    @Test fun bypassWinsOverBothAllowAllAndExplicitAllowlist() {
        val ready = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true, audioVerified = true,
            allowedIncomingNumbers = setOf("13800138000", "028-8123-4567"),
            bypassIncomingNumbers = setOf("+86 138 0013 8000", "0086 28 8123 4567"))
        for (allowAll in listOf(false, true)) {
            val config = ready.copy(allowAllIncoming = allowAll)
            for (number in listOf("13800138000", "008613800138000", "+8613800138000", "02881234567", "+862881234567")) {
                assertTrue(CallPolicy.isBypassed(config, number))
                assertFalse(CallPolicy.callerAllowed(config, number))
            }
        }
        for (number in listOf(null, "800138000", "81234567", "+113800138000", "13800138001")) {
            assertFalse(CallPolicy.isBypassed(ready, number))
        }
        assertTrue(CallPolicy.callerAllowed(ready.copy(preset = CallPreset.ALL), "13800138001"))
    }

    @Test fun pauseExpiresForNewCallsWithoutAnsweringCallsThatArrivedDuringIt() {
        val deadline = 100_000L
        val paused = CallConfig(enabled = true, autoAnswer = true, credentialsConfigured = true, audioVerified = true,
            preset = CallPreset.ALL, autoAnswerPausedUntilMs = deadline)
        val resumed = paused.copy(autoAnswerPausedUntilMs = null)
        assertEquals(1L, CallPolicy.autoAnswerPauseRemainingMs(paused, deadline - 1L))
        assertEquals(0L, CallPolicy.autoAnswerPauseRemainingMs(paused, deadline))
        assertFalse(CallPolicy.callerAllowed(paused, null, deadline - 1L))
        assertTrue(CallPolicy.callerAllowed(paused, null, deadline))
        assertFalse(CallPolicy.canStartAutoAnswer(paused, resumed, null, 1L, nowMs = deadline))
        assertFalse(CallPolicy.canStartAutoAnswer(resumed, paused, null, 1L, nowMs = deadline - 1L))
        assertTrue(CallPolicy.canStartAutoAnswer(paused, paused, null, 1L, nowMs = deadline + 1L))
    }

    @Test fun ownerRulesArePassedAsAnExplicitSectionOfTheBoundedCallPrompt() {
        val ownerRules = "仅在来电者说包裹到了时，请对方留下取件地点。"
        val prompt = CallPolicy.prompt("确认对方称呼。", CallDirection.INCOMING, ownerRules)
        assertTrue(prompt.indexOf("不得索取或透露密码") in 0 until prompt.indexOf(ownerRules))
        assertTrue(prompt.contains("机主明确保存的通话规则"))
        assertTrue(prompt.contains("确认对方称呼。"))
        assertFalse(CallPolicy.prompt("", CallDirection.INCOMING).contains("机主明确保存的通话规则"))
    }

    @Test fun legacyGreetingMigratesOnlyTheExactOldDefault() {
        val legacyDefault = "您好，我是 ACS 的 AI 电话助手。请问有什么需要我转告？"
        val customWithOldName = "您好，我是 ACS 的 AI 电话助手。请留下可回拨的时间。"
        val currentDefault = "您好，我是 ACS AI 电话助手。请问有什么需要我转告？"
        assertEquals(currentDefault, CallConfig().greeting)
        assertEquals(currentDefault, CallPolicy.migrateDefaultGreeting(legacyDefault))
        assertEquals(currentDefault, CallPolicy.spokenGreeting(legacyDefault, hasTask = false))
        assertEquals(customWithOldName, CallPolicy.migrateDefaultGreeting(customWithOldName))
        assertEquals(customWithOldName, CallPolicy.spokenGreeting(customWithOldName, hasTask = false))
        assertEquals("您好，我是 ACS AI 电话助手。请问现在方便通话吗？",
            CallPolicy.spokenGreeting(currentDefault, hasTask = true))
    }

    @Test fun explicitGreetingIsUsedExactlyAndBlankMeansSilence() {
        for (hasTask in listOf(false, true)) {
            assertEquals("你好", CallPolicy.spokenGreeting("你好", hasTask))
            assertEquals("", CallPolicy.spokenGreeting("", hasTask))
            assertEquals("", CallPolicy.spokenGreeting(" \n\t", hasTask))
        }
    }

    @Test fun dialogueDoesNotDemandAnotherIntroductionAfterTheConfiguredGreeting() {
        for (direction in CallDirection.entries) {
            val prompt = CallPolicy.prompt("你好", direction)
            assertTrue(prompt.contains("你好"))
            assertFalse(prompt.contains("通话开始时明确说明自己是 AI"))
            assertFalse(prompt.contains("Flash phone"))
            assertTrue(prompt.contains("只有对方直接问接话者的身份"))
            assertTrue(prompt.contains("‘喂，能听到吗’，只答‘能听到，您说’"))
            assertFalse(prompt.contains("你是 AI 电话助手"))
        }
    }

    @Test fun explicitSimOverridesPreferenceAndMissingPreferenceNeverFallsBack() {
        val first = CallSim("sim-1", "SIM 1", true)
        val second = CallSim("sim-2", "SIM 2", false)
        val both = listOf(first, second)
        assertEquals(second, CallPolicy.chooseOutgoingSim(both, null, second.id))
        assertEquals(first, CallPolicy.chooseOutgoingSim(both, first.id, second.id))
        assertEquals(first, CallPolicy.chooseOutgoingSim(both, "default", second.id))
        assertEquals(first, CallPolicy.chooseOutgoingSim(both, "default", "sim-404"))
        assertNull(CallPolicy.chooseOutgoingSim(listOf(first), null, second.id))
        assertNull(CallPolicy.chooseOutgoingSim(both, "sim-404", second.id))
        assertNull(CallPolicy.chooseOutgoingSim(both, null, null))
    }

    @Test fun capturesAppOpBaselineWithoutGuessingOnUnknownOutput() {
        assertEquals("default", CallPolicy.previousAppOpMode("No operations.\n"))
        assertEquals("default", CallPolicy.previousAppOpMode("No operations.\nDefault mode: default\n"))
        assertNull(CallPolicy.previousAppOpMode("No operations.\nDefault mode: allow"))
        assertNull(CallPolicy.previousAppOpMode("No operations.\nPermission denial"))
        assertEquals("allow", CallPolicy.previousAppOpMode("MANAGE_ONGOING_CALLS: allow; time=1s"))
        assertEquals("ignore", CallPolicy.previousAppOpMode("Uid mode: MANAGE_ONGOING_CALLS: ignore"))
        assertNull(CallPolicy.previousAppOpMode("Permission denial"))
        assertNull(CallPolicy.previousAppOpMode("Uid mode: MANAGE_ONGOING_CALLS: deny\nMANAGE_ONGOING_CALLS: allow"))
    }
}










