import json
from typing import Any

import firebase_admin
import streamlit as st
from firebase_admin import firestore


class FirebaseLogger:
    """Firebase Firestore를 사용한 사용자 활동 로깅 시스템 (컬렉션별 분리)"""

    def __init__(self):
        self.db = None
        self._initialize_firestore()

    def _initialize_firestore(self):
        """Firestore 클라이언트 초기화"""
        try:
            # Firebase Admin SDK가 초기화되었는지 확인
            firebase_admin.get_app()
            self.db = firestore.client()
        except ValueError:
            # Firebase Admin SDK 초기화
            self._initialize_firebase_admin()
            if self.db is None:
                self.db = firestore.client()
        except Exception as e:
            st.error(f"❌ Firestore 초기화 중 오류가 발생했습니다: {str(e)}")

    def _initialize_firebase_admin(self):
        """Firebase Admin SDK 초기화"""
        try:
            # streamlit_test.py에서 사용한 Firebase 키 정보
            FIREBASE_KEY = st.secrets["FIREBASE_KEY"]

            if not FIREBASE_KEY:
                raise ValueError("Firebase 키가 없습니다.")

            key_dict = json.loads(FIREBASE_KEY)

            if not firebase_admin._apps:
                from firebase_admin import credentials

                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred)

        except Exception as e:
            st.error(f"❌ Firebase Admin SDK 초기화 중 오류가 발생했습니다: {str(e)}")

    def is_available(self) -> bool:
        """Firebase Logger가 사용 가능한지 확인"""
        return self.db is not None

    def _log_to_collection(
        self, uid: str, collection_name: str, activity_type: str, detail: dict[str, Any]
    ) -> bool:
        """특정 컬렉션에 로그 저장"""
        if not self.is_available():
            return False

        try:
            log_ref = (
                self.db.collection("users")
                .document(uid)
                .collection(collection_name)
                .document()
            )

            log_data = {
                "type": activity_type,
                "detail": detail,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "session_id": st.session_state.get("session_id", "unknown"),
                "user_agent": st.session_state.get("user_agent", "unknown"),
            }

            log_ref.set(log_data)
            return True

        except Exception as e:
            st.error(f"❌ {collection_name} 로그 저장 중 오류가 발생했습니다: {str(e)}")
            return False

    # ========== 인증 관련 로그 (auth_logs) ==========
    def log_login(self, uid: str, login_method: str = "email"):
        """로그인 로그"""
        detail = {"login_method": login_method}
        return self._log_to_collection(uid, "auth_logs", "login", detail)

    def log_signup(self, uid: str, signup_method: str = "email"):
        """회원가입 로그"""
        detail = {"signup_method": signup_method}
        return self._log_to_collection(uid, "auth_logs", "signup", detail)

    def log_logout(self, uid: str):
        """로그아웃 로그"""
        detail = {}
        return self._log_to_collection(uid, "auth_logs", "logout", detail)

    # ========== 네비게이션 관련 로그 (navigation_logs) ==========
    def log_page_visit(self, uid: str, page_name: str):
        """페이지 방문 로그"""
        detail = {"page_name": page_name}
        return self._log_to_collection(uid, "navigation_logs", "page_visit", detail)

    def log_chat_step_progress(self, uid: str, step: str):
        """채팅 단계 진행 로그"""
        detail = {"step": step}
        return self._log_to_collection(
            uid, "navigation_logs", "chat_step_progress", detail
        )

    def log_location_change(self, uid: str, from_page: str):
        """위치 변경 로그"""
        detail = {"from_page": from_page}
        return self._log_to_collection(
            uid, "navigation_logs", "location_change", detail
        )

    # ========== 검색 관련 로그 (search_logs) ==========
    def log_location_search(
        self, uid: str, location: str, coordinates: dict[str, float] = None
    ):
        """위치 검색 로그"""
        detail = {"location": location, "coordinates": coordinates}
        return self._log_to_collection(uid, "search_logs", "location_search", detail)

    def log_menu_search(self, uid: str, search_term: str, results_count: int = 0):
        """메뉴 검색 로그"""
        detail = {"search_term": search_term, "results_count": results_count}
        return self._log_to_collection(uid, "search_logs", "menu_search", detail)

    def log_chat_interaction(
        self,
        uid: str,
        question: str,
        response: str,
        restaurants: list[dict[str, Any]] = None,
    ):
        """채팅 상호작용 로그"""
        detail = {
            "question": question,
            "response": response,
            "restaurants_count": len(restaurants) if restaurants else 0,
            "restaurants": restaurants[:5] if restaurants else [],  # 최대 5개만 저장
        }
        return self._log_to_collection(uid, "search_logs", "chat_interaction", detail)

    # ========== 상호작용 관련 로그 (interaction_logs) ==========
    def log_category_filter(self, uid: str, category: str):
        """카테고리 필터링 로그"""
        detail = {"category": category}
        return self._log_to_collection(
            uid, "interaction_logs", "category_filter", detail
        )

    def log_ranking_view(self, uid: str, ranking_type: str = "general"):
        """랭킹 페이지 조회 로그"""
        detail = {"ranking_type": ranking_type}
        return self._log_to_collection(uid, "interaction_logs", "ranking_view", detail)

    def log_radius_selection(
        self, uid: str, radius_km: float, radius_distance: str, restaurants_found: int
    ):
        """반경 선택 로그"""
        detail = {
            "radius_km": radius_km,
            "radius_distance": radius_distance,
            "restaurants_found": restaurants_found,
        }
        return self._log_to_collection(
            uid, "interaction_logs", "radius_selection", detail
        )

    def log_search_method_selection(self, uid: str, method: str):
        """검색 방법 선택 로그"""
        detail = {"method": method}
        return self._log_to_collection(
            uid, "interaction_logs", "search_method_selection", detail
        )

    def log_sort_option_change(
        self, uid: str, sort_option: str, from_page: str = "chat"
    ):
        """정렬 옵션 변경 로그"""
        detail = {"sort_option": sort_option, "from_page": from_page}
        return self._log_to_collection(
            uid, "interaction_logs", "sort_option_change", detail
        )

    # ========== 음식점 관련 로그 (restaurant_logs) ==========
    def log_restaurant_click(
        self,
        uid: str,
        restaurant_name: str,
        restaurant_url: str,
        restaurant_idx: str = None,
        category: str = None,
        location: str = None,
        grade: float = None,
        review_count: int = None,
        distance: float = None,
        from_page: str = "unknown",
    ):
        """음식점 클릭 로그 (강화된 버전)"""
        detail = {
            "restaurant_name": restaurant_name,
            "restaurant_url": restaurant_url,
            "restaurant_idx": restaurant_idx,
            "category": category,
            "location": location,
            "grade": grade,
            "review_count": review_count,
            "distance": distance,
            "from_page": from_page,
            "action": "click",
        }
        return self._log_to_collection(
            uid, "restaurant_logs", "restaurant_click", detail
        )

    def log_restaurant_detail_view(
        self,
        uid: str,
        restaurant_name: str,
        restaurant_idx: str = None,
        from_page: str = "unknown",
    ):
        """음식점 상세정보 조회 로그"""
        detail = {
            "restaurant_name": restaurant_name,
            "restaurant_idx": restaurant_idx,
            "from_page": from_page,
            "action": "detail_view",
        }
        return self._log_to_collection(
            uid, "restaurant_logs", "restaurant_detail_view", detail
        )

    def log_map_view(
        self,
        uid: str,
        restaurants_count: int,
        radius_km: float = None,
        from_page: str = "unknown",
    ):
        """지도 보기 로그"""
        detail = {
            "restaurants_count": restaurants_count,
            "radius_km": radius_km,
            "from_page": from_page,
            "action": "map_view",
        }
        return self._log_to_collection(uid, "restaurant_logs", "map_view", detail)

    def log_restaurant_favorite(
        self, uid: str, restaurant_name: str, restaurant_idx: str, action: str = "add"
    ):
        """음식점 즐겨찾기 로그"""
        detail = {
            "restaurant_name": restaurant_name,
            "restaurant_idx": restaurant_idx,
            "action": f"favorite_{action}",  # add, remove
        }
        return self._log_to_collection(
            uid, "restaurant_logs", "restaurant_favorite", detail
        )

    # ========== 기존 호환성을 위한 메서드 ==========
    def log_user_activity(
        self, uid: str, activity_type: str, detail: dict[str, Any]
    ) -> bool:
        """기존 호환성을 위한 통합 로그 메서드 (컬렉션 자동 분류)"""
        # 활동 타입에 따라 적절한 컬렉션으로 자동 분류
        if activity_type in ["login", "signup", "logout"]:
            collection_name = "auth_logs"
        elif activity_type in ["page_visit", "chat_step_progress", "location_change"]:
            collection_name = "navigation_logs"
        elif activity_type in ["location_search", "menu_search", "chat_interaction"]:
            collection_name = "search_logs"
        elif activity_type in [
            "category_filter",
            "ranking_view",
            "radius_selection",
            "search_method_selection",
            "sort_option_change",
        ]:
            collection_name = "interaction_logs"
        elif activity_type in [
            "restaurant_click",
            "restaurant_detail_view",
            "map_view",
            "restaurant_favorite",
        ]:
            collection_name = "restaurant_logs"
        elif activity_type in [
            "profile_created",
            "profile_updated",
            "profile_deleted",
            "onboarding_started",
            "onboarding_completed",
            "taste_rating_submitted",
        ]:
            collection_name = "onboarding_logs"
        else:
            # 분류되지 않은 활동은 기존 activity_logs에 저장
            collection_name = "activity_logs"

        return self._log_to_collection(uid, collection_name, activity_type, detail)

    # ========== 사용자 위치 관리 ==========
    def save_user_location(
        self, uid: str, address: str, lat: float, lon: float
    ) -> bool:
        """사용자 위치 정보를 Firestore에 저장"""
        if not self.is_available():
            return False

        try:
            user_ref = self.db.collection("users").document(uid)

            location_data = {
                "address": address,
                "lat": lat,
                "lon": lon,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }

            user_ref.set({"last_location": location_data}, merge=True)

            # 위치 저장 로그도 남기기
            self._log_to_collection(
                uid,
                "navigation_logs",
                "location_saved",
                {"address": address, "coordinates": {"lat": lat, "lon": lon}},
            )

            return True

        except Exception as e:
            st.error(f"❌ 사용자 위치 저장 중 오류가 발생했습니다: {str(e)}")
            return False

    def get_user_location(self, uid: str) -> dict[str, Any]:
        """사용자의 마지막 위치 정보를 Firestore에서 불러오기"""
        if not self.is_available():
            return None

        try:
            user_ref = self.db.collection("users").document(uid)
            user_doc = user_ref.get()

            if user_doc.exists:
                user_data = user_doc.to_dict()
                last_location = user_data.get("last_location")

                if last_location:
                    return {
                        "address": last_location.get("address"),
                        "lat": last_location.get("lat"),
                        "lon": last_location.get("lon"),
                        "updated_at": last_location.get("updated_at"),
                    }

            return None

        except Exception as e:
            st.error(f"❌ 사용자 위치 불러오기 중 오류가 발생했습니다: {str(e)}")
            return None

    # ========== 조회 메서드 ==========
    def get_user_logs(
        self, uid: str, limit: int = 10, collection_name: str = None
    ) -> list[dict[str, Any]]:
        """사용자 활동 로그 조회 (특정 컬렉션 또는 전체)"""
        if not self.is_available():
            return []

        try:
            all_logs = []

            if collection_name:
                # 특정 컬렉션만 조회
                logs_ref = (
                    self.db.collection("users")
                    .document(uid)
                    .collection(collection_name)
                )
                docs = (
                    logs_ref.order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(limit)
                    .stream()
                )
                all_logs = [
                    {"collection": collection_name, **doc.to_dict()} for doc in docs
                ]
            else:
                # 모든 컬렉션에서 조회
                collections = [
                    "auth_logs",
                    "navigation_logs",
                    "search_logs",
                    "interaction_logs",
                    "restaurant_logs",
                    "activity_logs",
                ]

                for col_name in collections:
                    try:
                        logs_ref = (
                            self.db.collection("users")
                            .document(uid)
                            .collection(col_name)
                        )
                        docs = (
                            logs_ref.order_by(
                                "timestamp", direction=firestore.Query.DESCENDING
                            )
                            .limit(limit)
                            .stream()
                        )
                        col_logs = [
                            {"collection": col_name, **doc.to_dict()} for doc in docs
                        ]
                        all_logs.extend(col_logs)
                    except Exception:
                        # 컬렉션이 존재하지 않는 경우 무시
                        continue

                # 타임스탬프로 정렬 후 limit 적용
                all_logs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
                all_logs = all_logs[:limit]

            return all_logs

        except Exception as e:
            st.error(f"❌ 활동 로그 조회 중 오류가 발생했습니다: {str(e)}")
            return []

    def get_user_statistics(self, uid: str) -> dict[str, Any]:
        """사용자 통계 정보 조회 (모든 컬렉션 통합)"""
        if not self.is_available():
            return {}

        try:
            collections = [
                "auth_logs",
                "navigation_logs",
                "search_logs",
                "interaction_logs",
                "restaurant_logs",
                "activity_logs",
                "onboarding_logs",
            ]

            total_activities = 0
            activity_types = {}
            collection_stats = {}

            for col_name in collections:
                try:
                    logs_ref = (
                        self.db.collection("users").document(uid).collection(col_name)
                    )
                    docs = list(logs_ref.stream())
                    col_count = len(docs)

                    if col_count > 0:
                        collection_stats[col_name] = col_count
                        total_activities += col_count

                        # 활동 유형별 통계
                        for doc in docs:
                            activity_type = doc.to_dict().get("type", "unknown")
                            activity_types[activity_type] = (
                                activity_types.get(activity_type, 0) + 1
                            )

                except Exception:
                    # 컬렉션이 존재하지 않는 경우 무시
                    continue

            return {
                "total_activities": total_activities,
                "activity_types": activity_types,
                "collection_stats": collection_stats,
                "most_active_type": max(activity_types.items(), key=lambda x: x[1])[0]
                if activity_types
                else None,
                "most_active_collection": max(
                    collection_stats.items(), key=lambda x: x[1]
                )[0]
                if collection_stats
                else None,
            }

        except Exception as e:
            st.error(f"❌ 사용자 통계 조회 중 오류가 발생했습니다: {str(e)}")
            return {}


# 전역 Firebase Logger 인스턴스
_firebase_logger = None


def get_firebase_logger() -> FirebaseLogger:
    """Firebase Logger 싱글톤 인스턴스 반환"""
    global _firebase_logger
    if _firebase_logger is None:
        _firebase_logger = FirebaseLogger()
    return _firebase_logger


def log_user_activity(activity_type: str, detail: dict[str, Any]) -> bool:
    """사용자 활동 로그 저장 (편의 함수)"""
    logger = get_firebase_logger()
    if "user_info" in st.session_state and st.session_state.user_info:
        uid = st.session_state.user_info.get("localId")
        if uid:
            return logger.log_user_activity(uid, activity_type, detail)
    return False
