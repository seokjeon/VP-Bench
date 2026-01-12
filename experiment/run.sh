#!/bin/bash

# argument for selecting models
MODELS=("deepwukong" "linevul" "pdbert" "vuddy")
SELECTED_MODELS=()
SUCCESSFUL_MODELS=()

# 로그 디렉토리 및 파일 설정
LOG_DIR="logs/experiment"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/$(date +"%Y%m%d_%H%M%S")_experiment.log"

# 모든 출력을 로그 파일과 화면에 동시에 출력
exec > >(tee -a "$LOG_FILE") 2>&1
echo "[$(date)] Command: $0 $@"

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--models)
            if [ "$2" = "all" ]; then
                SELECTED_MODELS=("${MODELS[@]}")
            else
                IFS=',' read -ra SELECTED_MODELS <<< "$2"
            fi
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ ${#SELECTED_MODELS[@]} -eq 0 ]; then
    echo "No models specified. Please use -m or --models to specify models."
    exit 1
fi

echo "Selected models: ${SELECTED_MODELS[*]}"

for model in "${SELECTED_MODELS[@]}"; do
    echo "Building Docker image for $model..."
    docker compose down "$model" || true
    docker compose up -d "$model" || { echo "Build failed for $model"; exit 1; }

    echo "Testing Docker container for $model..."
    bats "./docker/$model/test_container.bats" || { echo "Test failed for $model"; continue; }

    echo "$model setup and test completed."
    SUCCESSFUL_MODELS+=("$model")
done

echo ""
echo "Successful models: ${SUCCESSFUL_MODELS[*]}"

for model in "${SUCCESSFUL_MODELS[@]}"; do
    echo "Running experiment for $model..."
    bash "./experiment/scripts/run_${model}.sh"
done
