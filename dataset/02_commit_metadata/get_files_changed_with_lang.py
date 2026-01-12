import pandas as pd
import json
import time
import traceback
import sys
import cloudscraper
import ssl
import os
from dotenv import load_dotenv
from pathlib import Path

# .env 파일에서 환경 변수 로드
load_dotenv()
github_token = os.getenv('GITHUB_TOKEN')

BASE_DIR = Path(__file__).resolve().parent.parent

if not github_token:
    print("[ERROR] .env 파일 또는 GITHUB_TOKEN 환경변수가 없습니다. GitHub API를 사용할 수 없습니다.")
    sys.exit(1)

ssl._create_default_https_context = ssl._create_unverified_context
scraper = cloudscraper.create_scraper()

def get_response(url):
    try:
        resp = scraper.get(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Authorization': f'token {github_token}',
            'Accept': 'application/json'
        })
        return resp.json()
    except Exception:
        traceback.print_exc(file=sys.stdout)
        print(f"skip get_response: {url}")
        return None


# commit_id 기준 그룹화 및 CVE ID join 함수화
def group_by_commit_id(df):
    grouped = df.groupby("commit_id")
    new_rows = []
    for commit_id, group in grouped:
        cve_ids = ", ".join(group["CVE ID"].astype(str).unique())
        first_row = group.iloc[0].copy()
        first_row["CVE ID"] = cve_ids
        new_rows.append(first_row)
    return pd.DataFrame(new_rows)


# 각 행 처리 함수화 및 apply 활용
def process_row(row):
    codeLink = row["codeLink"]
    commit_id = row["commit_id"]
    start = codeLink.find("github.com") + len("github.com") # TODO: gitlab인 경우 핸들링
    end = codeLink.rfind("/commit")
    repo_path = codeLink[start:end]
    commit_url = f"https://api.github.com/repos{repo_path}/commits/{commit_id}"
    repo_url = f"https://api.github.com/repos{repo_path}"

    repo_response = get_response(repo_url)
    lang = repo_response.get("language") if repo_response else None # TODO: 여기도 dict 타입인지, language 키가 있는지 체크 필요

    response = get_response(commit_url)
    files_changed = None
    if response and isinstance(response, dict) and "files" in response:
        files_changed = "<_**next**_>".join([json.dumps(f) for f in response["files"]])
    return pd.Series({"lang": lang, "files_changed": files_changed})


if __name__ == "__main__":
    # output/jasper/ 기준 경로 지정
    input_path = BASE_DIR / "output" / "jasper" / "VP-Bench_jasper_(codeLink,CVE ID).csv"
    output_path = BASE_DIR / "output" / "jasper" / "VP-Bench_jasper_files_changed.csv"
    df = pd.read_csv(input_path)

    if "commit_id" in df.columns:
        df = group_by_commit_id(df)

    df[["lang", "files_changed"]] = df.apply(process_row, axis=1)

    # 결과 저장
    df.to_csv(output_path, index=False)
    print("완료")