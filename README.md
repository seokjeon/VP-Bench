# VP-Bench
## 개요
1. 환경 설정
2. 비교 도구 준비
3. 비교할 데이터 셋 준비
4. 실험 재현

## 1. 환경 설정
```bash
sudo apt update && sudo apt install -y bats universal-ctags jq
pip install -r requirements.txt
```

## 2. 비교 도구 준비
### 현재 실행 가능한 프로젝트 목록
- vuddy
- deepwukong
- linevul
- pdbert

### 실행 환경 구축 방법
`docker compose up -d --build {프로젝트 명}`

### 셸 접속
`docker compose exec {프로젝트 명} bash`

## 빌드 성공여부 검증
`bats ./docker/{프로젝트 명}/test_container.bats`

## 3. 비교할 데이터 셋 준비
### 사전 준비 사항
1. .venv 활성화
2. .env 파일 생성 및 설정 `GITHUB_TOKEN = {본인 깃헙 토큰 키 값}`
3. `bash ./dataset_pipeline/run.sh`
* 로그는 logs/dataset_pipeline에 기록

## 4. 실험 재현
Docker 빌드, 빌드 검증, 실험을 순차적으로 실행
* 로그는 logs/experiment에 기록

`bash ./experiment/run.sh -m {실험할 모델}`

사용 가능한 모델: `vuddy`, `deepwukong`, `linevul`, `pdbert`
- 전체 모델 지정 시, `all`
- 복수 모델 지정 시, `vuddy,deepwukong,linevul` (콤마로 구분, 띄어쓰기 없음)

