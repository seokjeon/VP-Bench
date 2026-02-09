#!/usr/bin/env python3

import argparse
from pathlib import Path
import pickle
import subprocess
from extract_functions import EXT_MAP, process_file, get_line_numbers

def build_all_functions(source_dir: Path) -> dict:
    all_funcs: dict[str, list[dict]] = {}
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix is None:
            extension = "c"
        elif path.suffix in EXT_MAP:
            extension = EXT_MAP[path.suffix]
        else:
            continue
        rel = path.relative_to(source_dir).as_posix()
        starts = get_line_numbers(str(path), extension)
        ranges = []
        for start in starts:
            try: 
                _, end = process_file(str(path), start)
                if end > 0:
                    ranges.append({"start": start, "end": end})
            except Exception as e:
                print(f"Error processing {path} at line {start}: {e}")
                continue
        if ranges:
            all_funcs[rel] = ranges
    return all_funcs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--uncertain-unit", choices=["file", "function"], default="function")
    args = parser.parse_args()

    source_dir = Path(args.input) # if args.source_dir else base_dir / "output" / project / "source_code"
    output_pickle = Path(args.output) # if args.output else base_dir / "output" / project / "all_functions" / f"{project}_new_all_functions.pickle"

    output_pickle.parent.mkdir(parents=True, exist_ok=True)
    all_funcs: dict[str, list[dict]] = {}
    
    if args.uncertain_unit == "file":
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(source_dir).as_posix()
            
            # 파일 전체를 하나의 범위로 (start=1, end=파일끝)
            with path.open("r", errors="ignore") as f:
                total_lines = sum(1 for _ in f)
            if total_lines > 0:
                all_funcs[rel] = [{"start": 1, "end": total_lines}]
    elif args.uncertain_unit == "function":
        all_funcs = build_all_functions(source_dir)
    
    with output_pickle.open("wb") as f:
        pickle.dump(all_funcs, f)

if __name__ == "__main__":
    main()