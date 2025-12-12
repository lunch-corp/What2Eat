# src/config/constants.py

import os

import streamlit as st

# 프로젝트 루트 디렉토리 경로 구하기 (src의 상위 디렉토리)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 이미지 경로 설정
LOGO_IMG_PATH = os.path.join(ROOT_DIR, "static", "img", "what2eat-logo-middle.png")
LOGO_SMALL_IMG_PATH = os.path.join(ROOT_DIR, "static", "img", "what2eat-logo-small.png")
LOGO_TITLE_IMG_PATH = os.path.join(
    ROOT_DIR, "static", "img", "what2eat-word-logo-small.png"
)
GUIDE_IMG_PATH = os.path.join(ROOT_DIR, "static", "img", "kakomap_nickname_guide.jpg")

DEFAULT_ADDRESS_INFO_LIST = ["강남구 삼성동", 127.0567474, 37.5074423]

DINER_REVIEW_AVG = 3.2

# 데이터 경로 설정 (절대 경로 사용)
DATA_PATH = os.path.join(ROOT_DIR, "data", "seoul_data", "*.csv")
ZONE_INFO_PATH = os.path.join(ROOT_DIR, "data", "zone_info.json")
MODEL_PATH = os.path.join(ROOT_DIR, "data", "model_data")

# Kakao API settings
KAKAO_API_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_API_HEADERS = {"Authorization": f"KakaoAK {st.secrets['REST_API_KEY']}"}

GOOGLE_ANALYTIC_ID = st.secrets["GOOGLE_ANALYTIC_ID"]
MICROSOFT_CLARITY_ID = st.secrets["MICROSOFT_CLARITY_ID"]

# yamyam-ops API URL
API_URL = st.secrets.get("API_URL", "http://localhost:8000")

# 우선순위를 정의
PRIORITY_ORDER = {"한식": 1, "중식": 2, "일식": 2, "양식": 2}

# 등급별 색상 매핑
GRADE_COLORS = {
    3: [255, 0, 0],  # 빨강
    2: [255, 69, 0],  # 초록
    1: [255, 140, 0],  # 파랑
}

GRADE_MAP = {"🌟": 1, "🌟🌟": 2, "🌟🌟🌟": 3}

# large category sorted by priority
LARGE_CATEGORIES = [
    "한식",
    "술집",
    "양식",
    "일식",
    "중식",
    "아시아음식",
    "카페",
    "간식",
    "기타",
    "식품판매",
    "여가시설",
    "유아",
    "전문대행",
]

LARGE_CATEGORIES_NOT_USED = [
    "카페",
    "간식",
    "기타",
    "식품판매",
    "여가시설",
    "유아",
    "전문대행",
]
