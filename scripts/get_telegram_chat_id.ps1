param(
    [string]$Token = $env:TELEGRAM_BOT_TOKEN
)
if (-not $Token) {
    $Token = Read-Host -Prompt "Enter your bot token (kept local)"
}
try {
    if (-not $Token) { throw "No token provided." }
    $url = "https://api.telegram.org/bot$Token/getUpdates"
    Write-Host "Calling getUpdates..."
    $resp = Invoke-RestMethod -Uri $url -UseBasicParsing -ErrorAction Stop
    Write-Host "\nRaw response (truncated):"
    $resp | ConvertTo-Json -Depth 5 | Out-Host

    Write-Host "\nDiscovered chat entries (id, type, title/username/first_name):"
    if ($resp.result -and $resp.result.Count -gt 0) {
        $resp.result | ForEach-Object {
            $m = $_.message
            if ($m -ne $null) {
                $chat = $m.chat
                [pscustomobject]@{
                    id = $chat.id
                    type = $chat.type
                    title = $chat.title
                    username = $chat.username
                    first_name = $chat.first_name
                    last_name = $chat.last_name
                }
            } elseif ($_.channel_post -ne $null) {
                $chat = $_.channel_post.chat
                [pscustomobject]@{
                    id = $chat.id
                    type = $chat.type
                    title = $chat.title
                    username = $chat.username
                    first_name = $chat.first_name
                    last_name = $chat.last_name
                }
            }
        } | Format-Table -AutoSize
    } else {
        Write-Host "No updates found. Make sure you (or the chat) sent a message to the bot, then run this script again." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error calling Telegram API: $_" -ForegroundColor Red
}
