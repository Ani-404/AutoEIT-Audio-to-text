from __future__ import annotations

from pathlib import Path
import argparse
import re

import av
import numpy as np
import pandas as pd
import whisper
from rapidfuzz import fuzz

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_AUDIO_DIR = PROJECT_ROOT / "data" / "audio"
DATA_SHEETS_DIR = PROJECT_ROOT / "data" / "sheets"

AUDIO_FILES = [
    DATA_AUDIO_DIR / "038015_EIT-1A.mp3",
    DATA_AUDIO_DIR / "038012_EIT-2A.mp3",
    DATA_AUDIO_DIR / "038011_EIT-1A.mp3",
    DATA_AUDIO_DIR / "038010_EIT-2A.mp3",
]

TEMPLATE_XLSX = DATA_SHEETS_DIR / "AutoEIT Sample Transcriptions for Scoring.xlsx"
OUT_XLSX = PROJECT_ROOT / "outputs" / "AutoEIT_TestI_Transcriptions.xlsx"
NOTES_MD = PROJECT_ROOT / "outputs" / "TestI_Approach_and_Challenges.md"


def load_audio_16k_mono(path: Path) -> np.ndarray:
    container = av.open(str(path))
    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
    chunks = []
    for frame in container.decode(audio=0):
        out = resampler.resample(frame)
        if out is None:
            continue
        frames = out if isinstance(out, list) else [out]
        for f in frames:
            arr = f.to_ndarray()
            if arr.ndim == 2:
                arr = arr[0]
            chunks.append(arr.astype(np.float32) / 32768.0)
    if not chunks:
        return np.zeros(16000, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def make_pause_groups(segments: list[dict], threshold: float) -> list[dict]:
    if not segments:
        return []
    groups = []
    cur = {"start": segments[0]["start"], "end": segments[0]["end"], "text": normalize_space(segments[0]["text"])}
    for s in segments[1:]:
        gap = float(s["start"]) - float(cur["end"])
        if gap > threshold:
            groups.append(cur)
            cur = {"start": s["start"], "end": s["end"], "text": normalize_space(s["text"])}
        else:
            cur["end"] = s["end"]
            cur["text"] = normalize_space(cur["text"] + " " + s["text"])
    groups.append(cur)
    return groups


def pick_30_with_alignment(groups: list[dict], stimuli: list[str]) -> list[dict]:
    n = len(groups)
    m = len(stimuli)
    neg = -10**9
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    keep = [[False] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = 0
    for i in range(1, n + 1):
        gi = groups[i - 1]["text"].lower()
        for j in range(1, m + 1):
            best = dp[i - 1][j]
            take = False
            prev = dp[i - 1][j - 1]
            if prev > neg:
                sim = fuzz.token_set_ratio(gi, stimuli[j - 1].lower()) / 100.0
                cand = prev + sim
                if cand > best:
                    best = cand
                    take = True
            dp[i][j] = best
            keep[i][j] = take
    out = []
    i, j = n, m
    while j > 0 and i > 0:
        if keep[i][j]:
            out.append(groups[i - 1])
            i -= 1
            j -= 1
        else:
            i -= 1
    out.reverse()
    return out


def segment_to_target(segments: list[dict], stimuli: list[str], target: int = 30) -> list[dict]:
    if not segments:
        return [{"start": 0.0, "end": 0.0, "text": ""} for _ in range(target)]
    thresholds = [x / 10.0 for x in range(6, 26)]
    candidates = [make_pause_groups(segments, t) for t in thresholds]
    base = min(candidates, key=lambda g: abs(len(g) - max(target + 8, target)))
    groups = pick_30_with_alignment(base, stimuli) if len(base) >= target else base
    while len(groups) > target:
        min_gap = None
        min_idx = 0
        for i in range(len(groups) - 1):
            gap = groups[i + 1]["start"] - groups[i]["end"]
            if min_gap is None or gap < min_gap:
                min_gap = gap
                min_idx = i
        merged = {
            "start": groups[min_idx]["start"],
            "end": groups[min_idx + 1]["end"],
            "text": normalize_space(groups[min_idx]["text"] + " " + groups[min_idx + 1]["text"]),
        }
        groups = groups[:min_idx] + [merged] + groups[min_idx + 2 :]
    while len(groups) < target:
        idx = max(range(len(groups)), key=lambda i: len(groups[i]["text"]))
        words = groups[idx]["text"].split()
        if len(words) < 4:
            groups.append({"start": groups[idx]["end"], "end": groups[idx]["end"], "text": ""})
            continue
        mid = len(words) // 2
        a = {"start": groups[idx]["start"], "end": (groups[idx]["start"] + groups[idx]["end"]) / 2, "text": " ".join(words[:mid])}
        b = {"start": a["end"], "end": groups[idx]["end"], "text": " ".join(words[mid:])}
        groups = groups[:idx] + [a, b] + groups[idx + 1 :]
    return groups[:target]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-size", default="small", help="Whisper size: tiny/base/small")
    args = parser.parse_args()

    model = whisper.load_model(args.model_size)

    stimuli_df = pd.read_excel(TEMPLATE_XLSX, sheet_name="38001-1A")[["Sentence", "Stimulus"]].copy()
    stimuli = [str(x) for x in stimuli_df["Stimulus"].tolist()]

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    temp_out = OUT_XLSX.with_suffix(".tmp.xlsx")

    notes = [
        "# AutoEIT Test I - Approach and Challenges",
        "",
        f"- Model: {args.model_size}",
        "- Audio decoding: PyAV",
        "- Segmentation: pause grouping + stimulus-aligned selection",
    ]

    with pd.ExcelWriter(temp_out, engine="openpyxl") as writer:
        pd.DataFrame({"Field": ["Generated by", "Date", "Files processed"], "Value": ["scripts/quick_test1_submit.py", pd.Timestamp.now().isoformat(), len(AUDIO_FILES)]}).to_excel(writer, sheet_name="Info", index=False)
        for audio_path in AUDIO_FILES:
            audio = load_audio_16k_mono(audio_path)
            result = model.transcribe(
                audio,
                language="es",
                task="transcribe",
                fp16=False,
                temperature=(0.0, 0.2, 0.4),
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0,
                logprob_threshold=-1.0,
                no_speech_threshold=0.6,
            )
            segs = result.get("segments", [])
            groups = segment_to_target(segs, stimuli=stimuli, target=30)
            out = stimuli_df.copy()
            out["Transcription Rater 1"] = [normalize_space(g["text"]) for g in groups]
            out["Score"] = ""
            out.to_excel(writer, sheet_name=audio_path.stem[:31], index=False)
            notes.append(f"- {audio_path.name}: raw={len(segs)}, final=30")

    temp_out.replace(OUT_XLSX)
    NOTES_MD.write_text("\n".join(notes), encoding="utf-8")
    print(f"Wrote: {OUT_XLSX}")


if __name__ == "__main__":
    main()


