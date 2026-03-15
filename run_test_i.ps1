param(
  [string]$InputXlsx = "AutoEIT Sample Audio for Transcribing.xlsx",
  [string]$AudioRoot = ".\audio",
  [string]$OutputXlsx = ".\outputs\AutoEIT_Sample_Audio_for_Transcribing_FILLED.xlsx",
  [string]$ModelSize = "medium",
  [string]$Language = "es"
)

python -m src.autoeit.transcribe `
  --input-xlsx "$InputXlsx" `
  --audio-root "$AudioRoot" `
  --output-xlsx "$OutputXlsx" `
  --model-size "$ModelSize" `
  --language "$Language"
