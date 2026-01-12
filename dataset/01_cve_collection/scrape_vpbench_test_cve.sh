#!/bin/bash
# run_cve_pipeline.sh - 메인 실행 스크립트

# 현재 스크립트의 디렉토리 경로 가져오기 (01_cve_collection 기준)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATASET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$DATASET_DIR/.." && pwd)"


# 모듈 로드 (같은 디렉토리 내 모듈들)
for f in nvd_config nvd_utils download_nvd filter_nvd merge_nvd; do
    source "$SCRIPT_DIR/$f.sh"
done

# ==============================================================================
# 메인 실행 로직
# ==============================================================================

# 인자 및 로그 파일 설정
TARGET=${1:-all}
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +"%Y%m%d_%H%M%S")_${TARGET}_execution.log"

{
    if [ "$TARGET" = "all" ]; then
        TARGET_LIST=("${ALL_PROJECTS[@]}")
        echo "🎯 전체 프로젝트 (${#ALL_PROJECTS[@]})"
    else
        TARGET_LIST=("$TARGET")
        echo "🎯 단일 프로젝트 '$TARGET'"
    fi

    setup_directories "${TARGET_LIST[@]}"
    print_banner "${TARGET_LIST[@]}"
    extract_all_cves "${TARGET_LIST[@]}"
    merge_all_projects "${TARGET_LIST[@]}"
    cleanup_empty_projects "${TARGET_LIST[@]}"
    echo "✨ 완료!"
} | tee "$LOG_FILE"