package com.wangzan101.mika.core.general

import com.wangzan101.mika.core.tool.AgentTool
import com.wangzan101.mika.core.tool.Args
import com.wangzan101.mika.core.tool.Concurrency
import com.wangzan101.mika.core.tool.Risk
import com.wangzan101.mika.core.tool.ToolContext
import com.wangzan101.mika.core.tool.ToolDef
import com.wangzan101.mika.core.tool.ToolExecution
import com.wangzan101.mika.core.tool.Verb
import com.wangzan101.mika.core.tool.fail
import com.wangzan101.mika.core.tool.str
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * 打开内置知识/技能里的一张图:主模型能看图就把图发过去,不能看就退回同名的文字描述。
 *
 * 内置技能与 App/网站知识的文件打包在 APK 里(`skills/<名字>/...`、`knowledge/...`),
 * 运行时用 ClassLoader 读,不依赖沙箱,也不受手机目录权限影响。图片旁若放着同名 `.md`
 * (如 `foo.jpg` 配 `foo.md`),那份文字就是这张图的说明,给不能看图的模型用。
 */
internal object ViewImage : AgentTool {
    override val verb = Verb.ReadFile
    override val label = "打开图片"
    override val risk = Risk.Read
    override val concurrency = Concurrency.ParallelSafe
    override val def = ToolDef(
        "view_image",
        "打开内置技能或知识里的一张图(路径形如 skills/<技能名>/references/img/xxx.jpg 或 knowledge/apps/<id>/...)。" +
            "主模型能看图时直接返回图片本身;不能看时返回同目录下同名 .md 的文字描述。",
        mapOf("path" to str("Relative bundled path of the image, e.g. skills/jinbiao-fengshui/references/img/jinbiao-001.jpg.")),
        listOf("path"),
    )

    private const val MAX_BYTES = 4 * 1024 * 1024

    override fun available(ctx: ToolContext) = ctx.config.skills != null

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val raw = a.str("path", max = 300)!!.trim()
        val path = raw.removePrefix("/")
        if (!(path.startsWith("skills/") || path.startsWith("knowledge/"))) {
            return fail("path_not_allowed", "Only bundled files under skills/ or knowledge/ can be opened, not: $raw")
        }
        if (path.split('/').any { it.isEmpty() || it == ".." }) {
            return fail("path_not_allowed", "Path must not contain empty or '..' segments: $raw")
        }
        val bytes = BundledFiles.read(path) ?: return fail("not_found", "No bundled file at $path")
        val mime = BundledFiles.imageMime(bytes)
        if (mime == null) return fail("not_image", "$path is not a JPEG/PNG/WEBP/GIF image")
        if (bytes.size > MAX_BYTES) return fail("too_large", "Image is ${bytes.size / 1024} KB; the limit is ${MAX_BYTES / 1024} KB")
        val desc = BundledFiles.read(BundledFiles.sidecar(path))?.toString(Charsets.UTF_8)?.trim()?.takeIf { it.isNotEmpty() }

        // 1) 主模型自己能看图:把图直接发过去,再附上已有说明。
        if (ctx.config.visionEnabled) {
            return ToolExecution(buildJsonObject {
                put("ok", true); put("path", path); put("bytes", bytes.size); put("mime", mime); put("vision", true)
                desc?.let { put("description", it) }
                put("hint", "The image itself is attached; read the drawing and any text in it directly.")
            }, image = bytes)
        }
        // 2) 主模型不能看图、但配了看图模型:让看图模型先读一遍,把读到的文字带回来。
        val vision = ctx.config.pictureVision ?: ctx.config.vision
        if (vision != null) {
            val read = runCatching {
                vision.ask(VISION_SYSTEM, "把这张图看清楚:说明画面内容(地形、建筑、罗盘、人物、器物等)," +
                    "照抄图中所有可辨认的文字与数字,并指出它想说明的要点。用中文,分条写,不要评论。", listOf(bytes))
            }
            read.getOrNull()?.let { text ->
                return ToolExecution(buildJsonObject {
                    put("ok", true); put("path", path); put("bytes", bytes.size); put("mime", mime); put("vision", false)
                    put("read_by", "vision_model"); put("read", text)
                    desc?.let { put("description", it) }
                    put("hint", "This model cannot see images; the text above was read from the picture by the configured vision model.")
                })
            }
            read.exceptionOrNull()?.let { e ->
                val why = if (e is com.wangzan101.mika.core.model.ModelError) e.message ?: "视觉模型调用失败" else "视觉模型调用失败"
                return ToolExecution(buildJsonObject {
                    put("ok", true); put("path", path); put("bytes", bytes.size); put("vision", false)
                    put("vision_error", why)
                    desc?.let { put("description", it) }
                    put("hint", "Vision model call failed; only the file path (and any sidecar text) is known.")
                })
            }
        }
        // 3) 没有看图能力:退回图片旁的文字说明。
        return ToolExecution(buildJsonObject {
            put("ok", true); put("path", path); put("bytes", bytes.size); put("vision", false)
            desc?.let { put("description", it) }
            put("hint", if (desc != null)
                "Neither the main model nor a vision model can see images here; the text description next to the image is given instead."
            else "No vision available and no text description next to this image; tell the user it exists but cannot be read here.")
        })
    }

    private const val VISION_SYSTEM = "你是把图片读成文字的眼睛。只描述你真正看见的内容,看不清的地方直说看不清。"
}

/** 读打包资源的最小实现:与内置目录(GuideCatalog)用同一个 ClassLoader。 */
internal object BundledFiles {
    fun read(path: String): ByteArray? =
        runCatching { BundledFiles::class.java.classLoader?.getResourceAsStream(path)?.use { it.readBytes() } }.getOrNull()

    /** 同名 `.md` 的文字说明;路径没有扩展名时原样加 `.md`。 */
    fun sidecar(path: String): String {
        val dot = path.lastIndexOf('.')
        val slash = path.lastIndexOf('/')
        return if (dot > slash) path.substring(0, dot) + ".md" else "$path.md"
    }

    fun imageMime(b: ByteArray): String? = when {
        b.size >= 3 && b[0] == 0xFF.toByte() && b[1] == 0xD8.toByte() && b[2] == 0xFF.toByte() -> "image/jpeg"
        b.size >= 8 && b[0] == 0x89.toByte() && b[1] == 'P'.code.toByte() && b[2] == 'N'.code.toByte() -> "image/png"
        b.size >= 12 && String(b, 0, 4, Charsets.ISO_8859_1) == "RIFF" && String(b, 8, 4, Charsets.ISO_8859_1) == "WEBP" -> "image/webp"
        b.size >= 4 && String(b, 0, 4, Charsets.ISO_8859_1) == "GIF8" -> "image/gif"
        else -> null
    }
}
