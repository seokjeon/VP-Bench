#!/bin/bash
# merge.sh - 연도별 데이터 통합

# 특정 프로젝트의 모든 연도 데이터를 통합
merge_project_data() {
    local project=$1
    local merged_file="$OUTPUT_DIR/$project/VP-Bench_${project}_(codeLink,CVE ID).csv"

    # 헤더 생성 (project 컬럼 포함)
    echo '"codeLink","CVE ID","project","commit_id"' > "$merged_file"

    local merge_count=0
    for year in $(seq $START_YEAR $END_YEAR); do
        local year_csv="$OUTPUT_DIR/$project/$year/${project}_${year}_(codeLink,CVE ID).csv"
        if [ -f "$year_csv" ]; then
            tail -n +2 "$year_csv" >> "$merged_file"
            merge_count=$((merge_count + 1))
        fi
    done
    
    if [ "$merge_count" -gt 0 ]; then
        local total_rows=$(tail -n +2 "$merged_file" | wc -l)
        echo "🎉 [완료] $project -> $merged_file (총 $total_rows 건)"
    else
        echo "💨 [Skip] $project -> 데이터 없음"
        rm "$merged_file"
    fi
}

# 모든 프로젝트의 데이터 통합
merge_all_projects() {
    local target_list=("$@")
    
    echo ""
    echo "=============================================================================="
    echo "   🔄 최종 통합 작업 (Merge)"
    echo "=============================================================================="
    
    for proj in "${target_list[@]}"; do
        merge_project_data "$proj"
    done
    
    # 전체 프로젝트 통합 (all 모드일 때만)
    if [ "${#target_list[@]}" -gt 1 ]; then
        merge_all_into_one "${target_list[@]}"
    fi
}

# 모든 프로젝트를 하나의 파일로 통합
merge_all_into_one() {
    local target_list=("$@")
    local final_merged="$OUTPUT_DIR/VP-Bench_ALL_(codeLink,CVE ID).csv"

    echo ""
    echo "   🌐 전체 프로젝트 통합 중..."

    # 헤더 생성 (project 컬럼 포함)
    echo '"codeLink","CVE ID","project"' > "$final_merged"

    local total_projects=0
    local total_rows=0

    for proj in "${target_list[@]}"; do
        local proj_merged="$OUTPUT_DIR/$proj/VP-Bench_${proj}_(codeLink,CVE ID).csv"
        if [ -f "$proj_merged" ]; then
            tail -n +2 "$proj_merged" >> "$final_merged"
            total_projects=$((total_projects + 1))
        fi
    done
    
    if [ "$total_projects" -gt 0 ]; then
        total_rows=$(tail -n +2 "$final_merged" | wc -l)
        echo "   🎉 전체 통합 완료: $total_projects 개 프로젝트, 총 $total_rows 건"
        echo "   📄 $final_merged"
    else
        rm "$final_merged"
        echo "   💨 통합할 데이터 없음"
    fi
}
