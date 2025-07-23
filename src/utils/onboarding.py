# utils/onboarding.py

from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from utils.auth import get_current_user
from utils.firebase_logger import get_firebase_logger
from utils.firebase_logger import get_firebase_logger


class OnboardingManager:
    """온보딩 관련 로직을 관리하는 클래스"""

    def __init__(self):
        self.logger = get_firebase_logger()

    def get_popular_restaurants_by_location(
        self, location: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """위치 기반 인기 음식점 조회 (실제로는 DB에서 조회)"""
        # 현재는 샘플 데이터를 반환, 실제로는 위치 기반 DB 쿼리 수행
        sample_restaurants = [
            {
                "id": "rest_1",
                "name": "맛있는 한식당",
                "category": "한식",
                "address": f"{location} 근처",
                "rating": 4.5,
                "review_count": 234,
                "image_url": "https://via.placeholder.com/200x150/FF6B6B/FFFFFF?text=Korean",
                "price_range": "2-3만원",
                "specialties": ["김치찌개", "불고기", "비빔밥"],
            },
            {
                "id": "rest_2",
                "name": "이탈리안 파스타",
                "category": "양식",
                "address": f"{location} 근처",
                "rating": 4.2,
                "review_count": 156,
                "image_url": "https://via.placeholder.com/200x150/4ECDC4/FFFFFF?text=Italian",
                "price_range": "3-4만원",
                "specialties": ["까르보나라", "아라비아타", "알리오올리오"],
            },
            {
                "id": "rest_3",
                "name": "스시 전문점",
                "category": "일식",
                "address": f"{location} 근처",
                "rating": 4.7,
                "review_count": 89,
                "image_url": "https://via.placeholder.com/200x150/45B7D1/FFFFFF?text=Sushi",
                "price_range": "5-7만원",
                "specialties": ["오마카세", "초밥", "사시미"],
            },
            {
                "id": "rest_4",
                "name": "매운 떡볶이",
                "category": "분식",
                "address": f"{location} 근처",
                "rating": 4.1,
                "review_count": 312,
                "image_url": "https://via.placeholder.com/200x150/F7DC6F/FFFFFF?text=Tteok",
                "price_range": "1-2만원",
                "specialties": ["떡볶이", "튀김", "순대"],
            },
            {
                "id": "rest_5",
                "name": "고급 스테이크하우스",
                "category": "양식",
                "address": f"{location} 근처",
                "rating": 4.8,
                "review_count": 67,
                "image_url": "https://via.placeholder.com/200x150/E74C3C/FFFFFF?text=Steak",
                "price_range": "10만원 이상",
                "specialties": ["토마호크", "티본스테이크", "와인"],
            },
            {
                "id": "rest_6",
                "name": "중화요리 전문점",
                "category": "중식",
                "address": f"{location} 근처",
                "rating": 4.3,
                "review_count": 178,
                "image_url": "https://via.placeholder.com/200x150/9B59B6/FFFFFF?text=Chinese",
                "price_range": "2-4만원",
                "specialties": ["짜장면", "짬뽕", "탕수육"],
            },
            {
                "id": "rest_7",
                "name": "타이 레스토랑",
                "category": "동남아식",
                "address": f"{location} 근처",
                "rating": 4.4,
                "review_count": 95,
                "image_url": "https://via.placeholder.com/200x150/27AE60/FFFFFF?text=Thai",
                "price_range": "3-5만원",
                "specialties": ["팟타이", "똠얌꿍", "그린커리"],
            },
        ]

        return sample_restaurants[:limit]

    def get_similar_restaurants(
        self, restaurant_id: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """유사 음식점 조회 (실제로는 추천 알고리즘 사용)"""
        similar_data = {
            "rest_1": [  # 한식당과 유사한 음식점
                {
                    "id": "similar_1_1",
                    "name": "전통 한정식",
                    "category": "한식",
                    "rating": 4.6,
                    "specialties": ["한정식", "전통요리"],
                },
                {
                    "id": "similar_1_2",
                    "name": "김치찌개 전문점",
                    "category": "한식",
                    "rating": 4.2,
                    "specialties": ["김치찌개", "된장찌개"],
                },
            ],
            "rest_2": [  # 이탈리안과 유사한 음식점
                {
                    "id": "similar_2_1",
                    "name": "피자 마르게리타",
                    "category": "양식",
                    "rating": 4.3,
                    "specialties": ["나폴리피자", "마르게리타"],
                },
                {
                    "id": "similar_2_2",
                    "name": "리조또 하우스",
                    "category": "양식",
                    "rating": 4.5,
                    "specialties": ["트러플리조또", "해산물리조또"],
                },
            ],
            "rest_3": [  # 스시와 유사한 음식점
                {
                    "id": "similar_3_1",
                    "name": "이자카야",
                    "category": "일식",
                    "rating": 4.4,
                    "specialties": ["사케", "안주", "야키토리"],
                },
                {
                    "id": "similar_3_2",
                    "name": "사시미 전문점",
                    "category": "일식",
                    "rating": 4.6,
                    "specialties": ["참치", "광어", "연어"],
                },
            ],
            "rest_4": [  # 분식과 유사한 음식점
                {
                    "id": "similar_4_1",
                    "name": "치킨 전문점",
                    "category": "치킨",
                    "rating": 4.2,
                    "specialties": ["양념치킨", "후라이드"],
                },
                {
                    "id": "similar_4_2",
                    "name": "족발보쌈",
                    "category": "한식",
                    "rating": 4.3,
                    "specialties": ["족발", "보쌈", "막국수"],
                },
            ],
        }

        return similar_data.get(restaurant_id, [])[:limit]

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


# 전역 인스턴스
onboarding_manager = OnboardingManager()


def get_onboarding_manager() -> OnboardingManager:
    """온보딩 매니저 인스턴스 반환"""
    return onboarding_manager
