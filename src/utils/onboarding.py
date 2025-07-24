# utils/onboarding.py

from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from utils.auth import get_current_user
from utils.data_processing import get_filtered_data
from utils.firebase_logger import get_firebase_logger


class OnboardingManager:
    """온보딩 관련 로직을 관리하는 클래스"""

    def __init__(self, app=None):
        self.logger = get_firebase_logger()
        self.app = app

    def get_popular_restaurants_by_location(
        self, location: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """위치 기반 인기 음식점 조회 (2km 반경, diner_grade 높은 순)"""
        if not self.app or not hasattr(self.app, "df_diner"):
            # app 인스턴스나 df_diner가 없는 경우 빈 리스트 반환
            return []

        # 현재 사용자 위치 정보 가져오기
        if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
            return []

        user_lat = st.session_state.user_lat
        user_lon = st.session_state.user_lon

        # 2km 반경 내 데이터 필터링
        df_geo_filtered = get_filtered_data(
            self.app.df_diner, user_lat, user_lon, max_radius=2
        )

        # diner_grade가 있는 데이터만 필터링
        df_geo_filtered = df_geo_filtered[df_geo_filtered["diner_grade"].notna()]

        # diner_grade가 1 이상인 찐맛집만 필터링
        df_quality = df_geo_filtered[df_geo_filtered["diner_grade"] >= 1]

        if len(df_quality) == 0:
            return []

        # diner_grade 높은 순으로 정렬
        df_sorted = df_quality.sort_values(by="diner_grade", ascending=False)

        # limit 개수만큼 선택
        df_selected = df_sorted.head(limit)

        # 결과를 딕셔너리 리스트로 변환
        restaurants = []
        for _, row in df_selected.iterrows():
            restaurant = {
                "id": str(row.get("diner_idx", "")),
                "name": row.get("diner_name", ""),
                "category": row.get("diner_category_large", "카테고리 정보 없음"),
                "diner_category_large": row.get("diner_category_large", ""),
                "address": row.get("diner_num_address", f"{location} 근처"),
                "rating": float(row.get("diner_review_avg", 0)),
                "review_count": int(row.get("diner_review_cnt", 0)),
                "price_range": "정보 없음",
                "specialties": row.get("diner_menu_name", [])[:3]
                if row.get("diner_menu_name")
                else [],
                "distance": round(row.get("distance", 0), 1),
            }
            restaurants.append(restaurant)

        return restaurants

    def get_similar_restaurants(
        self, restaurant_id: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """유사 음식점 조회 (같은 diner_category_large, diner_grade 높은 순)"""
        if not self.app or not hasattr(self.app, "df_diner"):
            return []

        # 현재 사용자 위치 정보 가져오기
        if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
            return []

        user_lat = st.session_state.user_lat
        user_lon = st.session_state.user_lon

        # 선택된 음식점 정보 찾기
        try:
            selected_restaurant = self.app.df_diner[
                self.app.df_diner["diner_idx"].astype(str) == restaurant_id
            ]

            if len(selected_restaurant) == 0:
                return []

            selected_category = selected_restaurant.iloc[0]["diner_category_large"]

        except Exception:
            return []

        # 2km 반경 내 데이터 필터링
        df_geo_filtered = get_filtered_data(
            self.app.df_diner, user_lat, user_lon, max_radius=2
        )

        # 같은 카테고리의 음식점만 필터링
        df_same_category = df_geo_filtered[
            df_geo_filtered["diner_category_large"] == selected_category
        ]

        # 선택된 음식점 제외
        df_same_category = df_same_category[
            df_same_category["diner_idx"].astype(str) != restaurant_id
        ]

        # diner_grade가 있는 데이터만 필터링
        df_same_category = df_same_category[df_same_category["diner_grade"].notna()]

        # diner_grade가 1 이상인 찐맛집만 필터링
        df_quality = df_same_category[df_same_category["diner_grade"] >= 1]

        if len(df_quality) == 0:
            return []

        # diner_grade 높은 순으로 정렬
        df_sorted = df_quality.sort_values(by="diner_grade", ascending=False)

        # limit 개수만큼 선택
        df_selected = df_sorted.head(limit)

        # 결과를 딕셔너리 리스트로 변환
        similar_restaurants = []
        for _, row in df_selected.iterrows():
            restaurant = {
                "id": str(row.get("diner_idx", "")),
                "name": row.get("diner_name", ""),
                "category": row.get("diner_category_large", ""),
                "rating": float(row.get("diner_grade", 0)),
                "specialties": row.get("diner_menu_name", [])[:2]
                if row.get("diner_menu_name")
                else [],
                "distance": round(row.get("distance", 0), 1),
                "review_count": int(row.get("diner_review_cnt", 0)),
            }
            similar_restaurants.append(restaurant)

        return similar_restaurants

    def save_user_profile(
        self, profile_data: Dict[str, Any], ratings_data: Dict[str, int]
    ) -> bool:
        """사용자 프로필 데이터를 저장"""
        try:
            user_info = get_current_user()
            if not user_info:
                return False

            uid = user_info.get("localId")
            if not uid:
                return False

            # 저장할 데이터 구성
            save_data = {
                "user_id": uid,
                "profile": profile_data,
                "ratings": ratings_data,
                "created_at": datetime.now().isoformat(),
                "onboarding_version": "1.0",
            }

            # 실제로는 Firestore에 저장
            # db.collection('user_profiles').document(uid).set(save_data)

            # 로그 기록
            if self.logger.is_available():
                self.logger.log_activity(
                    uid,
                    "profile_created",
                    {
                        "profile_fields": list(profile_data.keys()),
                        "ratings_count": len(
                            [r for r in ratings_data.values() if r > 0]
                        ),
                    },
                )

            return True

        except Exception as e:
            st.error(f"프로필 저장 중 오류: {str(e)}")
            return False

    def load_user_profile(self) -> Optional[Dict[str, Any]]:
        """사용자 프로필 데이터를 로드"""
        try:
            user_info = get_current_user()
            if not user_info:
                return None

            uid = user_info.get("localId")
            if not uid:
                return None

            # 실제로는 Firestore에서 로드
            # doc = db.collection('user_profiles').document(uid).get()
            # if doc.exists:
            #     return doc.to_dict()

            return None

        except Exception as e:
            st.error(f"프로필 로드 중 오류: {str(e)}")
            return None

    def validate_onboarding_data(
        self, profile_data: Dict[str, Any], ratings_data: Dict[str, int]
    ) -> List[str]:
        """온보딩 데이터 유효성 검사"""
        errors = []

        # 필수 프로필 정보 확인
        required_fields = ["location", "birth_year", "gender", "regular_budget"]
        for field in required_fields:
            if not profile_data.get(field):
                errors.append(f"{field} 정보가 누락되었습니다.")

        # 평가 개수 확인
        rated_count = len([r for r in ratings_data.values() if r > 0])
        if rated_count < 3:  # 최소 3개 평가 필요
            errors.append(f"최소 3개 음식점 평가가 필요합니다. (현재: {rated_count}개)")

        # 연령 유효성 확인
        birth_year = profile_data.get("birth_year")
        if birth_year:
            current_year = datetime.now().year
            age = current_year - birth_year
            if age < 10 or age > 100:
                errors.append("올바른 출생연도를 입력해주세요.")

        return errors

    def get_recommendation_preview(
        self, profile_data: Dict[str, Any], ratings_data: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """온보딩 데이터 기반 추천 미리보기 (간단한 버전)"""
        try:
            # 사용자가 높게 평가한 음식점들의 카테고리 분석
            high_rated_categories = []

            # 실제로는 ratings_data에서 높은 점수를 받은 음식점들의 카테고리를 분석
            # 현재는 샘플 데이터로 대체

            # 선호하는 음식 종류 고려
            preferred_categories = profile_data.get("food_preferences", [])

            # 매운맛 정도 고려
            spice_level = profile_data.get("spice_level", 2)

            # 예산 고려
            budget = profile_data.get("regular_budget", "1-2만원")

            # 간단한 추천 로직 (실제로는 더 복잡한 ML 모델 사용)
            recommended_restaurants = [
                {
                    "name": "추천 음식점 1",
                    "category": "한식" if "한식" in preferred_categories else "양식",
                    "reason": "취향 분석 결과 좋아하실 것 같아요!",
                    "rating": 4.6,
                },
                {
                    "name": "추천 음식점 2",
                    "category": "일식" if spice_level < 3 else "중식",
                    "reason": f"매운맛 {spice_level}단 기준으로 추천드려요!",
                    "rating": 4.4,
                },
                {
                    "name": "추천 음식점 3",
                    "category": "분식" if "1만원" in budget else "양식",
                    "reason": f"예산 {budget}에 맞는 맛집이에요!",
                    "rating": 4.3,
                },
            ]

            return recommended_restaurants

        except Exception as e:
            st.error(f"추천 미리보기 생성 중 오류: {str(e)}")
            return []

    def get_location_suggestions(self, query: str) -> List[str]:
        """위치 검색 자동완성 제안"""
        # 실제로는 지도 API나 위치 DB에서 검색
        seoul_districts = [
            "강남구",
            "강동구",
            "강북구",
            "강서구",
            "관악구",
            "광진구",
            "구로구",
            "금천구",
            "노원구",
            "도봉구",
            "동대문구",
            "동작구",
            "마포구",
            "서대문구",
            "서초구",
            "성동구",
            "성북구",
            "송파구",
            "양천구",
            "영등포구",
            "용산구",
            "은평구",
            "종로구",
            "중구",
            "중랑구",
        ]

        popular_areas = [
            "신사동",
            "홍대",
            "명동",
            "이태원",
            "강남역",
            "신촌",
            "여의도",
            "잠실",
            "건대",
            "압구정",
            "청담동",
            "삼성동",
            "논현동",
            "역삼동",
            "서면",
            "센텀시티",
        ]

        suggestions = []
        query_lower = query.lower()

        # 구 단위 검색
        for district in seoul_districts:
            if query_lower in district.lower():
                suggestions.append(f"서울시 {district}")

        # 동/지역명 검색
        for area in popular_areas:
            if query_lower in area.lower():
                suggestions.append(area)

        return suggestions[:5]  # 최대 5개 제안

    def analyze_user_taste_profile(
        self, ratings_data: Dict[str, int]
    ) -> Dict[str, Any]:
        """사용자 취향 프로필 분석"""
        analysis = {
            "total_ratings": len([r for r in ratings_data.values() if r > 0]),
            "average_rating": 0,
            "preferred_categories": [],
            "rating_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        }

        if analysis["total_ratings"] > 0:
            valid_ratings = [r for r in ratings_data.values() if r > 0]
            analysis["average_rating"] = sum(valid_ratings) / len(valid_ratings)

            # 평점 분포 계산
            for rating in valid_ratings:
                analysis["rating_distribution"][rating] += 1

        # 선호 카테고리 분석 (실제로는 음식점 ID로 카테고리 매칭)
        # 현재는 샘플 데이터로 대체
        analysis["preferred_categories"] = ["한식", "양식"]

        return analysis


# 전역 인스턴스 제거
# onboarding_manager = OnboardingManager()


def get_onboarding_manager(app=None) -> OnboardingManager:
    """온보딩 매니저 인스턴스 반환"""
    return OnboardingManager(app)
