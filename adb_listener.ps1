$adbPath = "C:\Users\veman\AppData\Local\Android\Sdk\platform-tools\adb.exe"
$backendPath = "C:\project\FoodRescueBackend"

Write-Host "===================================================" -ForegroundColor Green
Write-Host "  FoodRescue ADB Device & Backend Listener Active   " -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
Write-Host "This background listener will automatically:"
Write-Host "1. Boot your FastAPI backend server when your phone connects."
Write-Host "2. Configure ADB reverse port forwarding automatically."

$lastDeviceState = $false

while ($true) {
    if (Test-Path $adbPath) {
        $devices = &$adbPath devices
        $hasDevice = $false
        foreach ($line in $devices) {
            if ($line -match "\bdevice\b") {
                $hasDevice = $true
            }
        }

        if ($hasDevice) {
            if (-not $lastDeviceState) {
                Write-Host "[!] Phone connected via USB debugging!" -ForegroundColor Cyan
                
                # Check if uvicorn is already running on port 8000
                $portActive = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
                if (-not $portActive) {
                    Write-Host "[!] Starting backend server on port 8000..." -ForegroundColor Yellow
                    Start-Process cmd -ArgumentList "/c $backendPath\run_backend.bat" -WindowStyle Minimized
                } else {
                    Write-Host "[*] Backend server is already running." -ForegroundColor Green
                }

                # Run adb reverse
                Write-Host "[*] Executing adb reverse tcp:8000 tcp:8000..." -ForegroundColor Yellow
                &$adbPath reverse tcp:8000 tcp:8000
                $lastDeviceState = $true
            }
        } else {
            if ($lastDeviceState) {
                Write-Host "[!] Phone disconnected." -ForegroundColor Red
                $lastDeviceState = $false
            }
        }
    }
    Start-Sleep -Seconds 5
}
