package com.wangzan101.mika.core.cap.phone

import com.wangzan101.mika.core.cap.phone.PhoneReadiness.Unavailable
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** 手机操作不可用时，提示要按"离能用差多远"分档：能一键继续的，就直接指开关。 */
class PhoneReadinessTest {

    @Test fun helperConnectedNeedsNoComplaint() {
        assertNull(PhoneReadiness.unavailable(helperConnected = true, degradedApproved = false, accessibilityOn = false))
        assertNull(PhoneReadiness.unavailable(helperConnected = true, degradedApproved = true, accessibilityOn = true))
    }

    @Test fun missingHelperWithAccessibilityAndNoApprovalPointsAtTheSwitch() {
        assertEquals(
            Unavailable.HelperMissingCanDegrade,
            PhoneReadiness.unavailable(helperConnected = false, degradedApproved = false, accessibilityOn = true),
        )
    }

    @Test fun missingHelperWithoutAccessibilityFallsBackToSetup() {
        assertEquals(
            Unavailable.HelperMissing,
            PhoneReadiness.unavailable(helperConnected = false, degradedApproved = false, accessibilityOn = false),
        )
    }

    @Test fun missingHelperWithApprovalWouldHaveDegradedAlready() {
        // 开关开着时 degradedOrNull() 已经接管了，走不到这条提示；真走到就说明无障碍也没了
        assertEquals(
            Unavailable.HelperMissing,
            PhoneReadiness.unavailable(helperConnected = false, degradedApproved = true, accessibilityOn = true),
        )
    }
}
