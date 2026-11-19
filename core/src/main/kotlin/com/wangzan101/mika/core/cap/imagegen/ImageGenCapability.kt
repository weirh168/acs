package com.wangzan101.mika.core.cap.imagegen

import com.wangzan101.mika.core.capability.Capability
import com.wangzan101.mika.core.capability.CapabilityKey
import com.wangzan101.mika.core.capability.CapabilityStatus
import com.wangzan101.mika.core.capability.PromptEnv
import com.wangzan101.mika.core.tool.AgentTool
import com.wangzan101.mika.core.tool.Args
import com.wangzan101.mika.core.tool.Risk
import com.wangzan101.mika.core.tool.ToolContext
import com.wangzan101.mika.core.tool.ToolDef
import com.wangzan101.mika.core.tool.ToolExecution
import com.wangzan101.mika.core.tool.Verb
import com.wangzan101.mika.core.tool.fail
import com.wangzan101.mika.core.tool.str
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

const val IMAGE_GEN = "image_gen"

/** 画好的图:[message] 给人看的一句话,[bytes] 用来在对话里直接显示这张图(为空时只报文字)。 */
class ImageGenResult(val message: String, val bytes: ByteArray?)

/**
 * 生图：用户说「画一只猫」时用。真正的网络调用和存盘在 app 侧（app 才拿得到 Key 和相册），
 * 这里只把描述转过去，拿回一句结果（保存路径）。
 */
internal class ImageGenCapability(
    private val generate: (suspend (prompt: String) -> ImageGenResult)?,
) : Capability {
    override val id = IMAGE_GEN

    override fun status(): CapabilityStatus =
        if (generate == null) CapabilityStatus.Unavailable("no image model") else CapabilityStatus.Available

    override fun tools(): List<AgentTool> = if (generate == null) emptyList() else listOf(AcsDraw(generate))

    override fun sections(env: PromptEnv): List<String> = listOf(DRAW_SECTION)

    companion object {
        val KEY = CapabilityKey<ImageGenCapability>(IMAGE_GEN)

        /** 给模型看的说明：直接调工具，不要把调用写成标签。 */
        private const val DRAW_SECTION = "## 画图\n" +
            "用户要画图、生成图片、做配图时，必须真正调用工具 acs_draw（走工具调用通道），参数 prompt 传用户的原话。\n" +
            "严禁把调用写进回答正文：回答里出现尖括号、acs_draw 字样或任何标签，都算这次任务失败，什么都没有画。\n" +
            "也不要解释自己没有画图能力、不要建议用户去找别的工具。\n" +
            "工具会返回保存路径，把它告诉用户。"
    }
}

/** 画图工具；app 侧注入的实现拿描述去生图并存盘。 */
internal class AcsDraw(private val generate: suspend (prompt: String) -> ImageGenResult) : AgentTool {
    override val name = "acs_draw"
    override val verb = Verb.WriteFile
    override val label = "画图"
    override val risk = Risk.Read
    override val offScreen = true

    override val def = ToolDef(
        name,
        "画一张图并存到手机相册。用户说画图、画一张、生成图片、做个配图时必须调用它；这是唯一能出图的途径，不要用文字或标签代替调用。",
        mapOf("prompt" to str("要画什么，用用户的原话，别自己加内容性的东西。")),
        listOf("prompt"),
    )

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val prompt = a.str("prompt", max = 500)?.trim().orEmpty()
        if (prompt.isEmpty()) return fail("missing_prompt", "prompt 不能为空")
        val result = try {
            generate(prompt)
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) {
            return fail("draw_failed", e.message ?: "生图失败")
        }
        // 带上图片字节:对话里能把这张图直接显示出来
        return ToolExecution(buildJsonObject {
            put("ok", true)
            put("result", result.message)
        }, image = result.bytes)
    }
}

/** 这次任务有生图能力时，工具里这样拿到它。 */
internal val ToolContext.imageGen: ImageGenCapability? get() = this[ImageGenCapability.KEY]

const val VIDEO_GEN = "video_gen"

/** 生视频:和生图同一套注入方式;平台没放行时由实现返回一句人话。 */
internal class VideoGenCapability(
    private val make: (suspend (prompt: String) -> ImageGenResult)?,
) : Capability {
    override val id = VIDEO_GEN

    override fun status(): CapabilityStatus =
        if (make == null) CapabilityStatus.Unavailable("no video model") else CapabilityStatus.Available

    override fun tools(): List<AgentTool> = if (make == null) emptyList() else listOf(AcsVideo(make))

    override fun sections(env: PromptEnv): List<String> = listOf(VIDEO_SECTION)

    companion object {
        val KEY = CapabilityKey<VideoGenCapability>(VIDEO_GEN)

        private const val VIDEO_SECTION = "## 做视频\n" +
            "用户要做视频、生成一段视频时，必须真正调用工具 acs_video，参数 prompt 传用户的原话。\n" +
            "不要把调用写进回答正文（出现尖括号或标签算失败）。\n" +
            "工具会说 AGNES 没放行，并给出走 App 的做法。这时直接照做，按这个固定流程，不要摸索:\n" +
            "1) 打开即梦(Dreamina)；没登录就交给用户登录，别自己乱点。\n" +
            "2) 点底部中间的「+」进入创作，选「视频」或「AI 视频」。\n" +
            "3) 把用户的描述填进输入框，原话照抄，不要自己加设定。\n" +
            "4) 点「生成」，然后等它出片（可以每隔几秒看一眼进度）。\n" +
            "5) 出片后在「我的」或「作品」里找到这条视频，告诉用户在哪、能不能播。\n" +
            "即梦装不了或不好用时，再试剪映的「图文成片」。"
    }
}

internal class AcsVideo(private val make: suspend (prompt: String) -> ImageGenResult) : AgentTool {
    override val name = "acs_video"
    override val verb = Verb.WriteFile
    override val label = "做视频"
    override val risk = Risk.Read
    override val offScreen = true

    override val def = ToolDef(
        name,
        "生成一段视频并存到手机相册。用户要做视频、生成一小段动画时调用它。",
        mapOf("prompt" to str("要做什么视频,用用户的原话。")),
        listOf("prompt"),
    )

    override suspend fun execute(a: Args, ctx: ToolContext): ToolExecution {
        val prompt = a.str("prompt", max = 500)?.trim().orEmpty()
        if (prompt.isEmpty()) return fail("missing_prompt", "prompt 不能为空")
        val result = try {
            make(prompt)
        } catch (e: kotlinx.coroutines.CancellationException) {
            throw e
        } catch (e: Exception) {
            return fail("video_failed", e.message ?: "生视频失败")
        }
        return ToolExecution(buildJsonObject {
            put("ok", true)
            put("result", result.message)
        })
    }
}