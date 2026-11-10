# Pakuje projekt do LAB3_Nazwisko_Imie_Nazwisko_Imie.zip (bez danych i venv).
# Uzycie: powershell -ExecutionPolicy Bypass -File make_zip.ps1 -Nazwa "LAB3_Kowalska_Anna_Nowak_Jan"
param([Parameter(Mandatory = $true)][string]$Nazwa)

$root = $PSScriptRoot
$stage = Join-Path $env:TEMP $Nazwa
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory $stage | Out-Null

$items = 'README.md', 'ZAPYTANIA.md', 'Sprawozdanie.pdf', 'docker-compose.yml', 'requirements.txt',
         'make_zip.ps1', 'sql', 'solr', 'scripts', 'results', 'report'
foreach ($i in $items) { Copy-Item -Recurse (Join-Path $root $i) $stage }
Get-ChildItem -Recurse -Directory -Filter __pycache__ $stage | Remove-Item -Recurse -Force

$zip = Join-Path $root "$Nazwa.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip
Remove-Item -Recurse -Force $stage
Get-Item $zip | Select-Object Name, Length
