import argparse
import subprocess
from pathlib import Path
import pickle

def list_function_starts(file_path: Path, lang: str) -> list[int]:
    kinds_flag = "--c-kinds=f" if lang == "c" else "--c++-kinds=f"
    lang_flag = f"--language-force={'C' if lang == 'c' else 'C++'}"
    cmd = ["ctags", "-x", lang_flag, kinds_flag, str(file_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return []
    starts = []
    for line in proc.stdout.splitlines():
        tokens = [t for t in line.split() if t]
        if len(tokens) >= 3 and tokens[2].isdigit():
            starts.append(int(tokens[2]))
    return starts

def read_function_block(file_path: Path, start_line: int) -> int:
    depth = 0
    in_body = False
    with file_path.open("r", errors="ignore") as f:
        for idx, line in enumerate(f, start=1):
            if idx < start_line:
                continue
            if not line.lstrip().startswith("//"):
                depth += line.count("{")
                depth -= line.count("}")
                if line.count("{") > 0:
                    in_body = True
            if in_body and depth == 0:
                return idx
    return 0

def build_all_functions(source_dir: Path, lang: str) -> dict:
    all_funcs: dict[str, list[dict]] = {}
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir).as_posix()
        starts = list_function_starts(path, lang)
        ranges = []
        for start in starts:
            end = read_function_block(path, start)
            if end > 0:
                ranges.append({"start": start, "end": end})
        if ranges:
            all_funcs[rel] = ranges
    return all_funcs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="jasper")
    parser.add_argument("--source-dir")
    parser.add_argument("--output-pickle")
    parser.add_argument("--lang", default="c", choices=["c", "cpp"])
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    project = args.project
    source_dir = Path(args.source_dir) if args.source_dir else base_dir / "output" / project / "source_snapshots"
    output_pickle = Path(args.output_pickle) if args.output_pickle else base_dir / "output" / project / "all_functions" / f"{project}_new_all_functions.pickle"

    output_pickle.parent.mkdir(parents=True, exist_ok=True)
    all_funcs = build_all_functions(source_dir, args.lang)
    with output_pickle.open("wb") as f:
        pickle.dump(all_funcs, f)
    print(f"saved: {output_pickle} (files with functions: {len(all_funcs)})")

if __name__ == "__main__":
    main()