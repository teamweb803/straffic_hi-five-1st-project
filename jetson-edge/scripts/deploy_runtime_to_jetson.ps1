param(
    [string]$JetsonHost = "jetson@192.168.10.99",
    [string]$JetsonApp = "/home/jetson/hifive/app"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

scp -r (Join-Path $Root "hifive_jetson_py") "${JetsonHost}:${JetsonApp}/"
scp -r (Join-Path $Root "deepstream_plugins") "${JetsonHost}:${JetsonApp}/"
scp (Join-Path $Root "run_deepstream_nvinfer.py") "${JetsonHost}:${JetsonApp}/run_deepstream_nvinfer.py"
scp (Join-Path $Root "run_edge_runtime.py") "${JetsonHost}:${JetsonApp}/run_edge_runtime.py"
scp (Join-Path $Root "run_edge_service.py") "${JetsonHost}:${JetsonApp}/run_edge_service.py"
scp (Join-Path $Root "example_runtime_config.py") "${JetsonHost}:${JetsonApp}/example_runtime_config.py"

Write-Host "copied Jetson runtime files to ${JetsonHost}:${JetsonApp}"
Write-Host "on Jetson, run: cd ~/hifive/app/deepstream_plugins && make clean && make && make install"
