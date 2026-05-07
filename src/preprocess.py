import os
import re
import numpy as np
import pandas as pd
from pathlib import Path

# ==========================================
# [헬퍼 함수] 정규표현식 사이즈 추출
# ==========================================
size_pattern = re.compile(
    r'\b(XS|S|M|L|XL|2XL|3XL|SMALL|MEDIUM|LARGE|EXTRA\s*LARGE|MEDUIM|MEIDUM'
    r'|[2-9]?XL|[1-9][0-9]?(?=\b)|2[0-9]|3[0-9])\b', re.IGNORECASE
)
size_pattern2 = re.compile(r'(3XL|2XL|XL|XS|[SML])$')

def extract_size(val):
    if pd.isna(val): return None, None
    if val == 'F': return 'F', None
    match = size_pattern.search(val)
    if match:
        size = match.group().strip()
        option = size_pattern.sub('', val)
        option = re.sub(r'[\s·/]+', ' ', option).strip(' ·/-')
        return size, option if option else None
    return None, val

def extract_size2(val):
    if pd.isna(val): return None, None
    match = size_pattern2.search(val)
    if match:
        size = match.group()
        option = val[:match.start()].strip()
        return size, option if option else None
    return None, val

def extract_size_final(val):
    if pd.isna(val): return None, None
    result = extract_size(val)
    if result[0] is not None: return result
    return extract_size2(val)

# ==========================================
# [헬퍼 함수] 만족도 파싱
# ==========================================
def _parse_satisfaction(text):
    if pd.isna(text) or text == "":
        return None
    result = {}
    for part in str(text).split('/'):
        if ':' in part:
            key, value = part.split(':', 1)
            result[key.strip()] = value.strip()
    return result

# ==========================================
# 메인 전처리 함수
# ==========================================
def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """노트북의 전처리 로직을 DataFrame에 적용합니다."""
    
    # 1. 구매옵션
    df[['구매사이즈', '구매상세']] = df['구매옵션'].apply(lambda x: pd.Series(extract_size_final(x)))
    df['구매사이즈'] = df['구매사이즈'].replace({'MEDUIM': 'MEDIUM', 'MEIDUM': 'MEDIUM'})

    # 2. 키 / 몸무게 (이상치 NaN 처리 후, 중앙값 대체)
    df['키_clean'] = df['키'].astype(float).where((df['키'].astype(float) >= 120) & (df['키'].astype(float) <= 210), other=pd.NA)
    df['몸무게_clean'] = df['몸무게'].astype(float).where((df['몸무게'].astype(float) >= 30) & (df['몸무게'].astype(float) <= 200), other=pd.NA)
    
    group_median = df.groupby(['goodsNo', '구매사이즈'])[['키_clean', '몸무게_clean']].transform('median')
    df['키_clean'] = df['키_clean'].fillna(group_median['키_clean'])
    df['몸무게_clean'] = df['몸무게_clean'].fillna(group_median['몸무게_clean'])
    
    goods_median = df.groupby('goodsNo')[['키_clean', '몸무게_clean']].transform('median')
    df['키_clean'] = df['키_clean'].fillna(goods_median['키_clean'])
    df['몸무게_clean'] = df['몸무게_clean'].fillna(goods_median['몸무게_clean'])
    
    df['키'] = df['키_clean']
    df['몸무게'] = df['몸무게_clean']
    df.drop(columns=['키_clean', '몸무게_clean'], inplace=True)

    # 3. 성별
    df['성별'] = df['성별'].fillna('missing')

    # 4. 작성일 및 시간 파생변수
    df['작성일'] = pd.to_datetime(df['작성일']).dt.tz_localize(None)
    df['연도'] = df['작성일'].dt.year
    df['월'] = df['작성일'].dt.month
    df['일'] = df['작성일'].dt.day
    day_mapping = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
    df['요일'] = df['작성일'].dt.dayofweek.map(day_mapping)

    # 5. 체험단 / 사진유무
    for col in ['체험단', '사진유무']:
        df[col] = df[col].astype(str).str.strip().str.upper().map({'TRUE': True, 'FALSE': False}).astype('boolean')

    # 6. 리뷰별점
    df['평점_raw'] = df['평점']
    df['평점'] = df['평점'].astype(float).replace(0, np.nan)

    # 7. 만족도 파싱 및 점수화
    parsed = df['만족도'].apply(_parse_satisfaction)
    sat_df = pd.DataFrame(parsed.dropna().tolist(), index=parsed.dropna().index)
    df['만족도_응답여부'] = np.where(df['만족도'].notnull(), '응답', '미응답')
    
    for col in sat_df.columns:
        df[col] = sat_df[col]

    categories_dict = {
        '사이즈': ['매우 작음', '조금 작음', '정사이즈', '조금 큼', '많이 큼'],
        '화면 대비 색감': ['매우 어두움', '어두움', '화면과 비슷', '밝음', '매우 밝음'],
        '퀄리티': ['매우 나쁨', '나쁨', '보통', '좋음', '매우 좋음'],
        '구김': ['매우 많음', '많음', '약간 있음', '거의 없음', '전혀 없음'],
        '두께감': ['매우 얇음', '얇음', '적당함', '두꺼움', '매우 두꺼움'],
        '신축성': ['전혀 없음', '거의 없음', '적당함', '강함', '매우 강함'],
        '색감': ['매우 어두움', '어두움', '화면과 비슷', '밝음', '매우 밝음'], 
        '보온성': ['전혀 없음', '거의 없음', '적당함', '좋음', '매우 좋음'],
    }

    for col, order in categories_dict.items():
        if col in df.columns:
            df[col] = pd.Categorical(df[col], categories=order, ordered=True)

    linear_cols = ['퀄리티', '보온성', '신축성', '두께감', '구김']
    for col in linear_cols:
        if col in df.columns:
            df[f'{col}_점수'] = df[col].cat.codes.replace(-1, np.nan) + 1

    center_cols = ['사이즈', '화면 대비 색감', '색감']
    for col in center_cols:
        if col in df.columns:
            n = len(df[col].cat.categories)
            center = (n - 1) / 2
            code = df[col].cat.codes.replace(-1, np.nan)
            df[f'{col}_편차'] = code - center
            df[f'{col}_편차절대'] = (code - center).abs()

    # # 8. 도움돼요 - 사용 X
    # 기준일 = pd.to_datetime('today').normalize().tz_localize(None)
    # df['도움돼요'] = df['도움돼요'].astype(float).fillna(0)
    # df['노출일수'] = (기준일 - df['작성일'].dt.normalize()).dt.days + 1
    
    # # [주의] 주간 파이프라인이므로 7일 미만 데이터 삭제(Drop) 로직은 비활성화 처리했습니다.
    # # df = df[df['노출일수'] >= 7].copy()
    
    # df['일평균_도움돼요지수'] = df['도움돼요'] / np.log1p(df['노출일수'])
    # df['도움여부'] = (df['도움돼요'] > 0).astype(int)

    # 9. 컬럼명 변경 (공백 제거)
    df = df.rename(columns={
        "화면 대비 색감": "화면대비색감",
        "화면 대비 색감_편차": "화면대비색감_편차",
        "화면 대비 색감_편차절대": "화면대비색감_편차절대"
    })

    # 10. 중복 케이스 제거
    df = df.drop_duplicates().reset_index(drop=True)
    # 이후에 리뷰텍스트 전처리에서 처리됨
    # content_cols = [col for col in df.columns if col not in ['리뷰번호', '작성일']]
    # df_sorted = df.sort_values(by=content_cols + ['작성일']).reset_index(drop=True) 
    # time_diff = df_sorted.groupby(content_cols)['작성일'].diff() 
    # is_duplicate = time_diff <= pd.Timedelta(days=1)
    # df = df_sorted[~is_duplicate].reset_index(drop=True)

    return df

# ==========================================
# 파이프라인 진입점
# ==========================================
def run_preprocessing(data_dir: str = "data"):
    data_dir = Path(data_dir)
    new_raw_file = data_dir / "new_raw_reviews.csv.gz"
    cleaned_file = data_dir / "cleaned_reviews.csv.gz"
    weekly_new_file = data_dir / "weekly_new.csv"

    if not new_raw_file.exists():
        print("새로 수집된 리뷰가 없어 전처리를 건너뜁니다.", flush=True)
        if weekly_new_file.exists():
            weekly_new_file.unlink()
        return

    print("새로운 리뷰 전처리를 시작합니다...", flush=True)
    new_df = pd.read_csv(new_raw_file, compression='gzip', dtype=str)
    # 정제 로직 실행
    clean_df = clean_reviews(new_df)

    clean_df.to_csv(weekly_new_file, index=False, encoding='utf-8-sig')
    print(f"이번 주 신규 {len(clean_df)}건을 weekly_new.csv에 저장 (infer.py 입력)", flush=True)

    if cleaned_file.exists():
        # [수정된 부분] 기존 데이터의 컬럼(45개) 구조를 읽어와서, 새 데이터의 구조를 똑같이 맞춥니다.
        seed_cols = pd.read_csv(cleaned_file, nrows=0, compression='gzip').columns.tolist()
        
        for col in seed_cols:
            if col not in clean_df.columns:
                clean_df[col] = np.nan  # 기존엔 있는데 새 데이터엔 없으면 빈칸으로
                
        clean_df = clean_df[seed_cols]  # 기존 데이터와 열 순서를 완벽하게 일치시킴!

        clean_df.to_csv(cleaned_file, mode='a', header=False, index=False, 
                      encoding='utf-8-sig', compression='gzip')
        print(f"기존 데이터에 {len(clean_df)}건의 새 리뷰를 병합했습니다.", flush=True)
    else:
        clean_df.to_csv(cleaned_file, mode='w', header=True, index=False, 
                      encoding='utf-8-sig', compression='gzip')
        print("기존 전처리 파일이 없어 새로 생성했습니다.", flush=True)

    # 처리 끝난 임시 파일 삭제
    os.remove(new_raw_file)
    print("임시 원본 파일(new_raw_reviews.csv.gz) 삭제 완료.", flush=True)

if __name__ == "__main__":
    run_preprocessing()
