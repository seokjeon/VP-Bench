import numpy as np
import pandas as pd
import os
#coding=utf8
import sys
from urllib.error import HTTPError
import ssl
import time
import traceback
import json
import subprocess
import shlex
from dataclasses import dataclass
ssl._create_default_https_context = ssl._create_unverified_context
import cloudscraper
from dotenv import load_dotenv
import argparse
from pathlib import Path

# .env 파일에서 환경 변수 로드
load_dotenv()

# 환경 변수에서 토큰 읽기
github_token = os.getenv('GITHUB_TOKEN')

ssl._create_default_https_context = ssl._create_unverified_context
scraper = cloudscraper.create_scraper()

# Constants
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_BASE = BASE_DIR / "output" / "jasper"
# Store patch/split artifacts under the project output directory
PATCH_ROOT = OUTPUT_BASE / "patches"
SPLIT_ROOT = OUTPUT_BASE / "extracted_functions"
DEFAULT_CWE_ID = "others"
EXT_MAP = {
    "c": "c",
    "C": "c++",
    "cpp": "c++",
    "cc": "c++",
    "cxx": "c++",
    "c++": "c++",
    "Cpp": "c++",
}

def get_sourcefiles(url):
    try:
        file = scraper.get(url,headers={'User-Agent':'Mozilla/5.0',
               'Authorization': f'token {github_token}',
               'Content-Type':'application/json',
               'Accept':'application/json'}).text
        return file
    except HTTPError as e:
        if e.code == 429:
            time.sleep(10)
            return get_sourcefiles(url)
        if e.code == 404:
            print("\n not found:" + url+ "！")
            return ""
        if e.code == 403:
            print("403 please wait")
            print(url)
            return ""
        raise
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        print("reason", e)
        print("\n skip get_response:"+url+ "！")
        return ""
    
# find all the line numbers that the functions begins
def get_line_numbers(filename,lang_type):
    assert(lang_type in ["c","c++"])
    assert(type(filename) == str)
    # found = False
    #cmd = "ctags -x --c-kinds=fp " + filename + " | grep " + funcname
    cmd = "ctags -x --"+lang_type+"-kinds=f " + filename

    output = subprocess.getoutput(cmd)
    lines = output.splitlines()
    line_nums = []
    for line in lines:
        line = line.split(" ")
        char = list(filter(None, line))
        line_num = char[2]
        line_nums.append(int(line_num))
    return line_nums

    # if found == False:
    #     #print("Function not found")
    #     return 0

# given the file name and  line number(start), return the code of the line number and the endline num
def process_file(filename, line_num):
    print("opening " + filename + " on line " + str(line_num))

    code = ""
    cnt_braket = 0
    found_start = False
    found_end = False

    with open(filename, "r") as f:
        for i, line in enumerate(f):
            if(i >= (line_num - 1)):
                code += line

                if (not line.startswith("//")) and line.count("{") > 0:
                    found_start = True
                    cnt_braket += line.count("{")

                if (not line.startswith("//")) and line.count("}") > 0:
                    cnt_braket -= line.count("}")

                if cnt_braket == 0 and found_start == True:
                    found_end = True
                    return code, i+1

def get_diff_num(filename):
    diff_start_lines = []
    with open(filename, "r") as patch:
        for i, line in enumerate(patch):
            if line.startswith("@@ "):
                if not i == 0:
                    diff_start_lines.append(i)
        diff_start_lines.append(i+1)
    return diff_start_lines

def get_enumerate(filename):
    patch = open(filename, "r")
    return enumerate(patch)

#return anchor： @@ -61,7 +61,7 @@; how many -;  how many +; - positinons; + positions
'''
@@ -6835,12 +6835,16 @@ static void buffer_pipe_buf_release(struct pipe_inode_info *pipe,
 	buf->private = 0;
 }

-static void buffer_pipe_buf_get(struct pipe_inode_info *pipe,
+static bool buffer_pipe_buf_get(struct pipe_inode_info *pipe,
 				struct pipe_buffer *buf)
 {
 	struct buffer_ref *ref = (struct buffer_ref *)buf->private;

+	if (ref->ref > INT_MAX/2)
+		return false;
+
 	ref->ref++;
+	return true;
 }

 /* Pipe buffer operations for a buffer. */
 
 -------------------------------------------
 return:
 [[['6835', '12'], ['6835', '16'], 1, 5, [4], [5, 10, 11, 12, 14]]]
'''
def get_diff_information(filename,diff_start_lines):
    block_num = 0
    archor = []
    count = 0
    for diff_start_line in diff_start_lines:
        # reset some values
        count+=1
        minus_count = 0
        plus_count = 0
        before = None
        after = None
        start_line_num = None
        minus_pos = []
        plus_pos = []
        patch=[]
        for j, l in get_enumerate(filename):
            if count == len (diff_start_lines):
                if j == diff_start_line - 1:
                    patch.append(l)
                    if l.startswith("-"):
                        minus_count += 1
                        minus_pos.append(j-start_line_num)
                    if l.startswith("+"):
                        plus_count += 1
                        plus_pos.append(j-start_line_num)
                    block_num = j
                    before = list(map(int, before))
                    after = list(map(int, after))
                    if len(archor)==0:
                        archor.append([before, after, minus_count, plus_count, minus_pos, plus_pos, patch,after[0],minus_count,0])
                    else:
                        diff_value = archor[-1][8]+ minus_count
                        insert_after = after[0] + archor[-1][8]
                        last_end = archor[-1][1][0]+archor[-1][1][1]-1
                        archor.append([before, after, minus_count,plus_count,minus_pos,plus_pos,patch,insert_after,diff_value,last_end])
                    break

                if block_num <= j < diff_start_line-1:
                    patch.append(l)
                    if l.startswith("@@ "):
                        start_line_num = j
                        pos = l.find("@@ ")
                        end = l.find(" @@ ")
                        modified = l[pos + 3:end]
                        modified = modified.split(" ")
                        before = modified[0]
                        before = before.replace("-", "")
                        before = before.split(",")
                        after = modified[1]
                        after = after.replace("+", "")
                        after = after.split(",")
                        # now our source files are after-modified

                    if l.startswith("-"):
                        minus_count += 1
                        minus_pos.append(j-start_line_num)

                    if l.startswith("+"):
                        plus_count += 1
                        plus_pos.append(j-start_line_num)
                elif j<block_num:
                    continue
                else:
                    block_num = j
                    before = list(map(int, before))
                    after = list(map(int, after))
                    if len(archor) == 0:
                        archor.append(
                            [before, after, minus_count, plus_count, minus_pos, plus_pos, patch, after[0], minus_count,
                             0])
                    else:
                        diff_value = archor[-1][8] + minus_count
                        insert_after = after[0] + archor[-1][8]
                        last_end = archor[-1][1][0] + archor[-1][1][1] - 1
                        archor.append([before, after, minus_count, plus_count, minus_pos, plus_pos, patch, insert_after,
                                       diff_value, last_end])
                    break
            else:
                if block_num <= j < diff_start_line:
                    patch.append(l)
                    if l.startswith("@@ "):
                        start_line_num = j
                        pos = l.find("@@ ")
                        end = l.find(" @@ ")
                        modified = l[pos + 3:end]
                        modified = modified.split(" ")
                        before = modified[0]
                        before = before.replace("-", "")
                        before = before.split(",")
                        after = modified[1]
                        after = after.replace("+", "")
                        after = after.split(",")
                        # now our source files are after-modified

                    if l.startswith("-"):
                        minus_count += 1
                        minus_pos.append(j-start_line_num)

                    if l.startswith("+"):
                        plus_count += 1
                        plus_pos.append(j-start_line_num)
                elif j<block_num:
                    continue
                else:
                    block_num = j
                    before = list(map(int, before))
                    after = list(map(int, after))
                    if len(archor) == 0:
                        archor.append(
                            [before, after, minus_count, plus_count, minus_pos, plus_pos, patch, after[0], minus_count,
                             0])
                    else:
                        diff_value = archor[-1][8] + minus_count
                        insert_after = after[0] + archor[-1][8]
                        last_end = archor[-1][1][0] + archor[-1][1][1] - 1
                        archor.append([before, after, minus_count, plus_count, minus_pos, plus_pos, patch, insert_after,
                                       diff_value, last_end])
                    break

    return archor

def main():
    parser = argparse.ArgumentParser(description='Process VP-Bench dataset to extract vulnerable functions.')
    parser.add_argument('--input_csv', required=True, help='Input CSV file path')
    parser.add_argument('--output_csv', required=True, help='Output CSV file path')
    args = parser.parse_args()
    
    c_cpp_csv = pd.read_csv(args.input_csv)
    expanded_rows = []
    vul_number=0
    file_name_counter = 1
    # ensure columns
    if "vul" not in c_cpp_csv.columns:
        c_cpp_csv["vul"] = 0
    if "vul_func_with_fix" not in c_cpp_csv.columns:
        c_cpp_csv["vul_func_with_fix"] = ""

    for index, row in c_cpp_csv.iterrows():
        try:
            codeLink = row["codeLink"]
            commit_id = codeLink[codeLink.rfind("/")+1:]
            diff = row["files_changed"]
            CWE_ID = "others"
            files_changed = []
            project = row["project"]
            for i in diff.split("<_**next**_>"):
                files_changed.append(json.loads(i))

            vul_funcs_for_row = set()

            for file in files_changed:
                file_with_dir = file["filename"]
                pos = file_with_dir.rfind('/')
                if pos >0:
                    filename = file_with_dir[pos+1:]
                    file_dir = commit_id + "/"+ file_with_dir[:pos]
                elif pos ==0:
                    filename = file_with_dir[1:]
                    file_dir = commit_id
                else:
                    filename = file_with_dir
                    file_dir = commit_id
                raw_url = file["raw_url"]
                if "patch" in file:
                    patch = file["patch"]
                else:
                    patch = ""
                type_pos = filename.find('.')
                if type_pos>0:
                    only_name =  filename[:type_pos]
                    only_type = filename[type_pos+1:]
                else:
                    only_name =  filename
                    only_type = "not know"
                
                if only_type not in EXT_MAP.keys():
                    continue
                    
                sourcefiles = get_sourcefiles(raw_url)
                base_dir = PATCH_ROOT / only_type / project / CWE_ID / file_dir
                base_dir.mkdir(parents=True, exist_ok=True)
                sourcefile_dir = base_dir / filename
                patchfile_dir = base_dir / (only_name + '_patch.txt')
                with open(sourcefile_dir,"w+") as source_file, open(patchfile_dir,"w+") as patch_file:
                    source_file.write(sourcefiles)
                    patch_file.write(patch)
                num = get_diff_num(patchfile_dir)
                archors = get_diff_information(patchfile_dir,num)
                block_num = 0
                block_total = len(archors)
                for archor in archors:
                    block_num+=1
                    del_line_pos = archor[4]
                    add_line_pos = archor[5]
                    patch_start = int(archor[1][0])
                    patch_lines = int(archor[0][1])+archor[3]
                    patch_end = patch_start + patch_lines -1
                    source_end = patch_start + int(archor[1][1])-1
                    last_end = archor[9]
                    wrote = False
                    add_patch_file_dir = base_dir / ("add_patch_" + filename)
                    with open(sourcefile_dir,"r") as before, open(add_patch_file_dir,"a") as after:
                        lines = before.readlines()
                        flen = len(lines)
                        for i in range(flen):
                            if last_end-1 < i <= source_end - 1:
                                if i ==0:
                                    after.write(lines[i])
                                    continue
                                if (patch_start-1<= i <= source_end-1):
                                    if wrote == False:
                                        for patch_line in archor[6][1:]:
                                            if patch_line.startswith("+"):
                                                patch_line = patch_line.replace("+","//fix_flaw_line_below:\n//",1)
                                            if patch_line.startswith("-"):
                                                patch_line = patch_line.replace("-","//flaw_line_below:\n",1)
                                            if not patch_line.endswith("\n"):
                                                patch_line = patch_line + "\n"
                                            after.write(patch_line)
                                        wrote = True
                                else:
                                    after.write(lines[i])
                            if block_num == block_total and source_end<flen and i > source_end - 1:
                                after.write(lines[i])
                line_nums = get_line_numbers(str(add_patch_file_dir), EXT_MAP[only_type])
                if len(line_nums) > 0:
                    for line_num in line_nums:
                        code,i = process_file(str(add_patch_file_dir), line_num)
                        if "//flaw_line_below:" in code or "//fix_flaw_line_below:\n//" in code:
                            vul_number+=1
                            vul_funcs_for_row.add((code, line_num, only_type, filename))
                            split_vul_dir = SPLIT_ROOT / "vul" / project / CWE_ID
                            split_vul_dir.mkdir(parents=True, exist_ok=True)
                            split_vul_file = split_vul_dir / f"{CWE_ID}_add_patch_{str(i)}_{filename}"# +'/' +CWE_ID+"_"+"add_patch_"+str(i)+"_"+filename
                            with open (split_vul_file,"w+") as vulFun:
                                vulFun.write(code)
                            split_vul_dir_0 = SPLIT_ROOT / "vul0" / project
                            split_vul_dir_0.mkdir(parents=True, exist_ok=True)
                            # file_name: primary key (int)
                            file_name = str(file_name_counter)
                            split_vul_file_0 = split_vul_dir_0 / f"{file_name}.{only_type}"
                            with open (split_vul_file_0,"w+") as vulFun0:
                                vulFun0.write(code)
                            file_name_counter += 1
                        else:
                            split_nonevul_dir = SPLIT_ROOT / "nonevul" / project
                            split_nonevul_dir.mkdir(parents=True, exist_ok=True)
                            split_nonevul_file = split_nonevul_dir / f"add_patch_{str(i)}_{filename}"
                            with open (split_nonevul_file,"w+") as nonVulFun:
                                nonVulFun.write(code)
                    print("一共有 %d 个" % vul_number)
            has_vul = len(vul_funcs_for_row) > 0
            if not has_vul:
                new_row = row.to_dict()
                new_row["vul"] = 0
                new_row["vul_func_with_fix"] = ""
                new_row["file_name"] = ""
                expanded_rows.append(new_row)
            else:
                for func_code, line_num, only_type, filename in list(vul_funcs_for_row):
                    new_row = row.to_dict()
                    new_row["vul"] = 1
                    new_row["vul_func_with_fix"] = func_code
                    new_row["file_name"] = str(file_name_counter - len(list(vul_funcs_for_row)) + list(vul_funcs_for_row).index((func_code, line_num, only_type, filename)))
                    expanded_rows.append(new_row)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            print("reason", e)
            print("\n commit_id:"+str(commit_id)+ "！")
            print("\n index:"+str(index)+ "！")
            continue

    # expand rows: one record per vulnerable function (or single non-vul record)
    dataset_df = pd.DataFrame(expanded_rows)
    dataset_df.to_csv(args.output_csv, index=False)

if __name__ == "__main__":
    main()
