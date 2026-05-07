"""
Step 1 텍스트 정제: weekly_new.csv → weekly_new_step1.csv
"""

import re
from pathlib import Path

import emoji
import pandas as pd

TEXT_COL = '리뷰내용'

def clean_review_text(text):
    """약한 정제 (임베딩/토픽용). 의미 보존하면서 노이즈만 제거."""
    text = str(text)
    text = re.sub(r'#(?:NAME|N/A|VALUE|DIV/0|REF|NULL|NUM)[!?]?', ' ', text)
    text = re.sub(r'http\S+|www\.\S+', ' ', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = emoji.replace_emoji(text, replace=' ')
    text = re.sub(r'([ㄱ-ㅎㅏ-ㅣ])\1{3,}', r'\1\1\1', text)
    text = re.sub(r'(.)\1{3,}', r'\1\1\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_review_text(text):
    """강한 정규화 (중복 검출용). 자모만 1개로 압축, 한글/영문/숫자만 보존."""
    text = str(text).lower()
    text = re.sub(r'#(?:NAME|N/A|VALUE|DIV/0|REF|NULL|NUM)[!?]?', '', text)
    text = re.sub(r'http\S+|www\.\S+', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-zA-Z]+;', '', text)
    text = emoji.replace_emoji(text, replace='')
    text = re.sub(r'([ㄱ-ㅎㅏ-ㅣ])\1+', r'\1', text)
    text = re.sub(r'[^가-힣a-zA-Z0-9]', '', text)
    return text


def extract_flags(text):
    """원본 텍스트에서 감정 강도/통계 플래그 추출."""
    text = str(text)
    laugh_matches = re.findall(r'[ㅋㅎ]+', text)
    cry_matches = re.findall(r'[ㅠㅜ]+', text)
    return pd.Series({
        'laugh_count':       max((len(m) for m in laugh_matches), default=0),
        'cry_count':         max((len(m) for m in cry_matches), default=0),
        'exclamation_count': text.count('!'),
        'question_count':    text.count('?'),
        'emoji_count':       emoji.emoji_count(text),
        'has_repetition':    bool(re.search(r'(.)\1{2,}', text)),
        'text_length_orig':  len(text),
    })


def run_text_preprocess(data_dir: str = "data") -> int:
    data_dir = Path(data_dir)
    weekly_new = data_dir / "weekly_new.csv"
    output_path = data_dir / "weekly_new_step1.csv"

    if not weekly_new.exists():
        print("  weekly_new.csv 없음 → 텍스트 전처리 스킵", flush=True)
        if output_path.exists():
            output_path.unlink()
        return 0

    df = pd.read_csv(weekly_new)
    before = len(df)
    df = df.dropna(subset=[TEXT_COL]).reset_index(drop=True)
    if before != len(df):
        print(f"  본문 NaN 제거: {before:,} → {len(df):,}건", flush=True)

    if len(df) == 0:
        print("  처리할 리뷰 없음", flush=True)
        return 0

    df['리뷰내용_clean'] = df[TEXT_COL].apply(clean_review_text)
    df['리뷰내용_norm']  = df[TEXT_COL].apply(normalize_review_text)

    flags = df[TEXT_COL].apply(extract_flags).reset_index(drop=True)
    df = df.reset_index(drop=True)
    df = pd.concat([df, flags], axis=1)

    df['한글_글자수'] = df['리뷰내용_clean'].str.count(r'[가-힣]')
    df['전체_글자수'] = df['리뷰내용_clean'].str.len()
    df['is_valid_for_topic'] = df['한글_글자수'] >= 5

    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    n_valid = df['is_valid_for_topic'].sum()
    print(f"  완료: {len(df):,}건 (유효 {n_valid:,} / 무효 {len(df)-n_valid:,})", flush=True)
    return len(df)
