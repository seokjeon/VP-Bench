#!/bin/bash
# VP-Bench 데이터셋 생성 워크플로우 (Step 1)
# Step 1: scrape_vpbench_test_cve.sh 실행

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASET_DIR="$SCRIPT_DIR"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 로그 디렉토리 생성 및 워크플로우 로그 기록
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR/dataset_pipeline"
LOG_FILE="$LOG_DIR/dataset_pipeline/$(date +"%Y%m%d_%H%M%S")_dataset_pipeline.log"

# 모든 출력을 로그 파일과 화면에 동시에 출력
exec > >(tee -a "$LOG_FILE") 2>&1
echo "[$(date)] Command: $0 $@"

# Step 1: codeLink, CVE ID, project 추출 (jasper만)
STEP1_OUT="$DATASET_DIR/output/jasper/VP-Bench_jasper_(codeLink,CVE ID).csv"
if [ -f "$STEP1_OUT" ]; then
    echo "Step 1 결과 파일이 이미 존재합니다. 스킵합니다."
else
    bash "$DATASET_DIR/scripts/scrape_vpbench_test_cve.sh" jasper
    echo "Step 1 완료: $STEP1_OUT 생성 여부를 확인하세요."
fi



# Step 2: files_changed, lang 컬럼 추가
STEP2_OUT="$DATASET_DIR/output/jasper/VP-Bench_jasper_files_changed.csv"
if [ -f "$STEP2_OUT" ]; then
    echo "Step 2 결과 파일이 이미 존재합니다. 스킵합니다."
else
    cd "$DATASET_DIR"
    python3 scripts/get_files_changed_with_lang.py
    echo "Step 2 완료: $STEP2_OUT 생성 여부를 확인하세요."
fi


# Step 3: vulnerable function 확장
STEP3_OUT="$DATASET_DIR/output/jasper/VP-Bench_jasper_files_changed_with_vulfunc.csv"
if [ -f "$STEP3_OUT" ]; then
    echo "Step 3 결과 파일이 이미 존재합니다. 스킵합니다."
else
    cd "$SCRIPT_DIR"
    python3 scripts/extract_functions.py \
        --input_csv "$DATASET_DIR/output/jasper/VP-Bench_jasper_files_changed.csv" \
        --output_csv "$DATASET_DIR/output/jasper/VP-Bench_jasper_files_changed_with_vulfunc.csv"
    echo "Step 3 완료: $STEP3_OUT 생성 여부를 확인하세요."
fi


# Step 4: flaw_line_index, processed_func 컬럼 추가
STEP4_IN="$DATASET_DIR/output/jasper/VP-Bench_jasper_files_changed_with_vulfunc.csv"
STEP4_OUT="$DATASET_DIR/output/jasper/VP-Bench_jasper_files_changed_with_targets.csv"
if [ -f "$STEP4_OUT" ]; then
    echo "Step 4 결과 파일이 이미 존재합니다. 스킵합니다."
else
    cd "$SCRIPT_DIR"
    python3 scripts/add_processed_columns.py --input-csv "$STEP4_IN" --output-csv "$STEP4_OUT"
    echo "Step 4 완료: $STEP4_OUT 생성 여부를 확인하세요."
fi

# Step 5: RealVul 형식 변환 (jasper_dataset.csv 생성)
STEP5_IN="$DATASET_DIR/output/jasper/VP-Bench_jasper_files_changed_with_targets.csv"
STEP5_OUT="$DATASET_DIR/output/jasper/jasper_dataset.csv"
if [ -f "$STEP5_OUT" ]; then
    echo "Step 5 결과 파일이 이미 존재합니다. 스킵합니다."
else
    mkdir -p "$SCRIPT_DIR/output/jasper/repository"
    cd "$SCRIPT_DIR"
    SLURM_TMPDIR="$SCRIPT_DIR/output/jasper/repository" python3 scripts/data_collection.py --input-csv "$STEP5_IN" --output-csv "$STEP5_OUT"
    echo "Step 5 완료: $STEP5_OUT 생성 여부를 확인하세요."
fi

# Step 5.5: all_functions pickle 생성
STEP55_OUT="$DATASET_DIR/output/jasper/all_functions/jasper_new_all_functions.pickle"
if [ -f "$STEP55_OUT" ]; then
    echo "Step 5.5 결과 파일이 이미 존재합니다. 스킵합니다."
else
    mkdir -p "$DATASET_DIR/output/jasper/all_functions"
    cd "$SCRIPT_DIR"
    python3 scripts/generate_all_functions.py --project jasper --lang c
    echo "Step 5.5 완료: $STEP55_OUT 생성 여부를 확인하세요."
fi

# Step 6: data_filtration.py 실행
STEP6_OUT="$DATASET_DIR/output/jasper/real_vul_functions_dataset.csv"
if [ -f "$STEP6_OUT" ]; then
    echo "Step 6 결과 파일이 이미 존재합니다. 스킵합니다."
else
    cd "$SCRIPT_DIR"
    python3 scripts/data_filtration.py --projects jasper
    echo "Step 6 완료: $STEP6_OUT 생성 여부를 확인하세요."
fi