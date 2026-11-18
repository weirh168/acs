package com.wangzan101.mika.core

import com.wangzan101.mika.core.uistate.RiskyActions
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** 危险动作识别:命中就要用户确认,普通点击不能误报。 */
class RiskyActionsTest {

    @Test fun moneyActionsAreRisky() {
        assertEquals("付款", RiskyActions.hits("付款"))
        assertEquals("提交订单", RiskyActions.hits("提交订单"))
        assertEquals("转账", RiskyActions.hits("确认转账"))
    }

    @Test fun outboundAndDestructiveAreRisky() {
        assertEquals("发送", RiskyActions.hits("发送给 张三"))
        assertEquals("删除", RiskyActions.hits("删除这条记录"))
        assertEquals("注销", RiskyActions.hits("注销账号"))
    }

    @Test fun socialActionsAlsoAsk() {
        assertEquals("关注", RiskyActions.hits("关注"))
        assertEquals("点赞", RiskyActions.hits("点赞"))
    }

    @Test fun ordinaryClicksAreNotRisky() {
        assertNull(RiskyActions.hits("微信"))
        assertNull(RiskyActions.hits("搜索"))
        assertNull(RiskyActions.hits("下一页"))
        assertNull(RiskyActions.hits(null))
        assertNull(RiskyActions.hits(""))
    }

    @Test fun messageTellsTheModelToAsk() {
        val m = RiskyActions.askUser("付款")
        org.junit.Assert.assertTrue(m.contains("付款"))
        org.junit.Assert.assertTrue(m.contains("confirmed"))
    }
}