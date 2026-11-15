package com.wangzan101.mika.core.cap.web

import com.wangzan101.mika.core.net.UrlHost
import com.wangzan101.mika.core.prompt.Feedback
import com.wangzan101.mika.core.prompt.Prompts
import com.wangzan101.mika.core.tool.Args
import com.wangzan101.mika.core.tool.Risk
import com.wangzan101.mika.core.tool.ToolContext
import com.wangzan101.mika.core.tool.ToolDef
import com.wangzan101.mika.core.tool.ToolExecution
import com.wangzan101.mika.core.tool.Verb
import com.wangzan101.mika.core.tool.fail
import com.wangzan101.mika.core.tool.ok
import com.wangzan101.mika.core.uistate.lastSnapshot
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.put

/**
 * 判断当前网页是不是登录墙,以及下一步该怎么登录。
 *
 * 页面本身很有欺骗性:有的站只在正文里留一句「登录后查看」,有的弹一层遮罩,有的干脆把网址跳到 /login。
 * 这里在读取世界里看三样东西:密码框、登录表单的 action、正文里的登录字样与网址路径;任一条命中就是可疑,
 * 两条以上就判为登录墙。判出来后告诉模型去 `mika_login_site` 让用户自己登录(不自己填账号密码)。
 */
internal object WebAuth : WebTool {
    override val verb = Verb.ReadPage
    override val label = "检查登录"
    override val risk = Risk.Read
    override val def = ToolDef("web_auth", Prompts.tool("web_auth"), emptyMap(), emptyList())

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val r = try {
            ctx.web!!.evaluate(authScript(), READ_SCRIPT_DEFAULT_TIMEOUT_MS.toLong(), null)
        } catch (e: WebTabCrashed) {
            return fail("tab_crashed", "The page closed before it could be checked; open it again with web_navigate.")
        } catch (e: WebTabHandedOver) {
            return fail("handed_over", "This tab is with the user right now; check again after they hand it back.")
        } catch (e: WebDialogOpen) {
            return fail(DIALOG_OPEN, "A page dialog is open; answer it first.")
        }
        if (r is EvalJs.Failed) return fail(r.error, r.message)
        val parsed = parse((r as EvalJs.Ok).json)
            ?: return fail("not_a_page", "The page did not answer the login check; try web_observe first.")
        val host = (parsed["host"] as? JsonPrimitive)?.contentOrNull.orEmpty()
        val signals = (parsed["signals"] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.orEmpty()
        val needsLogin = (parsed["needsLogin"] as? JsonPrimitive)?.contentOrNull == "true"
        val url = ctx.lastSnapshot?.web?.url
        val seen = webRead(
            "网页登录检查(${url ?: "当前网页"})：${if (needsLogin) "需要登录" else "不需要登录"}；信号 ${signals.joinToString(",").ifEmpty { "无" }}",
            url,
        )
        return ok {
            put("needsLogin", needsLogin)
            put("host", host.ifBlank { url?.let { UrlHost.of(it) }.orEmpty() })
            put("signals", JsonArray(signals.map { JsonPrimitive(it) }))
            if (needsLogin) {
                put("hint", Feedback.format("web_auth.needs_login", "host" to host.ifBlank { "this site" }))
                put("nextTool", "mika_login_site")
            }
        }.observing(seen)
    }

    private fun parse(text: String): JsonObject? {
        val el = runCatching { Json.parseToJsonElement(text) }.getOrNull() ?: return null
        return when (el) {
            is JsonObject -> el
            is JsonPrimitive -> (el.contentOrNull?.let { runCatching { Json.parseToJsonElement(it) }.getOrNull() }) as? JsonObject
            else -> null
        }
    }

    private fun authScript(): String = """
(function(){
  var signals = [];
  var hasPassword = !!document.querySelector('input[type=password]');
  if (hasPassword) signals.push('password_field');
  var forms = document.querySelectorAll('form');
  for (var i = 0; i < forms.length; i++) {
    var a = (forms[i].getAttribute('action') || '').toLowerCase();
    if (/login|signin|sign-in|auth|passport/.test(a)) { signals.push('login_form'); break; }
  }
  if (/login|signin|sign-in|passport|auth/.test(location.pathname.toLowerCase())) signals.push('url_path');
  var text = '';
  try { text = (document.body && document.body.innerText || '').slice(0, 6000).toLowerCase(); } catch (e) {}
  var words = ['登录', '登入', 'sign in', 'log in', 'signin', 'login', '扫码登录'];
  for (var j = 0; j < words.length; j++) {
    if (text.indexOf(words[j]) >= 0) { signals.push('text:' + words[j]); break; }
  }
  var needs = false;
  if (signals.indexOf('login_form') >= 0) needs = true;
  else if (hasPassword && signals.length >= 2) needs = true;
  else if (signals.indexOf('url_path') >= 0 && (hasPassword || signals.length >= 2)) needs = true;
  return { host: location.host, path: location.pathname, signals: signals, needsLogin: needs };
})()
""".trimIndent()
}
