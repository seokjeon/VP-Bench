#!/usr/bin/env python3
from __future__ import annotations

"""
PDBERT 모델 정밀 분석 스크립트
- Confusion Matrix (TP, TN, FP, FN) 계산
- FN/FP 샘플 추출 및 저장
- 다운스트림 분류기가 실제로 사용하는 CLS feature export 및 t-SNE 시각화
"""
import argparse
import json
import sys
from pathlib import Path
from pprint import pprint

import matplotlib
import numpy as np
import torch
from allennlp.data.data_loaders import MultiProcessDataLoader
from allennlp.models.model import Model
from sklearn import manifold
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
)
from tqdm import tqdm

sys.path.extend(['/PDBERT/downstream', '/PDBERT/downstream/..'])

from downstream import *
from utils.allennlp_utils.build_utils import build_dataset_reader_from_config

matplotlib.use('Agg')
import matplotlib.pyplot as plt

try:
    import seaborn as sns
except ModuleNotFoundError:
    sns = None

if sns is not None:
    sns.set(rc={'figure.figsize': (11.7, 8.27)})
else:
    plt.rcParams['figure.figsize'] = (11.7, 8.27)

FEATURE_BASENAME = 'test_last_hidden_state_vectors'
RAW_MODEL_EVAL_DIRNAME = 'raw_model_eval'
COMBINED_TEST_TSNE_BASENAME = 'combined_test_last_hidden_state_vectors'
DEFAULT_TSNE_FIGSIZE = (10, 10)
DEFAULT_TSNE_MARKER_SIZE = 3
DEFAULT_TSNE_MARKER_LINEWIDTH = 0.2
DEFAULT_TSNE_MARKER_ALPHA = 0.35
DEFAULT_TSNE_MARKER_ZORDER = 2
DEFAULT_TSNE_SHUFFLE_SEED = 0
BEFORE_NON_VULN_TSNE_COLOR = '#31a354'
AFTER_NON_VULN_TSNE_COLOR = '#3182bd'
BEFORE_VULN_TSNE_COLOR = '#cb181d'
AFTER_VULN_TSNE_COLOR = '#f16913'
SINGLE_TSNE_TITLE = 'PDBERT t-SNE on SARD-Juliet SA TracePair'
COMBINED_TSNE_TITLE = 'PDBERT t-SNE on SARD-Juliet SA TracePair (Combined)'
DEFAULT_LEGEND_FONT_SIZE = 12
DEFAULT_LEGEND_Y = 1.03


def parse_args():
    parser = argparse.ArgumentParser(description='PDBERT 모델 정밀 분석')
    parser.add_argument('--data-path', required=True, help='테스트 데이터 경로')
    parser.add_argument('--model-dir', required=True, help='모델 디렉토리 경로')
    parser.add_argument('--batch-size', type=int, default=32, help='배치 크기')
    parser.add_argument('--cuda', type=int, default=0, help='CUDA 장치 (-1은 CPU)')
    parser.add_argument('--output', default=None, help='분석 결과 저장 경로')
    return parser.parse_args()


def build_feature_artifact_paths(model_dir: str) -> tuple[Path, Path, Path]:
    base_path = Path(model_dir) / FEATURE_BASENAME
    return (
        base_path.with_suffix('.npz'),
        Path(f'{base_path}.jpeg'),
        Path(f'{base_path}-tsne-features.json'),
    )


def _resolve_group_style(stage_label: str, target_value: int) -> dict:
    if stage_label == 'Before Fine-tuned' and target_value == 0:
        return {'color': BEFORE_NON_VULN_TSNE_COLOR}
    if stage_label == 'After Fine-tuned' and target_value == 0:
        return {'color': AFTER_NON_VULN_TSNE_COLOR}
    if stage_label == 'Before Fine-tuned' and target_value == 1:
        return {'color': BEFORE_VULN_TSNE_COLOR}
    return {'color': AFTER_VULN_TSNE_COLOR}


def _build_group_spec(
    stage_label: str,
    target_value: int,
    *,
    model_value: int | None = None,
    zorder: int | None = None,
) -> dict:
    style = _resolve_group_style(stage_label, target_value)
    spec = {
        'label': f"{stage_label} / {'Vuln' if target_value == 1 else 'Non-Vuln'}",
        'target_value': target_value,
        'marker': 'o',
        'facecolor': style['color'],
        'edgecolor': style['color'],
        'alpha': DEFAULT_TSNE_MARKER_ALPHA,
        'linewidth': DEFAULT_TSNE_MARKER_LINEWIDTH,
    }
    if model_value is not None:
        spec['model_value'] = model_value
    spec['zorder'] = DEFAULT_TSNE_MARKER_ZORDER if zorder is None else zorder
    return spec


def _resolve_single_group_specs(title: str | None) -> list[dict]:
    title_str = str(title) if title is not None else ''
    is_raw_model = RAW_MODEL_EVAL_DIRNAME in title_str
    stage_label = 'Before Fine-tuned' if is_raw_model else 'After Fine-tuned'
    return [
        _build_group_spec(stage_label, 0),
        _build_group_spec(stage_label, 1),
    ]


def _resolve_paired_group_specs() -> list[dict]:
    return [
        _build_group_spec(
            'Before Fine-tuned',
            1,
            model_value=1,
        ),
        _build_group_spec(
            'After Fine-tuned',
            1,
            model_value=0,
        ),
        _build_group_spec(
            'Before Fine-tuned',
            0,
            model_value=1,
        ),
        _build_group_spec(
            'After Fine-tuned',
            0,
            model_value=0,
        ),
    ]


def _scatter_groups(X, labels, group_specs, *, model_source=None):
    draw_queue = []
    for spec in group_specs:
        mask = labels == spec['target_value']
        if model_source is not None:
            mask &= model_source == spec['model_value']

        point_indices = np.flatnonzero(mask)
        if point_indices.size == 0:
            continue

        plt.scatter(
            [],
            [],
            marker=spec['marker'],
            facecolors=spec['facecolor'],
            edgecolors=spec['edgecolor'],
            c=None,
            s=DEFAULT_TSNE_MARKER_SIZE,
            alpha=spec['alpha'],
            linewidths=spec['linewidth'],
            label=spec['label'],
            zorder=spec.get('zorder', DEFAULT_TSNE_MARKER_ZORDER),
        )
        for point_index in point_indices:
            draw_queue.append((point_index, spec))

    if not draw_queue:
        return

    rng = np.random.default_rng(DEFAULT_TSNE_SHUFFLE_SEED)
    for queue_index in rng.permutation(len(draw_queue)):
        point_index, spec = draw_queue[queue_index]
        point = X[point_index]
        plt.scatter(
            point[0],
            point[1],
            marker=spec['marker'],
            facecolors=spec['facecolor'],
            edgecolors=spec['edgecolor'],
            c=None,
            s=DEFAULT_TSNE_MARKER_SIZE,
            alpha=spec['alpha'],
            linewidths=spec['linewidth'],
            label='_nolegend_',
            zorder=spec.get('zorder', DEFAULT_TSNE_MARKER_ZORDER),
        )


def _apply_tsne_layout(
    plot_title: str | None,
    *,
    legend_ncol: int,
    top_margin: float = 0.9,
    legend_fontsize: int = DEFAULT_LEGEND_FONT_SIZE,
):
    axes = plt.gca()
    axes.set_box_aspect(1)
    plt.xticks([]), plt.yticks([])
    if plot_title is not None:
        plt.title(plot_title)
    plt.legend(
        frameon=False,
        loc='lower center',
        bbox_to_anchor=(0.5, DEFAULT_LEGEND_Y),
        ncol=legend_ncol,
        borderaxespad=0.0,
        fontsize=legend_fontsize,
        markerscale=5.0,
        handletextpad=0.6,
        columnspacing=1.4,
    )
    plt.tight_layout(rect=(0, 0, 1, top_margin))


def _tensor_to_list(value) -> list:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().reshape(-1).tolist()
    if isinstance(value, list):
        return value
    return [value]

# 고차원 벡터를 2차원으로 축소하는 로직
def _fit_embedding(X_org):
    if X_org.shape[0] < 2:
        return None

    perplexity = min(30, X_org.shape[0] - 1) # 한 점이 주변 몇 개 이웃을 중요하게 볼지 결정하는 하이퍼파라미터. 일반적으로 5~50 사이의 값을 사용하며, 데이터 샘플 수보다 작은 값이어야 합니다.
    tsne = manifold.TSNE(n_components=2, init='pca', random_state=0, perplexity=perplexity) # 순서대로 - n_components: 축소된 차원 수 (여기서는 2차원), init: 초기화 방법 (점의 시작위치를 PCA로 초기화), random_state: 난수 시드
    print('Fitting TSNE!')
    X = tsne.fit_transform(X_org) # 고차원 벡터 X_org을 2차원으로 축소하여 X에 저장: (160, 768) -> (160, 2)
    x_min, x_max = np.min(X, 0), np.max(X, 0)
    denom = np.where((x_max - x_min) == 0, 1, (x_max - x_min)) # (x_max - x_min)이 0인 경우에는 나눗셈 오류를 방지하기 위해 1로 대체, 그렇지 않은 경우에는 원래의 (x_max - x_min) 값을 사용
    return (X - x_min) / denom # 정규화


def plot_embedding(X_org, y, title=None, new=True):
    X_org = np.asarray(X_org)
    Y = np.asarray(y)

    if X_org.shape[0] < 2:
        print(f'Skipping TSNE for {title}: need at least 2 samples, got {X_org.shape[0]}')
        return False

    cache_path = str(title) + '-tsne-features.json'
    if not new and Path(cache_path).exists():
        with open(cache_path, 'r', encoding='utf-8') as file:
            _x, _y = json.load(file)
        X = np.array(_x)
        Y = np.array(_y)
    else:
        X = _fit_embedding(X_org)
        if X is None:
            print(f'Skipping TSNE for {title}: need at least 2 samples, got {X_org.shape[0]}')
            return False

        with open(cache_path, 'w', encoding='utf-8') as file_:
            json.dump([X.tolist(), Y.tolist()], file_)

    if sns is not None:
        sns.set(style='white')
    plt.figure(figsize=DEFAULT_TSNE_FIGSIZE, edgecolor='black')
    _scatter_groups(X, Y, _resolve_single_group_specs(title))
    _apply_tsne_layout(
        SINGLE_TSNE_TITLE if title is not None else None,
        legend_ncol=2,
        top_margin=0.9,
    )
    plt.savefig(str(title) + '.jpeg', dpi=1000)
    plt.close()
    return True


def plot_paired_embedding(fine_X_org, fine_labels, raw_X_org, raw_labels, title=None, new=True):
    fine_X_org = np.asarray(fine_X_org) # fine-tuned 모델의 feature matrix
    fine_y = np.asarray(fine_labels)    # fine-tuned 모델의 label(취약/비취약)
    raw_X_org = np.asarray(raw_X_org)   # raw 모델의 feature matrix
    raw_y = np.asarray(raw_labels)      # raw 모델의 label(취약/비취약)

    combined_features = np.concatenate([fine_X_org, raw_X_org], axis=0)
    combined_labels = np.concatenate([fine_labels, raw_labels], axis=0)
    model_source = np.concatenate(
        [
            np.zeros(fine_X_org.shape[0], dtype=np.int64),
            np.ones(raw_X_org.shape[0], dtype=np.int64),
        ],
        axis=0,
    )

    cache_path = str(title) + '-tsne-features.json'
    if not new and Path(cache_path).exists(): # 기본적으로 실행되지 않는 if 블럭(new=True)
        with open(cache_path, 'r', encoding='utf-8') as file:
            payload = json.load(file)
        X = np.array(payload['embedding'])
        combined_labels = np.array(payload['labels'])
        model_source = np.array(payload['model_source'])
    else:
        X = _fit_embedding(combined_features) # 고차원 벡터를 2차원으로 축소하는 로직
        if X is None:
            print(
                f'Skipping paired TSNE for {title}: '
                f'need at least 2 samples, got {combined_features.shape[0]}'
            )
            return False
        with open(cache_path, 'w', encoding='utf-8') as file_:
            json.dump(
                {
                    'embedding': X.tolist(),                # 축소된 2차원 벡터 리스트
                    'labels': combined_labels.tolist(),     # 취약/비취약 라벨 리스트
                    'model_source': model_source.tolist(),  # fine-tuned 모델(0)과 raw 모델(1)을 구분하는 리스트
                },
                file_,
            )

    if sns is not None:
        sns.set(style='white')
    plt.figure(figsize=DEFAULT_TSNE_FIGSIZE, edgecolor='black')
    _scatter_groups(
        X,
        combined_labels,
        _resolve_paired_group_specs(),
        model_source=model_source,
    )
    _apply_tsne_layout(
        COMBINED_TSNE_TITLE if title is not None else None,
        legend_ncol=2,
        top_margin=0.86,
    )
    plt.savefig(str(title) + '.jpeg', dpi=1000)
    plt.close()
    return True


def load_feature_artifact(feature_npz_path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(feature_npz_path) as payload:
        return np.asarray(payload['features']), np.asarray(payload['labels'])


def validate_paired_feature_artifacts(
    fine_features: np.ndarray,
    fine_labels: np.ndarray,
    raw_features: np.ndarray,
    raw_labels: np.ndarray,
    *,
    fine_feature_npz_path: Path,
    raw_feature_npz_path: Path,
) -> None:
    if fine_features.ndim != 2 or raw_features.ndim != 2:
        raise ValueError(
            'Expected 2D feature arrays for paired TSNE: '
            f'{fine_feature_npz_path} -> {fine_features.shape}, '
            f'{raw_feature_npz_path} -> {raw_features.shape}'
        )

    if fine_features.shape[1] != raw_features.shape[1]:
        raise ValueError(
            'Fine-tuned and raw test feature dimensions do not match: '
            f'{fine_feature_npz_path} -> {fine_features.shape}, '
            f'{raw_feature_npz_path} -> {raw_features.shape}'
        )

    if fine_features.shape[0] != raw_features.shape[0]:
        raise ValueError(
            'Fine-tuned and raw test sample counts do not match: '
            f'{fine_feature_npz_path} -> {fine_features.shape[0]}, '
            f'{raw_feature_npz_path} -> {raw_features.shape[0]}'
        )

    if fine_labels.shape != raw_labels.shape or not np.array_equal(fine_labels, raw_labels):
        raise ValueError(
            'Fine-tuned and raw test labels do not match: '
            f'{fine_feature_npz_path} -> {fine_labels.shape}, '
            f'{raw_feature_npz_path} -> {raw_labels.shape}'
        )


def maybe_export_paired_test_tsne(raw_feature_npz_path: Path) -> tuple[Path | None, Path | None]:
    raw_feature_npz_path = Path(raw_feature_npz_path)
    raw_output_dir = raw_feature_npz_path.parent
    if raw_output_dir.name != RAW_MODEL_EVAL_DIRNAME:
        return None, None

    fine_output_dir = raw_output_dir.parent # vuln_patch 경로
    fine_feature_npz_path, _, _ = build_feature_artifact_paths(str(fine_output_dir))
    if not fine_feature_npz_path.exists():  # vuln_patch/test_last_hidden_state_vectors.npz
        print(
            'Skipping paired TSNE: fine-tuned test hidden states not found under '
            f'{fine_output_dir}'
        )
        return None, None

    fine_features, fine_labels = load_feature_artifact(fine_feature_npz_path)
    raw_features, raw_labels = load_feature_artifact(raw_feature_npz_path)
    
    # feature 검증 함수
    validate_paired_feature_artifacts(
        fine_features,
        fine_labels,
        raw_features,
        raw_labels,
        fine_feature_npz_path=fine_feature_npz_path,
        raw_feature_npz_path=raw_feature_npz_path,
    )

    # combined t-SNE 이미지 및 캐시 경로 생성
    combined_output_base = fine_output_dir / COMBINED_TEST_TSNE_BASENAME
    combined_tsne_image_path = Path(f'{combined_output_base}.jpeg')
    combined_tsne_cache_path = Path(f'{combined_output_base}-tsne-features.json')

    # combined tsne 연산 로직
    tsne_generated = plot_paired_embedding(
        fine_features,  # fine-tuned 모델의 feature matrix
        fine_labels,    # fine-tuned 모델의 label(취약/비취약)
        raw_features,   # raw 모델의 feature matrix
        raw_labels,     # raw 모델의 label(취약/비취약)
        title=str(combined_output_base), # combined t-SNE 이미지 및 캐시의 공통 베이스 이름 (확장자 제외)
        new=True,
    )
    if not tsne_generated:
        return None, None

    print(f'Paired t-SNE 이미지 저장 완료: {combined_tsne_image_path}')
    print(f'Paired t-SNE 캐시 저장 완료: {combined_tsne_cache_path}')
    return combined_tsne_image_path, combined_tsne_cache_path


def predict_on_dataloader(model, data_loader):
    """모델 예측 수행"""
    all_pred = []
    all_ref = []
    all_score = []
    feature_batches = []

    with torch.no_grad():
        model.eval()
        for batch in tqdm(data_loader, desc='예측 수행'):
            outputs = model(**batch)
            # 현재 PDBERT 설정에서는 code_feature_squeezer=cls_pooler 이므로
            # classifier 입력 feature는 code_encoder 출력의 첫 토큰 벡터다.
            encoded_code_outputs = model.embed_encode_code(batch['code'])
            code_features = encoded_code_outputs['outputs']

            # CLS 토큰 벡터만 추출 (보통 첫 번째 토큰)
            if code_features.ndim == 3:
                cls_features = code_features[:, 0, :]  # [batch, hidden_dim]
            else:
                cls_features = code_features  # 이미 [batch, hidden_dim]이면 그대로

            all_pred.extend(_tensor_to_list(outputs['pred']))
            all_score.extend(_tensor_to_list(outputs['logits']))
            all_ref.extend(_tensor_to_list(batch['label']))
            feature_batches.append(cls_features.detach().cpu().numpy())

    feature_dim = getattr(model.classifier, 'get_exp_input_dim', lambda: 0)()
    all_features = (
        np.concatenate(feature_batches, axis=0)
        if feature_batches
        else np.empty((0, feature_dim), dtype=np.float32)
    )
    return all_ref, all_pred, all_score, all_features


def analyze_predictions(all_ref, all_pred, all_score, original_data):
    """예측 결과 분석"""
    cm = confusion_matrix(all_ref, all_pred)
    tn, fp, fn, tp = cm.ravel()

    result_dict = {
        'Accuracy': accuracy_score(all_ref, all_pred),
        'Precision': precision_score(all_ref, all_pred, average='binary'),
        'Recall': recall_score(all_ref, all_pred, average='binary'),
        'F1-Score': f1_score(all_ref, all_pred, average='binary'),
        'MCC': matthews_corrcoef(all_ref, all_pred),
        'TP (True Positive)': int(tp),
        'TN (True Negative)': int(tn),
        'FP (False Positive)': int(fp),
        'FN (False Negative)': int(fn),
        'Total Samples': len(all_ref),
    }

    fn_samples = []
    fp_samples = []

    for i, (ref, pred) in enumerate(zip(all_ref, all_pred)):
        sample = original_data[i].copy()
        sample['index'] = i
        sample['predicted'] = pred
        sample['actual'] = ref
        sample['score'] = all_score[i]

        if ref == 1 and pred == 0:
            fn_samples.append(sample)
        elif ref == 0 and pred == 1:
            fp_samples.append(sample)

    return result_dict, fn_samples, fp_samples


def main():
    args = parse_args()

    data_file_path = args.data_path + '/test.json'
    model_path = args.model_dir + '/model.tar.gz'
    output_path = args.output or (args.model_dir + '/prediction_analysis.json')
    feature_npz_path, tsne_image_path, tsne_cache_path = build_feature_artifact_paths(args.model_dir)

    print('=' * 80)
    print('PDBERT 정밀 분석 시작')
    print('=' * 80)
    print(f'데이터: {data_file_path}')
    print(f'모델: {model_path}')
    print(f'출력: {output_path}')
    print(f'Feature export: {feature_npz_path}')
    print('=' * 80)

    print('\n모델 로딩 중...')
    dataset_reader = build_dataset_reader_from_config(
        config_path=args.model_dir + '/config.json',
        serialization_dir=args.model_dir + '/',
    )
    model = Model.from_archive(model_path)

    if args.cuda != -1:
        model = model.cuda(args.cuda)
        torch.cuda.set_device(args.cuda)

    data_loader = MultiProcessDataLoader(
        dataset_reader,
        data_file_path,
        shuffle=False,
        batch_size=args.batch_size,
        cuda_device=args.cuda,
    )
    data_loader.index_with(model.vocab)

    with open(data_file_path, 'r', encoding='utf-8') as f:
        original_data = json.load(f)

    print()
    all_ref, all_pred, all_score, all_features = predict_on_dataloader(model, data_loader)

    if all_features.shape[0] != len(all_ref):
        raise RuntimeError(
            'Feature export sample count mismatch: '
            f'features={all_features.shape[0]}, labels={len(all_ref)}'
        )

    np.savez_compressed(feature_npz_path, features=all_features, labels=np.asarray(all_ref))
    print(f'\nFeature vectors 저장 완료: {feature_npz_path}')

    # 단일 모델의 t-SNE 시각화
    tsne_generated = plot_embedding(
        all_features,
        np.asarray(all_ref),
        title=str(feature_npz_path.with_suffix('')),
        new=True,
    )
    if tsne_generated:
        print(f't-SNE 이미지 저장 완료: {tsne_image_path}')
        print(f't-SNE 캐시 저장 완료: {tsne_cache_path}')

    # Before Fine-tuned 모델과 After Fine-tuned 모델의 paired t-SNE 시각화
    # 후순위 연산 대상인 Before Fine-tuned 모델의 feature npz 경로에 'raw_model_eval'이 포함되어 있는지 확인
    # if RAW_MODEL_EVAL_DIRNAME in str(feature_npz_path.parent):
    combined_tsne_image_path, combined_tsne_cache_path = maybe_export_paired_test_tsne(
        feature_npz_path
    )

    result_dict, fn_samples, fp_samples = analyze_predictions(
        all_ref, all_pred, all_score, original_data
    )

    print('\n' + '=' * 80)
    print('평가 결과:')
    print('=' * 80)
    pprint(result_dict)

    csv_file_path = args.data_path + '/Real_Vul_data.csv'
    eval_result_path = args.model_dir + '/eval_result.csv'
    unique_ids = []

    try:
        import csv

        csv.field_size_limit(sys.maxsize)

        with open(csv_file_path, 'r', encoding='utf-8') as f_in, open(
            eval_result_path, 'w', encoding='utf-8', newline=''
        ) as f_out:
            reader = csv.DictReader(f_in)
            fieldnames = reader.fieldnames + ['model_predict', 'confusion_matrix']
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            for i, row in enumerate(reader):
                uid = row.get('unique_id', '')
                unique_ids.append(uid)

                if i < len(all_pred):
                    ref = all_ref[i]
                    pred = all_pred[i]

                    if ref == 1 and pred == 1:
                        cm_label = 'TP'
                    elif ref == 0 and pred == 0:
                        cm_label = 'TN'
                    elif ref == 0 and pred == 1:
                        cm_label = 'FP'
                    else:
                        cm_label = 'FN'

                    row['model_predict'] = pred
                    row['confusion_matrix'] = cm_label
                    writer.writerow(row)

        print(f'\neval_result.csv 저장 완료: {eval_result_path}')
        print(f'총 {len(unique_ids)}개 샘플 처리')

    except Exception as e:
        print(f'\nWarning: eval_result.csv 생성 실패 - {e}')
        unique_ids = ['unknown'] * len(original_data)

    for sample in fn_samples:
        idx = sample['index']
        sample['unique_id'] = unique_ids[idx] if idx < len(unique_ids) else 'unknown'
    for sample in fp_samples:
        idx = sample['index']
        sample['unique_id'] = unique_ids[idx] if idx < len(unique_ids) else 'unknown'

    analysis_result = {
        'summary': result_dict,
        'csv_file': csv_file_path,
        'feature_npz': str(feature_npz_path),
        'tsne_image': str(tsne_image_path) if tsne_generated else None,
        'tsne_cache': str(tsne_cache_path) if tsne_generated else None,
        'combined_tsne_image': (
            str(combined_tsne_image_path) if combined_tsne_image_path is not None else None
        ),
        'combined_tsne_cache': (
            str(combined_tsne_cache_path) if combined_tsne_cache_path is not None else None
        ),
        'fn_count': len(fn_samples),
        'fp_count': len(fp_samples),
        'fn_samples': fn_samples,
        'fp_samples': fp_samples,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_result, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 80}")
    print(f'분석 결과 저장: {output_path}')
    print(f'FN (놓친 취약점): {len(fn_samples)}개')
    print(f'FP (오탐): {len(fp_samples)}개')

    if fn_samples:
        print(f"\n{'=' * 80}")
        print('FN (False Negative) 샘플 목록:')
        print('=' * 80)
        for i, sample in enumerate(fn_samples):
            print(f"  #{i+1}: unique_id={sample['unique_id']}")
            print(f"       index={sample['index']}, score={sample['score']:.4f}")

        print(f"\n{'=' * 80}")
        print('CSV에서 상세 정보 조회 명령어:')
        print('=' * 80)
        for i, sample in enumerate(fn_samples):
            uid = sample['unique_id']
            print(f'# FN #{i+1}:')
            print(f"grep '{uid}' {csv_file_path}")
            print()

    if fp_samples:
        print(f"\n{'=' * 80}")
        print('FP (False Positive) 샘플 목록:')
        print('=' * 80)
        for i, sample in enumerate(fp_samples):
            print(f"  #{i+1}: unique_id={sample['unique_id']}")
            print(f"       index={sample['index']}, score={sample['score']:.4f}")

    print(f"\n{'=' * 80}")
    print('분석 완료!')
    print('=' * 80)


if __name__ == '__main__':
    main()
