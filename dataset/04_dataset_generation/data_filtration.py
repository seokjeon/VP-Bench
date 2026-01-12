import pandas as pd
import hashlib
from collections import defaultdict
from tqdm import tqdm
from os.path import join
import os
import pickle
import shutil
from pathlib import Path
import argparse
import tarfile

def getMD5(s):
    hl = hashlib.md5()
    hl.update(s.encode("utf-8"))
    return hl.hexdigest()

parser = argparse.ArgumentParser()
parser.add_argument('--projects', default='jasper', help='Comma-separated list of projects')
args = parser.parse_args()
projects = args.projects.split(',')

BASE_DIR = Path(__file__).resolve().parent.parent

for project_name in tqdm(projects, total=len(projects)):
    combined_functions = []  # Reset per project
    project_folder = BASE_DIR / "output" / project_name
    functions_folder = project_folder / "all_functions"
    slurm_tmp = Path(os.environ.get("SLURM_TMPDIR", BASE_DIR / "output" / project_name / "source_code"))
    SLURM_source_code_path = slurm_tmp / project_name
    SLURM_source_code_path.mkdir(parents=True, exist_ok=True)

    source_code_path = project_folder / f"{project_name}_source_code.tar.gz"
    with tarfile.open(source_code_path, "r:*") as tar:
        tar.extractall(path=SLURM_source_code_path)
    
    # Read from Step 4 output to preserve vulnerable_line_numbers
    csv_data = pd.read_csv(project_folder / f"{project_name}_dataset.csv")
    csv_data["vulnerable_line_numbers"] = csv_data["vulnerable_line_numbers"].fillna("").astype(str)
    csv_data["file_name"] = csv_data["file_name"].astype(str)  # file_name = unique_id
    csv_data["commit_hash"] = csv_data["commit_hash"]
    csv_data["dataset_type"] = csv_data["dataset_type"]  # Default value
    
    with open(functions_folder / f"{project_name}_new_all_functions.pickle", "rb") as output_file:
        all_functions = pickle.load(output_file)
    vul_functions_hash = defaultdict(list)

    for _, row in csv_data[csv_data["vulnerable_line_numbers"].str.len() > 0].iterrows():
        vul_file = row["file_name"]
        with open(join(SLURM_source_code_path, 'source_code', vul_file), "r", encoding="ISO-8859-1") as f:
            source_code = "".join(f.readlines())
            combined_functions.append({"file_name": row["file_name"], "vulnerable_line_numbers": row["vulnerable_line_numbers"], "dataset_type": row["dataset_type"], "commit_hash": row["commit_hash"], "project": project_name, "target": 1})
        vul_hash = getMD5("".join(source_code.split()))
        vul_functions_hash[vul_hash].append([vul_file, project_name])
    for _, row in csv_data[csv_data["vulnerable_line_numbers"].str.len() == 0].iterrows():
        file = row["file_name"]
        if file in all_functions:
            with open(join(SLURM_source_code_path, 'source_code', file), "r", encoding="ISO-8859-1") as f:
                source_code = f.readlines()
            for function in all_functions[file]:
                non_vul_hash = getMD5("".join("".join(source_code[function["start"] - 1:function["end"]]).split()))
                if non_vul_hash not in vul_functions_hash:
                    combined_functions.append({"file_name": file, "target": 0, "vulnerable_line_numbers": "", "project": project_name, "commit_hash": row["commit_hash"], "dataset_type": row["dataset_type"]})
    functions_dataset = pd.DataFrame(combined_functions)
    functions_dataset.to_csv(project_folder / "real_vul_functions_dataset.csv", index=False)