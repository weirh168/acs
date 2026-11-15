package com.wangzan101.mika.core.cap.web

import com.wangzan101.mika.core.observation.Untrusted
import com.wangzan101.mika.core.prompt.Feedback
import com.wangzan101.mika.core.prompt.Prompts
import com.wangzan101.mika.core.tool.Args
import com.wangzan101.mika.core.tool.Risk
import com.wangzan101.mika.core.tool.ToolContext
import com.wangzan101.mika.core.tool.ToolDef
import com.wangzan101.mika.core.tool.ToolExecution
import com.wangzan101.mika.core.tool.Verb
import com.wangzan101.mika.core.tool.fail
import com.wangzan101.mika.core.tool.int
import com.wangzan101.mika.core.tool.ok
import com.wangzan101.mika.core.tool.str
import com.wangzan101.mika.core.uistate.lastSnapshot
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

private const val MAX_ITEMS = 100
private const val DEFAULT_ITEMS = 20
private const val ITEM_TEXT_MAX = 600
private const val ITEM_TITLE_MAX = 200
private const val MAX_SELECTOR = 200

/**
 * 把页面上重复的一组条目一条条读成结构化数据(列表、卡片、搜索结果、表格行)。
 *
 * 和 [ReadPage] 的区别:`read_page` 把整页正文压成一段,条目边界会糊在一起;这个工具按重复单元切开,
 * 每条带 `text`/`title`/`link`。不给 `selector` 时自己找页面上最大的那组同构兄弟节点。
 * 脚本在页面的读取世界里只读地跑(与 [EvaluateJs] 同一条通道),不改页面、不发网络请求。
 */
internal object ReadAll : WebTool {
    override val verb = Verb.ReadPage
    override val label = "读取列表"
    override val risk = Risk.Read
    override val def = ToolDef("web_read_all",
        Prompts.tool("web_read_all", "max_items" to MAX_ITEMS, "default_items" to DEFAULT_ITEMS),
        mapOf(
            "selector" to str("Optional CSS selector for ONE item (e.g. `li.result`, `.card`, `table tbody tr`). Omit to auto-detect the largest repeated group on the page."),
            "maxItems" to int("How many items to return, 1-$MAX_ITEMS (default $DEFAULT_ITEMS).", 1, MAX_ITEMS),
        ))

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val selector = a.str("selector", max = MAX_SELECTOR)?.trim()?.takeIf { it.isNotEmpty() }
        val maxItems = a.int("maxItems", 1, MAX_ITEMS) ?: DEFAULT_ITEMS
        val r = try {
            ctx.web!!.evaluate(listScript(selector, maxItems), READ_SCRIPT_DEFAULT_TIMEOUT_MS.toLong(), null)
        } catch (e: WebTabCrashed) {
            return fail("tab_crashed", "The page closed before it could be read; open it again with web_navigate.")
        } catch (e: WebTabHandedOver) {
            return fail("handed_over", "This tab is with the user right now; continue after they hand it back.")
        } catch (e: WebDialogOpen) {
            return fail(DIALOG_OPEN, "A page dialog is open; answer it first.")
        }
        if (r is EvalJs.Failed) return fail(r.error, r.message)

        val parsed = parse((r as EvalJs.Ok).json)
            ?: return fail("not_a_list",
                "The page did not return a list. Try web_observe or web_read_page, or pass a selector such as `li` or `.card`.")
        val items = (parsed["items"] as? JsonArray).orEmpty()
        val found = (parsed["found"] as? JsonPrimitive)?.contentOrNull?.toIntOrNull() ?: items.size
        val used = (parsed["usedSelector"] as? JsonPrimitive)?.takeIf { it.isString }?.content
        val url = ctx.lastSnapshot?.web?.url
        val title = ctx.lastSnapshot?.web?.title

        val shown = items.take(maxItems)
        val read = shown.joinToString("\n") { el ->
            val o = el as? JsonObject
            val t = (o?.get("text") as? JsonPrimitive)?.contentOrNull.orEmpty()
            val h = (o?.get("title") as? JsonPrimitive)?.contentOrNull.orEmpty()
            if (h.isNotBlank() && h != t) "「$h」$t" else t
        }
        val seen = if (read.isNotBlank()) {
            webRead("网页列表(${url ?: "当前网页"}，${shown.size} 条)\n$read", url, title)
        } else null

        return ok {
            put("count", shown.size)
            put("found", found)
            used?.let { put("selector", it) }
            if (used == null) put("autoDetected", true)
            put("items", JsonArray(shown.map { el ->
                val o = el as? JsonObject ?: return@map buildJsonObject { }
                buildJsonObject {
                    (o["title"] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }?.let { put("title", it.take(ITEM_TITLE_MAX)) }
                    put("text", ((o["text"] as? JsonPrimitive)?.contentOrNull.orEmpty()).take(ITEM_TEXT_MAX))
                    (o["link"] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }?.let { put("link", it) }
                }
            }))
            put("truncated", found > shown.size || r.truncated)
            if (shown.isEmpty()) put("hint", Feedback["read_all.empty"])
            else if (used == null) put("hint", Feedback["read_all.auto"])
        }.observing(seen)
    }

    /** 端口回来的是 JSON 文本;对象、或字符串里再套一层 JSON,都接住。 */
    private fun parse(text: String): JsonObject? {
        val el = runCatching { Json.parseToJsonElement(text) }.getOrNull() ?: return null
        return when (el) {
            is JsonObject -> el
            is JsonPrimitive -> (el.contentOrNull?.let { runCatching { Json.parseToJsonElement(it) }.getOrNull() }) as? JsonObject
            else -> null
        }
    }

    private fun listScript(selector: String?, maxItems: Int): String {
        val sel = selector?.let { JsonPrimitive(it).toString() } ?: "null"
        return """
(function(){
  var SEL = $sel;
  var MAX = $maxItems;
  function clean(s){ return (s || '').replace(/\s+/g, ' ').trim(); }
  function abs(h){ try { return new URL(h, location.href).href; } catch (e) { return h; } }
  function text(el){ return clean(el.innerText || el.textContent || ''); }
  function pick(el){
    var a = el.querySelector('a[href]');
    var h = el.querySelector('h1,h2,h3,h4,h5,h6,[role="heading"],.title,.name');
    var t = text(el);
    return {
      title: clean((h && h.textContent) || (a && a.textContent) || '').slice(0, ${ITEM_TITLE_MAX}),
      text: t.slice(0, ${ITEM_TEXT_MAX}),
      link: a ? abs(a.getAttribute('href')) : null
    };
  }
  var nodes = [], used = null;
  if (SEL) {
    nodes = Array.prototype.slice.call(document.querySelectorAll(SEL));
    used = SEL;
  } else {
    var groups = {}, all = document.querySelectorAll('body *');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (!el.parentElement || el.children.length === 0) continue;
      var cls = (el.className && el.className.toString) ? el.className.toString() : '';
      var key = el.parentElement.tagName + '>' + el.tagName + '.' + cls.split(/\s+/).slice(0, 2).join('.');
      (groups[key] = groups[key] || []).push(el);
    }
    var best = null, bestScore = 0;
    for (var k in groups) {
      var arr = groups[k];
      if (arr.length < 3 || arr.length > 500) continue;
      var sum = 0;
      for (var j = 0; j < arr.length; j++) sum += text(arr[j]).length;
      var avg = sum / arr.length;
      if (avg < 8) continue;
      var score = arr.length * Math.min(avg, 400);
      if (score > bestScore) { bestScore = score; best = arr; }
    }
    nodes = best || [];
  }
  return {
    usedSelector: used,
    found: nodes.length,
    items: nodes.slice(0, MAX).map(pick)
  };
})()
""".trimIndent()
    }
}
