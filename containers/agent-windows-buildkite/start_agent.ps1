c:\credentials\buildkite-env.ps1
# Install Buildkite agent.
iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/buildkite/agent/master/install.ps1'))

$env:SCCACHE_DIR="C:\ws\sccache"

Remove-Item -Recurse -Force -ErrorAction Ignore $env:SCCACHE_DIR
# needed for jenkins likely $env:SCCACHE_IDLE_TIMEOUT="0"
sccache --start-server

C:\buildkite-agent\bin\buildkite-agent.exe start
