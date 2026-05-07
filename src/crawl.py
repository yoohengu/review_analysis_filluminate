"""
무신사 신규 리뷰 크롤링.

기존 노트북(01_1_crawling.ipynb)의 로직을 GH Actions에서
실행 가능한 모듈로 재구성. 핵심: 이미 수집된 리뷰번호를
collected_ids로 들고 있으면서, 만나는 순간 중단(증분 크롤링).
"""

import time
from pathlib import Path

import pandas as pd
import requests

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────
BRANDS_CATEGORIES = [
    {"brand": "filluminate", "category": "001", "category_name": "상의"},
    {"brand": "filluminate", "category": "002", "category_name": "아우터"},
    {"brand": "filluminate", "category": "003", "category_name": "하의"},
    {"brand": "jemut",       "category": "001", "category_name": "상의"},
    {"brand": "jemut",       "category": "002", "category_name": "아우터"},
    {"brand": "jemut",       "category": "003", "category_name": "하의"},
    {"brand": "travel",      "category": "001", "category_name": "상의"},
    {"brand": "travel",      "category": "002", "category_name": "아우터"},
    {"brand": "travel",      "category": "003", "category_name": "하의"},
]

PAGE_SIZE = 30
SLEEP_SEC = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.musinsa.com/",
    "Origin":  "https://www.musinsa.com",
}


# ─────────────────────────────────────────────────────────────
# HTTP 유틸
# ─────────────────────────────────────────────────────────────
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def request_json(session, url, params=None, timeout=10, retry=3):
    last_status = None
    for attempt in range(1, retry + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)
            last_status = r.status_code
            if r.status_code == 200:
                return r.json(), r.status_code
            print(f"    요청 실패 ({r.status_code}) → 재시도 {attempt}/{retry}", flush=True)
        except Exception as e:
            print(f"    요청 오류 → 재시도 {attempt}/{retry}: {e}", flush=True)
        time.sleep(2 * attempt)
    return None, last_status


# ─────────────────────────────────────────────────────────────
# 상품 / 리뷰 fetch
# ─────────────────────────────────────────────────────────────
def fetch_products(session, brand, category, category_name):
    session.headers["Referer"] = f"https://www.musinsa.com/brand/{brand}"
    products, page, next_url = [], 1, None

    while True:
        if next_url:
            data, _ = request_json(session, next_url)
        else:
            data, _ = request_json(
                session,
                "https://api.musinsa.com/api2/dp/v2/plp/goods",
                params={
                    "gf": "A", "isSoldOut": "true", "sortCode": "REVIEW",
                    "category": category, "brand": brand,
                    "size": PAGE_SIZE, "caller": "FLAGSHIP", "page": page,
                },
            )
        if not data:
            break

        body = data.get("data", {})
        items = body.get("list", [])
        if not items:
            break

        for it in items:
            products.append({
                "플랫폼": "무신사",
                "카테고리": category_name,
                "브랜드": it.get("brandName", ""),
                "goodsNo": str(it.get("goodsNo", "")),
                "상품명": it.get("goodsName", ""),
                "정가": it.get("normalPrice", 0),
                "판매가": it.get("price", 0),
                "할인율": it.get("saleRate", 0),
                "리뷰수": it.get("reviewCount", 0),
                "리뷰점수": it.get("reviewScore", 0),
                "판매상태": "SOLD_OUT" if it.get("isSoldOut") else "SALE",
            })

        pagination = body.get("pagination", {})
        next_url = pagination.get("nextPageUrl")
        if not pagination.get("hasNext", False):
            break
        page += 1
        time.sleep(SLEEP_SEC)

    return products


def parse_satisfaction(survey):
    if not survey:
        return ""
    parts = []
    for q in survey.get("questions", []):
        attr = q.get("attribute", "")
        ans = ", ".join(a.get("answerShortText", "") for a in q.get("answers", []))
        parts.append(f"{attr}: {ans}")
    return " / ".join(parts)


def fetch_new_reviews(session, goods_no, collected_ids, max_pages=9999):
    reviews, stop = [], False

    for page in range(max_pages):
        if stop:
            break
        data, _ = request_json(
            session,
            "https://goods.musinsa.com/api2/review/v1/view/list",
            params={
                "page": page, "pageSize": 10, "goodsNo": goods_no,
                "sort": "new", "selectedSimilarNo": goods_no,
                "myFilter": "false", "hasPhoto": "false", "isExperience": "false",
            },
        )
        if not data:
            break

        body = data.get("data", {})
        review_list = body.get("list", [])
        if not review_list:
            break

        for r in review_list:
            review_no = str(r.get("no", ""))
            if review_no in collected_ids:
                stop = True
                break
            profile = r.get("userProfileInfo") or {}
            images = r.get("images") or []
            reviews.append({
                "goodsNo": str(goods_no),
                "리뷰번호": review_no,
                "리뷰타입": r.get("type", ""),
                "작성자": profile.get("userNickName", ""),
                "리뷰내용": r.get("content", ""),
                "평점": int(r.get("grade", 0)),
                "체험단": r.get("type") == "experience",
                "구매옵션": r.get("goodsOption", ""),
                "키": profile.get("userHeight", ""),
                "몸무게": profile.get("userWeight", ""),
                "성별": profile.get("reviewSex", ""),
                "작성일": r.get("createDate", ""),
                "만족도": parse_satisfaction(r.get("reviewSurveySatisfaction")),
                "사진유무": len(images) > 0,
                "도움돼요": r.get("likeCount", 0),
            })

        total_pages = body.get("page", {}).get("totalPages", 0)
        if page >= total_pages - 1:
            break
        time.sleep(SLEEP_SEC)

    return reviews


# ─────────────────────────────────────────────────────────────
# 저장 유틸
# ─────────────────────────────────────────────────────────────
def escape_excel(text):
    if isinstance(text, str) and text.startswith(("-", "=", "+", "@", "#")):
        return "'" + text
    return text


def append_csv(path: Path, df: pd.DataFrame):
    """
    경로가 .gz로 끝나면 자동으로 압축해서 저장합니다.
    """
    is_gzip = path.suffix == '.gz'
    if path.exists():
        df.to_csv(path, mode="a", header=False, index=False, encoding="utf-8-sig",
                  compression='gzip' if is_gzip else None)
    else:
        df.to_csv(path, mode="w", header=True, index=False, encoding="utf-8-sig",
                  compression='gzip' if is_gzip else None)


# ─────────────────────────────────────────────────────────────
# 메인 진입점
# ─────────────────────────────────────────────────────────────
def crawl_new_reviews(data_dir: Path, test_mode: bool = False) -> int:
    """
    모든 (브랜드, 카테고리) 신규 리뷰 크롤링.

    Args:
        data_dir: data/ 폴더 경로
        test_mode: True면 1개 (브랜드, 카테고리), 상위 3개 상품만 테스트

    Returns:
        새로 수집된 리뷰 건수
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. 기준이 될 기존 전처리 완료 데이터 (압축 포맷)
    cleaned_reviews_csv = data_dir / "cleaned_reviews.csv.gz"
    cleaned_products_csv = data_dir / "cleaned_products.csv.gz"  # (전처리 단계에서 사용될 예정)
    
    # 2. 새로 수집된 데이터가 임시로 저장될 파일 (압축 포맷)
    new_raw_reviews_csv = data_dir / "new_raw_reviews.csv.gz"
    new_raw_products_csv = data_dir / "new_raw_products.csv.gz"
    errors_csv = data_dir / "errors.csv"

    # 기존 리뷰번호 로드 (중복 수집 방지용 기준점)
    if cleaned_reviews_csv.exists():
        existing = pd.read_csv(cleaned_reviews_csv, usecols=["리뷰번호"], dtype=str)
        collected_ids = set(existing["리뷰번호"].astype(str).tolist())
        print(f"기존 전처리된 리뷰 {len(collected_ids):,}건 로드됨 (중복 기준점)", flush=True)
    else:
        collected_ids = set()
        print("기존 리뷰 없음 (첫 실행 또는 시드 데이터 누락)", flush=True)

    # 이전 주 임시 파일이 남아있으면 정리 (preprocess 실패 등으로 인한)
    for stale in [new_raw_reviews_csv, new_raw_products_csv]:
        if stale.exists():
            print(f" 이전 주 임시 파일 정리: {stale.name}", flush=True)
            stale.unlink()
            
    combos = BRANDS_CATEGORIES[:1] if test_mode else BRANDS_CATEGORIES
    session = make_session()
    total_new = 0
    max_pages_per_product = 3 if test_mode else 9999


    for combo in combos:
        brand = combo["brand"]
        category = combo["category"]
        category_name = combo["category_name"]
        print(f"\n{'='*60}\n▶ {brand} / {category_name}\n{'='*60}", flush=True)

        try:
            products = fetch_products(session, brand, category, category_name)
        except Exception as e:
            print(f"상품 수집 실패: {e}", flush=True)
            continue

        print(f"상품 {len(products)}개 발견", flush=True)
        if test_mode:
            products = products[:3]
            print("  (test_mode: 상위 3개만 처리)", flush=True)

        if products:
            # 새 상품 데이터도 임시 파일(.gz)에 저장
            append_csv(new_raw_products_csv, pd.DataFrame(products))

        new_brand = 0
        for i, prod in enumerate(products, 1):
            goods_no = prod["goodsNo"]
            print(f"  [{i}/{len(products)}] {prod['상품명'][:30]}...", flush=True)
            try:
                new_revs = fetch_new_reviews(session, goods_no, collected_ids, max_pages=max_pages_per_product)
                if new_revs:
                    df = pd.DataFrame(new_revs)
                    df["리뷰내용"] = df["리뷰내용"].astype(str).str.replace(r"[\n\r\t]", " ", regex=True)
                    for col in ["리뷰내용", "작성자"]:
                        df[col] = df[col].apply(escape_excel)
                    df["브랜드"] = brand
                    df["카테고리"] = category_name
                    
                    # 수집된 원본 데이터를 new_raw_reviews.csv.gz 에 임시 저장
                    append_csv(new_raw_reviews_csv, df)
                    
                    collected_ids.update(df["리뷰번호"].astype(str).tolist())
                    new_brand += len(new_revs)
                    print(f"    → 신규 {len(new_revs)}건", flush=True)
            except Exception as e:
                print(f"    실패: {e}", flush=True)
                append_csv(errors_csv, pd.DataFrame([{
                    "goodsNo": goods_no, "error_type": "review",
                    "message": str(e),
                    "time": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                }]))
            time.sleep(SLEEP_SEC)

        print(f"\n[{brand}/{category_name}] 신규 {new_brand}건", flush=True)
        total_new += new_brand

    print(f"\n{'='*60}\n전체 신규 리뷰: {total_new:,}건\n{'='*60}", flush=True)
    return total_new
