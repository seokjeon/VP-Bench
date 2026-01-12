#!/bin/bash
# utils.sh - 유틸리티 함수들

# 프로젝트별 output 디렉토리 생성
setup_directories() {
    local target_list=("$@")
    
    mkdir -p "$ARCHIVE_DIR" "$INPUT_DIR" "$OUTPUT_DIR"
    
    for proj in "${target_list[@]}"; do
        mkdir -p "$OUTPUT_DIR/$proj"
    done
}

# 프로젝트-연도별 분석 결과 폴더 생성
setup_year_directories() {
    local project=$1
    local year=$2
    
    mkdir -p "$OUTPUT_DIR/$project/$year"
}

# 배너 출력
print_banner() {
    local target_list=("$@")
    
    echo "=============================================================================="
    echo "   NVD 기반 취약점(Code Link) 추출 파이프라인"
    echo "   - 대상: ${target_list[*]}"
    echo "   - 기간: $START_YEAR ~ $END_YEAR"
    echo "=============================================================================="
}
