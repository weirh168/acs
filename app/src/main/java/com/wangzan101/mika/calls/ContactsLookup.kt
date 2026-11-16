package com.wangzan101.mika.calls

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import android.util.Log

/**
 * 「这个号码在不在通讯录里」,给自动接听规则用(通讯录内本人接、通讯录外交给 AI)。
 * 只查一个号码的 PhoneLookup,读通讯录的权限没给就返回 false 并记一行日志——不因为查不到就改判。
 */
internal object ContactsLookup {
    private const val TAG = "MikaContacts"

    fun allowed(context: Context): Boolean =
        context.checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED

    fun inContacts(context: Context, number: String?): Boolean {
        val value = number?.takeIf { it.isNotBlank() } ?: return false
        if (!allowed(context)) {
            Log.i(TAG, "no READ_CONTACTS permission; treating every caller as not in contacts")
            return false
        }
        return runCatching {
            context.contentResolver.query(
                Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(value)),
                arrayOf(ContactsContract.PhoneLookup._ID),
                null,
                null,
                null,
            )?.use { it.count > 0 } ?: false
        }.onFailure { Log.w(TAG, "cannot look up the caller in contacts", it) }.getOrDefault(false)
    }
}
