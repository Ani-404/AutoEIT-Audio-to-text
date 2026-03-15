from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from jiwer import cer, wer


REF_CANDIDATES = (
    "reviewed_transcript",
    "transcription",
    "reference",
    "gold",
    "human_transcript",
)
HYP_CANDIDATES = (
    "asr_transcript_raw",
    "reviewed_transcript",
    "prediction",
    "hypothesis",
)


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


def _to_text(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip()


def _safe_metric(metric_fn, refs, hyps) -> float:
    if not refs:
        return float("nan")
    return float(metric_fn(refs, hyps))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate AutoEIT transcriptions from Excel sheets.")
    parser.add_argument("--input-xlsx", required=True, help="Workbook with predictions and references.")
    parser.add_argument("--output-report", required=True, help="Markdown report path.")
    parser.add_argument("--reference-column", default="", help="Explicit reference column.")
    parser.add_argument("--hypothesis-column", default="", help="Explicit hypothesis column.")
    args = parser.parse_args()

    input_xlsx = Path(args.input_xlsx).resolve()
    output_report = Path(args.output_report).resolve()
    output_report.parent.mkdir(parents=True, exist_ok=True)

    if not input_xlsx.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_xlsx}")

    xls = pd.ExcelFile(input_xlsx)

    sheet_lines = []
    all_refs = []
    all_hyps = []

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(input_xlsx, sheet_name=sheet_name)
        if df.empty:
            continue

        ref_col = args.reference_column or _find_column(df.columns, REF_CANDIDATES)
        hyp_col = args.hypothesis_column or _find_column(df.columns, HYP_CANDIDATES)

        if ref_col is None or hyp_col is None:
            sheet_lines.append(f"- {sheet_name}: skipped (missing reference/hypothesis column)")
            continue

        pairs = []
        for _, row in df.iterrows():
            ref = _to_text(row.get(ref_col, ""))
            hyp = _to_text(row.get(hyp_col, ""))
            if ref and hyp:
                pairs.append((ref, hyp))

        if not pairs:
            sheet_lines.append(f"- {sheet_name}: skipped (no comparable non-empty rows)")
            continue

        refs = [r for r, _ in pairs]
        hyps = [h for _, h in pairs]

        sw = _safe_metric(wer, refs, hyps)
        sc = _safe_metric(cer, refs, hyps)
        exact = sum(1 for r, h in pairs if r == h) / len(pairs)

        all_refs.extend(refs)
        all_hyps.extend(hyps)

        sheet_lines.append(
            f"- {sheet_name}: n={len(pairs)}, WER={sw:.4f}, CER={sc:.4f}, ExactMatch={exact:.4f}"
        )

    if all_refs and all_hyps:
        overall_wer = _safe_metric(wer, all_refs, all_hyps)
        overall_cer = _safe_metric(cer, all_refs, all_hyps)
        overall_exact = sum(1 for r, h in zip(all_refs, all_hyps) if r == h) / len(all_refs)
    else:
        overall_wer = float("nan")
        overall_cer = float("nan")
        overall_exact = float("nan")

    lines = [
        "# AutoEIT Transcription Evaluation Report",
        "",
        f"- Input workbook: `{input_xlsx}`",
        f"- Total comparable utterances: {len(all_refs)}",
        "",
        "## Overall",
        f"- WER: {overall_wer:.4f}" if all_refs else "- WER: N/A",
        f"- CER: {overall_cer:.4f}" if all_refs else "- CER: N/A",
        f"- Exact Match: {overall_exact:.4f}" if all_refs else "- Exact Match: N/A",
        "",
        "## By Participant Sheet",
    ]
    lines.extend(sheet_lines if sheet_lines else ["- No evaluable sheets found"])

    output_report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Evaluation report written to: {output_report}")


if __name__ == "__main__":
    main()
