package com.wangzan101.mika.calls

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.speech.tts.TextToSpeech
import android.telecom.TelecomManager
import android.telephony.PhoneStateListener
import android.telephony.TelephonyManager
import com.wangzan101.mika.MikaApp
import com.wangzan101.mika.R
import com.wangzan101.mika.voice.Transcriber
import kotlinx.coroutines.*
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.MediaType.Companion.toMediaType
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 免提代接:不依赖「通话伴侣」权限的做法。
 *
 * 系统中只有默认电话应用能拿 MANAGE_ONGOING_CALLS(荣耀锁死),所以改走三条都公开的能力:
 *   1) READ_PHONE_STATE 监听响铃
 *   2) ANSWER_PHONE_CALLS 自动接起(TelecomManager.acceptRingingCall)
 *   3) 免提 + 麦克风录音,通话结束后把录音转成文字(硅基流动 SenseVoice)
 *
 * 音质不如系统通话音频:对方声音靠扬声器外放、再由本机麦克风拾取,适合安静环境。
 */
class AcousticAnswerService : Service() {

    private fun log(msg: String) {
        android.util.Log.i("AcousticAnswer", msg)
        runCatching {
            File(filesDir, "acoustic.log").appendText(
                java.text.SimpleDateFormat("MM-dd HH:mm:ss", Locale.US).format(Date()) + " " + msg + "\n"
            )
        }
    }

    private var telephony: TelephonyManager? = null
    private var listener: PhoneStateListener? = null
    private var tts: TextToSpeech? = null
    private var record: AudioRecord? = null
    private var recordJob: Job? = null
    private var answerJob: Job? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var pendingFile: File? = null
    private var lastState = TelephonyManager.CALL_STATE_IDLE

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        runCatching { File(filesDir, "acoustic.log").appendText("onCreate\n") }
        // 普通 App 拿不到 phoneCall 类型的前台服务,用 specialUse 即可(只监听响铃)
        prefetchGreeting()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFY_ID, notification("AI 免提代接已开启"),
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFY_ID, notification("AI 免提代接已开启"))
        }
        log("service created")
        tts = TextToSpeech(this) { }
        listen()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        runCatching { unregisterReceiver(phoneReceiver) }
        stopRecording()
        @Suppress("DEPRECATION")
        listener?.let { telephony?.listen(it, PhoneStateListener.LISTEN_NONE) }
        tts?.shutdown()
        scope.cancel()
        super.onDestroy()
    }

    private val phoneReceiver = object : android.content.BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val state = intent?.getStringExtra(TelephonyManager.EXTRA_STATE)
            log("broadcast -> " + state)
            when (state) {
                TelephonyManager.EXTRA_STATE_RINGING -> handleState(TelephonyManager.CALL_STATE_RINGING)
                TelephonyManager.EXTRA_STATE_OFFHOOK -> handleState(TelephonyManager.CALL_STATE_OFFHOOK)
                TelephonyManager.EXTRA_STATE_IDLE -> handleState(TelephonyManager.CALL_STATE_IDLE)
            }
        }
    }

    private fun listen() {
        runCatching {
            registerReceiver(phoneReceiver, android.content.IntentFilter(TelephonyManager.ACTION_PHONE_STATE_CHANGED))
            log("receiver registered")
        }.onFailure { log("receiver failed: " + it) }
        val tm = getSystemService(TelephonyManager::class.java) ?: return
        telephony = tm
        if (Build.VERSION.SDK_INT >= 31) {
            val callback = object : android.telephony.TelephonyCallback(),
                android.telephony.TelephonyCallback.CallStateListener {
                override fun onCallStateChanged(state: Int) = handleState(state)
            }
            tm.registerTelephonyCallback(mainExecutor, callback)
        } else {
            @Suppress("DEPRECATION")
            val pl = object : PhoneStateListener() {
                @Deprecated("Deprecated in Java")
                override fun onCallStateChanged(state: Int, phoneNumber: String?) = handleState(state)
            }
            listener = pl
            @Suppress("DEPRECATION")
            tm.listen(pl, PhoneStateListener.LISTEN_CALL_STATE)
        }
    }

    private fun handleState(state: Int) {
        log("call state -> " + state + " (last " + lastState + ")")
        when {
            state == TelephonyManager.CALL_STATE_RINGING && lastState != TelephonyManager.CALL_STATE_RINGING -> {
                answerJob = scope.launch {
                    delay(AcousticAnswer.answerDelayMs(this@AcousticAnswerService).toLong())
                    answer()
                }
            }
            state == TelephonyManager.CALL_STATE_OFFHOOK -> {
                answerJob?.cancel()
                speaker(true)
                startRecording()
                speakGreeting()
            }
            state == TelephonyManager.CALL_STATE_IDLE && lastState != TelephonyManager.CALL_STATE_IDLE -> {
                stopRecording()
                speaker(false)
                lastTranscript()?.let { notify("AI 代接完成", it) }
            }
        }
        lastState = state
    }

    /** 系统没有 TTS 引擎,改用硅基流动的语音合成生成开场白,再用 MediaPlayer 放出去。 */
    private fun speakGreeting() {
        scope.launch {
            val cached = File(cacheDir, "greeting.mp3").takeIf { it.length() > 1000 }
            val file = cached ?: runCatching {
                val app = applicationContext as MikaApp
                val provider = app.providers.providers.value.firstOrNull { it.name.contains("硅基") }
                    ?: return@runCatching null
                val key = app.providers.providerKey(provider.id) ?: return@runCatching null
                val body = kotlinx.serialization.json.buildJsonObject {
                    put("model", kotlinx.serialization.json.JsonPrimitive("FunAudioLLM/CosyVoice2-0.5B"))
                    put("input", kotlinx.serialization.json.JsonPrimitive(AcousticAnswer.greeting(this@AcousticAnswerService)))
                    put("voice", kotlinx.serialization.json.JsonPrimitive("FunAudioLLM/CosyVoice2-0.5B:alex"))
                    put("response_format", kotlinx.serialization.json.JsonPrimitive("mp3"))
                }.toString()
                val request = okhttp3.Request.Builder()
                    .url(provider.baseUrl.trimEnd('/') + "/audio/speech")
                    .addHeader("Authorization", "Bearer " + key)
                    .post(body.toRequestBody("application/json".toMediaType()))
                    .build()
                val response = okhttp3.OkHttpClient().newCall(request).execute()
                if (!response.isSuccessful) {
                    log("tts http " + response.code)
                    return@runCatching null
                }
                val bytes = response.body?.bytes() ?: return@runCatching null
                val f = File(cacheDir, "greeting.mp3")
                f.writeBytes(bytes)
                f
            }.getOrNull()
            if (file == null) {
                log("greeting audio unavailable")
                return@launch
            }
            log("greeting audio ready " + file.length())
            withContext(Dispatchers.Main) {
                runCatching {
                    // 通话中要让对方听见:走通话音频流,并把扬声器与音量拉满
                    val am = getSystemService(AudioManager::class.java)
                    runCatching {
                        am?.mode = AudioManager.MODE_IN_CALL
                        am?.isSpeakerphoneOn = true
                        val max = am?.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL) ?: 0
                        am?.setStreamVolume(AudioManager.STREAM_VOICE_CALL, max, 0)
                        val maxMusic = am?.getStreamMaxVolume(AudioManager.STREAM_MUSIC) ?: 0
                        am?.setStreamVolume(AudioManager.STREAM_MUSIC, maxMusic, 0)
                    }
                    val player = android.media.MediaPlayer()
                    player.setAudioAttributes(
                        android.media.AudioAttributes.Builder()
                            .setUsage(android.media.AudioAttributes.USAGE_VOICE_COMMUNICATION)
                            .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH)
                            .setLegacyStreamType(AudioManager.STREAM_VOICE_CALL)
                            .build(),
                    )
                    player.setDataSource(file.absolutePath)
                    player.prepare()
                    player.start()
                    player.setOnCompletionListener { player.release() }
                    log("greeting played")
                }.onFailure { log("greeting play failed: " + it) }
            }
        }
    }

    /** 提前把开场白下好,通话接通时直接播,不给对方干等。 */
    private fun prefetchGreeting() {
        scope.launch {
            val target = File(cacheDir, "greeting.mp3")
            if (target.length() > 1000) return@launch
            runCatching {
                val app = applicationContext as MikaApp
                val provider = app.providers.providers.value.firstOrNull { it.name.contains("硅基") }
                    ?: return@launch
                val key = app.providers.providerKey(provider.id) ?: return@launch
                val body = kotlinx.serialization.json.buildJsonObject {
                    put("model", kotlinx.serialization.json.JsonPrimitive("FunAudioLLM/CosyVoice2-0.5B"))
                    put("input", kotlinx.serialization.json.JsonPrimitive(AcousticAnswer.greeting(this@AcousticAnswerService)))
                    put("voice", kotlinx.serialization.json.JsonPrimitive("FunAudioLLM/CosyVoice2-0.5B:alex"))
                    put("response_format", kotlinx.serialization.json.JsonPrimitive("mp3"))
                }.toString()
                val request = okhttp3.Request.Builder()
                    .url(provider.baseUrl.trimEnd('/') + "/audio/speech")
                    .addHeader("Authorization", "Bearer " + key)
                    .post(body.toRequestBody("application/json".toMediaType()))
                    .build()
                val response = okhttp3.OkHttpClient().newCall(request).execute()
                if (response.isSuccessful) {
                    response.body?.bytes()?.let { target.writeBytes(it); log("greeting prefetched " + it.size) }
                } else log("prefetch http " + response.code)
            }.onFailure { log("prefetch failed: " + it) }
        }
    }

    private fun answer() {
        if (checkSelfPermission(Manifest.permission.ANSWER_PHONE_CALLS) != PackageManager.PERMISSION_GRANTED) {
            notify("AI 未能接起", "缺少「接听电话」权限,请在系统设置里允许")
            return
        }
        val telecom = getSystemService(TelecomManager::class.java)
        val result = runCatching { telecom?.acceptRingingCall() }
        log("acceptRingingCall -> " + result.toString())
        result.onFailure { notify("AI 未能接起", it.message ?: "接听失败") }
    }

    private fun speaker(on: Boolean) {
        runCatching {
            val am = getSystemService(AudioManager::class.java) ?: return
            am.isSpeakerphoneOn = on
        }
    }

    private fun startRecording() {
        if (record != null) return
        runCatching {
            val dir = File(filesDir, "acoustic").apply { mkdirs() }
            val name = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date()) + ".wav"
            val file = File(dir, name)
            pendingFile = file
            val rate = 16000
            val min = AudioRecord.getMinBufferSize(rate, android.media.AudioFormat.CHANNEL_IN_MONO,
                android.media.AudioFormat.ENCODING_PCM_16BIT)
            val rec = AudioRecord(MediaRecorder.AudioSource.MIC, rate,
                android.media.AudioFormat.CHANNEL_IN_MONO, android.media.AudioFormat.ENCODING_PCM_16BIT,
                maxOf(min, rate))
            rec.startRecording()
            record = rec
            recordJob = scope.launch {
                val pcm = java.io.ByteArrayOutputStream()
                val buf = ByteArray(4096)
                while (isActive) {
                    val n = rec.read(buf, 0, buf.size)
                    if (n > 0) pcm.write(buf, 0, n)
                }
                writeWav(file, pcm.toByteArray(), rate)
            }
        }
    }

    private fun stopRecording() {
        val rec = record ?: return
        record = null
        runCatching { rec.stop(); rec.release() }
        recordJob?.cancel()
        recordJob = null
    }

    private fun writeWav(file: File, pcm: ByteArray, rate: Int) = runCatching {
        FileOutputStream(file).use { out ->
            val len = pcm.size
            val header = java.nio.ByteBuffer.allocate(44).order(java.nio.ByteOrder.LITTLE_ENDIAN)
            header.put("RIFF".toByteArray()); header.putInt(36 + len); header.put("WAVE".toByteArray())
            header.put("fmt ".toByteArray()); header.putInt(16); header.putShort(1); header.putShort(1)
            header.putInt(rate); header.putInt(rate * 2); header.putShort(2); header.putShort(16)
            header.put("data".toByteArray()); header.putInt(len)
            out.write(header.array())
            out.write(pcm)
        }
        transcribeAsync(file)
    }

    /** 通话结束后把录音转成文字,结果写进最新一条通话摘要。 */
    private fun transcribeAsync(file: File) {
        scope.launch {
            val text = runCatching {
                val app = applicationContext as MikaApp
                val wav = file.readBytes()
                val choice = app.speech.choice.value
                val spec = com.wangzan101.mika.voice.SpeechResolver.resolve(
                    choice,
                    com.wangzan101.mika.voice.SystemSpeech.capability(this@AcousticAnswerService, app.speech.systemSilent.value),
                    app.providers.providers.value,
                )
                if (spec !is com.wangzan101.mika.voice.SpeechEngineSpec.Provider) return@runCatching null
                Transcriber(okhttp3.OkHttpClient()).transcribe(
                    spec.provider, app.providers.providerKey(spec.provider.id), spec.model, spec.method, wav, "zh",
                )
            }.getOrNull()
            if (!text.isNullOrBlank()) {
                lastText = text
                File(file.parentFile, file.nameWithoutExtension + ".txt").writeText(text)
                notify("AI 代接:对方说了什么", text.take(120))
            }
        }
    }

    private fun lastTranscript(): String? = lastText ?: runCatching {
        val dir = File(filesDir, "acoustic")
        dir.listFiles { f -> f.name.endsWith(".txt") }?.maxByOrNull { it.lastModified() }?.readText()
    }.getOrNull()

    private fun notification(text: String): Notification {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "AI 免提代接", NotificationManager.IMPORTANCE_LOW),
        )
        return Notification.Builder(this, CHANNEL)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setSmallIcon(android.R.drawable.sym_action_call)
            .setOngoing(true)
            .build()
    }

    private fun notify(title: String, text: String) {
        runCatching {
            val manager = getSystemService(NotificationManager::class.java) ?: return
            manager.notify((System.currentTimeMillis() % 10000).toInt(),
                Notification.Builder(this, CHANNEL)
                    .setContentTitle(title).setContentText(text)
                    .setSmallIcon(android.R.drawable.sym_action_call)
                    .setStyle(Notification.BigTextStyle().bigText(text))
                    .build())
        }
    }

    companion object {
        private const val CHANNEL = "mika_acoustic_answer"
        private const val NOTIFY_ID = 4201
        private var lastText: String? = null

        fun start(context: Context) {
            runCatching {
                context.startForegroundService(Intent(context, AcousticAnswerService::class.java))
            }
        }

        fun stop(context: Context) {
            runCatching { context.stopService(Intent(context, AcousticAnswerService::class.java)) }
        }
    }
}

/** 免提代接的开关与偏好(存在独立的一小份设置里,不动通话主配置)。 */
object AcousticAnswer {
    private const val PREFS = "mika_acoustic"
    private const val ON = "enabled"
    private const val DELAY = "delay_seconds"

    fun enabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(ON, false)

    fun setEnabled(context: Context, on: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(ON, on).apply()
        if (on) AcousticAnswerService.start(context) else AcousticAnswerService.stop(context)
    }

    fun answerDelayMs(context: Context): Int =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getInt(DELAY, 3) * 1000

    fun greeting(context: Context): String =
        "您好,我是 ACS 电话助手。机主现在不方便接听,请直接说出您的姓名和事情,我会转告。"

    /** 能不能用:需要负责接听和读状态的权限。 */
    fun available(context: Context): Boolean =
        context.checkSelfPermission(android.Manifest.permission.ANSWER_PHONE_CALLS) == PackageManager.PERMISSION_GRANTED &&
            context.checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED
}