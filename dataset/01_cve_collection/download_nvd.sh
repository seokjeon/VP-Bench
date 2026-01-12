#!/bin/bash
# download.sh - 데이터 다운로드 및 압축 해제

# 특정 연도의 NVD 데이터 다운로드 및 압축 해제
download_and_extract() {
    local year=$1
    local zip_file="nvdcve-2.0-${year}.json.zip"
    local json_file="nvdcve-2.0-${year}.json"
    local download_url="$BASE_URL/$zip_file"
    
    # input 폴더에 이미 JSON이 있으면 스킵
    if [ -f "$INPUT_DIR/$json_file" ]; then
        echo "   [Check] 이미 ${year}년 NVD CVE JSON 파일이 준비되어 있습니다."
        return 0
    fi
    
    # 아카이브에 압축 파일이 없으면 다운로드
    if [ ! -f "$ARCHIVE_DIR/$zip_file" ]; then
        echo "   [Download] $zip_file 다운로드 중..."
        wget -q --user-agent="Mozilla/5.0" "$download_url" || curl -s -A "Mozilla/5.0" -O "$download_url"
        
        if [ ! -f "$zip_file" ]; then
            echo "   ⚠️  [Warning] ${year}년도 데이터가 없습니다."
            return 1
        fi
        mv "$zip_file" "$ARCHIVE_DIR/"
    else
        echo "   [Check] 아카이브에 압축 파일이 존재합니다."
    fi
    
    # 압축 해제
    echo "   [Unzip] 압축 해제 중..."
    unzip -o -q "$ARCHIVE_DIR/$zip_file" -d "$INPUT_DIR/"
    
    # unzip 결과가 현재 폴더에 풀린 경우 이동
    if [ -f "$json_file" ]; then
        mv "$json_file" "$INPUT_DIR/"
    fi
    
    # 최종 확인
    if [ ! -f "$INPUT_DIR/$json_file" ]; then
        echo "   ❌ [Error] JSON 파일을 찾을 수 없습니다."
        return 1
    fi
    
    return 0
}
