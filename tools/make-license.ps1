# 生成 ACS 激活码(管理员用)。和 App 里的 LicenseCode 保持一致。
#
# 用法:
#   .\make-license.ps1 -Plan T -Days 15 -Device <用户发来的6位设备码>
#   .\make-license.ps1 -Plan M -Days 30 -Device 7A3F21
#   .\make-license.ps1 -Plan P -Days 30 -Device 7A3F21 -Count 5
param(
    [ValidateSet("T","M","P")] [string]$Plan = "T",
    [int]$Days = 15,
    [Parameter(Mandatory=$true)] [string]$Device,
    [int]$Count = 1
)
$secret = "acs-license-v1-5f0c9e2a71b84d3c"
$dev = $Device.Trim().ToUpper()
if ($dev -notmatch "^[0-9A-F]{6}$") { Write-Error "设备码必须是 6 位十六进制,例如 7A3F21"; exit 1 }

function Sign([string]$payload) {
    $h = New-Object System.Security.Cryptography.HMACSHA256
    $h.Key = [Text.Encoding]::UTF8.GetBytes($secret)
    $bytes = $h.ComputeHash([Text.Encoding]::UTF8.GetBytes($payload))
    $hex = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
    $hex.ToUpper().Substring(0,8)
}

$expiry = (Get-Date).AddDays($Days).ToString("yyyyMMdd")
for ($i = 0; $i -lt $Count; $i++) {
    $rand = -join ((48..57) + (65..90) | Get-Random -Count 4 | ForEach-Object { [char]$_ })
    $payload = "$Plan$expiry$rand$dev"
    $code = "$payload-$(Sign $payload)"
    $planName = switch ($Plan) { "T" { "15 天免费" } "M" { "10 元/月(仅 AGNES)" } "P" { "30 元/月(可自选模型)" } }
    Write-Output "$code   [$planName | 到期 $expiry | 设备 $dev]"
}
