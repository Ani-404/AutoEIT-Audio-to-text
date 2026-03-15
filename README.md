# AutoEIT GSoC 2026 - Test I (Audio-to-Text) Toolkit

This repository contains a reproducible pipeline for the **AutoEIT Test I** task:

- batch-transcribe participant EIT audio
- preserve learner production (including disfluencies)
- generate an output workbook with 30 sentence-level transcriptions per participant
- optionally compute agreement metrics against available human transcriptions

## What This Covers

1. **ASR draft generation** for all participant utterances.
2. **Structured output** in Excel format for manual correction.
3. **Evaluation report** (WER/CER and exact-match) when references are present.
4. **Reproducible CLI workflow** suitable for GitHub submission.

## Project Layout

```text
.
├─ requirements.txt
├─ src/
│  └─ autoeit/
│     ├─ __init__.py
│     ├─ transcribe.py
│     └─ evaluate.py
└─ outputs/              # created at runtime
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Input Assumptions

- You have:
  - `AutoEIT Sample Audio for Transcribing.xlsx`
  - participant audio files in one folder tree
- Excel has one sheet per participant.
- Each row corresponds to an item/utterance.

The scripts use flexible column matching for common names:
- audio file column: `audio`, `audio_file`, `filename`, `wav`, `recording`
- prompt/target column: `target`, `prompt`, `sentence`
- human reference column (optional): `transcription`, `reference`, `gold`, `human`

If your column names differ, pass them explicitly using CLI flags.

## Run Test I Transcription

```powershell
python -m src.autoeit.transcribe `
  --input-xlsx "AutoEIT Sample Audio for Transcribing.xlsx" `
  --audio-root ".\audio" `
  --output-xlsx ".\outputs\AutoEIT_Sample_Audio_for_Transcribing_FILLED.xlsx" `
  --model-size medium `
  --language es
```

### Output Columns Added

- `asr_transcript_raw`: direct ASR output
- `asr_avg_logprob`: confidence signal from ASR
- `asr_no_speech_prob`: silence signal from ASR
- `reviewed_transcript`: empty by default for human correction
- `review_notes`: auto note when file missing or low confidence

Use `reviewed_transcript` as final submission text (correct ASR mistakes only).

## Evaluate Against Human Transcriptions (Optional but recommended)

```powershell
python -m src.autoeit.evaluate `
  --input-xlsx ".\outputs\AutoEIT_Sample_Audio_for_Transcribing_FILLED.xlsx" `
  --output-report ".\outputs\transcription_eval_report.md"
```

This creates a report with:
- overall WER / CER
- exact match rate
- per-sheet metrics

## Suggested Submission Bundle

1. GitHub branch link containing this code.
2. Filled workbook output.
3. Evaluation report.
4. Short methodology note (can be a section in README or separate markdown):
   - preprocessing decisions
   - model choice
   - error patterns
   - unresolved challenges/questions

## Notes for AutoEIT Test Requirements

- Keep learner grammar/vocabulary exactly as produced.
- Correct only ASR recognition mistakes.
- Include disfluencies and partial repetitions where audible.
- Flag uncertain segments for review in `review_notes`.
