# src/utils/my_page_helpers.py
"""마이페이지 관련 헬퍼 함수들"""

import streamlit as st

from utils.auth import get_user_profile_from_firestore, organize_user_profile_data
from utils.firebase_logger import get_firebase_logger


def get_onboarding_history(uid: str):
    """온보딩 이력 조회 (개선된 버전)"""
    logger = get_firebase_logger()

    onboarding_info = {
        "completed": False,
        "completed_date": None,
        "profile_created": False,
        "profile_created_date": None,
        "profile_data": None,
        "taste_ratings_count": 0,
    }

    # 1. 직접 프로필 문서 확인
    try:
        raw_profile_data = get_user_profile_from_firestore(uid)
        if raw_profile_data:
            onboarding_info["profile_created"] = True
            onboarding_info["profile_created_date"] = raw_profile_data.get("created_at")

            # organize_user_profile_data 사용하여 데이터 정리
            onboarding_info["profile_data"] = organize_user_profile_data(
                raw_profile_data
            )

            # 평점 데이터에서 taste_ratings_count 계산
            ratings = raw_profile_data.get("ratings", {})
            onboarding_info["taste_ratings_count"] = len(
                [r for r in ratings.values() if r > 0]
            )
    except Exception as e:
        st.warning(f"프로필 데이터 조회 중 오류: {str(e)}")

    # 2. 온보딩 완료 로그 확인
    if logger.is_available():
        try:
            onboarding_logs = logger.get_user_logs(
                uid, limit=10, collection_name="onboarding_logs"
            )

            for log in onboarding_logs:
                log_type = log.get("type", "")
                timestamp = log.get("timestamp", "")

                if log_type == "onboarding_completed":
                    onboarding_info["completed"] = True
                    onboarding_info["completed_date"] = timestamp
                    break  # 가장 최근 완료 로그만 사용
        except Exception as e:
            st.warning(f"온보딩 로그 조회 중 오류: {str(e)}")

    return onboarding_info


def get_location_history(uid: str):
    """위치 변경 이력 조회"""
    logger = get_firebase_logger()
    if not logger.is_available():
        return []

    # 네비게이션 로그에서 위치 관련 정보 조회
    nav_logs = logger.get_user_logs(uid, limit=20, collection_name="navigation_logs")

    location_changes = []
    for log in nav_logs:
        log_type = log.get("type", "")
        detail = log.get("detail", {})
        timestamp = log.get("timestamp", "")

        if log_type == "location_saved":
            location_changes.append(
                {
                    "type": "위치 저장",
                    "address": detail.get("address", "알 수 없음"),
                    "coordinates": detail.get("coordinates", {}),
                    "timestamp": timestamp,
                }
            )
        elif log_type == "location_change":
            location_changes.append(
                {
                    "type": "위치 변경",
                    "from_page": detail.get("from_page", "알 수 없음"),
                    "timestamp": timestamp,
                }
            )

    return location_changes


def get_restaurant_history(uid: str):
    """클릭한 음식점 이력 조회"""
    logger = get_firebase_logger()
    if not logger.is_available():
        return []

    # 음식점 로그 조회
    restaurant_logs = logger.get_user_logs(
        uid, limit=50, collection_name="restaurant_logs"
    )

    restaurant_history = []
    for log in restaurant_logs:
        log_type = log.get("type", "")
        detail = log.get("detail", {})
        timestamp = log.get("timestamp", "")

        if log_type == "restaurant_click":
            restaurant_history.append(
                {
                    "type": "음식점 클릭",
                    "restaurant_name": detail.get("restaurant_name", "알 수 없음"),
                    "category": detail.get("category", ""),
                    "location": detail.get("location", ""),
                    "grade": detail.get("grade"),
                    "from_page": detail.get("from_page", ""),
                    "timestamp": timestamp,
                    "url": detail.get("restaurant_url", ""),
                }
            )
        elif log_type == "restaurant_detail_view":
            restaurant_history.append(
                {
                    "type": "상세정보 조회",
                    "restaurant_name": detail.get("restaurant_name", "알 수 없음"),
                    "from_page": detail.get("from_page", ""),
                    "timestamp": timestamp,
                }
            )

    return restaurant_history
