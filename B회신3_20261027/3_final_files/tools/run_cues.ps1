# 혼자 하는 시험용 음성 안내. 계획 CSV(t_s,event,say)의 시각마다 한국어로 말하고,
# 말을 시작한 시각을 노트북 시계와 Pi 시계 기준으로 함께 기록한다.
# Pi 시계 = 노트북 시계 + offset (시작 전에 ssh로 한 번 잼, 왕복 시간 절반 보정)
#   powershell -File run_cues.ps1 -Plan plan_radar_test3.csv -Out test3_cues.csv
param([Parameter(Mandatory)][string]$Plan, [Parameter(Mandatory)][string]$Out,
      [string]$PiHost = "pi@172.20.10.5")  # 핫스팟에서 safeguard.local 이름 찾기가 가끔 실패해서 IP 사용

function NowS { [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0 }

$t0 = NowS
$piNow = [double](ssh -o BatchMode=yes -o HostKeyAlias=safeguard.local $PiHost "date +%s.%N")
$t1 = NowS
$offset = $piNow - ($t0 + $t1) / 2
"Pi clock offset {0:F3} s (ssh round trip {1:F3} s)" -f $offset, ($t1 - $t0)

Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.SelectVoice("Microsoft Heami Desktop")

$rows = Import-Csv -Path $Plan -Encoding UTF8
$log = New-Object System.Collections.Generic.List[string]
$log.Add("event,t_plan_s,laptop_time,pi_time,say")
$start = NowS
foreach ($r in $rows) {
    $target = $start + [double]$r.t_s
    while ((NowS) -lt $target) { Start-Sleep -Milliseconds 20 }
    $now = NowS
    $voice.SpeakAsync($r.say) | Out-Null
    $log.Add(("{0},{1},{2:F3},{3:F3},{4}" -f $r.event, $r.t_s, $now, ($now + $offset), $r.say))
    "[{0,5:F1}s] {1}" -f ($now - $start), $r.event
}
Start-Sleep -Seconds 4
$log | Out-File -FilePath $Out -Encoding utf8
"saved: $Out"
