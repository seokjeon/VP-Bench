#!/bin/bash
# VP-Bench 데이터셋 생성 워크플로우 (Step 1)
# Step 1: scrape_vpbench_test_cve.sh 실행

# 디렉토리 경우
set -a
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARCHIVE_DIR="$BASE_DIR/archive"
INPUT_DIR="$BASE_DIR/input"
OUTPUT_BASE="$BASE_DIR/output"
SCRIPT_DIR="$BASE_DIR/scripts"
PROJECT_ROOT="$(cd "$BASE_DIR/.." && pwd)"
CACHE_DIR="$BASE_DIR/cache"  # 공유 캐시 디렉토리
REPO_CACHE_DIR="$CACHE_DIR/repositories"  # Git repository 캐시
set +a

LOG_DIR="$PROJECT_ROOT/logs/dataset_pipeline"
PROJECTS=("FFmpeg" "ImageMagick" "jasper" "krb5" "openssl" "php-src" "qemu" "tcpdump" "linux" "Chrome")
SELECTED_PROJECTS=("jasper")  # 기본값
ORIG_ARGS=("$@")
MODE="vpbench"

declare -A PROJECT_REPO_NAME=(
  ["FFmpeg"]="FFmpeg"
  ["ImageMagick"]="ImageMagick"
  ["jasper"]="jasper"
  ["krb5"]="krb5"
  ["openssl"]="openssl"
  ["php-src"]="php-src"
  ["qemu"]="qemu"   
  ["tcpdump"]="tcpdump"
  ["linux"]="linux"
  ["Chrome"]="chromium"
)

# Git URLs 정의
declare -A PROJECT_GIT_URLS=(
  ["FFmpeg"]="https://github.com/FFmpeg/FFmpeg.git"
  ["ImageMagick"]="https://github.com/ImageMagick/ImageMagick.git"
  ["jasper"]="https://github.com/jasper-software/jasper.git"
  ["krb5"]="https://github.com/krb5/krb5.git"
  ["openssl"]="https://github.com/openssl/openssl.git"
  ["php-src"]="https://github.com/php/php-src.git"
  ["qemu"]="https://github.com/qemu/qemu.git"
  ["tcpdump"]="https://github.com/the-tcpdump-group/tcpdump.git"
  ["linux"]="https://github.com/torvalds/linux.git"
  ["Chrome"]="https://github.com/chromium/chromium.git"
)

usage() {
    echo "Usage: $0 [--projects <target_project>] [--mode <vpbench|realvul>]"
    echo "  --projects: 처리할 프로젝트 (기본값: jasper)"
    echo "              'all'을 지정하면 모든 프로젝트 처리"
    echo "  --mode: 출력 루트 모드 (vpbench|realvul, 기본값: vpbench)"
}

# 스텝 실행 함수
run_step() {
    local step_num=$1
    local output=$2
    local script=$3
    shift 3
    local args=("$@")
    
    if [ -f "$output" ]; then
        echo "Step $step_num 결과 파일이 이미 존재합니다. 스킵합니다."
    else
        "$SCRIPT_DIR/$script" "${args[@]}"
        if [[ "$output" == *.csv ]] && [[ $(wc -l < "$output") -le 1 ]]; then
            echo "Step $step_num 실패: $output 파일이 비어 있습니다."
            return 1
        fi
        echo "Step $step_num 완료: $output 생성 여부를 확인하세요."
    fi
    return 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --projects)
            if [ "$2" = "all" ]; then
                SELECTED_PROJECTS=("${PROJECTS[@]}")
            else
                IFS=',' read -ra SELECTED_PROJECTS <<< "$2"
            fi
            shift 2
            ;;
        --mode)
            if [ -n "$2" ]; then
                MODE="$2"
            fi
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

# 모든 출력을 로그 파일과 화면에 동시에 출력
mkdir -p "$LOG_DIR"
mkdir -p "$REPO_CACHE_DIR"  # 공유 repository 캐시 디렉토리 생성
exec > >(tee -a "$LOG_DIR/$(date +"%Y%m%d_%H%M%S")_dataset_pipeline.log") 2>&1
echo "[$(date)] Command: $0 ${ORIG_ARGS[*]}"

export OUTPUT_DIR="$OUTPUT_BASE/$MODE"
if [ "$MODE" = "vpbench" ]; then
    LABEL="test"
else # MODE = "realvul"
    LABEL="train_val"
fi

# 각 프로젝트마다 반복 처리
for PROJECT in "${SELECTED_PROJECTS[@]}"; do
    echo "=========================================="
    echo "Processing project: $PROJECT"
    echo "=========================================="
    
    # 프로젝트 output 디렉토리에 repository 심볼릭 링크 생성
    PROJECT_OUTPUT_DIR="$OUTPUT_DIR/$PROJECT"
    mkdir -p "$PROJECT_OUTPUT_DIR"
    REPO_NAME="${PROJECT_REPO_NAME[$PROJECT]}"
    REPO_LINK="$PROJECT_OUTPUT_DIR/repository"
    REPO_PATH="$REPO_CACHE_DIR/$REPO_NAME"
    GIT_URL="${PROJECT_GIT_URLS[$PROJECT]}"
    
    # 공유 캐시에 필요한 repository 미리 clone하기
    echo "=========================================="
    echo "공유 캐시 repository 준비 중..."
    echo "=========================================="
    
    if [ -d "$REPO_PATH/.git" ]; then
        echo "[✓] $REPO_NAME repository 이미 캐시됨: $REPO_PATH"
    else
        echo "[↓] $REPO_NAME clone 중: $GIT_URL"
        git clone --progress "$GIT_URL" "$REPO_PATH"
        if [ -d "$REPO_PATH/.git" ]; then
            echo "[✓] $REPO_NAME clone 완료"
        else
            echo "[✗] $REPO_NAME clone 실패!"
            exit 1
        fi
    fi

    # 기존 repository 디렉토리 처리
    if [ -e "$REPO_LINK" ] && [ ! -L "$REPO_LINK" ]; then
        echo "기존 repository 디렉토리를 백업합니다: ${REPO_LINK}.backup.$(date +%s)"
        mv "$REPO_LINK" "${REPO_LINK}.backup.$(date +%s)"
    fi
    
    # 심볼릭 링크 생성
    if [ ! -L "$REPO_LINK" ]; then
        mkdir -p "$(dirname "$REPO_LINK")"
        ln -s "$REPO_CACHE_DIR/$REPO_NAME" "$REPO_LINK"
        echo "[✓] 심볼릭 링크 생성: $REPO_LINK -> $REPO_CACHE_DIR/$REPO_NAME"
    else
        echo "[✓] 심볼릭 링크 이미 존재: $REPO_LINK"
    fi
    
    if [ "$MODE" = "vpbench" ]; then
        # Step 1: codeLink, CVE ID, project 추출
        STEP1_OUT="$PROJECT_OUTPUT_DIR/VP-Bench_${PROJECT}_(codeLink,CVE ID).csv"
        run_step 1 "$STEP1_OUT" "scrape_vpbench_test_cve.sh" "$PROJECT" || continue

        # Step 2: files_changed, lang 컬럼 추가
        STEP2_OUT="$PROJECT_OUTPUT_DIR/VP-Bench_${PROJECT}_files_changed.csv"
        run_step 2 "$STEP2_OUT" "get_files_changed_with_lang.py" --input "$STEP1_OUT" --output "$STEP2_OUT" || continue

        # Step 3: vulnerable function 확장
        STEP3_OUT="$PROJECT_OUTPUT_DIR/VP-Bench_${PROJECT}_files_changed_with_vulfunc.csv"
        run_step 3 "$STEP3_OUT" "extract_functions.py" --input "$STEP2_OUT" --output "$STEP3_OUT" --project "$PROJECT" --output-dir "$OUTPUT_DIR" || continue

        # Step 4: flaw_line_index, processed_func 컬럼 추가
        STEP4_OUT="$PROJECT_OUTPUT_DIR/VP-Bench_${PROJECT}_files_changed_with_targets.csv"
        run_step 4 "$STEP4_OUT" "add_processed_columns.py" --input "$STEP3_OUT" --output "$STEP4_OUT" || continue

        # Step 5: RealVul 형식 변환 (project_dataset.csv 생성)
        STEP5_OUT="$PROJECT_OUTPUT_DIR/${PROJECT}_dataset.csv"
        run_step 5 "$STEP5_OUT" "data_collection.py" --input "$STEP4_OUT" --mode "$MODE" --output "$STEP5_OUT" --project "$PROJECT" --output-dir "$OUTPUT_DIR" --labels "$LABEL" || continue

    fi

    if [ "$MODE" = "realvul" ]; then
        # TODO: dataset_type을 라벨에 맞게 지정
        mkdir -p "$PROJECT_OUTPUT_DIR"
        DATASET_CACHE_DIR="$CACHE_DIR/realvul_datasets"
        SOURCE_CODE_CACHE_DIR="$CACHE_DIR/realvul_source_codes"
        mkdir -p "$DATASET_CACHE_DIR" "$SOURCE_CODE_CACHE_DIR"

        STEP5_OUT="$PROJECT_OUTPUT_DIR/${PROJECT}_dataset.csv"

        # 이전에 생성된 RealVul 데이터셋과 소스코드 다운로드
        if [ ! -f "$DATASET_CACHE_DIR/${PROJECT}_dataset.csv.old" ]; then
            wget -O "$DATASET_CACHE_DIR/${PROJECT}_dataset.csv.old" "https://github.com/seokjeon/VP-Bench/releases/download/RealVul_Dataset/${PROJECT}_dataset.csv"
        fi
        cp "$DATASET_CACHE_DIR/${PROJECT}_dataset.csv.old" "$PROJECT_OUTPUT_DIR"

        if [ ! -f "$SOURCE_CODE_CACHE_DIR/${PROJECT}_source_code.tar.gz.old" ]; then
            wget -O "$SOURCE_CODE_CACHE_DIR/${PROJECT}_source_code.tar.gz.old" "https://github.com/seokjeon/VP-Bench/releases/download/RealVul_Dataset/${PROJECT}_source_code.tar.gz"
        fi
        cp "$SOURCE_CODE_CACHE_DIR/${PROJECT}_source_code.tar.gz.old" "$PROJECT_OUTPUT_DIR"
        
        # 이전 소스코드 압축 해제
        if [ ! -d "$PROJECT_OUTPUT_DIR/source_code.old" ]; then
            tar -xf "$PROJECT_OUTPUT_DIR/${PROJECT}_source_code.tar.gz.old" -C "$PROJECT_OUTPUT_DIR"
            mv "$PROJECT_OUTPUT_DIR/source_code" "$PROJECT_OUTPUT_DIR/source_code.old"
        fi

        # Step 5: RealVul 형식 변환 (project_dataset.csv 생성)
        run_step 5 "$STEP5_OUT" "data_collection.py" --input "$STEP5_OUT.old" --mode "$MODE" --output "$STEP5_OUT" --project "$PROJECT" --output-dir "$OUTPUT_DIR" --labels "$LABEL" || continue
    fi

    # Step 6: all_functions pickle 생성
    STEP6_OUT="$PROJECT_OUTPUT_DIR/all_functions/${PROJECT}_new_all_functions.pkl"
    run_step 6 "$STEP6_OUT" "generate_all_functions.py" --input "$PROJECT_OUTPUT_DIR/source_code" --output "$STEP6_OUT" --project "$PROJECT" || continue

done

# Step 7: data_filtration.py 실행
STEP7_OUT="$OUTPUT_DIR/Real_Vul_data.csv"
run_step 7 "$STEP7_OUT" "data_filtration.py" --output-dir "$OUTPUT_DIR" --projects "${SELECTED_PROJECTS[@]}"