from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, Optional

import pandas as pd
from tqdm import tqdm


DEFAULT_AUDIO_CANDIDATES = ("audio", "audio_file", "filename", "file", "wav", "recording")
DEFAULT_TARGET_CANDIDATES = ("target", "target_sentence", "prompt", "sentence", "stimulus")


def _normalize_col(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _find_column(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    normalized = {_normalize_col(c): c for c in columns}
    for cand in candidates:
        if cand in normalized:
            return normalized[cand]
    for key, original in normalized.items():
        for cand in candidates:
            if cand in key:
                return original
    return None


def _build_audio_index(audio_root: Path) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    for p in audio_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
            index[p.name.lower()] = p
    return index


def _safe_str(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip()


def _load_model(model_size: str):
    import whisper

    return whisper.load_model(model_size)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch transcribe AutoEIT participant audio from Excel mapping.")
    parser.add_argument("--input-xlsx", required=True, help="Input workbook with one sheet per participant.")
    parser.add_argument("--audio-root", required=True, help="Root directory containing all audio files.")
    parser.add_argument("--output-xlsx", required=True, help="Output workbook path.")
    parser.add_argument("--model-size", default="medium", help="Whisper model size (tiny/base/small/medium/large).")
    parser.add_argument("--language", default="es", help="Language code. Use 'es' for Spanish.")
    parser.add_argument("--audio-column", default="", help="Explicit audio filename column name.")
    parser.add_argument("--target-column", default="", help="Explicit target/prompt sentence column name.")
    args = parser.parse_args()

    input_xlsx = Path(args.input_xlsx).resolve()
    output_xlsx = Path(args.output_xlsx).resolve()
    audio_root = Path(args.audio_root).resolve()

    if not input_xlsx.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_xlsx}")
    if not audio_root.exists():
        raise FileNotFoundError(f"Audio root not found: {audio_root}")

    output_xlsx.parent.mkdir(parents=True, exist_ok=True)

    print("Indexing audio files...")
    audio_index = _build_audio_index(audio_root)
    print(f"Indexed {len(audio_index)} audio files")

    print(f"Loading Whisper model: {args.model_size}")
    model = _load_model(args.model_size)

    xls = pd.ExcelFile(input_xlsx)
    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(input_xlsx, sheet_name=sheet_name)
            if df.empty:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                continue

            audio_col = args.audio_column or _find_column(df.columns, DEFAULT_AUDIO_CANDIDATES)
            target_col = args.target_column or _find_column(df.columns, DEFAULT_TARGET_CANDIDATES)
            if audio_col is None:
                raise ValueError(
                    f"Could not detect audio column in sheet '{sheet_name}'. "
                    f"Pass --audio-column explicitly."
                )

            raw_out = []
            avg_logprob_out = []
            no_speech_out = []
            review_notes_out = []

            print(f"Transcribing sheet: {sheet_name} (rows: {len(df)})")
            for _, row in tqdm(df.iterrows(), total=len(df), desc=sheet_name):
                fname = _safe_str(row.get(audio_col, ""))
                target_text = _safe_str(row.get(target_col, "")) if target_col else ""

                if not fname:
                    raw_out.append("")
                    avg_logprob_out.append(None)
                    no_speech_out.append(None)
                    review_notes_out.append("No audio filename in row")
                    continue

                audio_path = audio_index.get(fname.lower())
                if audio_path is None:
                    raw_out.append("")
                    avg_logprob_out.append(None)
                    no_speech_out.append(None)
                    review_notes_out.append(f"Audio file not found under audio root: {fname}")
                    continue

                result = model.transcribe(
                    str(audio_path),
                    language=args.language,
                    task="transcribe",
                    fp16=False,
                    initial_prompt=target_text if target_text else None,
                    temperature=0.0,
                )

                text = (result.get("text") or "").strip()
                raw_out.append(text)

                segments = result.get("segments") or []
                if segments:
                    avg_lp = sum(float(s.get("avg_logprob", 0.0)) for s in segments) / len(segments)
                    nsp = sum(float(s.get("no_speech_prob", 0.0)) for s in segments) / len(segments)
                else:
                    avg_lp, nsp = None, None

                avg_logprob_out.append(avg_lp)
                no_speech_out.append(nsp)

                note = ""
                if avg_lp is not None and avg_lp < -1.0:
                    note = "Low confidence ASR segment; prioritize manual review"
                if nsp is not None and nsp > 0.5:
                    note = (note + " | " if note else "") + "Possible silence/very low speech content"
                review_notes_out.append(note)

            df["asr_transcript_raw"] = raw_out
            df["asr_avg_logprob"] = avg_logprob_out
            df["asr_no_speech_prob"] = no_speech_out
            df["reviewed_transcript"] = ""
            df["review_notes"] = review_notes_out
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"Done. Output written to: {output_xlsx}")


if __name__ == "__main__":
    main()
