package com.wangzan101.mika.ui

import com.wangzan101.mika.ui.components.SearchField

import androidx.compose.ui.unit.dp

import androidx.compose.foundation.layout.padding

import androidx.compose.foundation.layout.fillMaxWidth

import androidx.compose.ui.unit.sp

import com.wangzan101.mika.R
import com.wangzan101.mika.i18n.tr
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import com.wangzan101.mika.settings.ProviderConnection
import android.app.ActivityManager
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import com.wangzan101.mika.ui.components.MikaDialog
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import com.wangzan101.mika.BuildConfig
import com.wangzan101.mika.cap.sandbox.SandboxState
import com.wangzan101.mika.capsule.CapsuleMode
import com.wangzan101.mika.capsule.CapsuleSetup
import com.wangzan101.mika.cap.phone.a11y.ScreenAccessibility
import com.wangzan101.mika.core.agent.SpeedFlags
import com.wangzan101.mika.core.cap.sandbox.SandboxStatus
import com.wangzan101.mika.core.model.ModelRole
import com.wangzan101.mika.core.shell.BuiltinShellStatus
import com.wangzan101.mika.record.RunStore
import com.wangzan101.mika.settings.AccessibilityState
import com.wangzan101.mika.settings.FeatureFlags
import com.wangzan101.mika.settings.Prerequisites
import com.wangzan101.mika.settings.Problem
import com.wangzan101.mika.settings.ProviderStore
import com.wangzan101.mika.settings.NetProxyStore
import com.wangzan101.mika.settings.WebSearchConfig
import com.wangzan101.mika.settings.WebSearchSettings
import com.wangzan101.mika.cap.web.WebProxy
import com.wangzan101.mika.settings.SystemStatus
import com.wangzan101.mika.settings.notificationOverview
import com.wangzan101.mika.task.ParallelCapability
import com.wangzan101.mika.ui.components.ButtonKind
import com.wangzan101.mika.ui.components.ButtonSize
import com.wangzan101.mika.ui.components.GroupCard
import com.wangzan101.mika.ui.components.GroupLabel
import com.wangzan101.mika.ui.components.ListRow
import com.wangzan101.mika.ui.components.MikaButton
import com.wangzan101.mika.ui.components.MikaSwitch
import com.wangzan101.mika.ui.components.PageScaffold
import com.wangzan101.mika.ui.components.PillTone
import com.wangzan101.mika.ui.components.RowChevron
import com.wangzan101.mika.ui.components.RowValue
import com.wangzan101.mika.ui.components.StateCard
import com.wangzan101.mika.ui.components.StatusPill
import com.wangzan101.mika.ui.components.TileTone
import com.wangzan101.mika.ui.theme.MikaIcons
import com.wangzan101.mika.ui.theme.MikaTheme
import com.wangzan101.mika.i18n.AppLanguage
import com.wangzan101.mika.wechat.WechatConnectionState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** 设置里能进入的子页面;[Home] 是设置首页,[Advanced] 集中放置连接、维护和工程能力。 */
private enum class SettingsPage { Home, MyData, Advanced, AppAccess, PhoneOps, Calls, Wechat, DuringWork, Capsule, Language, Notifications, Recommendations, Sandbox, Recovery, SelfCheck, ComputerAccess, McpServers, Root, Developer, RunStats, Proactive }

/**
 * 设置页:总状态卡 + 常用 / 我的数据 / 其他。高级与其他只增加一层,各子页返回来时的页面。
 * 模型页由 [onOpenModels]、记忆与数据由 [onOpenMemory]、关于页由 [onOpenAbout] 交给 Activity。
 * 修复动作由 [onFix] 交给 Activity 去做(请求权限、跳转系统设置)。
 */
@Composable
fun SettingsScreen(
    store: ProviderStore,
    status: SystemStatus,
    androidRelease: String,
    onFix: (Fix) -> Unit,
    onBack: () -> Unit,
    onOpenModels: () -> Unit,
    onOpenMemory: (() -> Unit)? = null,
    /** 任务运行里的「自主模式」:当前值和换它的办法。 */
    autonomous: Boolean = false,
    onAutonomous: (Boolean) -> Unit = {},
    /** 查到的新版本号;有它时「关于 Mika」一行写「x 可更新」带红点。 */
    updateVersion: String? = null,
    onOpenAbout: () -> Unit = {},
    /** 外部 MCP server 设置(outbound);为空时不显示入口。 */
    mcpServers: com.wangzan101.mika.settings.McpServerStore? = null,
    /** 接打电话此刻是否开着;null 表示调用方没传。 */
    callsEnabled: Boolean? = null,
) {
    val configs by store.configs.collectAsState()
    val roles by store.roles.collectAsState()
    // 开发者选项里的「看图定位已验证」跟着看图模型(看图用主模型时是主模型那条配置)
    val visionConfig = remember(configs, roles) { store.configFor(ModelRole.Vision) }
    var page by rememberSaveable { mutableStateOf(SettingsPage.Home) }
    var explaining by remember { mutableStateOf<Problem?>(null) }
    // 「完全退出」先问一句:任务、胶囊和通知都会停
    var confirmingQuit by remember { mutableStateOf(false) }

    fun fix(f: Fix) = if (f == Fix.AddModel) onOpenModels() else onFix(f)
    val onProblem: (Problem) -> Unit = { p -> StatusCopy.directFix(p)?.let(::fix) ?: run { explaining = p } }

    // 并行任务的上限只在实验开关 parallelTasks 打开时出现;设备能力按此刻算,第二块屏建失败过就按失败算
    val context = LocalContext.current
    val recommendedTasks = remember { (context.applicationContext as com.wangzan101.mika.MikaApp).recommendedTasks }
    val root = remember { com.wangzan101.mika.cap.phone.PhoneServices.of(context).shellManager.root }
    val rootState by root.state.collectAsState()
    LaunchedEffect(Unit) { root.refresh() }
    val wechat = remember { (context.applicationContext as com.wangzan101.mika.MikaApp).wechat }
    val wechatState by wechat.state.collectAsState()
    val flags = remember { FeatureFlags.get(context) }
    var personalStart by remember { mutableStateOf(flags.personalStart()) }
    var parallelMax by remember { mutableIntStateOf(flags.parallelMax()) }
    var keepScreenOn by remember { mutableStateOf(flags.keepScreenOn()) }
    var muteTarget by remember { mutableStateOf(flags.muteTarget()) }
    var operatingPace by remember { mutableStateOf(flags.operatingPace()) }
    var stepLimit by remember { mutableStateOf(flags.taskStepLimit()) }
    var tokenBudget by remember { mutableStateOf(flags.taskTokenBudget()) }
    var selfConfig by remember { mutableStateOf(flags.selfConfig()) }
    var degradedScreen by remember { mutableStateOf(flags.degradedScreen()) }
    var selfOperate by remember { mutableStateOf(flags.selfOperate()) }
    var pipOperate by remember { mutableStateOf(flags.pipOperate()) }
    var externalSchedule by remember { mutableStateOf(flags.externalSchedule()) }
    var autoArchiveDays by remember { mutableStateOf(flags.autoArchiveDays()) }
    var editingAutoArchive by remember { mutableStateOf(false) }
    val capsuleMode by remember(flags) { flags.capsuleModeChanges() }.collectAsState(flags.capsuleMode())
    var capsuleIdleOpacity by remember { mutableStateOf(flags.capsuleIdleOpacity()) }
    var capsuleCardScale by remember { mutableStateOf(flags.capsuleCardScale()) }
    // 换语言时界面会重建,这里每次进来读一次即可
    val language = remember { AppLanguage.current(context) }
    val runtimeLimit by (context.applicationContext as com.wangzan101.mika.MikaApp).taskState.parallelLimit.collectAsState()
    var speed by remember { mutableStateOf(flags.speedFlags()) }
    val scope = rememberCoroutineScope()
    val sandboxStatus by remember { SandboxState.get(context) }.status.collectAsState()
    // 网络代理:只在这里改;读设置要解密、看浏览器支不支持要加载 WebView,都放到后台
    val proxies = remember { NetProxyStore.get(context) }
    var proxy by remember { mutableStateOf<String?>(null) }
    var browserProxy by remember { mutableStateOf<WebProxy.Mode?>(null) }
    var editingProxy by remember { mutableStateOf(false) }
    LaunchedEffect(proxy) {
        if (proxy == null) proxy = withContext(Dispatchers.IO) { proxies.get() }
        browserProxy = withContext(Dispatchers.IO) { WebProxy.mode() }
    }
    val searchSettings = remember { WebSearchSettings.get(context) }
    var webSearch by remember { mutableStateOf<WebSearchConfig?>(null) }
    var editingSearch by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { webSearch = withContext(Dispatchers.IO) { searchSettings.get() } }
    val mcp = remember { (context.applicationContext as com.wangzan101.mika.MikaApp).mcp }
    val mcpNetworkOn by mcp.settings.enabled.collectAsState()
    val mcpUsbOn by mcp.usb.enabled.collectAsState()
    val mcpOn = mcpNetworkOn || mcpUsbOn
    val parallel = if (!speed.parallelTasks) null else ParallelSetting(
        parallelMax,
        ParallelCapability.detect(
            status.sdkInt, context.getSystemService(ActivityManager::class.java).isLowRamDevice, parallelMax,
            secondDisplayFailed = runtimeLimit.reason == ParallelCapability.SECOND_DISPLAY_FAILED,
        ),
    )
    // 开发者选项只在调试版和性能测试版里列出:发布版的各开关按评测结果统一定默认值
    val showDeveloper = com.wangzan101.mika.record.DetailedTraces.supportedBuild
    val toHome = { page = SettingsPage.Home }
    val toAdvanced = { page = SettingsPage.Advanced }
    val back = {
        page = when (page) {
            SettingsPage.RunStats, SettingsPage.Proactive -> SettingsPage.Developer
            SettingsPage.SelfCheck -> SettingsPage.Recovery
            SettingsPage.Sandbox, SettingsPage.Recovery, SettingsPage.ComputerAccess,
            SettingsPage.McpServers, SettingsPage.Root, SettingsPage.Developer -> SettingsPage.Advanced
            else -> SettingsPage.Home
        }
    }

    if (page != SettingsPage.Home) BackHandler { back() }

    val visiblePage = when {
        !showDeveloper && (page == SettingsPage.Developer || page == SettingsPage.RunStats || page == SettingsPage.Proactive) -> SettingsPage.Home
        page == SettingsPage.Root && !rootState.suPresent -> SettingsPage.Advanced
        else -> page
    }
    when (visiblePage) {
        SettingsPage.MyData -> MyDataScreen(
            counts = run {
                // 记忆走 Flow,对话取一次列表;登录与学到做法暂时还没有读数接口,如实留 0
                val app = context.applicationContext as com.wangzan101.mika.MikaApp
                val memories by remember(app) { app.memory.items() }.collectAsState()
                val conversations = remember(app) { runCatching { app.conversations.list() }.getOrDefault(emptyList()) }
                MyDataCounts(memories = memories.size, conversations = conversations.size)
            },
            onBack = toHome,
            onManageMemories = { onOpenMemory?.invoke() },

            onClearAll = {
                val app = context.applicationContext as com.wangzan101.mika.MikaApp
                // 记忆:stripMemory(空集) 表示一条都不留;对话:逐个删
                runCatching { app.memory.stripMemory(emptySet()) }
                runCatching { app.conversations.list().forEach { app.conversations.delete(it.id) } }
            },
        )
        SettingsPage.Home -> SettingsContent(
            status = status, androidRelease = androidRelease,
            mainModel = roles.main?.let { id -> configs.firstOrNull { it.id == id } }?.let(ProviderConnection::displayName),
            onBack = onBack, onProblem = onProblem, onOpenModels = onOpenModels,
            onOpenPhoneOps = { page = SettingsPage.PhoneOps },
            onOpenCalls = { page = SettingsPage.Calls },
            wechatState = wechatState, wechatBound = wechat.store.account() != null,
            onOpenWechat = { page = SettingsPage.Wechat },
            onOpenAppAccess = { page = SettingsPage.AppAccess },
            onOpenDuringWork = { page = SettingsPage.DuringWork },
            capsuleMode = capsuleMode, onOpenCapsule = { page = SettingsPage.Capsule },
            onOpenNotifications = { page = SettingsPage.Notifications },
            language = language, onOpenLanguage = { page = SettingsPage.Language },
            personalStart = personalStart,
            onPersonalStart = { flags.setPersonalStart(it); personalStart = it },
            autoArchiveDays = autoArchiveDays,
            onOpenAutoArchive = { editingAutoArchive = true },
            onOpenMemory = { page = SettingsPage.MyData },
        callsEnabled = callsEnabled,
            onOpenRecommendations = { page = SettingsPage.Recommendations },
            onOpenAdvanced = { page = SettingsPage.Advanced },
            versionName = BuildConfig.VERSION_NAME, updateVersion = updateVersion, onOpenAbout = onOpenAbout,
        )
        SettingsPage.Advanced -> AdvancedSettingsContent(
            proxy = proxy, proxyNote = proxy?.let { NetProxyCopy.subtitle(it, browserProxy) }, onOpenProxy = { editingProxy = true },
            modelBaseUrl = configs.firstOrNull()?.baseUrl,
            onClearProxy = {
                scope.launch {
                    withContext(Dispatchers.IO) { proxies.set("") }
                    proxy = withContext(Dispatchers.IO) { proxies.get() }
                }
            },
            webSearch = webSearch, onOpenWebSearch = { editingSearch = true },
            sandbox = sandboxStatus, onOpenSandbox = { page = SettingsPage.Sandbox },
            showRecovery = status.sdkInt >= Prerequisites.MIN_SDK, onOpenRecovery = { page = SettingsPage.Recovery },
            computerAccess = mcpOn, onOpenComputerAccess = { page = SettingsPage.ComputerAccess },
            mcpServersCount = mcpServers?.servers?.value?.size, onOpenMcpServers = { page = SettingsPage.McpServers },
            showRoot = rootState.suPresent, rootCommands = rootState.commands, onOpenRoot = { page = SettingsPage.Root },
            showDeveloper = showDeveloper, onOpenDeveloper = { page = SettingsPage.Developer },
            onBack = toHome,
            onQuit = { confirmingQuit = true },
        )
        SettingsPage.AppAccess -> AppAccessScreen(onBack = toHome)
        SettingsPage.Wechat -> WechatSettingsScreen(wechat, onBack = toHome)
        SettingsPage.PhoneOps -> PhoneOpsScreen(
            status, androidRelease, onProblem,
            onRepair = { onFix(Fix.RepairPhoneHelper) }, onUnpair = { onFix(Fix.UnpairPhoneHelper) }, onBack = toHome,
        )
        SettingsPage.Calls -> CallSettingsScreen((context.applicationContext as com.wangzan101.mika.MikaApp).calls, onBack = toHome)
        SettingsPage.Notifications -> NotificationsScreen(status, onFix = ::fix, onBack = back)
        SettingsPage.DuringWork -> DuringWorkScreen(
            keepScreenOn, onKeepScreenOn = { flags.setKeepScreenOn(it); keepScreenOn = it },
            muteTarget, onMuteTarget = { flags.setMuteTarget(it); muteTarget = it },
            parallel, onParallelMax = { flags.setParallelMax(it); parallelMax = it }, onBack = toHome,
            autonomous = autonomous, onAutonomous = onAutonomous,
            operatingPace = operatingPace, onOperatingPace = { flags.setOperatingPace(it); operatingPace = it },
            stepLimit = stepLimit, onStepLimit = { flags.setTaskStepLimit(it); stepLimit = it },
            tokenBudget = tokenBudget, onTokenBudget = { flags.setTaskTokenBudget(it); tokenBudget = it },
            selfConfig = selfConfig, onSelfConfig = { flags.setSelfConfig(it); selfConfig = it },
            degradedScreen = degradedScreen, onDegradedScreen = { flags.setDegradedScreen(it); degradedScreen = it },
            selfOperate = selfOperate, onSelfOperate = { flags.setSelfOperate(it); selfOperate = it },
            pipOperate = pipOperate, onPipOperate = { flags.setPipOperate(it); pipOperate = it },
            externalSchedule = externalSchedule, onExternalSchedule = { flags.setExternalSchedule(it); externalSchedule = it },
        )
        SettingsPage.Language -> LanguageScreen(language, onLanguage = { AppLanguage.set(context, it) }, onBack = toHome)
        SettingsPage.Recommendations -> RecommendedTasksScreen(recommendedTasks, onBack = toHome)
        SettingsPage.Capsule -> CapsuleScreen(
            capsuleMode, onMode = {
                flags.setCapsuleMode(it)
                if (CapsuleSetup.needsAccessibility(it, ScreenAccessibility.instance.value != null)) onFix(Fix.OpenAccessibility)
            }, onBack = toHome,
            idleOpacity = capsuleIdleOpacity,
            onIdleOpacity = { flags.setCapsuleIdleOpacity(it); capsuleIdleOpacity = it },
            cardScale = capsuleCardScale,
            onCardScale = { flags.setCapsuleCardScale(it); capsuleCardScale = it },
        )
        SettingsPage.Sandbox -> SandboxScreen(onBack = toAdvanced)
        SettingsPage.Recovery -> RecoveryScreen(onBack = toAdvanced, onOpenSelfCheck = { page = SettingsPage.SelfCheck })
        SettingsPage.SelfCheck -> SelfCheckScreen(status, onBack = back)
        SettingsPage.ComputerAccess -> McpScreen(mcp, onBack = toAdvanced)
        SettingsPage.McpServers -> mcpServers?.let { McpServersScreen(it, onBack = toAdvanced) }
        SettingsPage.Root -> RootScreen(helperRow = status.sdkInt >= Prerequisites.MIN_SDK, onBack = toAdvanced)
        SettingsPage.Developer -> DeveloperOptionsScreen(
            speed, onSpeed = { flags.setSpeed(it); speed = it }, onBack = toAdvanced,
            grounding = visionConfig?.let { GroundingSetting(it.model, it.capabilities.groundingVerified) },
            onGrounding = { verified -> scope.launch { withContext(Dispatchers.IO) { store.setVisionGroundingVerified(verified) } } },
            onOpenRunStats = { page = SettingsPage.RunStats },
            onOpenProactive = { page = SettingsPage.Proactive },
        )
        SettingsPage.RunStats -> RunStatsScreen(remember { RunStore(context).metrics }, onBack = back)
        SettingsPage.Proactive -> com.wangzan101.mika.proactive.ProactiveScreen(onBack = back)
    }

    if (editingProxy) NetProxyDialog(
        initial = proxy.orEmpty(),
        onDismiss = { editingProxy = false },
        onSave = { v ->
            scope.launch {
                withContext(Dispatchers.IO) { proxies.set(v) }
                proxy = v.trim()
                editingProxy = false
            }
        },
    )

    if (editingSearch) WebSearchDialog(
        initial = webSearch ?: WebSearchConfig(),
        onDismiss = { editingSearch = false },
        onSave = { config ->
            scope.launch {
                withContext(Dispatchers.IO) { searchSettings.set(config) }
                webSearch = searchSettings.get()
                editingSearch = false
            }
        },
    )

    explaining?.let { p ->
        val e = StatusCopy.explain(p, androidRelease)
        MikaDialog(
            onDismissRequest = { explaining = null },
            title = { Text(e.title) },
            text = {
                Column {
                    Text(e.body)
                    e.secondaryAction?.let { (label, destination) ->
                        TextButton(onClick = {
                            explaining = null
                            fix(destination)
                        }) { Text(label) }
                    }
                }
            },
            confirmButton = {
                if (e.action != null && e.fix != null) {
                    TextButton({ explaining = null; fix(e.fix) }) { Text(e.action) }
                } else {
                    TextButton({ explaining = null }) { Text(stringResource(R.string.ok_got_it)) }
                }
            },
            dismissButton = if (e.fix != null) ({ TextButton({ explaining = null }) { Text(stringResource(R.string.cancel)) } }) else null,
        )
    }

    if (confirmingQuit) {
        AlertDialog(
            onDismissRequest = { confirmingQuit = false },
            title = { Text(stringResource(R.string.quit_title)) },
            text = { Text(stringResource(R.string.quit_confirm_body)) },
            confirmButton = {
                TextButton({ confirmingQuit = false; com.wangzan101.mika.quit.MikaQuit.quit(context) }) {
                    Text(stringResource(R.string.quit_confirm_action), color = MikaTheme.colors.bad)
                }
            },
            dismissButton = { TextButton({ confirmingQuit = false }) { Text(stringResource(R.string.cancel)) } },
        )
    }

    if (editingAutoArchive) {
        AutoArchiveDialog(
            current = autoArchiveDays,
            onPick = { days ->
                flags.setAutoArchiveDays(days)
                autoArchiveDays = days
                editingAutoArchive = false
                // 选完马上按新设置跑一次,老对话立刻进归档
                (context.applicationContext as com.wangzan101.mika.MikaApp).autoArchiveNow()
            },
            onDismiss = { editingAutoArchive = false },
        )
    }
}

/** 不带状态的设置首页,便于测试。首页只列常用入口,高级能力统一从 [onOpenAdvanced] 进入。 */
@Composable
fun SettingsContent(
    status: SystemStatus,
    androidRelease: String,
    /** 当前主模型的名字;没有可用的主模型时为空。 */
    mainModel: String?,
    onBack: () -> Unit,
    onProblem: (Problem) -> Unit,
    onOpenModels: () -> Unit,
    onOpenPhoneOps: () -> Unit = {},
    onOpenCalls: () -> Unit = {},
    wechatState: WechatConnectionState = WechatConnectionState.NeedsBinding,
    wechatBound: Boolean = false,
    onOpenWechat: () -> Unit = {},
    onOpenAppAccess: () -> Unit = {},
    onOpenDuringWork: () -> Unit = {},
    /** 悬浮胶囊此刻的选择,写在「悬浮胶囊」一行的右边。 */
    capsuleMode: CapsuleMode = CapsuleMode.DEFAULT,
    onOpenCapsule: () -> Unit = {},
    onOpenNotifications: () -> Unit = {},
    /** 此刻选的界面语言,写在「语言与外观」一行的右边。 */
    language: AppLanguage = AppLanguage.System,
    onOpenLanguage: () -> Unit = {},
    onOpenMemory: (() -> Unit)? = null,
    callsEnabled: Boolean? = null,
    onOpenRecommendations: () -> Unit = {},
    onOpenAdvanced: () -> Unit = {},
    versionName: String = "",
    updateVersion: String? = null,
    onOpenAbout: () -> Unit = {},
    personalStart: Boolean = false,
    onPersonalStart: ((Boolean) -> Unit)? = null,
    /** 自动归档:多久没有新消息的对话自动归档;0 表示关闭。 */
    autoArchiveDays: Int = 0,
    onOpenAutoArchive: () -> Unit = {},
) {
    val check = Prerequisites.check(status, hasMainModel = mainModel != null)
    PageScaffold(stringResource(R.string.settings_title), onBack) {
        StatusSummary(
            check, onProblem, onOpenNotifications = onOpenNotifications,
            callsEnabled = callsEnabled,
            phoneOpsReady = status.sdkInt >= Prerequisites.MIN_SDK &&
                status.builtinShell == BuiltinShellStatus.Running && status.accessibility == AccessibilityState.On,
            wechatConnected = wechatState == WechatConnectionState.Connected,
        )

        // 搜索:只在三组内过滤;标题先转成文字,再按标题/副标题/别名匹配
        var settingsQuery by remember { mutableStateOf("") }
        val q = settingsQuery.trim()
        fun hit(vararg texts: String): Boolean =
            q.isEmpty() || texts.any { it.contains(q, ignoreCase = true) }

        val tCalls = stringResource(R.string.calls_title)
        val tPhoneOps = stringResource(R.string.settings_phone_ops)
        val tDuringWork = stringResource(R.string.settings_during_work)
        val tCapsule = CapsuleSettingsCopy.TITLE
        val tLanguage = stringResource(R.string.settings_language_appearance)
        val tPersonalStart = stringResource(R.string.settings_personal_start)
        val tModel = stringResource(R.string.settings_model)
        val tWechat = stringResource(R.string.wechat_title)
        val tNotif = StatusCopy.NOTIFICATIONS
        // 用和行内一致的判定(含别名),否则别名命中时还会误报「没有匹配」
        val anyShown = listOf(
            hit(tCalls, "打电话", "接电话"),
            hit(tPhoneOps, "无障碍", "权限"),
            hit(tDuringWork, "节奏", "声音"),
            hit(tCapsule, "悬浮", "胶囊"),
            hit(tLanguage, "字体", "深浅色"),
            hit(tPersonalStart, "启动", "首屏"),
            hit(tModel, "大模型", "服务商", "Token"),
            hit(tWechat, "微信"),
            hit(tNotif, "弹窗", "通知"),
        ).any { it }

        SearchField(settingsQuery, { settingsQuery = it }, "搜索设置项", Modifier.testTag("settings-search"))
        if (!anyShown) {
            Text("没有匹配「" + settingsQuery + "」的设置", fontSize = 13.sp, color = MikaTheme.colors.ink3,
                modifier = Modifier.padding(horizontal = 4.dp, vertical = 8.dp))
        }

        // 组内一行都没命中时,组名也不显示
        val aiShown = hit(tCalls, "打电话", "接电话") || hit(tPhoneOps, "无障碍", "权限") || hit(tDuringWork, "节奏", "声音")
        val handyShown = hit(tCapsule, "悬浮", "胶囊") || hit(tLanguage, "字体", "深浅色") || hit(tPersonalStart, "启动", "首屏")
        val connShown = hit(tModel, "大模型", "服务商", "Token") || hit(tWechat, "微信") || hit(tNotif, "弹窗", "通知")
        // 三组按「我想干什么」排,不按模块名排;AI 接打电话是核心能力,放第一行
        if (aiShown) GroupLabel(stringResource(R.string.settings_group_ai))
        GroupCard {
            if (hit(tCalls, "打电话", "接电话")) {
                ListRow(MikaIcons.Phone, tCalls, stringResource(R.string.calls_entry_sub), first = true, onClick = onOpenCalls) {
                    // 彩色胶囊只表示健康;开关状态用灰字值
                    callsEnabled?.let { RowValue(if (it) stringResource(R.string.state_on) else stringResource(R.string.state_off)) }
                    RowChevron()
                }
            }
            val phoneOpsReady = status.sdkInt >= Prerequisites.MIN_SDK &&
                status.builtinShell == BuiltinShellStatus.Running && status.accessibility == AccessibilityState.On
            if (hit(tPhoneOps, "无障碍", "权限")) {
                ListRow(MikaIcons.Phone, tPhoneOps, stringResource(R.string.settings_phone_ops_sub), onClick = onOpenPhoneOps) {
                    PhoneOpsPill(status)
                    // 没通时行内直接给动作,不用点进子页才知道要补什么
                    if (!phoneOpsReady && status.sdkInt >= Prerequisites.MIN_SDK) {
                        TextButton(onClick = onOpenPhoneOps) {
                            Text(stringResource(R.string.settings_fix_row), fontSize = 13.sp)
                        }
                    }
                    RowChevron()
                }
            }
            if (hit(tDuringWork, "节奏", "声音")) {
                ListRow(MikaIcons.Moon, tDuringWork, stringResource(R.string.settings_during_work_sub), onClick = onOpenDuringWork) { RowChevron() }
            }
        }

        if (handyShown) GroupLabel("用起来顺手")
        GroupCard {
            if (hit(tCapsule, "悬浮", "胶囊")) {
                ListRow(MikaIcons.Message, tCapsule, CapsuleSettingsCopy.SUBTITLE, first = true, onClick = onOpenCapsule) {
                    RowValue(CapsuleSettingsCopy.label(capsuleMode))
                    RowChevron()
                }
            }
            if (hit(tLanguage, "字体", "深浅色")) {
                ListRow(MikaIcons.Globe, tLanguage, stringResource(R.string.settings_language_sub), onClick = onOpenLanguage) {
                    RowValue(languageLabel(language))
                    RowChevron()
                }
            }
            onPersonalStart?.let { change ->
                if (hit(tPersonalStart, "启动", "首屏")) {
                    ListRow(MikaIcons.Spark, tPersonalStart, stringResource(R.string.settings_personal_start_sub)) {
                        MikaSwitch(personalStart, change, Modifier.semantics { contentDescription = tPersonalStart })
                    }
                }
            }
        }

        if (connShown) GroupLabel(stringResource(R.string.settings_group_connect))
        GroupCard {
            if (hit(tModel, "大模型", "服务商", "Token")) {
                ListRow(MikaIcons.Spark, tModel, stringResource(R.string.settings_model_sub), first = true, onClick = onOpenModels) {
                    RowValue(mainModel ?: stringResource(R.string.settings_not_set))
                    RowChevron()
                }
            }
            if (hit(tWechat, "微信")) {
                ListRow(MikaIcons.Chats, tWechat, stringResource(R.string.wechat_settings_sub), onClick = onOpenWechat) {
                    WechatEntryStatus(wechatState, wechatBound)
                    RowChevron()
                }
            }
            val (notifText, notifTone) = StatusCopy.notificationSummary(status.notificationOverview().summary)
            if (hit(tNotif, "弹窗", "通知")) {
                ListRow(MikaIcons.Bell, tNotif, stringResource(R.string.settings_notif_sub), onClick = onOpenNotifications) {
                    RowValue(notifText, notifTone)
                    RowChevron()
                }
            }
        }

        GroupLabel(stringResource(R.string.settings_privacy))
        GroupCard {
            onOpenMemory?.let {
                ListRow(MikaIcons.Heart, stringResource(R.string.settings_memory_data), stringResource(R.string.settings_memory_sub), first = true, onClick = it) { RowChevron() }
            }
            ListRow(
                MikaIcons.Archive,
                stringResource(R.string.settings_auto_archive),
                stringResource(R.string.settings_auto_archive_sub),
                first = onOpenMemory == null,
                onClick = onOpenAutoArchive,
            ) {
                RowValue(
                    if (autoArchiveDays <= 0) stringResource(R.string.state_off)
                    else pluralStringResource(R.plurals.settings_auto_archive_days, autoArchiveDays, autoArchiveDays),
                )
                RowChevron()
            }
            ListRow(MikaIcons.Shield, stringResource(R.string.appaccess_title), stringResource(R.string.appaccess_row_sub), onClick = onOpenAppAccess) { RowChevron() }
        }

        GroupLabel(stringResource(R.string.settings_other))
        GroupCard {
            ListRow(MikaIcons.Message, stringResource(R.string.recommendations_title), "首页那几张推荐卡，可以关掉", first = true, onClick = onOpenRecommendations) { RowChevron() }
            ListRow(MikaIcons.Wrench, stringResource(R.string.settings_advanced), stringResource(R.string.settings_advanced_sub), onClick = onOpenAdvanced) { RowChevron() }
        }
        GroupCard {
            ListRow(MikaIcons.Info, stringResource(R.string.settings_about), first = true, onClick = onOpenAbout) {
                TrailingValue(AboutCopy.settingsValue(updateVersion, versionName))
                RowChevron()
            }
        }
    }
}

/** 高级与其他:网络与连接、维护、开发者三组;各能力仍使用原来的完整子页。 */
@Composable
fun AdvancedSettingsContent(
    onBack: () -> Unit,
    proxy: String? = null,
    proxyNote: String? = null,
    onOpenProxy: () -> Unit = {},
    onClearProxy: () -> Unit = {},
    /** 主模型的地址:用来测「模型服务」通不通。 */
    modelBaseUrl: String? = null,
    webSearch: WebSearchConfig? = null,
    onOpenWebSearch: () -> Unit = {},
    sandbox: SandboxStatus? = null,
    onOpenSandbox: () -> Unit = {},
    showRecovery: Boolean = true,
    onOpenRecovery: () -> Unit = {},
    computerAccess: Boolean? = null,
    onOpenComputerAccess: () -> Unit = {},
    mcpServersCount: Int? = null,
    onOpenMcpServers: () -> Unit = {},
    showRoot: Boolean = false,
    rootCommands: Boolean = false,
    onOpenRoot: () -> Unit = {},
    showDeveloper: Boolean = false,
    onOpenDeveloper: () -> Unit = {},
    onQuit: () -> Unit = {},
) {
    PageScaffold(stringResource(R.string.settings_advanced), onBack) {
        val sandboxRow = sandbox?.takeIf { it !is SandboxStatus.Unsupported }
        if (proxy != null || webSearch != null || sandboxRow != null || computerAccess != null || mcpServersCount != null || showRoot) {
        // 结论卡:先回答「通不通」,再让人改设置
        var probing by remember { mutableStateOf(false) }
        var probeLines by remember { mutableStateOf<List<Pair<String, String>>?>(null) }
        // 最近几次失败的时间点:5 分钟内两次就给个主动提示
        var failureTimes by remember { mutableStateOf<List<Long>>(emptyList()) }
        val probeScope = rememberCoroutineScope()
        val probeContext = LocalContext.current
        // 探测逻辑抽成函数:首次测量与「关掉代理再测一次」共用
        val runProbe: () -> Unit = {
            probing = true
            probeScope.launch {
                val lines = mutableListOf<Pair<String, String>>()
                modelBaseUrl?.takeIf { it.isNotBlank() }?.let { base ->
                    // 模型服务只要连得上就算通(401/403 也说明网络到了)
                    val r = com.wangzan101.mika.net.NetworkProbe.head(base) { it in 100..499 }
                    lines += "模型服务" to com.wangzan101.mika.net.ProbeResult.summary(r)
                }
                val searchSettings = com.wangzan101.mika.settings.WebSearchSettings.get(probeContext)
                val searchConfig = runCatching { searchSettings.get() }.getOrNull()
                val searchService = runCatching { searchSettings.service() }.getOrNull()
                when {
                    searchService != null -> {
                        val s = com.wangzan101.mika.net.SearchProbe.run(searchService)
                        lines += "网页搜索" to com.wangzan101.mika.net.ProbeResult.summary(s)
                    }
                    searchConfig?.enabled != true -> lines += "网页搜索" to "未启用"
                    else -> lines += "网页搜索" to "没填完整"
                }
                // GitHub 的 release 接口不认 HEAD(会回 404),用 GET 只取状态码
                val d = com.wangzan101.mika.net.NetworkProbe.head(
                    com.wangzan101.mika.about.MikaLinks.LATEST_RELEASE_API,
                    method = "GET",
                    accept = { it in 200..399 || it == 403 || it == 404 },
                )
                lines += "下载更新" to com.wangzan101.mika.net.ProbeResult.summary(d)
                probeLines = lines
                probing = false
            }
        }
        val allOk = probeLines?.all { it.second.endsWith("秒") } ?: true
        GroupCard(Modifier.testTag("net-conclusion")) {
            ListRow(
                MikaIcons.Globe,
                when {
                    probeLines == null -> "网络"
                    allOk -> "网络正常"
                    else -> "网络有点问题"
                },
                probeLines?.joinToString(" · ") { it.first + " " + it.second }
                    ?: "点右边测一下，看模型、搜索、下载通不通",
                first = true,
            ) {
                TextButton(
                    onClick = { runProbe() },
                    enabled = !probing,
                    modifier = Modifier.testTag("net-probe"),
                ) { Text(if (probing) "测着…" else "测一下", fontSize = 14.sp) }
            }
            // 有失败就给下一步:配了代理就建议先关掉,没配且是搜索失败就直接去改搜索设置
            val recentFailures = failureTimes.count { System.currentTimeMillis() - it <= 5 * 60_000L }
            if (recentFailures >= 2) {
                NetProbeRetryRow("5 分钟内连着两次不通，代理可能有问题", if (proxy?.isNotBlank() == true) "先关掉代理" else "去改搜索设置") {
                    if (proxy?.isNotBlank() == true) { onClearProxy(); runProbe() } else onOpenWebSearch()
                }
            }
            if (probeLines != null && !allOk) {
                val searchFailed = probeLines?.any { it.first == "网页搜索" && !it.second.endsWith("秒") } == true
                if (proxy?.isNotBlank() == true) {
                    NetProbeRetryRow("看起来是代理的问题，要不要先关掉再试？", "关掉代理再测一次") {
                        onClearProxy(); runProbe()
                    }
                } else if (searchFailed) {
                    NetProbeRetryRow("网页搜索没通，可能是服务或额度的问题", "去改搜索设置") {
                        onOpenWebSearch()
                    }
                }
            }
        }
            GroupLabel(stringResource(R.string.settings_connections))
            GroupCard {
                var first = true
                fun take(): Boolean = first.also { first = false }
                proxy?.let {
                    ListRow(MikaIcons.Link, NetProxyCopy.TITLE, "填了就走代理，不填就直连", first = take(), onClick = onOpenProxy) {
                        RowValue(NetProxyCopy.value(it))
                        // 代理坏了要能立刻关掉,不用点进子页
                        if (it.isNotBlank()) {
                            TextButton(onClick = onClearProxy, modifier = Modifier.testTag("net-proxy-off")) {
                                Text("关掉", fontSize = 13.sp)
                            }
                        }
                        RowChevron()
                    }
                }
                webSearch?.let { config ->
                    ListRow(MikaIcons.Globe, stringResource(R.string.web_search_title), stringResource(R.string.web_search_row_sub), first = take(), onClick = onOpenWebSearch) {
                        RowValue(WebSearchCopy.value(config)); RowChevron()
                    }
                }
                if (sandboxRow != null) {
                    ListRow(MikaIcons.Terminal, stringResource(R.string.settings_sandbox), "已就绪，不用管", first = take(), onClick = onOpenSandbox) {
                        RowValue(sandboxValue(sandboxRow)); RowChevron()
                    }
                }
                mcpServersCount?.let { count ->
                    ListRow(MikaIcons.Link, stringResource(R.string.mcp_servers_title), "0 个也能正常用", first = take(), onClick = onOpenMcpServers) {
                        RowValue(stringResource(R.string.mcp_servers_count, count)); RowChevron()
                    }
                }
                if (showRoot) {
                    ListRow(MikaIcons.Key, PhoneSetupCopy.ROOT_GROUP, PhoneSetupCopy.rootEntryLine(rootCommands), first = take(), onClick = onOpenRoot) {
                        RowChevron()
                    }
                }
            }
        }
        // 连接电脑属于调试通道,不属于「网络」
        computerAccess?.let { on ->
            GroupLabel("调试")
            GroupCard {
                ListRow(MikaIcons.Desktop, stringResource(R.string.mcp_title), "只有排查问题才要用", first = true,
                    onClick = onOpenComputerAccess) {
                    RowValue(stringResource(if (on) R.string.state_on else R.string.state_off)); RowChevron()
                }
            }
        }
        if (showRecovery) {
            GroupLabel(stringResource(R.string.settings_maintenance))
            GroupCard {
                ListRow(MikaIcons.Wrench, stringResource(R.string.settings_recovery), first = true, onClick = onOpenRecovery) { RowChevron() }
            }
        }
        if (showDeveloper) {
            GroupLabel(stringResource(R.string.settings_developer_group))
            GroupCard {
                ListRow(MikaIcons.Code, stringResource(R.string.settings_developer), first = true, onClick = onOpenDeveloper) { RowChevron() }
            }
        }

        // 完全退出:和无障碍服务不同,它只是让 Mika 安静下来;下次打开 App 就回来
        GroupCard {
            ListRow(
                MikaIcons.Power, stringResource(R.string.quit_title), stringResource(R.string.quit_row_sub),
                first = true, titleColor = MikaTheme.colors.bad, onClick = onQuit,
            ) { RowChevron() }
        }
    }
}

/** 「手机操作」一行尾部的状态胶囊:无障碍和内置助手都就绪才是「可用」。 */
@Composable
private fun PhoneOpsPill(status: SystemStatus) {
    when {
        status.sdkInt < Prerequisites.MIN_SDK -> StatusPill(stringResource(R.string.pill_unsupported), PillTone.Neutral)
        status.builtinShell == BuiltinShellStatus.Running && status.accessibility == AccessibilityState.On -> StatusPill(stringResource(R.string.pill_available), PillTone.Ok)
        else -> StatusPill(stringResource(R.string.pill_needs_attention), PillTone.Warn)
    }
}

private fun sandboxValue(s: SandboxStatus): String = when (s) {
    is SandboxStatus.Ready -> tr(R.string.sandbox_ready)
    is SandboxStatus.Installing -> tr(R.string.sandbox_preparing)
    is SandboxStatus.Broken -> tr(R.string.pill_needs_attention)
    else -> tr(R.string.sandbox_not_prepared)
}

/**
 * 页面顶上的总状态:一切正常是「一切就绪」;否则变成第一个问题的提示,带修复按钮。
 * 焦点提醒改不了,只在手机操作页的「系统版本」一行里提示,不占这里。
 */
@Composable
private fun StatusSummary(
    check: Prerequisites.Check,
    onProblem: (Problem) -> Unit,
    onOpenNotifications: () -> Unit,
    callsEnabled: Boolean? = null,
    phoneOpsReady: Boolean = true,
    wechatConnected: Boolean = false,
) {
    // 通知被调低不在这里出卡片:下面的「通知」一行已经标了「有 N 项不会弹出」,
    // 顶栏只在真有别的毛病时占用(没有别的毛病时也不硬说「一切就绪」)。
    val problem = check.problems.firstOrNull { it != Problem.FocusMayLeak && it !is Problem.AttentionLowered }
    val onlyLoweredNotifications = problem == null && check.problems.any { it !is Problem.FocusMayLeak }
    when {
        onlyLoweredNotifications -> Unit
        problem == null -> {
            // 一句人话说清「现在能干什么」,不让人滚到底才发现问题
            val abilities = buildList {
                add(if (phoneOpsReady) "能看屏幕" else "屏幕操作没通")
                if (callsEnabled != null) add(if (callsEnabled) "能接电话" else "接电话已关")
                if (wechatConnected) add("连着微信")
            }
            StateCard(
                MikaIcons.Check, "AI 现在能用", abilities.joinToString(" · "),
                TileTone.Ok, Modifier.testTag("settings-status"),
            )
        }
        else -> {
            val copy = StatusCopy.banner(problem)
            StateCard(
                MikaIcons.Exclaim, copy.title, copy.detail,
                if (problem in check.blockers) TileTone.Bad else TileTone.Warn,
                Modifier.testTag("settings-status"),
            ) {
                MikaButton(copy.link, { onProblem(problem) }, kind = ButtonKind.Tonal, size = ButtonSize.Small)
            }
        }
    }
}

/** 探测失败且配了代理时的一行:先建议关掉代理再测一次。
 *  独立成函数是为了避开本文件里同名的自定义 Row / Text 组件。 */
@Composable
private fun NetProbeRetryRow(text: String, action: String, onClick: () -> Unit) {
    androidx.compose.foundation.layout.Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
    ) {
        androidx.compose.material3.Text(
            "看起来是代理的问题，要不要先关掉再试？",
            fontSize = 13.sp,
            color = MikaTheme.colors.ink2,
            modifier = Modifier.weight(1f),
        )
        androidx.compose.material3.TextButton(
            onClick = onClick,
            modifier = Modifier.testTag("net-probe-without-proxy"),
        ) {
            androidx.compose.material3.Text(action, fontSize = 13.sp)
        }
    }
}




















