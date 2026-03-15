# AutoEIT Test I Submission Guide

## 1) Prepare folder structure

Place your files like this:

```text
C:\Projects\AutoEIT Audio-to-text
├─ AutoEIT Sample Audio for Transcribing.xlsx
├─ audio\
│  ├─ participant_01\...
│  ├─ participant_02\...
│  └─ ...
```

## 2) Create clean environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## 3) Run transcription pipeline

```powershell
python -m src.autoeit.transcribe `
  --input-xlsx "AutoEIT Sample Audio for Transcribing.xlsx" `
  --audio-root ".\audio" `
  --output-xlsx ".\outputs\AutoEIT_Sample_Audio_for_Transcribing_FILLED.xlsx" `
  --model-size medium `
  --language es
```

## 4) Manual correction pass (required by test)

Open output workbook and fill `reviewed_transcript` for each row:

- Keep learner errors as-is.
- Correct only ASR recognition mistakes.
- Preserve disfluencies/false starts where audible.
- Use `review_notes` for uncertainty/challenges.

## 5) Optional metric report

If a human reference column exists:

```powershell
python -m src.autoeit.evaluate `
  --input-xlsx ".\outputs\AutoEIT_Sample_Audio_for_Transcribing_FILLED.xlsx" `
  --output-report ".\outputs\transcription_eval_report.md"
```

## 6) What to submit

- GitHub branch URL (no PR)
- Filled transcription workbook
- `outputs/transcription_eval_report.md` (if references available)
- Short method note including:
  - model and settings
  - preprocessing assumptions
  - main transcription challenges
  - evaluation approach

## Common challenge notes to include

- Non-native pronunciation and L1 transfer
- Low volume/noise overlap
- Truncated responses
- Filled pauses and self-corrections
- Prompt leakage vs genuine recall
