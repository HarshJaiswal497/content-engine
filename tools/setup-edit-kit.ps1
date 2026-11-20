<#
  Edit-Kit setup for Windows: checks the computer, checks the tools, installs what is missing (only if you say yes),
  then installs the kit's skills and runs its self-test.

  Safe by design:
   - reads hardware info only; changes no system or security settings
   - installs nothing without asking (add -Yes to accept the winget installs)
   - the kit only copies skills into %USERPROFILE%\.claude\skills (same-named skills are backed up first)
   - stops if the kit contains any program files (.exe .dll .msi .scr .com)

  Run (PowerShell):
    powershell -ExecutionPolicy Bypass -File setup-edit-kit.ps1 -Kit "C:\Users\you\Downloads\Edit-Kit"
  -Kit can be the unzipped folder or the .zip. -CheckOnly only reports (nothing installed).
  A report is saved to your Desktop: edit-kit-setup-report.txt
#>
param([string]$Kit = "", [switch]$Yes, [switch]$CheckOnly)

$ErrorActionPreference = "Continue"
$report = New-Object System.Collections.Generic.List[string]
function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color; $report.Add($msg) }
function Ask($q) {
  if ($Yes) { return $true }
  $a = Read-Host "$q (y/n)"
  return ($a -match "^(y|yes)$")
}
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Say "=== Edit-Kit setup check ===" Cyan

# ---------- 1. Is this computer good enough? ----------
$os = Get-CimInstance Win32_OperatingSystem
$cs = Get-CimInstance Win32_ComputerSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$gpus = (Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join "; "
$ramGb = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
$cores = $cpu.NumberOfCores
$threads = $cpu.NumberOfLogicalProcessors
$sysDrive = ($env:SystemDrive).TrimEnd(":")
$freeGb = [math]::Round((Get-PSDrive -Name $sysDrive).Free / 1GB, 1)
$is64 = [Environment]::Is64BitOperatingSystem

Say ("Windows : {0} ({1})" -f $os.Caption, $os.OSArchitecture)
Say ("CPU     : {0} - {1} cores / {2} threads" -f $cpu.Name.Trim(), $cores, $threads)
Say ("RAM     : {0} GB" -f $ramGb)
Say ("Graphics: {0}" -f $gpus)
Say ("Disk    : {0} GB free on {1}:" -f $freeGb, $sysDrive)

$problems = @(); $slow = @()
if (-not $is64) { $problems += "needs 64-bit Windows" }
if ($ramGb -lt 8) { $problems += "RAM under 8 GB (Chrome renders frames in the background)" }
elseif ($ramGb -lt 16) { $slow += "8-15 GB RAM works, close other apps while rendering" }
if ($cores -lt 4) { $slow += "under 4 CPU cores: renders will be slow (a 30 s video can take 10+ minutes)" }
if ($freeGb -lt 10) { $problems += "under 10 GB free disk (temporary frames and videos need room)" }

if ($problems.Count -gt 0) {
  Say "Verdict : NOT ENOUGH - $($problems -join '; ')" Red
  Say "Use the GitHub pipeline instead (free, no local power needed). You can still use the kit's look inside our repo."
} elseif ($slow.Count -gt 0) {
  Say "Verdict : OK, but slower - $($slow -join '; ')" Yellow
} else {
  Say "Verdict : GOOD. This computer can run the kit comfortably." Green
}
Say ""

# ---------- 2. Tools ----------
Say "--- Tools ---" Cyan
$missing = @()
$nodeOk = $false
if (Have "node") {
  $nv = (node -v) -replace "^v", ""
  $nodeOk = ([int]($nv.Split(".")[0]) -ge 22)
  Say ("Node.js : {0} {1}" -f $nv, $(if ($nodeOk) { "ok" } else { "TOO OLD (need 22+)" }))
} else { Say "Node.js : missing" Yellow }
if (-not $nodeOk) { $missing += @{ name = "Node.js 22+"; id = "OpenJS.NodeJS.LTS" } }

if (Have "ffmpeg") { Say "FFmpeg  : ok" } else { Say "FFmpeg  : missing" Yellow; $missing += @{ name = "FFmpeg"; id = "Gyan.FFmpeg" } }
if (Have "git") { Say "Git     : ok" } else { Say "Git     : missing (Claude Code needs it on Windows)" Yellow; $missing += @{ name = "Git for Windows"; id = "Git.Git" } }

$py = $null
if (Have "python") { $py = "python" } elseif (Have "py") { $py = "py" }
if ($py) {
  Say ("Python  : {0}" -f (& $py --version 2>&1))
  & $py -c "import PIL, numpy" 2>$null
  if ($LASTEXITCODE -eq 0) { Say "Pillow + NumPy : ok" } else { Say "Pillow + NumPy : missing (will install with pip, no admin needed)" Yellow }
} else { Say "Python  : missing" Yellow; $missing += @{ name = "Python 3"; id = "Python.Python.3.12" } }

if (Have "claude") { Say "Claude Code : ok" } else { Say "Claude Code : not on PATH. Install it from claude.com/claude-code (needs a Pro or Max plan), or use the Code tab in the Claude desktop app." Yellow }
Say ""

if ($CheckOnly) { Say "Check only: nothing installed." Cyan }
elseif ($problems.Count -gt 0) { Say "Stopping before installs because of the verdict above." Red }
else {
  # ---------- 3. Install what is missing (winget, with your yes) ----------
  if ($missing.Count -gt 0) {
    if (-not (Have "winget")) {
      Say "winget not found. Install the missing tools by hand: $($missing | ForEach-Object { $_.name })" Yellow
    } else {
      foreach ($m in $missing) {
        if (Ask ("Install {0} with winget?" -f $m.name)) {
          winget install --id $m.id -e --accept-source-agreements --accept-package-agreements
          Say ("installed {0}" -f $m.name)
        } else { Say ("skipped {0}" -f $m.name) Yellow }
      }
      Say "If anything was installed: close this window, open a new PowerShell and run this script again (PATH refreshes)." Yellow
    }
  }
  if ($py) {
    & $py -c "import PIL, numpy" 2>$null
    if ($LASTEXITCODE -ne 0 -and (Ask "Install Pillow and NumPy with pip (current user only)?")) { & $py -m pip install --user pillow numpy }
  }

  # ---------- 4. The kit ----------
  Say ""; Say "--- Kit ---" Cyan
  if (-not $Kit) {
    $guess = Get-ChildItem (Join-Path $env:USERPROFILE "Downloads") -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "Edit-Kit*" } | Select-Object -First 1
    if ($guess) { $Kit = $guess.FullName }
  }
  if (-not $Kit -or -not (Test-Path $Kit)) {
    Say "Kit not found. Run again with  -Kit ""C:\path\to\Edit-Kit""  (folder or .zip)." Red
  } else {
    if ($Kit -like "*.zip") {
      $tmp = Join-Path $env:TEMP ("edit-kit-" + (Get-Date -Format "yyyyMMddHHmmss"))
      Expand-Archive -Path $Kit -DestinationPath $tmp -Force
      $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
      $Kit = if ($inner -and (Test-Path (Join-Path $inner.FullName "install.ps1"))) { $inner.FullName } else { $tmp }
    }
    if (-not (Test-Path (Join-Path $Kit "install.ps1"))) { Say "install.ps1 not found in $Kit" Red }
    else {
      $bad = Get-ChildItem $Kit -Recurse -File -Include *.exe, *.dll, *.msi, *.scr, *.com -ErrorAction SilentlyContinue
      if ($bad) { Say ("STOP: program files found in the kit:`n" + (($bad | ForEach-Object { $_.FullName }) -join "`n")) Red }
      else {
        $n = (Get-ChildItem (Join-Path $Kit "skills") -Directory).Count
        Say ("Kit looks clean (no program files). {0} skills will be copied to {1}\.claude\skills" -f $n, $env:USERPROFILE)
        if (Ask "Install the skills now?") {
          & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Kit "install.ps1")
          Say "Skills installed."
          if ($py -and (Ask "Run the kit's self-test now (2-5 minutes, renders a 3 s test video)?")) {
            Push-Location $Kit; & $py selftest.py; Pop-Location
          }
        }
      }
    }
  }
}

# ---------- 5. Save the report ----------
$desk = [Environment]::GetFolderPath("Desktop")
$path = Join-Path $desk "edit-kit-setup-report.txt"
$report | Out-File -FilePath $path -Encoding utf8
Write-Host ""
Write-Host "Report saved: $path  (send it to Claude if something failed)" -ForegroundColor Cyan
