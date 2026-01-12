#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import traceback

try:
    import pandas as pd
except Exception:
    print("pandas is required. Please install it: pip install pandas")
    sys.exit(1)

# Constants
DEFAULT_INPUT_PATH = os.path.join(os.path.dirname(__file__), "../output/jasper/VP-Bench_jasper_files_changed_with_vulfunc.csv")
DEFAULT_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "../output/jasper/VP-Bench_jasper_files_changed_with_targets.csv")
OUTPUT_COLUMNS = [
    "unique_id",
    "project",
    "commit_id",
    "flaw_line_index",
    "processed_func",
]

# Helper: inline vulnerable line extractor
def calculate_vulnerable_lines(vul_func_with_fix: str) -> tuple[str, list[int]]:
    lines = vul_func_with_fix.split('\n') if isinstance(vul_func_with_fix, str) else []
    vulnerable_lines_index: list[int] = []
    processed_func: list[str] = []
    is_flaw_line = False
    is_fix_line = False
    for index, line in enumerate(lines):
        if is_fix_line:
            is_fix_line = False
            continue
        if is_flaw_line:
            vulnerable_lines_index.append(len(processed_func))
            is_flaw_line = False
        if line.startswith("//flaw_line_below:"):
            is_flaw_line = True
        elif line.startswith('//fix_flaw_line_below:'):
            is_fix_line = True
        elif not is_fix_line:
            processed_func.append(line)
    return '\n'.join(processed_func), vulnerable_lines_index


def reorder_columns(df, priority_cols):
    """우선순위 컬럼을 앞으로 배치"""
    cols = [c for c in priority_cols if c in df.columns] + [c for c in df.columns if c not in priority_cols]
    return df[cols]


def main():
    parser = argparse.ArgumentParser(description="Add processed_func and target columns to VP-Bench CSV.")
    parser.add_argument(
        "--input-csv",
        default=DEFAULT_INPUT_PATH,
        help=f"Path to input CSV (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--output-csv",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to output CSV (default: {DEFAULT_OUTPUT_PATH})",
    )
    args = parser.parse_args()

    # Load CSV
    try:
        df = pd.read_csv(args.input_csv)
    except Exception as e:
        print(f"Failed to read input CSV {args.input_csv}: {e}")
        sys.exit(1)

    # Ensure columns exist
    if "vul_func_with_fix" not in df.columns:
        print("Input CSV is missing 'vul_func_with_fix' column.")
        sys.exit(2)
    if "vul" not in df.columns:
        df["vul"] = 0

    processed_funcs = []
    flaw_line_indexes = []

    for idx, row in df.iterrows():
        try:
            func_code = row.get("vul_func_with_fix", "")
            # Support rows without vulnerable function (vul==0)
            if not isinstance(func_code, str):
                func_code = ""
            processed_func, vulnerable_lines_index = calculate_vulnerable_lines(func_code)
            processed_funcs.append(processed_func)
            # Store vulnerable lines indices as JSON strings for CSV safety
            flaw_line_indexes.append(json.dumps(vulnerable_lines_index, ensure_ascii=False))
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            print(f"Row {idx} processing failed: {e}")
            processed_funcs.append("")
            flaw_line_indexes.append("[]")

    df["processed_func"] = processed_funcs
    df["flaw_line_index"] = flaw_line_indexes

    # Add unique_id (row index) and commit_id (derived from codeLink)
    df.reset_index(drop=True, inplace=True)
    df["unique_id"] = df.index.astype(str)
    try:
        df = reorder_columns(df, ["unique_id", "codeLink", "commit_id"])
    except Exception:
        # If codeLink missing or malformed, keep commit_id as-is at the end
        print("Warning: Could not reorder columns due to missing 'codeLink' or 'commit_id'.")
        pass

    # Write output
    try:
        out_dir = os.path.dirname(args.output_csv)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        # Restrict output to requested columns only
        for col in OUTPUT_COLUMNS:
            if col not in df.columns:
                # Create missing columns with empty values to ensure consistent output schema
                df[col] = ""

        # Subset and order columns
        vul_rows = (df["vul"] == 1).sum()
        df = df[OUTPUT_COLUMNS]

        # flaw_line_index 컬럼을 쉼표로만 구분된 값으로 변환 (대괄호, 공백 제거)
        df["flaw_line_index"] = df["flaw_line_index"].apply(lambda x: x[1:-1].replace(" ", "") if isinstance(x, str) and x.startswith("[") and x.endswith("]") else x)

        df.to_csv(args.output_csv, index=False)
        print(
            f"Saved CSV with selected columns {OUTPUT_COLUMNS}: {args.output_csv}"
        )
        print(f"Total rows: {len(df)}; vul rows: {vul_rows}")
    except Exception as e:
        print(f"Failed to write output CSV {args.output_csv}: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
