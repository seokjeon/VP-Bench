#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(pwd)"
DOWNLOADS_DIR="$PROJECT_ROOT/downloads"

# RealVul Train 데이터셋 준비 함수 (vpbench | realvul)
# 데이터를 PDBERT 경로 구조로 복사
prepare_dataset() {
    local variant="${1:-vpbench}"
    local target_subdir
    case "$variant" in
        vpbench) 
            target_subdir="vpbench";;
        realvul) 
            target_subdir="realvul";;
        *)
            echo "Error: invalid dataset source '$variant' (use 'vpbench' or 'realvul')"
            exit 1
            ;;
    esac

    local target_dir="$DOWNLOADS_DIR/PDBERT/data/datasets/extrinsic/vul_detect/$target_subdir/Real_Vul"
    mkdir -p "$target_dir"

    # 작업 디렉토리를 보존하기 위해 pushd/popd 사용
    pushd "$target_dir" > /dev/null

    local input_root="$PROJECT_ROOT/dataset_pipeline/output/$variant"
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

    # all_source_code 복사 (현재 사용 안함 - vpbench에는 all_source_code가 없음)
    # if [ ! -d "all_source_code" ]; then
    #     echo "  - all_source_code 가져오는 중... (from $input_root)"
    #     cp -r "$input_root/all_source_code" .
    # else
    #     echo "  - all_source_code 이미 존재 (스킵)"
    # fi

    popd > /dev/null
}

echo "=== PDBERT 데이터 준비 스크립트 ==="

# 디렉토리 구조 생성
echo "[1/6] 디렉토리 구조 생성..."
mkdir -p "$DOWNLOADS_DIR/PDBERT"
mkdir -p "$DOWNLOADS_DIR/PDBERT/pretrain/microsoft"
mkdir -p "$DOWNLOADS_DIR/PDBERT/downstream/microsoft"
mkdir -p "$DOWNLOADS_DIR/PDBERT/data/datasets/extrinsic/vul_detect"

# ===================================================================
# PDBERT_data.zip 다운로드 (pdbert-base 모델 + 데이터셋 포함, 약 1.1GB)
# ===================================================================
echo "[2/6] PDBERT_data.zip 다운로드..."
cd "$DOWNLOADS_DIR/PDBERT"

if [ -d "data/models/pdbert-base" ]; then
    echo "  - pdbert-base 이미 존재 (스킵)"
elif [ -f "PDBERT_data.zip" ]; then
    FILE_SIZE=$(stat -c%s "PDBERT_data.zip" 2>/dev/null || stat -f%z "PDBERT_data.zip" 2>/dev/null || echo "0")
    if [ "$FILE_SIZE" -gt 1000000000 ]; then
        echo "  - PDBERT_data.zip 이미 다운로드됨 (size: $FILE_SIZE bytes)"
    else
        echo "  - PDBERT_data.zip 파일 크기가 작음, 재다운로드..."
        rm -f PDBERT_data.zip
        wget -nc https://github.com/MJ-bin/PDBERT/releases/download/v0.1.0/PDBERT_data.zip
    fi
else
    echo "  - PDBERT_data.zip 다운로드 중 (약 1.1GB)..."
    wget -nc https://github.com/MJ-bin/PDBERT/releases/download/v0.1.0/PDBERT_data.zip
fi

# PDBERT_data.zip 압축 해제
echo "[3/6] PDBERT_data.zip 압축 해제..."
if [ -d "data/models/pdbert-base" ]; then
    echo "  - pdbert-base 이미 존재 (스킵)"
else
    if [ -f "PDBERT_data.zip" ]; then
        echo "  - 압축 해제 중 (시간이 다소 소요될 수 있습니다)..."
        7z x PDBERT_data.zip -y
        mkdir -p ./data
        cp -r PDBERT_data/data/* ./data/
        rm -rf PDBERT_data
        echo "  - 압축 해제 완료"
    else
        echo "  - [ERROR] PDBERT_data.zip 파일을 찾을 수 없습니다"
        exit 1
    fi
fi

# ===================================================================
# RealVul 데이터셋 준비 (realvul + vpbench 통합 처리)
# ===================================================================
# 데이터셋 variant 배열: "variant:target_subdir:라벨"
DATASET_VARIANTS=(
    "realvul:realvul:RealVul (Train)"
    "vpbench:vpbench:VP-Bench (Test)"
)

echo "[4/6] 데이터셋 준비 (realvul, vpbench)..."
for entry in "${DATASET_VARIANTS[@]}"; do
    IFS=':' read -r variant target_subdir label <<< "$entry"
    target_dir="$DOWNLOADS_DIR/PDBERT/data/datasets/extrinsic/vul_detect/$target_subdir/Real_Vul"
    
    echo "  [$label] 처리 중..."
    mkdir -p "$target_dir"
    
    # Real_Vul_data.csv 확인
    if [ -f "$target_dir/Real_Vul_data.csv" ]; then
        echo "    - Real_Vul_data.csv 이미 존재 (스킵)"
    else
        echo "    - prepare_dataset '$variant' 호출..."
        prepare_dataset "$variant"
        
        # 결과 확인
        if [ -f "$target_dir/Real_Vul_data.csv" ]; then
            echo "    - Real_Vul_data.csv 복사 완료"
        else
            echo "    - [WARNING] Real_Vul_data.csv를 찾을 수 없습니다"
        fi
    fi
done

EXTENDED_REALVUL_DIR="$DOWNLOADS_DIR/PDBERT/data/datasets/extrinsic/vul_detect/extended_realvul"
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

# ===================================================================
# CodeBERT 모델 다운로드 (pretrain & downstream)
# ===================================================================
echo "[5/6] CodeBERT pretrain 모델 다운로드..."
cd "$DOWNLOADS_DIR/PDBERT/pretrain/microsoft"

if [ -d "codebert-base" ]; then
    echo "  - codebert-base (pretrain) 이미 존재 (스킵)"
else
    echo "  - codebert-base 클론 중..."
    git lfs install
    git clone https://huggingface.co/microsoft/codebert-base codebert-base
    echo "  - codebert-base (pretrain) 다운로드 완료"
fi

echo "[6/6] CodeBERT downstream 모델 다운로드..."
cd "$DOWNLOADS_DIR/PDBERT/downstream/microsoft"

if [ -d "codebert-base" ]; then
    echo "  - codebert-base (downstream) 이미 존재 (스킵)"
else
    echo "  - codebert-base 클론 중..."
    git lfs install
    git clone https://huggingface.co/microsoft/codebert-base codebert-base
    echo "  - codebert-base (downstream) 다운로드 완료"
fi

echo "✅ 모든 파일 검증 완료!"
echo ""
echo "=========================================="
echo "✅ 모든 데이터 준비 완료!"
echo "prepare.sh 완료"
echo "=========================================="
echo ""
echo "다음 단계:"
echo "  1. docker compose down pdbert"
echo "  2. docker compose up -d pdbert"
echo "  3. bats ./docker/pdbert/test_container.bats"
