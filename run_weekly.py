"""
무신사 리뷰 분석 - 주간 파이프라인 (메인 진입점)

GitHub Actions cron에 의해 매주 자동 실행되는 메인 스크립트.
실제 로직은 src/ 하위 모듈로 분리되어 있고, 이 파일은 흐름만 조립한다.

실행:
    python run_weekly.py
"""

import sys
import traceback
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# 경로 설정
# ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data_ghactions"
MODELS_DIR = ROOT / "models"
OUTPUTS_DIR = ROOT / "outputs"

for d in (DATA_DIR, OUTPUTS_DIR):
    d.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────
# 로깅
# ─────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    """타임스탬프와 함께 stdout에 즉시 flush."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────
# 파이프라인 단계
# ─────────────────────────────────────────────────────────────
def step_1_crawl() -> None:
    """신규 리뷰 크롤링."""
    log("[Step 1/4] 크롤링 시작")
    
    import os
    from src.crawl import crawl_new_reviews
    
    # test_mode = True
    test_mode = os.environ.get("CRAWL_TEST_MODE", "0") == "1"
    if test_mode:
        log("  ⚠️ TEST_MODE: 1개 (브랜드, 카테고리), 상위 3개 상품만")
    
    n_new = crawl_new_reviews(DATA_DIR, test_mode=test_mode)
    log(f"[Step 1/4] 크롤링 완료 — 신규 {n_new}건")


def step_2_preprocess() -> None:
    """전처리 + 중복 제거."""
    log("[Step 2/4] 전처리 + 중복제거 시작")
    
    # 방금 만든 preprocess.py의 함수를 불러와서 실행합니다.
    from src.preprocess import run_preprocessing
    run_preprocessing(DATA_DIR)
    
    log("[Step 2/4] 전처리 완료")


def step_3_text_preprocess() -> None:
    log("[Step 3] 리뷰 텍스트 전처리")
    from src.text_preprocess import run_text_preprocess
    run_text_preprocess(data_dir=str(DATA_DIR))


def step_4_dedup() -> None:
    log("[Step 4] 리뷰 중복 제거")
    from src.dedup import run_dedup
    run_dedup(data_dir=str(DATA_DIR))


def step_5_extract() -> None:
    log("[Step 5] 임베딩 입력 parquet 생성")
    from src.extract_embedding_input import run_extract
    run_extract(data_dir=str(DATA_DIR))


def step_6_colab_handoff() -> None:
    log("[Step 6] 임베딩~감성 분석은 Colab에서 별도 처리 → 스킵")


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────
def main() -> int:
    log("=" * 60)
    log("주간 파이프라인 시작")
    log("=" * 60)

    try:
        step_1_crawl()
        step_2_preprocess()
        step_3_text_preprocess()
        step_4_dedup()
        step_5_extract()
        step_6_colab_handoff()
        
    except Exception as e:
        log(f"✗ 파이프라인 실패: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    log("=" * 60)
    log("✓ 전체 파이프라인 정상 완료")
    log("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
