#!/bin/bash
# filter.sh - CVE 필터링 및 추출


# 1단계: 도메인, commit, project명 포함 URL 필터링
filter_by_project_url() {
    local json_file=$1
    local project=$2
    jq --arg project "$project" '
        [
            .vulnerabilities[] | .cve
            | {cve_id: .id, urls: [
                .references[].url
                | select(
                    ((test("git\\."+$project+"\\.org"; "i") and test("commit"; "i")))
                    or
                    (((test("github.com"; "i") or test("gitlab.com"; "i")) and test("commit"; "i") and test("/"+$project+"/"; "i")))
                )
            ]}
            | select(.urls | length > 0)
        ]
    ' "$json_file"
}

# 2단계: dedup - urls 배열에서 중복 제거
dedup_urls() {
    jq '[.[] | .urls |= unique]'
}

# 3단계: 개수 필터링 - unique link가 정확히 1개인 CVE만
filter_by_count() {
    jq 'select((.urls | length) == 1)'
}

# 4단계: CSV 형식으로 변환 (URL, CVE_ID, project 순서)
convert_to_csv() {
    local project="$1"
    jq -r --arg project "$project" '[.urls[0], .cve_id, $project] | @csv'
}

# 2단계: 개수 필터링 - unique link가 정확히 1개인 CVE만
filter_by_count() {
    jq -s '
      .[] 
      | .urls |= unique
      | select((.urls | length) == 1)
    '
}

# 3단계: CSV 형식으로 변환 (URL, CVE_ID 순서)
convert_to_csv() {
    jq -r '
      [.urls[0], .cve_id] | @csv
    '
}

# 특정 연도, 특정 프로젝트의 CVE 추출 (도메인+commit+project명 포함 URL 기준)
extract_cve_for_project() {
    local year=$1
    local project=$2
    local json_file="$INPUT_DIR/nvdcve-2.0-${year}.json"
    local year_dir="$OUTPUT_DIR/$project/$year"
    local output_csv="$year_dir/${project}_${year}_(codeLink,CVE ID).csv"

    # 현재 처리 중인 프로젝트-연도 표시
    echo "   🔍 [$project/$year] 처리 중..."

    # JSON 파일 존재 확인
    if [ ! -f "$json_file" ]; then
        echo "   ⚠️  [Warning] JSON 파일이 없습니다: $json_file"
        return 1
    fi

    # 연도별 디렉토리 생성
    setup_year_directories "$project" "$year"

    # 1단계: URL 필터링
    local project_url_filtered="$year_dir/1_project_url_filtered.json"
    filter_by_project_url "$json_file" "$project" > "$project_url_filtered"
    local filtered_count=$(jq 'length' "$project_url_filtered")
    echo "      → URL+도메인+프로젝트 필터링: $filtered_count 건"

    # 2단계: dedup
    local dedup_filtered="$year_dir/2_dedup_filtered.json"
    dedup_urls < "$project_url_filtered" > "$dedup_filtered"

    # 3단계: 개수 필터링
    local count_filtered="$year_dir/3_count_filtered.json"
    jq '[.[] | select((.urls | length) == 1) | {cve_id, url: .urls[0]}]' "$dedup_filtered" > "$count_filtered"
    local count_count=$(jq 'length' "$count_filtered")
    echo "      → 개수 필터링 (1개만): $count_count 건"


    # 4단계: CSV 변환 (project, commit_id 컬럼 포함)
    echo '"codeLink","CVE ID","project","commit_id"' > "$output_csv"
    jq -r --arg project "$project" '
        .[] |
        select(.url | test("/commit/")) |
        (.url | split("/commit/") | .[1]) as $commit_id |
        [.url, .cve_id, $project, $commit_id] | @csv
    ' "$count_filtered" >> "$output_csv"

    echo "   ✅ [$project/$year] 추출 완료: $count_count 건"
    return 0
}

# 빈 프로젝트 폴더 정리
cleanup_empty_projects() {
    local target_list=("$@")
    
    for proj in "${target_list[@]}"; do
        # 프로젝트 폴더 내 빈 연도 폴더 삭제
        find "$OUTPUT_DIR/$proj" -type d -empty -delete 2>/dev/null
        
        # 프로젝트 폴더도 비어있으면 삭제
        rmdir "$OUTPUT_DIR/$proj" 2>/dev/null
    done
}

# 모든 연도와 모든 프로젝트에 대해 CVE 추출
extract_all_cves() {
    local target_list=("$@")
    
    for year in $(seq $START_YEAR $END_YEAR); do
        echo ""
        echo "📅 [Processing Year: $year]"
        
        # 다운로드 및 압축 해제
        if ! download_and_extract "$year"; then
            echo "   ⏭️  [Skip] ${year}년 건너뜁니다."
            continue
        fi
        
        # 각 프로젝트별 필터링
        for proj in "${target_list[@]}"; do
            extract_cve_for_project "$year" "$proj"
        done
    done
}
