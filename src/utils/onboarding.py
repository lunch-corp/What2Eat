# utils/onboarding.py

import asyncio
from datetime import datetime
from typing import Any, Optional

import pandas as pd
import streamlit as st
from firebase_admin import firestore

from utils.api import APIRequester
from utils.api_client import get_yamyam_ops_client
from utils.auth import get_current_user
from utils.firebase_logger import get_firebase_logger
from utils.similar_restaurants import SimilarRestaurantFetcher


class OnboardingManager:
    """온보딩 관련 로직을 관리하는 클래스 (API 기반)"""

    def __init__(self, app=None):
        self.logger = get_firebase_logger()
        self.app = app  # 레거시 호환성
        # 유사 식당 fetcher 초기화
        if app and hasattr(app, "df_diner"):
            self.similar_fetcher = SimilarRestaurantFetcher()
        else:
            self.similar_fetcher = None
        self.api_requester = APIRequester(endpoint=st.secrets["API_URL"])

    def _convert_api_response_to_restaurant(
        self, row: dict[str, Any]
    ) -> dict[str, Any]:
        """API 응답을 온보딩용 음식점 형식으로 변환"""
        # NaN 값 안전하게 처리
        review_count = row.get("diner_review_cnt", 0)
        if pd.isna(review_count):
            review_count = 0
        else:
            review_count = int(review_count)

        rating = row.get("diner_review_avg", 0)
        if pd.isna(rating):
            rating = 0.0
        else:
            rating = float(rating)

        distance = row.get("distance_km", 0)
        if pd.isna(distance):
            distance = 0.0
        else:
            distance = round(float(distance), 1)

        # diner_menu_name 처리
        specialties = row.get("diner_menu_name", [])
        if isinstance(specialties, str):
            # 문자열인 경우 쉼표로 분리
            specialties = [s.strip() for s in specialties.split(",") if s.strip()][:3]
        elif isinstance(specialties, list):
            specialties = specialties[:3]
        else:
            specialties = []

        return {
            "id": str(row.get("diner_idx", "")),
            "name": row.get("diner_name", ""),
            "category": row.get("diner_category_large", "카테고리 정보 없음"),
            "diner_category_large": row.get("diner_category_large", ""),
            "address": row.get("diner_num_address", "주소 정보 없음"),
            "rating": rating,
            "review_count": review_count,
            "price_range": "정보 없음",
            "specialties": specialties,
            "distance": distance,
        }

    def get_popular_restaurants_by_location(
        self, location: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """위치 기반 인기 음식점 조회 (2km 반경, API 호출)"""
        # 현재 사용자 위치 정보 가져오기
        if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
            return []

        user_lat = st.session_state.user_lat
        user_lon = st.session_state.user_lon

        try:
            # API 클라이언트 가져오기
            client = get_yamyam_ops_client()
            if not client:
                return []

            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            restaurants = loop.run_until_complete(
                client.get_restaurants(
                    user_lat=user_lat,
                    user_lon=user_lon,
                    radius_km=2.0,
                    sort_by="popularity",
                    limit=limit,
                )
            )
            loop.close()

            if not restaurants:
                return []

            # 응답 형식 변환
            return [self._convert_api_response_to_restaurant(r) for r in restaurants]

        except Exception as e:
            print(f"인기 음식점 조회 실패: {e}")
            return []

    def get_restaurants_by_preferred_categories(
        self,
        location: str,
        preferred_categories: list[str],
        offset: int = 0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """선호 카테고리 기반 음식점 조회 (페이징 지원, API 호출)
        
        여러 카테고리를 전달받으면 각 카테고리별로 API를 호출하고,
        결과를 합친 후 popularity 기준으로 정렬하여 반환합니다.
        """
        # 현재 사용자 위치 정보 가져오기
        if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
            return []

        user_lat = st.session_state.user_lat
        user_lon = st.session_state.user_lon

        try:
            # API 클라이언트 가져오기
            client = get_yamyam_ops_client()
            if not client:
                return []

            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            restaurants = loop.run_until_complete(
                client.get_restaurants(
                    user_lat=user_lat,
                    user_lon=user_lon,
                    radius_km=3.0,
                    large_categories=preferred_categories,
                    sort_by="popularity",
                    limit=limit,
                    offset=offset,
                )
            )
            loop.close()

            if not restaurants:
                return []

            # 응답 형식 변환
            return [self._convert_api_response_to_restaurant(r) for r in restaurants]

        except Exception as e:
            print(f"선호 카테고리 기반 음식점 조회 실패: {e}")
            return []

    def get_total_restaurants_count(
        self, location: str, preferred_categories: list[str] = None
    ) -> int:
        """
        전체 음식점 개수 조회 (API 기반에서는 정확한 개수를 알 수 없음)

        Note: API 기반으로 전환되면서 정확한 전체 개수를 알 수 없습니다.
        대신 충분히 큰 숫자를 반환하여 "더 보기" 버튼이 계속 표시되도록 합니다.
        """
        # API 기반에서는 전체 개수를 정확히 알 수 없으므로
        # 충분히 큰 숫자를 반환 (실제로는 페이지네이션으로 처리)
        return 9999

    def get_similar_restaurants(
        self, restaurant_id: str, limit: int = 3, use_item_cf: bool = True
    ) -> list[dict[str, Any]]:
        """
        유사 음식점 조회

        Args:
            restaurant_id: 기준 식당 ID
            limit: 반환할 최대 개수
            use_item_cf: True면 API 사용, False면 카테고리 기반
        """
        if not self.similar_fetcher:
            return []

        return self.similar_fetcher.get_similar_restaurants(
            diner_idx=int(restaurant_id),
            user_lat=st.session_state.get("user_lat"),
            user_lon=st.session_state.get("user_lon"),
            use_item_cf=use_item_cf,
            limit=limit,
        )

    def save_user_profile(
        self, profile_data: dict[str, Any], ratings_data: dict[str, int]
    ) -> bool:
        """사용자 프로필 데이터를 users/{uid}/onboarding_logs 하위 컬렉션에 저장"""
        try:
            user_info = get_current_user()
            if not user_info:
                return False

            uid = user_info.get("localId")
            if not uid:
                return False

            # 저장할 데이터 구성 (profile_data를 직접 사용하여 중복 제거)
            save_data = {
                "user_id": uid,
                **profile_data,  # profile_data의 모든 필드를 직접 저장
                "ratings": ratings_data,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "onboarding_version": "1.0",
            }

            # Firestore의 users/{uid}/onboarding_logs 하위 컬렉션에 저장
            try:
                db = firestore.client()
                # activity_logs와 같은 레벨의 하위 컬렉션으로 저장
                db.collection("users").document(uid).collection(
                    "onboarding_logs"
                ).document("profile").set(save_data)

            except Exception as firestore_error:
                st.warning(f"⚠️ Firestore 저장 실패: {str(firestore_error)}")
                # Firestore 저장 실패해도 계속 진행

            # 로그 기록
            if self.logger.is_available():
                self.logger.log_user_activity(
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

    def load_user_profile(self) -> Optional[dict[str, Any]]:
        """users/{uid}/onboarding_logs 하위 컬렉션에서 사용자 프로필 데이터를 로드"""
        try:
            user_info = get_current_user()
            if not user_info:
                return None

            uid = user_info.get("localId")
            if not uid:
                return None

            # Firestore의 users/{uid}/onboarding_logs 하위 컬렉션에서 로드
            try:
                db = firestore.client()
                doc = (
                    db.collection("users")
                    .document(uid)
                    .collection("onboarding_logs")
                    .document("profile")
                    .get()
                )
                if doc.exists:
                    return doc.to_dict()
                else:
                    return None
            except Exception as firestore_error:
                st.warning(f"⚠️ Firestore 로드 실패: {str(firestore_error)}")
                return None

        except Exception as e:
            st.error(f"프로필 로드 중 오류: {str(e)}")
            return None

    def update_user_profile(
        self,
        profile_updates: dict[str, Any] = None,
        ratings_updates: dict[str, int] = None,
    ) -> bool:
        """사용자 프로필 데이터를 부분적으로 업데이트"""
        try:
            user_info = get_current_user()
            if not user_info:
                return False

            uid = user_info.get("localId")
            if not uid:
                return False

            # Firestore의 users/{uid}/onboarding_logs 하위 컬렉션에서 업데이트
            try:
                db = firestore.client()
                doc_ref = (
                    db.collection("users")
                    .document(uid)
                    .collection("onboarding_logs")
                    .document("profile")
                )

                # 업데이트할 데이터 구성
                update_data = {
                    "updated_at": datetime.now().isoformat(),
                }

                # 프로필 데이터 업데이트
                if profile_updates:
                    update_data.update(profile_updates)

                # 평점 데이터 업데이트
                if ratings_updates:
                    # 기존 평점 데이터와 병합
                    existing_doc = doc_ref.get()
                    if existing_doc.exists:
                        existing_ratings = existing_doc.to_dict().get("ratings", {})
                        existing_ratings.update(ratings_updates)
                        update_data["ratings"] = existing_ratings
                    else:
                        update_data["ratings"] = ratings_updates

                # 문서 업데이트 (merge=True로 기존 데이터 유지)
                doc_ref.set(update_data, merge=True)
                st.success("✅ 프로필이 성공적으로 업데이트되었습니다!")

            except Exception as firestore_error:
                st.warning(f"⚠️ Firestore 업데이트 실패: {str(firestore_error)}")
                return False

            # 로그 기록
            if self.logger.is_available():
                self.logger.log_user_activity(
                    uid,
                    "profile_updated",
                    {
                        "updated_fields": list(profile_updates.keys())
                        if profile_updates
                        else [],
                        "updated_ratings_count": len(ratings_updates)
                        if ratings_updates
                        else 0,
                    },
                )

            return True

        except Exception as e:
            st.error(f"프로필 업데이트 중 오류: {str(e)}")
            return False

    def delete_user_profile(self) -> bool:
        """사용자 프로필 데이터를 삭제"""
        try:
            user_info = get_current_user()
            if not user_info:
                return False

            uid = user_info.get("localId")
            if not uid:
                return False

            # Firestore의 users/{uid}/onboarding_logs 하위 컬렉션에서 삭제
            try:
                db = firestore.client()
                db.collection("users").document(uid).collection(
                    "onboarding_logs"
                ).document("profile").delete()
                st.success("✅ 프로필이 성공적으로 삭제되었습니다!")

            except Exception as firestore_error:
                st.warning(f"⚠️ Firestore 삭제 실패: {str(firestore_error)}")
                return False

            # 로그 기록
            if self.logger.is_available():
                self.logger.log_user_activity(
                    uid,
                    "profile_deleted",
                    {},
                )

            return True

        except Exception as e:
            st.error(f"프로필 삭제 중 오류: {str(e)}")
            return False

    def validate_onboarding_data(
        self, profile_data: dict[str, Any], ratings_data: dict[str, int]
    ) -> list[str]:
        """온보딩 데이터 유효성 검사"""
        errors = []

        # 필수 프로필 정보 확인
        required_fields = ["location"]
        for field in required_fields:
            if not profile_data.get(field):
                errors.append(f"{field} 정보가 누락되었습니다.")

        # 선호 음식 카테고리 확인
        food_prefs_large = profile_data.get("food_preferences_large", [])
        if not food_prefs_large:
            errors.append("최소 1개의 선호 음식 종류를 선택해주세요.")

        # 평가 개수 확인
        rated_count = len([r for r in ratings_data.values() if r > 0])
        if rated_count < 5:  # 최소 5개 평가 필요
            errors.append(f"최소 5개 음식점 평가가 필요합니다. (현재: {rated_count}개)")

        return errors

    def _get_age_group(self, birth_year: int) -> str:
        """출생연도를 기반으로 연령대 반환"""
        if not birth_year:
            return "전체"

        current_year = datetime.now().year
        age = current_year - birth_year

        if age < 20:
            return "10대"
        elif age < 30:
            return "20대"
        elif age < 40:
            return "30대"
        elif age < 50:
            return "40대"
        elif age < 60:
            return "50대"
        else:
            return "60대 이상"

    def _analyze_rated_categories(self, ratings_data: dict[str, int]) -> list[str]:
        """사용자가 높게 평가한 음식점들의 카테고리 분석"""
        if not self.app or not hasattr(self.app, "df_diner"):
            return []

        high_rated_categories = []

        # 4점 이상 평가한 음식점들의 카테고리 추출
        for restaurant_id, rating in ratings_data.items():
            if rating >= 4:
                try:
                    restaurant_info = self.app.df_diner[
                        self.app.df_diner["diner_idx"].astype(str) == restaurant_id
                    ]
                    if len(restaurant_info) > 0:
                        category = restaurant_info.iloc[0].get("diner_category_large")
                        if category and category not in high_rated_categories:
                            high_rated_categories.append(category)
                except Exception:
                    continue

        return high_rated_categories

    def _get_category_based_recommendations(
        self, df_quality: pd.DataFrame, preferred_categories: list[str], limit: int = 2
    ) -> list[dict[str, Any]]:
        """선호 카테고리 기반 추천"""
        category_recs = []

        for category in preferred_categories[:2]:  # 상위 2개 카테고리만
            category_df = df_quality[df_quality["diner_category_large"] == category]
            if len(category_df) > 0:
                # diner_grade 높은 순으로 정렬하여 상위 1개 선택
                top_restaurant = category_df.nlargest(1, "diner_grade")
                category_recs.extend(
                    self._convert_to_recommendation_format(top_restaurant)
                )

        return category_recs[:limit]

    def _get_pattern_based_recommendations(
        self,
        df_quality: pd.DataFrame,
        high_rated_categories: list[str],
        preferred_categories: list[str],
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        """평가 패턴 기반 추천"""
        pattern_recs = []

        # 이미 선호 카테고리에서 추천된 것과 다른 카테고리 선택
        available_categories = [
            cat for cat in high_rated_categories if cat not in preferred_categories
        ]

        for category in available_categories[:2]:
            category_df = df_quality[df_quality["diner_category_large"] == category]
            if len(category_df) > 0:
                top_restaurant = category_df.nlargest(1, "diner_grade")
                pattern_recs.extend(
                    self._convert_to_recommendation_format(top_restaurant)
                )

        return pattern_recs[:limit]

    def _get_budget_friendly_recommendations(
        self,
        df_quality: pd.DataFrame,
        budget: str,
        exclude_categories: list[str],
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """예산 친화적 추천 (분식, 한식 등 가성비 좋은 카테고리 우선)"""

        # 예산에 따른 카테고리 우선순위 조정
        if "1만원" in budget or "만원 이하" in budget:
            priority_categories = ["분식", "패스트푸드", "치킨"]
        elif "1-2만원" in budget:
            priority_categories = ["한식", "분식", "중식"]
        else:
            priority_categories = ["한식", "양식", "일식"]

        for category in priority_categories:
            if category not in exclude_categories:
                category_df = df_quality[df_quality["diner_category_large"] == category]
                if len(category_df) > 0:
                    top_restaurant = category_df.nlargest(1, "diner_grade")
                    return self._convert_to_recommendation_format(top_restaurant)[
                        :limit
                    ]

        return []

    def _get_spice_level_recommendations(
        self,
        df_quality: pd.DataFrame,
        spice_level: int,
        exclude_categories: list[str],
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """매운맛 선호도 기반 추천"""
        if spice_level <= 2:  # 순한맛 선호
            mild_categories = ["일식", "양식", "디저트", "베이커리"]
        elif spice_level <= 3:  # 보통맛
            mild_categories = ["한식", "중식", "분식"]
        else:  # 매운맛 선호
            mild_categories = ["중식", "한식", "동남아시아음식", "인도음식"]

        for category in mild_categories:
            if category not in exclude_categories:
                category_df = df_quality[df_quality["diner_category_large"] == category]
                if len(category_df) > 0:
                    top_restaurant = category_df.nlargest(1, "diner_grade")
                    return self._convert_to_recommendation_format(top_restaurant)[
                        :limit
                    ]

        return []

    def _get_demographic_recommendations(
        self,
        df_quality: pd.DataFrame,
        age_group: str,
        gender: str,
        exclude_categories: list[str],
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """연령/성별 기반 인기 맛집 추천"""
        # 전체적으로 인기 높은 카테고리에서 추천
        popular_categories = ["한식", "양식", "일식", "중식", "카페"]

        for category in popular_categories:
            if category not in exclude_categories:
                category_df = df_quality[df_quality["diner_category_large"] == category]
                if len(category_df) > 0:
                    # 리뷰 수와 평점을 모두 고려한 종합 점수로 정렬
                    category_df = category_df.copy()

                    # diner_review_cnt를 숫자형으로 변환하고 NaN을 0으로 처리
                    review_counts = pd.to_numeric(
                        category_df["diner_review_cnt"], errors="coerce"
                    ).fillna(0)
                    max_review_count = review_counts.max()

                    # 0으로 나누기 방지: max_review_count가 0이면 정규화 점수는 0으로 설정
                    if max_review_count > 0:
                        normalized_review_score = review_counts / max_review_count
                    else:
                        normalized_review_score = 0

                    category_df["composite_score"] = (
                        category_df["diner_grade"] * 0.7 + normalized_review_score * 0.3
                    )
                    top_restaurant = category_df.nlargest(1, "composite_score")
                    return self._convert_to_recommendation_format(top_restaurant)[
                        :limit
                    ]

        return []

    def _convert_to_recommendation_format(
        self, df_restaurants: pd.DataFrame
    ) -> list[dict[str, Any]]:
        """DataFrame을 추천 형식으로 변환"""
        recommendations = []

        for _, row in df_restaurants.iterrows():
            # NaN 값 안전하게 처리
            review_count = row.get("diner_review_cnt", 0)
            if pd.isna(review_count):
                review_count = 0
            else:
                review_count = int(review_count)

            diner_grade = row.get("diner_grade", 0)
            if pd.isna(diner_grade):
                diner_grade = 0.0
            else:
                diner_grade = float(diner_grade)

            distance = row.get("distance", 0)
            if pd.isna(distance):
                distance = 0.0
            else:
                distance = round(float(distance), 1)

            # diner_menu_name 처리 - list 타입이면 문자열로 변환
            specialties = row.get("diner_menu_name", [])
            if isinstance(specialties, list):
                specialties = specialties[:3]
            else:
                specialties = []

            recommendation = {
                "id": str(row.get("diner_idx", "")),
                "name": row.get("diner_name", ""),
                "category": row.get("diner_category_large", ""),
                "address": row.get("diner_num_address", ""),
                "diner_grade": diner_grade,
                "rating": diner_grade,  # 호환성을 위해 중복
                "review_count": review_count,
                "distance": distance,
                "specialties": specialties,
                "price_range": "정보 없음",
            }
            recommendations.append(recommendation)

        return recommendations

    def _remove_duplicates(
        self, recommendations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """중복 음식점 제거"""
        seen_ids = set()
        unique_recs = []

        for rec in recommendations:
            if rec["id"] not in seen_ids:
                seen_ids.add(rec["id"])
                unique_recs.append(rec)

        return unique_recs

    def _ensure_diversity(
        self, recommendations: list[dict[str, Any]], max_count: int = 5
    ) -> list[dict[str, Any]]:
        """추천 목록의 다양성 확보"""
        if len(recommendations) <= max_count:
            return recommendations

        # 카테고리별로 분류
        category_groups = {}
        for rec in recommendations:
            category = rec["category"]
            if category not in category_groups:
                category_groups[category] = []
            category_groups[category].append(rec)

        # 각 카테고리에서 최대 2개씩 선택하여 다양성 확보
        diverse_recs = []
        for category, recs in category_groups.items():
            # diner_grade 높은 순으로 정렬하여 상위 2개 선택
            sorted_recs = sorted(recs, key=lambda x: x["diner_grade"], reverse=True)
            diverse_recs.extend(sorted_recs[:2])

        # 전체 평점 순으로 정렬하여 최종 max_count개 선택
        final_recs = sorted(diverse_recs, key=lambda x: x["diner_grade"], reverse=True)
        return final_recs[:max_count]

    def analyze_user_taste_profile(
        self, ratings_data: dict[str, int]
    ) -> dict[str, Any]:
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
