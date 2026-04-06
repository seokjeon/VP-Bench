#!/bin/bash

set -euo pipefail

DOWNLOADS_DIR="downloads"

# RealVul Train 데이터셋 준비 함수 (vpbench | realvul)
prepare_dataset() {
    local variant="${1:-vpbench}"
    case "$variant" in
        vpbench) 
            DS_NAME="VP-Bench_Test_Dataset";;
        realvul) 
            DS_NAME="VP-Bench_Train_Dataset";;
        *)
            echo "Error: invalid dataset source '$variant' (use 'vpbench' or 'realvul')"
            exit 1
            ;;
    esac

    mkdir -p "$DOWNLOADS_DIR/RealVul/datasets/$DS_NAME"

    # 작업 디렉토리를 보존하기 위해 pushd/popd 사용
    pushd "$DOWNLOADS_DIR/RealVul/datasets/$DS_NAME" > /dev/null

    local input_root="../../../../dataset_pipeline/output/$variant"
    # Real_Vul_data.csv
    if [ ! -f "Real_Vul_data.csv" ]; then
        echo "  - Real_Vul_data.csv 가져오는 중... (from $input_root)"
        if [ -f "$input_root/Real_Vul_data.csv" ]; then
            cp "$input_root/Real_Vul_data.csv" .
        else
            echo "Error: 소스에서 Real_Vul_data.csv를 찾을 수 없습니다: $input_root"
            popd > /dev/null
            exit 1
        fi
    else
        echo "  - Real_Vul_data.csv 이미 존재 (스킵)"
    fi

    popd > /dev/null
}

echo "=== LineVul 데이터 준비 스크립트 ==="

# 디렉토리 구조 생성
echo "[1/5] 디렉토리 구조 생성..."
mkdir -p "$DOWNLOADS_DIR/LineVul/models"
mkdir -p "$DOWNLOADS_DIR/RealVul/datasets"

# RealVul 공통 데이터셋 (이미 존재하면 스킵)
echo "[2/5] RealVul 데이터셋 다운로드..."
prepare_dataset realvul
echo $PWD
wget -nc -P "$DOWNLOADS_DIR/RealVul/datasets/" https://github.com/seokjeon/VP-Bench/releases/download/RealVul_Dataset/jasper_dataset.csv
wget -nc -P "$DOWNLOADS_DIR/RealVul/datasets/" https://github.com/seokjeon/VP-Bench/releases/download/RealVul_Dataset/jasper_source_code.tar.gz
tar -xf $DOWNLOADS_DIR/RealVul/datasets/jasper_source_code.tar.gz -C "$DOWNLOADS_DIR/RealVul/datasets/"

# Extended RealVul-FuncPair (이미 존재하면 스킵)
echo "[2.5/5] Extended RealVul-FuncPair 데이터셋 다운로드..."
/home/mjbin/lab/VP-Bench/baseline/RealVul/Experiments/LineVul/extended_realvul

EXTENDED_REALVUL_DIR="$DOWNLOADS_DIR/LineVul/extended_realvul"
EXTENDED_REALVUL_FILE="$EXTENDED_REALVUL_DIR/all_projects_vul_patch_dataset.csv"
EXTENDED_REALVUL_URL="https://github.com/seokjeon/VP-Bench/releases/download/VP-Bench_Test_Dataset/all_projects_vul_patch_dataset.csv"

echo "  [Extended RealVul] 처리 중..."
mkdir -p "$EXTENDED_REALVUL_DIR"
if [ -s "$EXTENDED_REALVUL_FILE" ]; then
    echo "    - all_projects_vul_patch_dataset.csv 이미 존재 (스킵)"
else
    echo "    - all_projects_vul_patch_dataset.csv 다운로드 중..."
    rm -f "$EXTENDED_REALVUL_FILE"
    wget -O "$EXTENDED_REALVUL_FILE" "$EXTENDED_REALVUL_URL"
    echo "    - 다운로드 완료"
fi

# LineVul 모델 다운로드
echo "[3/5] LineVul 모델 다운로드..."
echo $PWD
pushd "$DOWNLOADS_DIR/LineVul/models"
mkdir -p checkpoint-best-f1

if [ ! -f "checkpoint-best-f1/12heads_linevul_model.bin" ]; then
    echo "  - 모델 파일 다운로드 중..."
    gdown --fuzzy "https://drive.google.com/uc?id=1oodyQqRb9jEcvLMVVKILmu8qHyNwd-zH" \
        -O checkpoint-best-f1/12heads_linevul_model.bin
    echo "  - 모델 파일 다운로드 완료"
else
    echo "  - 모델 파일 이미 존재 (스킵)"
fi
popd

# VP-Bench 테스트 데이터셋 다운로드
echo "[4/5] VP-Bench 테스트 데이터셋 다운로드..."
prepare_dataset vpbench

# 파일 검증 (모든 데이터 준비 후, lock 파일 생성 이전)
echo ""
echo "[5/5] 파일 검증..."

test -f "$DOWNLOADS_DIR/RealVul/datasets/VP-Bench_Train_Dataset/Real_Vul_data.csv" || { echo "Error: VP-Bench_Train_Dataset/Real_Vul_data.csv를 찾을 수 없습니다"; exit 1; }
test -f "$DOWNLOADS_DIR/LineVul/models/checkpoint-best-f1/12heads_linevul_model.bin" || { echo "Error: 모델 파일을 찾을 수 없습니다"; exit 1; }
test -f "$DOWNLOADS_DIR/RealVul/datasets/VP-Bench_Test_Dataset/Real_Vul_data.csv" || { echo "Error: VP-Bench_Test_Dataset/Real_Vul_data.csv를 찾을 수 없습니다"; exit 1; }
test -f "$DOWNLOADS_DIR/RealVul/datasets/jasper_dataset.csv" || { echo "Error: jasper_dataset.csv를 찾을 수 없습니다"; exit 1; }
test -d "$DOWNLOADS_DIR/RealVul/datasets/source_code" || { echo "Error: source_code를 찾을 수 없습니다"; exit 1; }

echo "✅ 모든 파일 검증 완료!"

# TODO: datasets.lock.json 생성 기능 추가 예정
# - 다운로드한 모든 파일의 메타데이터(URL, SHA256) 기록
# - 데이터 무결성 검증 및 버전 관리용

echo ""
echo "=========================================="
echo "✅ 모든 데이터 준비 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "  1. docker compose down linevul"
echo "  2. docker compose up -d linevul"
echo "  3. bats ./docker/linevul/test_container.bats"
