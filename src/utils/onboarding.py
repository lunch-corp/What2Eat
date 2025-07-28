# utils/onboarding.py

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from firebase_admin import firestore

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

            distance = row.get("distance", 0)
            if pd.isna(distance):
                distance = 0.0
            else:
                distance = round(float(distance), 1)

            restaurant = {
                "id": str(row.get("diner_idx", "")),
                "name": row.get("diner_name", ""),
                "category": row.get("diner_category_large", "카테고리 정보 없음"),
                "diner_category_large": row.get("diner_category_large", ""),
                "address": row.get("diner_num_address", f"{location} 근처"),
                "rating": rating,
                "review_count": review_count,
                "price_range": "정보 없음",
                "specialties": row.get("diner_menu_name", [])[:3]
                if row.get("diner_menu_name")
                else [],
                "distance": distance,
            }
            restaurants.append(restaurant)

        return restaurants

    def get_restaurants_by_preferred_categories(
        self,
        location: str,
        preferred_categories: List[str],
        offset: int = 0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """선호 카테고리 기반 음식점 조회 (페이징 지원)"""
        if not self.app or not hasattr(self.app, "df_diner"):
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

        # 선호 카테고리 기반 필터링 (우선순위: 선호 카테고리 > 기타)
        preferred_restaurants = []
        other_restaurants = []
        df_quality = df_quality[df_quality["diner_category_large"].notna()]

        for _, row in df_quality.iterrows():
            restaurant_category = row.get("diner_category_large", "")

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

            distance = row.get("distance", 0)
            if pd.isna(distance):
                distance = 0.0
            else:
                distance = round(float(distance), 1)

            diner_grade = row.get("diner_grade", 0)
            if pd.isna(diner_grade):
                diner_grade = 0.0
            else:
                diner_grade = float(diner_grade)

            restaurant = {
                "id": str(row.get("diner_idx", "")),
                "name": row.get("diner_name", ""),
                "category": restaurant_category,
                "diner_category_large": restaurant_category,
                "address": row.get("diner_num_address", f"{location} 근처"),
                "rating": rating,
                "review_count": review_count,
                "price_range": "정보 없음",
                "specialties": row.get("diner_menu_name", [])[:3]
                if row.get("diner_menu_name")
                else [],
                "distance": distance,
                "diner_grade": diner_grade,
                "is_preferred": restaurant_category in preferred_categories,
            }

            if restaurant_category in preferred_categories:
                preferred_restaurants.append(restaurant)
            else:
                other_restaurants.append(restaurant)

        # 선호 카테고리는 diner_grade 높은 순, 기타 카테고리도 diner_grade 높은 순 정렬
        preferred_restaurants.sort(key=lambda x: x["diner_grade"], reverse=True)
        other_restaurants.sort(key=lambda x: x["diner_grade"], reverse=True)

        # 선호 카테고리를 먼저 배치하고, 그 다음 기타 카테고리 배치
        all_restaurants = preferred_restaurants + other_restaurants

        # 페이징 처리
        end_idx = offset + limit
        return all_restaurants[offset:end_idx]

    def get_total_restaurants_count(
        self, location: str, preferred_categories: List[str] = None
    ) -> int:
        """전체 음식점 개수 조회"""
        if not self.app or not hasattr(self.app, "df_diner"):
            return 0

        # 현재 사용자 위치 정보 가져오기
        if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
            return 0

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

        return len(df_quality)

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
        df_selected["diner_review_cnt"].fillna(0, inplace=True)

        # 결과를 딕셔너리 리스트로 변환
        similar_restaurants = []
        for _, row in df_selected.iterrows():
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

            restaurant = {
                "id": str(row.get("diner_idx", "")),
                "name": row.get("diner_name", ""),
                "category": row.get("diner_category_large", ""),
                "rating": diner_grade,
                "specialties": row.get("diner_menu_name", [])[:2]
                if row.get("diner_menu_name")
                else [],
                "distance": distance,
                "review_count": review_count,
            }
            similar_restaurants.append(restaurant)

        return similar_restaurants

    def save_user_profile(
        self, profile_data: Dict[str, Any], ratings_data: Dict[str, int]
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
                db.collection("users").document(uid).collection("onboarding_logs").document("profile").set(save_data)
                st.success("✅ 프로필이 성공적으로 저장되었습니다!")
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

    def load_user_profile(self) -> Optional[Dict[str, Any]]:
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
                doc = db.collection("users").document(uid).collection("onboarding_logs").document("profile").get()
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
        self, profile_updates: Dict[str, Any] = None, ratings_updates: Dict[str, int] = None
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
                doc_ref = db.collection("users").document(uid).collection("onboarding_logs").document("profile")
                
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
                        "updated_fields": list(profile_updates.keys()) if profile_updates else [],
                        "updated_ratings_count": len(ratings_updates) if ratings_updates else 0,
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
                db.collection("users").document(uid).collection("onboarding_logs").document("profile").delete()
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
        self, profile_data: Dict[str, Any], ratings_data: Dict[str, int]
    ) -> List[str]:
        """온보딩 데이터 유효성 검사"""
        errors = []

        # 필수 프로필 정보 확인
        required_fields = ["location", "birth_year", "gender", "regular_budget"]
        for field in required_fields:
            if not profile_data.get(field):
                errors.append(f"{field} 정보가 누락되었습니다.")

        # 선호 음식 카테고리 확인
        food_prefs_large = profile_data.get("food_preferences_large", [])
        if not food_prefs_large:
            errors.append("최소 1개의 선호 음식 종류를 선택해주세요.")

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
        """온보딩 데이터 기반 추천 미리보기 - 실제 데이터 활용"""
        try:
            if not self.app or not hasattr(self.app, "df_diner"):
                return []

            # 현재 사용자 위치 정보 확인
            if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
                return []

            user_lat = st.session_state.user_lat
            user_lon = st.session_state.user_lon

            # 2km 반경 내 데이터 필터링
            df_geo_filtered = get_filtered_data(
                self.app.df_diner, user_lat, user_lon, max_radius=100
            )

            # diner_grade가 있는 데이터만 필터링
            df_geo_filtered = df_geo_filtered[df_geo_filtered["diner_grade"].notna()]

            # diner_grade가 1 이상인 찐맛집만 필터링
            df_quality = df_geo_filtered[df_geo_filtered["diner_grade"] >= 1]

            if len(df_quality) == 0:
                return []

            # 온보딩 정보 분석
            preferred_categories = profile_data.get(
                "food_preferences_large", profile_data.get("food_preferences", [])
            )
            spice_level = profile_data.get("spice_level", 2)
            budget = profile_data.get("regular_budget", "1-2만원")
            age_group = self._get_age_group(profile_data.get("birth_year"))
            gender = profile_data.get("gender", "기타")

            # 사용자가 높게 평가한 음식점들의 카테고리 분석
            high_rated_categories = self._analyze_rated_categories(ratings_data)

            # 추천 로직 적용
            recommendations = []

            # 1. 선호 카테고리 기반 추천 (가중치 높음)
            if preferred_categories:
                pref_recs = self._get_category_based_recommendations(
                    df_quality, preferred_categories, limit=2
                )
                for rec in pref_recs:
                    rec["reason"] = f"선호하시는 {rec['category']} 카테고리의 인기 맛집이에요! (평점 {rec['diner_grade']:.1f})"
                    rec["recommendation_type"] = "선호 카테고리"
                recommendations.extend(pref_recs)

            # 2. 평가 패턴 기반 추천
            if high_rated_categories:
                pattern_recs = self._get_pattern_based_recommendations(
                    df_quality, high_rated_categories, preferred_categories, limit=2
                )
                for rec in pattern_recs:
                    rec["reason"] = f"평가하신 {rec['category']} 맛집들과 비슷한 스타일이에요! (평점 {rec['diner_grade']:.1f})"
                    rec["recommendation_type"] = "취향 분석"
                recommendations.extend(pattern_recs)

            # 3. 예산 고려 추천
            budget_recs = self._get_budget_friendly_recommendations(
                df_quality, budget, preferred_categories + high_rated_categories, limit=1
            )
            for rec in budget_recs:
                rec["reason"] = f"예산 {budget}에 맞는 가성비 좋은 맛집이에요! (평점 {rec['diner_grade']:.1f})"
                rec["recommendation_type"] = "예산 맞춤"
            recommendations.extend(budget_recs)

            # 4. 매운맛 선호도 기반 추천
            spice_recs = self._get_spice_level_recommendations(
                df_quality, spice_level, preferred_categories + high_rated_categories, limit=1
            )
            for rec in spice_recs:
                spice_desc = "순한맛" if spice_level <= 2 else "보통맛" if spice_level <= 3 else "매운맛"
                rec["reason"] = f"매운맛 {spice_level}단 기준으로 {spice_desc} 좋아하실 것 같아요! (평점 {rec['diner_grade']:.1f})"
                rec["recommendation_type"] = "매운맛 맞춤"
            recommendations.extend(spice_recs)

            # 5. 연령/성별 기반 인기 맛집 추천
            demo_recs = self._get_demographic_recommendations(
                df_quality, age_group, gender, preferred_categories + high_rated_categories, limit=1
            )
            for rec in demo_recs:
                rec["reason"] = f"{age_group} {gender}분들이 많이 찾는 인기 맛집이에요! (평점 {rec['diner_grade']:.1f})"
                rec["recommendation_type"] = "인기 맛집"
            recommendations.extend(demo_recs)

            # 중복 제거 및 최종 정리
            unique_recommendations = self._remove_duplicates(recommendations)

            # 최대 5개로 제한하고 다양성 확보
            final_recommendations = self._ensure_diversity(unique_recommendations, max_count=5)

            return final_recommendations

        except Exception as e:
            st.error(f"추천 미리보기 생성 중 오류: {str(e)}")
            return []

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

    def _analyze_rated_categories(self, ratings_data: Dict[str, int]) -> List[str]:
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
        self, df_quality: pd.DataFrame, preferred_categories: List[str], limit: int = 2
    ) -> List[Dict[str, Any]]:
        """선호 카테고리 기반 추천"""
        category_recs = []
        
        for category in preferred_categories[:2]:  # 상위 2개 카테고리만
            category_df = df_quality[df_quality["diner_category_large"] == category]
            if len(category_df) > 0:
                # diner_grade 높은 순으로 정렬하여 상위 1개 선택
                top_restaurant = category_df.nlargest(1, "diner_grade")
                category_recs.extend(self._convert_to_recommendation_format(top_restaurant))
                
        return category_recs[:limit]

    def _get_pattern_based_recommendations(
        self, df_quality: pd.DataFrame, high_rated_categories: List[str], 
        preferred_categories: List[str], limit: int = 2
    ) -> List[Dict[str, Any]]:
        """평가 패턴 기반 추천"""
        pattern_recs = []
        
        # 이미 선호 카테고리에서 추천된 것과 다른 카테고리 선택
        available_categories = [cat for cat in high_rated_categories if cat not in preferred_categories]
        
        for category in available_categories[:2]:
            category_df = df_quality[df_quality["diner_category_large"] == category]
            if len(category_df) > 0:
                top_restaurant = category_df.nlargest(1, "diner_grade")
                pattern_recs.extend(self._convert_to_recommendation_format(top_restaurant))
                
        return pattern_recs[:limit]

    def _get_budget_friendly_recommendations(
        self, df_quality: pd.DataFrame, budget: str, exclude_categories: List[str], limit: int = 1
    ) -> List[Dict[str, Any]]:
        """예산 친화적 추천 (분식, 한식 등 가성비 좋은 카테고리 우선)"""
        budget_friendly_categories = ["분식", "한식", "치킨", "중식", "패스트푸드"]
        
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
                    return self._convert_to_recommendation_format(top_restaurant)[:limit]
                    
        return []

    def _get_spice_level_recommendations(
        self, df_quality: pd.DataFrame, spice_level: int, exclude_categories: List[str], limit: int = 1
    ) -> List[Dict[str, Any]]:
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
                    return self._convert_to_recommendation_format(top_restaurant)[:limit]
                    
        return []

    def _get_demographic_recommendations(
        self, df_quality: pd.DataFrame, age_group: str, gender: str, 
        exclude_categories: List[str], limit: int = 1
    ) -> List[Dict[str, Any]]:
        """연령/성별 기반 인기 맛집 추천"""
        # 전체적으로 인기 높은 카테고리에서 추천
        popular_categories = ["한식", "양식", "일식", "중식", "카페"]
        
        for category in popular_categories:
            if category not in exclude_categories:
                category_df = df_quality[df_quality["diner_category_large"] == category]
                if len(category_df) > 0:
                    # 리뷰 수와 평점을 모두 고려한 종합 점수로 정렬
                    category_df = category_df.copy()
                    category_df["composite_score"] = (
                        category_df["diner_grade"] * 0.7 + 
                        (category_df["diner_review_cnt"].fillna(0) / category_df["diner_review_cnt"].fillna(0).max()) * 0.3
                    )
                    top_restaurant = category_df.nlargest(1, "composite_score")
                    return self._convert_to_recommendation_format(top_restaurant)[:limit]
                    
        return []

    def _convert_to_recommendation_format(self, df_restaurants: pd.DataFrame) -> List[Dict[str, Any]]:
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

            recommendation = {
                "id": str(row.get("diner_idx", "")),
                "name": row.get("diner_name", ""),
                "category": row.get("diner_category_large", ""),
                "address": row.get("diner_num_address", ""),
                "diner_grade": diner_grade,
                "rating": diner_grade,  # 호환성을 위해 중복
                "review_count": review_count,
                "distance": distance,
                "specialties": row.get("diner_menu_name", [])[:3] if row.get("diner_menu_name") else [],
                "price_range": "정보 없음",
            }
            recommendations.append(recommendation)
            
        return recommendations

    def _remove_duplicates(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """중복 음식점 제거"""
        seen_ids = set()
        unique_recs = []
        
        for rec in recommendations:
            if rec["id"] not in seen_ids:
                seen_ids.add(rec["id"])
                unique_recs.append(rec)
                
        return unique_recs

    def _ensure_diversity(self, recommendations: List[Dict[str, Any]], max_count: int = 5) -> List[Dict[str, Any]]:
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
