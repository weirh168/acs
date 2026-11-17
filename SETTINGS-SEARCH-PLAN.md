# 设置页顶部搜索：重构方案

现状：`SettingsScreen.kt` 的 `SettingsContent`（约 428-520 行）里，三组共 9 行都是硬编码的
`ListRow(...)`，标题来自 `stringResource`，尾部是各自的 Composable。没有任何统一数据结构，
所以无法按关键词索引。要加搜索，必须先抽出「设置项」这一层。

## 一、抽出的模型

```kotlin
private data class SettingEntry(
    val group: String,                          // 组名（已解析成文字）
    val title: String,                          // 行标题（已解析成文字，供搜索匹配）
    val subtitle: String? = null,
    val keywords: List<String> = emptyList(),   // 别名：搜「通话」能命中「AI 接打电话」
    val onClick: () -> Unit,
    val trailing: @Composable RowScope.() -> Unit, // 保留原有胶囊/值/动作
    val toggle: (@Composable () -> Unit)? = null,  // 开关行单独处理
)
```

要点：**标题在构造时就转成 String**（`stringResource` 只在 Composable 里能调，所以在
`SettingsContent` 内、渲染前构造列表）。

## 二、匹配规则

```kotlin
fun SettingEntry.matches(q: String): Boolean {
    val needle = q.trim()
    if (needle.isEmpty()) return true
    val hay = (listOf(title) + (subtitle?.let(::listOf) ?: emptyList()) + keywords)
    return hay.any { it.contains(needle, ignoreCase = true) }
}
```

- 空搜索 = 全显示（不改变现状）
- 匹配标题、副标题、别名
- 中文用 `contains` 即可，不做分词

## 三、渲染

```kotlin
val entries = remember(...) { listOf(/* 9 项 */) }
val shown = entries.filter { it.matches(query) }

if (shown.isEmpty()) EmptyState("没有匹配「$query」的设置")
else shown.groupBy { it.group }.forEach { (group, rows) ->
    GroupLabel(group)
    GroupCard { rows.forEachIndexed { i, e -> render(e, first = i == 0) } }
}
```

`groupBy` 保持插入顺序，所以组顺序仍由 `entries` 的顺序决定，不会乱。

## 四、搜索框本体

- 放在健康卡下方、第一组上方
- 用现成的输入组件（项目里 `MikaDialog` 之外的文本输入已有用法，需先确认组件名）
- 输入即过滤（9 项，无需防抖）
- 有输入时右侧给一个「清空」×

## 五、改动范围与风险

| 文件 | 改动 |
|---|---|
| `SettingsScreen.kt` | 三组 9 行改写为 entries 列表 + 渲染函数（约 +90 / -60 行） |
| `strings_settings.xml`（中英） | 新增 2 条：搜索占位符、空结果 |

风险点：
1. `trailing` 里用到局部变量（`callsEnabled`、`personalStart`、`status`），构造 entries 时必须
   在作用域内，且 `remember` 的 key 要包含这些变量，否则状态更新后不刷新
2. 开关行（`onPersonalStart`）与普通行的结构不同，需要单独分支
3. `first = true` 的首行标记要按过滤后的顺序重新算

## 六、建议

先做「只读搜索」：不抽 `toggle`，开关行在搜索时仍按普通行显示（点击进子页改）。
这样第一版改动量减半，且不影响功能。等稳定后再把开关行纳入。

## 七、验收

1. 不输入时，三组与现在完全一致（逐行 diff）
2. 输「电话」→ 只剩「AI 接打电话」
3. 输「模型」→ 命中「AI 引擎」（靠 keywords）
4. 输「zzz」→ 显示空结果提示
5. 清空后恢复原状
