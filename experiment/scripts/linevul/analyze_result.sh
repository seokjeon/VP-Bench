#!/bin/bash

# =============================================================================
# LineVul 모델 분석 스크립트
# 독립적으로 모델을 테스트하여 Confusion Matrix 분석 및 FN/FP 샘플 추출
# 본 스크립트는 모델 학습, 테스트가 종료된 후 실행합니다.
# =============================================================================

set -e

# 분석 스크립트 경로 (호스트 경로)
SCRIPT_DIR="experiment/scripts/linevul"
ANALYSIS_SCRIPT="$SCRIPT_DIR/analyze_prediction.py"

# Arguments (Docker 컨테이너 내부 경로)
DATASET_PATH="/app/RealVul/Dataset"
MODEL_DIR="/app/RealVul/Experiments/LineVul/best_model"
OUTPUT_DIR="/app/RealVul/Experiments/LineVul"
BATCH_SIZE=8 # 필요시 수정하세요.


echo "=== LineVul 모델 세부분석 시작 ==="
echo ""
echo "데이터셋 경로: $DATASET_PATH"
echo "모델 경로: $MODEL_DIR"
echo "출력 경로: $OUTPUT_DIR"
echo "분석 스크립트: $ANALYSIS_SCRIPT"
echo ""

# 1. 분석 스크립트를 Docker 컨테이너로 복사
echo "[1/2] 분석 스크립트 복사 중..."

docker cp "$ANALYSIS_SCRIPT" linevul:/app/analyze_prediction.py
echo "  - 복사 완료: /app/analyze_prediction.py"


# 2. 분석 수행
echo ""
echo "[2/2] 정밀 분석 수행 (FN/FP 샘플 추출)..."
echo ""

time docker exec linevul bash -c "
    cd /app && python /app/analyze_prediction.py \\
        --dataset-path $DATASET_PATH \\
        --model-dir $MODEL_DIR \\
        --output-dir $OUTPUT_DIR \\
        --batch-size $BATCH_SIZE"

echo ""
echo "=== LineVul 모델 분석 완료 ==="
echo ""
echo "분석 결과 파일 위치:"
echo "  - Docker 내부: $OUTPUT_DIR/prediction_analysis.json"
echo "  - 로컬 (마운트): downloads/LineVul/experiments/prediction_analysis.json"
