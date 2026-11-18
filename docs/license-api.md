# 会员系统 A 方案接口契约（服务器 + 短信 + 支付）

> 当前已上线的是 **B 方案（本地激活码）**，见 `settings/License.kt` 与 `tools/make-license.ps1`。
> 这份文档是 A 方案的对接约定，等服务器就绪后按此实现。

## 1. 为什么必须有服务端

| 需求 | 只靠 App 为什么做不到 |
|---|---|
| 手机号 + 短信验证码登录 | 需要短信服务商下发，App 内不能自己发 |
| 15 天免费判定 | 本地时间可改、本地存储可清，必须服务端记录注册时间 |
| 10 元/30 元订阅 | 支付回调必须服务端验签，否则可伪造 |
| 管理员调价 | 价格要在服务端下发，不能烧进 APK |
| 一码一设备 | B 方案靠指纹，换机重装仍可复用；服务端可做强绑定 |

## 2. 通用约定

- Base URL：`https://<your-domain>/api/v1`
- 编码：`application/json; charset=utf-8`
- 鉴权：登录后返回 `token`，后续请求带 `Authorization: Bearer <token>`
- 时间：全部用 **毫秒时间戳**（UTC）
- 错误统一返回：

```json
{ "code": "PHONE_NOT_VERIFIED", "message": "手机号未验证" }
```

## 3. 登录（手机号 + 短信）

### 3.1 发送验证码

`POST /auth/sms`

```json
{ "phone": "13800138000", "scene": "login" }
```

返回：

```json
{ "ok": true, "retryAfterSec": 60 }
```

服务端要求：同一手机号 60 秒内只能发一次、单日上限 10 条、图形验证码防刷。

### 3.2 校验并登录

`POST /auth/login`

```json
{ "phone": "13800138000", "code": "123456", "deviceId": "BE1CF3", "deviceName": "FNE-AN00" }
```

返回：

```json
{
  "token": "eyJhb...",
  "expiresAtMs": 1790000000000,
  "account": {
    "id": "u_1024",
    "phone": "138****8000",
    "trialEndsAtMs": 1789000000000,
    "plan": "TRIAL",
    "planExpiresAtMs": 1789000000000,
    "canPickModel": false,
    "allowedModels": ["agnes"]
  }
}
```

`plan` 取值：`NONE` / `TRIAL` / `MONTHLY` / `PRO`。

首次登录自动进入 15 天试用，`trialEndsAtMs = now + 15d`。

## 4. 权益校验（App 启动与每次发消息前）

`GET /entitlement`

返回同 `account` 结构。App 缓存在内存 + 本地，**离线时最多允许 24 小时**，之后必须联网校验。

## 5. 下单与支付

### 5.1 创建订单

`POST /orders`

```json
{ "plan": "PRO", "channel": "wechat" }
```

返回：

```json
{
  "orderId": "o_20261118001",
  "amountCents": 3000,
  "channel": "wechat",
  "payParams": { "prepay_id": "wx20171...", "nonceStr": "...", "sign": "..." }
  "expiresAtMs": 1790000000000
}
```

### 5.2 支付回调（服务端对服务端）

`POST /pay/notify/wechat` — 微信回调，服务端验签后：

1. 校验订单金额与 `amountCents` 一致
2. 幂等处理（同一 `orderId` 只处理一次）
3. 延长 `planExpiresAtMs`：`max(now, 原到期) + 30d`
4. 写账本，返回微信要求的成功应答

App 侧用 `GET /orders/{orderId}` 轮询或长连接拿结果，**不信任客户端回调**。

## 6. 管理员接口

需要管理员账号（`role=admin`）。

### 6.1 调价

`PUT /admin/pricing`

```json
{ "MONTHLY": 1000, "PRO": 3000, "trialDays": 15 }
```

金额单位：**分**。App 从 `GET /pricing` 拉取展示文案，不再写死。

### 6.2 手动开通 / 续期

`POST /admin/grant`

```json
{ "phone": "13800138000", "plan": "PRO", "days": 30, "note": "线下收款" }
```

### 6.3 订单与收入查询

`GET /admin/orders?from=&to=&status=`

## 7. 设备绑定

登录时上报 `deviceId`（App 侧即 `LicenseCode.deviceFingerprint()` 的 6 位值）。

- 同一账号默认允许 1 台在线设备；换机时旧设备被挤出
- 服务端记录 `deviceId -> accountId`，可随时解绑

## 8. App 侧需要改造的点

| 位置 | 改造 |
|---|---|
| `Membership.kt` | 增加「手机号登录」流程，激活码保留为离线兜底 |
| `LicenseStore` | 权益改为「服务端为准 + 本地缓存」，缓存带 24 小时有效期 |
| `ModelsScreen.kt` | 门控改读服务端 `canPickModel`，`allowedModels` 控制可选列表 |
| 定价文案 | 从 `GET /pricing` 拉取 |
| 隐私说明 | 必须改写：会收集手机号、有服务器、有支付 |

## 9. 与 B 方案的兼容

激活码继续可用：

- 服务端账号存在 → 以服务端权益为准
- 无账号但有本地激活码 → 用激活码权益（B 方案）
- 两者都没有 → 只能走 15 天试用（本地记录，可被清除，属于 B 方案已知弱点）

