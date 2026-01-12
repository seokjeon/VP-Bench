#!/bin/bash
# config.sh - 설정 파일

START_YEAR=2020
END_YEAR=2025
BASE_URL="https://nvd.nist.gov/feeds/json/cve/2.0"

# 정의된 프로젝트 전체 리스트
ALL_PROJECTS=("FFmpeg" "ImageMagick" "jasper" "krb5" "openssl" "php-src" "qemu" "tcpdump" "linux" "chrome") # Chrome: chromium

# 디렉토리 경로
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE_DIR="$BASE_DIR/archive"
INPUT_DIR="$BASE_DIR/input"
OUTPUT_DIR="$BASE_DIR/output"