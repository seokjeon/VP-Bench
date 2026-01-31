#!/usr/bin/env python3
"""
LineVul 모델 정밀 분석 스크립트
- Confusion Matrix (TP, TN, FP, FN) 계산
- FN/FP 샘플 추출 및 저장
- baseline을 수정하지 않고 독립적으로 실행

사용법:
    python analyze_prediction.py \
        --dataset-path /app/RealVul/Dataset \
        --model-dir /app/RealVul/Experiments/LineVul/best_model \
        --output-dir /app/RealVul/Experiments/LineVul \
        --batch-size 8
"""
import sys
import json
import argparse
import pickle
from os.path import join, exists
from pprint import pprint

import numpy as np
import torch
from tqdm import tqdm
from transformers import (
    RobertaForSequenceClassification,
    RobertaTokenizer,
    TrainingArguments,
    Trainer
)
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, matthews_corrcoef, confusion_matrix
)


def parse_args():
    parser = argparse.ArgumentParser(description='LineVul 모델 정밀 분석')
    parser.add_argument('--dataset-path', required=True, help='데이터셋 경로 (pickle 파일 위치)')
    parser.add_argument('--model-dir', required=True, help='best_model 디렉토리 경로')
    parser.add_argument('--output-dir', required=True, help='분석 결과 저장 경로')
    parser.add_argument('--batch-size', type=int, default=8, help='배치 크기')
    parser.add_argument('--cuda', type=int, default=0, help='CUDA 장치 (-1은 CPU)')
    return parser.parse_args()


def load_pickle_dataset(dataset_path, dataset_type='test'):
    """저장된 pickle 데이터셋 로드"""
    pickle_path = join(dataset_path, f'{dataset_type}_dataset.pkl')
    if not exists(pickle_path):
        raise FileNotFoundError(f"Pickle 파일을 찾을 수 없습니다: {pickle_path}")
    
    with open(pickle_path, 'rb') as f:
        dataset = pickle.load(f)
    return dataset


def predict_with_trainer(model, dataset, batch_size, cuda_device):
    """Trainer를 사용하여 예측 수행"""
    train_args = TrainingArguments(
        output_dir='/tmp/linevul_predict',
        per_device_eval_batch_size=batch_size,
        fp16=(cuda_device >= 0),
        dataloader_drop_last=False,
    )
    
    trainer = Trainer(model=model, args=train_args)
    
    print("예측 수행 중...")
    raw_pred, _, _ = trainer.predict(dataset)
    y_pred = np.argmax(raw_pred, axis=1)
    y_true = np.array(dataset.labels)
    
    return y_true, y_pred, raw_pred


def analyze_predictions(y_true, y_pred, raw_probs):
    """예측 결과 분석"""
    # Confusion Matrix 계산
    cm = confusion_matrix(y_true, y_pred)
    
    # 2x2 매트릭스 처리
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
    else:
        # 단일 클래스만 있는 경우 처리
        tn, fp, fn, tp = 0, 0, 0, 0
        if cm.shape == (1, 1):
            if y_true[0] == 0:
                tn = cm[0, 0]
            else:
                tp = cm[0, 0]
    
    # 메트릭 계산
    result_dict = {
        'Accuracy': float(accuracy_score(y_true, y_pred)),
        'Precision': float(precision_score(y_true, y_pred, average='binary', zero_division=0)),
        'Recall': float(recall_score(y_true, y_pred, average='binary', zero_division=0)),
        'F1-Score': float(f1_score(y_true, y_pred, average='binary', zero_division=0)),
        'MCC': float(matthews_corrcoef(y_true, y_pred)),
        'TP': int(tp),
        'TN': int(tn),
        'FP': int(fp),
        'FN': int(fn),
        'Total Samples': len(y_true),
    }
    
    # FN, FP 인덱스 찾기
    fn_indices = []
    fp_indices = []
    
    for i, (ref, pred) in enumerate(zip(y_true, y_pred)):
        if ref == 1 and pred == 0:
            fn_indices.append({
                'index': i,
                'predicted': int(pred),
                'actual': int(ref),
                'prob_vuln': float(raw_probs[i][1]),
                'prob_safe': float(raw_probs[i][0]),
            })
        elif ref == 0 and pred == 1:
            fp_indices.append({
                'index': i,
                'predicted': int(pred),
                'actual': int(ref),
                'prob_vuln': float(raw_probs[i][1]),
                'prob_safe': float(raw_probs[i][0]),
            })
    
    return result_dict, fn_indices, fp_indices


def main():
    args = parse_args()
    
    pickle_path = join(args.dataset_path, 'test_dataset.pkl')
    output_path = join(args.output_dir, 'prediction_analysis.json')
    
    print("=" * 80)
    print("LineVul 정밀 분석 시작")
    print("=" * 80)
    print(f"데이터: {pickle_path}")
    print(f"모델: {args.model_dir}")
    print(f"출력: {output_path}")
    print("=" * 80)
    
    # 모델 로드
    print("\n모델 로딩 중...")
    model = RobertaForSequenceClassification.from_pretrained(args.model_dir, num_labels=2)
    
    if args.cuda >= 0 and torch.cuda.is_available():
        model = model.cuda(args.cuda)
        print(f"CUDA 장치 {args.cuda} 사용")
    else:
        print("CPU 사용")
    
    # 데이터셋 로드
    print("테스트 데이터셋 로딩 중...")
    test_dataset = load_pickle_dataset(args.dataset_path, 'test')
    print(f"테스트 샘플 수: {len(test_dataset)}")
    
    # 예측 수행
    y_true, y_pred, raw_probs = predict_with_trainer(
        model, test_dataset, args.batch_size, args.cuda
    )
    
    # 분석 수행
    result_dict, fn_samples, fp_samples = analyze_predictions(y_true, y_pred, raw_probs)
    
    # 결과 출력
    print("\n" + "=" * 80)
    print("평가 결과:")
    print("=" * 80)
    pprint(result_dict)
    
    # 결과 저장
    analysis_result = {
        'summary': result_dict,
        'predictions': {
            'y_pred': y_pred.tolist(),
            'y_true': y_true.tolist(),
            'raw_probs': raw_probs.tolist(),
        },
        'fn_count': len(fn_samples),
        'fp_count': len(fp_samples),
        'fn_samples': fn_samples,
        'fp_samples': fp_samples,
    }
    
    with open(output_path, 'w') as f:
        json.dump(analysis_result, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 80}")
    print(f"분석 결과 저장: {output_path}")
    print(f"FN (놓친 취약점): {len(fn_samples)}개")
    print(f"FP (오탐): {len(fp_samples)}개")
    
    # FN 샘플 상위 10개 출력
    if fn_samples:
        print(f"\n{'=' * 80}")
        print("FN (False Negative) 샘플 상위 10개:")
        print("=" * 80)
        for i, sample in enumerate(fn_samples[:10]):
            print(f"  #{i+1}: index={sample['index']}, prob_vuln={sample['prob_vuln']:.4f}")
    
    # FP 샘플 상위 10개 출력
    if fp_samples:
        print(f"\n{'=' * 80}")
        print("FP (False Positive) 샘플 상위 10개:")
        print("=" * 80)
        for i, sample in enumerate(fp_samples[:10]):
            print(f"  #{i+1}: index={sample['index']}, prob_vuln={sample['prob_vuln']:.4f}")
    
    print(f"\n{'=' * 80}")
    print("분석 완료!")
    print("=" * 80)


if __name__ == '__main__':
    main()
