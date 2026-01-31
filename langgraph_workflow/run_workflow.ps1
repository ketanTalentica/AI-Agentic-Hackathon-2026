param(
    [string]$InputText
)

$scriptPath = Join-Path $PSScriptRoot "langgraph_agents\langgraph_main.py"

if (-not $InputText -or $InputText.Trim().Length -eq 0) {
    # If no input provided, just run interactive
    python $scriptPath
} else {
    # Run with input
    python $scriptPath $InputText
}
