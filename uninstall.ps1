# Remove do computador tudo o que o Solarhub criou no Windows: skills, MCP, tarefa agendada, atalho,
# PATH, a pasta %USERPROFILE%\solarhub e o ambiente .venv deste clone.
#   .\uninstall.cmd               remove tudo (pede confirmação)
#   .\uninstall.cmd --keep-data   mantém %USERPROFILE%\solarhub
#   .\uninstall.cmd --yes         sem confirmação
param([switch]$KeepData, [switch]$Yes)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Cli  = Join-Path $Root ".venv\Scripts\solarhub.exe"
$a = @("uninstall")
if ($KeepData) { $a += "--keep-data" }
if ($Yes) { $a += "--yes" }
if (Test-Path $Cli) { & $Cli @a }
elseif (Get-Command solarhub -ErrorAction SilentlyContinue) { solarhub @a }
else { Write-Host "comando solarhub não encontrado; nada a desfazer no sistema" }
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Remove-Item -Recurse -Force (Join-Path $Root ".venv") -ErrorAction SilentlyContinue
Write-Host "OK Solarhub removido. Sobrou só esta pasta com o código: $Root (apague se quiser)" -ForegroundColor Green
