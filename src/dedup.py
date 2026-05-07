"""
Step 2 중복 제거: weekly_new_step1.csv → weekly_new_step2_dedup.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.text_preprocess import clean_review_text, normalize_review_text   # ← 추가

LOOKBACK_HOURS = 48   # cleaned_reviews에서 lookback 가져올 시간 윈도우

TEXT_COL = '리뷰내용_clean'
NORM_COL = '리뷰내용_norm'

# 임계값 (노트북에서 결정된 값)
JACCARD_THRESHOLD       = 0.7
COSINE_THRESHOLD        = 0.8
SHORT_JACCARD_THRESHOLD = 0.9
SHORT_COSINE_THRESHOLD  = 0.95
SHORT_TEXT_LIMIT        = 15

_VEC = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3), min_df=1)


def char_bigrams(s):
    return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}


def jaccard_sim(s1, s2):
    g1, g2 = char_bigrams(str(s1 or '')), char_bigrams(str(s2 or ''))
    union = g1 | g2
    return round(len(g1 & g2) / len(union), 4) if union else 0.0


def cosine_sim(s1, s2):
    n1, n2 = str(s1 or ''), str(s2 or '')
    if not n1 or not n2:
        return 0.0
    try:
        mat = _VEC.fit_transform([n1, n2])
        return round(float(cosine_similarity(mat[0], mat[1])[0, 0]), 4)
    except Exception:
        return 0.0


def is_duplicate(s1, s2):
    if str(s1) == str(s2):
        return True
    is_short = max(len(str(s1)), len(str(s2))) < SHORT_TEXT_LIMIT
    j_thresh = SHORT_JACCARD_THRESHOLD if is_short else JACCARD_THRESHOLD
    c_thresh = SHORT_COSINE_THRESHOLD if is_short else COSINE_THRESHOLD
    if jaccard_sim(s1, s2) >= j_thresh:
        return True
    if cosine_sim(s1, s2) >= c_thresh:
        return True
    return False


def make_option_key(s, d):
    s_v = s if pd.notna(s) else None
    d_v = d if pd.notna(d) else None
    return (s_v, d_v)


def assign_sessions(group):
    """24h 세션 분리 (체이닝 방지)."""
    times = group['작성일'].values
    sessions, sid, sstart = [], 0, times[0]
    for t in times:
        if (t - sstart) / np.timedelta64(1, 'h') > 24:
            sid += 1
            sstart = t
        sessions.append(sid)
    return pd.Series(sessions, index=group.index)


def union_find_components(n, dup_pairs):
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j in dup_pairs:
        parent[find(i)] = find(j)
    return [find(i) for i in range(n)]


def process_group(group):
    """같은 (작성자, 상품, 세션) 그룹 내 중복 처리."""
    g = group.copy().reset_index(drop=False)
    n = len(g)

    if n == 1:
        g['action']   = 'keep'
        g['dup_flag'] = 'unique'
        g['is_base']  = True
        g['kept_id']  = g['리뷰번호'].iloc[0]
        return g.set_index('index')

    texts   = g[NORM_COL].tolist()
    options = g['옵션키'].tolist()
    rtypes  = g['리뷰타입'].tolist()

    dup_pairs, pair_flags = [], {}

    for i in range(n):
        for j in range(i + 1, n):
            same_opt = options[i] == options[j]
            same_typ = rtypes[i] == rtypes[j]
            dup = is_duplicate(texts[i], texts[j])

            if same_opt and same_typ:
                flag = 'same_option_same_type_dup' if dup else 'same_option_same_type_unique'
            elif (not same_opt) and same_typ:
                flag = 'multi_option_dup' if dup else 'multi_option_unique'
            elif same_opt and (not same_typ):
                flag = 'multi_type_dup' if dup else 'multi_type_unique'
            else:
                flag = 'multi_option_type_dup' if dup else 'multi_option_type_unique'

            if dup:
                dup_pairs.append((i, j))
            pair_flags[(i, j)] = pair_flags[(j, i)] = flag

    components = union_find_components(n, dup_pairs)

    actions, flags, is_bases, kept_ids = [], [], [], []
    for ci in range(n):
        comp_id = components[ci]
        comp_indices = [k for k, c in enumerate(components) if c == comp_id]

        if len(comp_indices) == 1:
            # 컴포넌트 단독 → 다른 멤버와의 unique flag 중 하나 선택
            related = [pair_flags.get((min(ci, j), max(ci, j)))
                       for j in range(n) if j != ci]
            related = [f for f in related if f]
            unique_flags = [f for f in related if 'unique' in f]
            actions.append('keep')
            flags.append(unique_flags[0] if unique_flags else 'unique')
            is_bases.append(True)
            kept_ids.append(g.iloc[ci]['리뷰번호'])
        else:
            # 컴포넌트 ≥ 2 → base 선정
            # lookback (이미 처리된 기존 데이터)이 있으면 무조건 그게 base (보존 필수)
            lookback_in_comp = [k for k in comp_indices
                                if g.iloc[k].get('_is_lookback', False)]
            if lookback_in_comp:
                base_idx = max(lookback_in_comp, key=lambda k: g.iloc[k]['전체_글자수'])
            else:
                base_idx = max(comp_indices, key=lambda k: g.iloc[k]['전체_글자수'])
            base_id = g.iloc[base_idx]['리뷰번호']

            if ci == base_idx:
                actions.append('keep')
                is_bases.append(True)
            else:
                actions.append('drop')
                is_bases.append(False)

            dup_flags = [pair_flags.get((min(ci, j), max(ci, j)))
                         for j in comp_indices if j != ci]
            dup_flags = [f for f in dup_flags if f and 'dup' in f]
            flags.append(dup_flags[0] if dup_flags else 'unique')
            kept_ids.append(base_id)

    g['action']   = actions
    g['dup_flag'] = flags
    g['is_base']  = is_bases
    g['kept_id']  = kept_ids
    return g.set_index('index')


def run_dedup(data_dir: str = "data") -> int:
    data_dir = Path(data_dir)
    input_path = data_dir / "weekly_new_step1.csv"
    cleaned_path = data_dir / "cleaned_reviews.csv.gz"
    out_keep = data_dir / "weekly_new_step2_dedup.csv"
    out_drop = data_dir / "weekly_new_step2_dropped.csv"

    if not input_path.exists():
        print("  weekly_new_step1.csv 없음 → 중복 제거 스킵", flush=True)
        for f in [out_keep, out_drop]:
            if f.exists():
                f.unlink()
        return 0

    df = pd.read_csv(input_path, low_memory=False)
    df['작성일'] = pd.to_datetime(df['작성일'], errors='coerce')
    df[TEXT_COL] = df[TEXT_COL].fillna('').astype(str)
    df[NORM_COL] = df[NORM_COL].fillna('').astype(str)

    if '전체_글자수' not in df.columns:
        df['전체_글자수'] = df[TEXT_COL].str.len()

    # 신규 데이터 마킹
    df['_is_lookback'] = False

    # ── Lookback Window: cleaned_reviews에서 최근 48h 가져와 검사에 포함 ──
    if cleaned_path.exists() and len(df) > 0:
        try:
            cleaned_df = pd.read_csv(cleaned_path, compression='gzip', low_memory=False)
            cleaned_df['작성일'] = pd.to_datetime(cleaned_df['작성일'], errors='coerce')

            cutoff = df['작성일'].min() - pd.Timedelta(hours=LOOKBACK_HOURS)
            lookback = cleaned_df[cleaned_df['작성일'] >= cutoff].copy()

            # 신규에 이미 있는 리뷰는 lookback에서 제외
            lookback = lookback[~lookback['리뷰번호'].astype(str)
                                .isin(df['리뷰번호'].astype(str))]
            
            if len(lookback) > 0:
                # cleaned_reviews엔 텍스트 정제 결과 없음 → 즉석 적용
                lookback['리뷰내용'] = lookback['리뷰내용'].fillna('').astype(str)
                lookback['리뷰내용_clean'] = lookback['리뷰내용'].apply(clean_review_text)
                lookback['리뷰내용_norm']  = lookback['리뷰내용'].apply(normalize_review_text)
                lookback['전체_글자수']   = lookback['리뷰내용_clean'].str.len()
                lookback['_is_lookback']  = True

                df['리뷰번호'] = df['리뷰번호'].astype(str)
                lookback['리뷰번호'] = lookback['리뷰번호'].astype(str)

                # lookback에 없는 컬럼은 NaN으로 채워서 신규의 전체 컬럼셋을 보존
                for col in df.columns:
                    if col not in lookback.columns:
                        lookback[col] = None
                df = pd.concat([df, lookback[df.columns]], ignore_index=True)
                print(f"  Lookback {LOOKBACK_HOURS}h: cleaned_reviews에서 {len(lookback):,}건 추가 검사", flush=True)
            else:
                print(f"  Lookback {LOOKBACK_HOURS}h: 해당 시간대 기존 데이터 없음", flush=True)
        except Exception as e:
            print(f"  Lookback 로드 실패: {e} → 신규만 처리", flush=True)

    # STEP 0: 탈퇴/닉변 작성자 → 익명 ID
    df['작성자_norm'] = df['작성자'].astype(str)
    mask_anon = df['작성자_norm'].str.strip().isin(['-', "'-"])
    df.loc[mask_anon, '작성자_norm'] = '_anon_' + df.loc[mask_anon].index.astype(str)

    # STEP 1: month 리뷰 분리
    mask_month = df['리뷰타입'] == 'month'
    df_month = df[mask_month].copy()
    df_main = df[~mask_month].copy()

    if len(df_month) > 0:
        df_month['action']   = 'keep'
        df_month['dup_flag'] = 'month_excluded'
        df_month['is_base']  = True
        df_month['kept_id']  = df_month['리뷰번호']
        df_month['옵션키']    = None
        df_month['세션']      = 0
        df_month['long_gap_review'] = False

    # 옵션키
    df_main['옵션키'] = [make_option_key(s, d) for s, d in
                       zip(df_main['구매사이즈'], df_main['구매상세'])]

    # 24h 세션
    df_main = df_main.sort_values(['작성자_norm', 'goodsNo', '작성일']).reset_index(drop=True)
    sessions_list = []
    for _, group in df_main.groupby(['작성자_norm', 'goodsNo'], sort=False):
        sessions_list.append(assign_sessions(group))
    df_main['세션'] = pd.concat(sessions_list).sort_index() if sessions_list else 0

    # long_gap_review
    sessions_per_pair = df_main.groupby(['작성자_norm', 'goodsNo'])['세션'].transform('nunique')
    df_main['long_gap_review'] = sessions_per_pair > 1

    # 그룹 단위 중복 처리
    group_sizes = df_main.groupby(['작성자_norm', 'goodsNo', '세션']).size()
    df_main = df_main.merge(group_sizes.rename('그룹크기').reset_index(),
                            on=['작성자_norm', 'goodsNo', '세션'], how='left')

    mask_single = df_main['그룹크기'] == 1
    df_single = df_main[mask_single].copy()
    df_multi  = df_main[~mask_single].copy()

    df_single['action']   = 'keep'
    df_single['dup_flag'] = 'unique'
    df_single['is_base']  = True
    df_single['kept_id']  = df_single['리뷰번호']

    if len(df_multi) > 0:
        processed_list = []
        for _, group in df_multi.groupby(['작성자_norm', 'goodsNo', '세션'], sort=False):
            processed_list.append(process_group(group))
        df_multi_processed = pd.concat(processed_list)
        for col in ['작성자_norm', 'goodsNo', '세션']:
            if col not in df_multi_processed.columns:
                df_multi_processed[col] = df_multi.loc[df_multi_processed.index, col]
        df_main_done = pd.concat([df_single, df_multi_processed], ignore_index=True)
    else:
        df_main_done = df_single

    if len(df_month) > 0:
        df_final = pd.concat([df_main_done, df_month], ignore_index=True)
    else:
        df_final = df_main_done

    df_final = df_final.sort_values('리뷰번호').reset_index(drop=True)

    # lookback은 결과에서 제외 (이미 cleaned_reviews에 처리됨)
    df_final_new = df_final[~df_final.get('_is_lookback', False)].copy()
    df_keep = df_final_new[df_final_new['action'] == 'keep'].copy()
    df_drop = df_final_new[df_final_new['action'] == 'drop'].copy()

    # 출력 시 _is_lookback 컬럼은 제거
    df_keep = df_keep.drop(columns=['_is_lookback'], errors='ignore')
    df_drop = df_drop.drop(columns=['_is_lookback'], errors='ignore')

    df_keep.to_csv(out_keep, index=False, encoding='utf-8-sig')
    df_drop.to_csv(out_drop, index=False, encoding='utf-8-sig')

    print(f"  보존: {len(df_keep):,}건 / 제거: {len(df_drop):,}건", flush=True)
    return len(df_keep)
