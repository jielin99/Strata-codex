param([string]$PythonExe = "")
$ErrorActionPreference = "Stop"
$reportDir = Join-Path $PSScriptRoot ("reports\" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$report = [ordered]@{
    scope = "Read-only Windows hardware/toolchain inventory. No installs or system setting changes."
    source_tag = "v0.1.43.1"
    source_commit = "a0116b2782a5b82622358c04a06496485d12b2d6"
    errors = @()
}
$queries = [ordered]@{
    cpu = { Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors }
    memory = { Get-CimInstance Win32_ComputerSystem | Select-Object Model,TotalPhysicalMemory }
    memory_modules = { Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed }
    os = { Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,FreePhysicalMemory }
    gpu = { Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,Status }
    ai_devices = { Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'AI Boost|NPU|Neural Processing' } | Select-Object Name,Status,ConfigManagerErrorCode }
    ai_drivers = { Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -match 'AI Boost|NPU|Neural Processing' } | Select-Object DeviceName,DriverVersion,DriverDate }
}
foreach ($name in $queries.Keys) {
    try { $report[$name] = @(& $queries[$name]) }
    catch { $report.errors += ($name + ": " + $_.Exception.Message) }
}
$toolList = @("python", "py", "sycl-ls", "icx", "icx-cl", "cmake", "ninja", "cl")
$report["tools_in_path"] = @(foreach ($tool in $toolList) {
    $found = Get-Command $tool -ErrorAction SilentlyContinue | Select-Object -First 1
    [ordered]@{ name = $tool; found = [bool]$found }
})
$oneapiRoots = @()
if (${env:ProgramFiles(x86)}) { $oneapiRoots += (Join-Path ${env:ProgramFiles(x86)} "Intel\oneAPI\setvars.bat") }
if ($env:ProgramFiles) { $oneapiRoots += (Join-Path $env:ProgramFiles "Intel\oneAPI\setvars.bat") }
if ($env:ONEAPI_ROOT) { $oneapiRoots += (Join-Path $env:ONEAPI_ROOT "setvars.bat") }
$report["oneapi_setvars_found"] = [bool]@($oneapiRoots | Where-Object { Test-Path -LiteralPath $_ }).Count
$hardwarePath = Join-Path $reportDir "hardware.json"
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $hardwarePath -Encoding UTF8
Write-Host "Hardware report: $hardwarePath"

$pythonArgs = @()
if ($PythonExe) {
    $pythonCommand = $PythonExe
} elseif (Test-Path -LiteralPath (Join-Path $PSScriptRoot ".venv\Scripts\python.exe")) {
    $pythonCommand = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
    $pythonArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
} else {
    Write-Host "Python was not found. Hardware report is complete. Return reports for the next step."
    exit 0
}
$probePath = Join-Path $PSScriptRoot "probe_openvino.py"
$openvinoPath = Join-Path $reportDir "openvino.json"
try {
    # Resolve py.exe to python.exe so a timeout stops the inference process itself.
    $resolvedPython = @(& $pythonCommand @pythonArgs -c "import sys; print(sys.executable)" 2>&1)
    if ($LASTEXITCODE -ne 0 -or $resolvedPython.Count -ne 1 -or -not (Test-Path -LiteralPath ([string]$resolvedPython[0]))) {
        throw "Could not resolve a working Python interpreter: $resolvedPython"
    }
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = [string]$resolvedPython[0]
    $process.StartInfo.Arguments = '"' + $probePath + '" --smoke --output "' + $openvinoPath + '"'
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.EnvironmentVariables["PYTHONUTF8"] = "1"
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(120000)) {
        $process.Kill()
        $process.WaitForExit()
        $stdoutTask.Result | Set-Content -LiteralPath (Join-Path $reportDir "openvino-console.txt") -Encoding UTF8
        $stderrTask.Result | Set-Content -LiteralPath (Join-Path $reportDir "openvino-errors.txt") -Encoding UTF8
        "Timeout after 120 seconds; only the launched Python probe was stopped." |
            Set-Content -LiteralPath (Join-Path $reportDir "openvino-status.txt") -Encoding UTF8
        Write-Host "OpenVINO timed out. Return all report files."
        exit 0
    }
    $probeExit = $process.ExitCode
    $stdoutTask.Result | Set-Content -LiteralPath (Join-Path $reportDir "openvino-console.txt") -Encoding UTF8
    $stderrTask.Result | Set-Content -LiteralPath (Join-Path $reportDir "openvino-errors.txt") -Encoding UTF8
    "Python exit code: $probeExit" | Set-Content -LiteralPath (Join-Path $reportDir "openvino-status.txt") -Encoding UTF8
    Write-Host "OpenVINO probe exit: $probeExit (0=NPU smoke passed; 2=needs attention)."
} catch {
    $_.Exception.Message | Set-Content -LiteralPath (Join-Path $reportDir "openvino-console.txt") -Encoding UTF8
    Write-Host "OpenVINO probe could not start. See openvino-console.txt."
}
Write-Host "Return the reports folder: $reportDir"
Write-Host "This does not test Strata, LLM quality, or CPU/GPU/NPU cooperation."
