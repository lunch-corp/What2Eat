# src/utils/api_data_loader.py
"""API를 통한 데이터 로딩 유틸리티"""

import os
from typing import Optional

import pandas as pd
import requests
import streamlit as st


def get_api_url() -> str:
    """
    secrets 또는 환경변수에서 API URL 가져오기
    """
    try:
        # Streamlit secrets에서 가져오기 시도
        if "API_URL" in st.secrets:
            return st.secrets["API_URL"]
    except Exception:
        pass

    return os.getenv("API_URL")


@st.cache_data(ttl=3600)  # 1시간 캐시
def load_diners_from_api(
    api_url: Optional[str] = None,
    category_large: Optional[str] = None,
    category_middle: Optional[str] = None,
    min_rating: Optional[float] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    API에서 카카오 음식점 데이터를 가져옵니다.

    Args:
        api_url: API 베이스 URL (None이면 secrets에서 가져옴)
        category_large: 대분류 카테고리 (선택)
        category_middle: 중분류 카테고리 (선택)
        min_rating: 최소 평점 (선택)
        limit: 가져올 최대 레코드 수 (None이면 전체)

    Returns:
        음식점 데이터프레임
    """
    # api_url이 제공되지 않으면 secrets에서 가져오기
    if api_url is None:
        api_url = get_api_url()

    try:
        # API 엔드포인트
        endpoint = f"{api_url}/kakao/diners/"

        # 쿼리 파라미터 설정
        params = {}
        if limit is not None:
            params["limit"] = limit
        if category_large:
            params["diner_category_large"] = category_large
        if category_middle:
            params["diner_category_middle"] = category_middle
        if min_rating is not None:
            params["min_rating"] = min_rating

        # API 요청
        response = requests.get(endpoint, params=params, timeout=60)
        response.raise_for_status()

        # JSON 데이터를 DataFrame으로 변환
        diners_data = response.json()

        if not diners_data:
            st.error("⚠️ API에서 데이터를 가져오지 못했습니다.")
            return pd.DataFrame()

        df = pd.DataFrame(diners_data)

        # 기존 코드와 호환되도록 컬럼 이름 확인 및 변환
        # diner_url 컬럼이 없으면 생성
        if "diner_url" not in df.columns and "diner_idx" in df.columns:
            df["diner_url"] = df["diner_idx"].apply(
                lambda x: f"https://place.map.kakao.com/{x}" if pd.notna(x) else ""
            )

        print(f"✅ API에서 {len(df)}개의 음식점 데이터를 로드했습니다.")
        return df

    except requests.exceptions.RequestException as e:
        st.error(f"❌ API 요청 실패: {str(e)}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 데이터 로딩 중 오류 발생: {str(e)}")
        return pd.DataFrame()
