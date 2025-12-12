"""
yamyam-ops API 클라이언트
Firebase 인증을 사용하여 yamyam-ops PostgreSQL과 통신
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
import streamlit as st

logger = logging.getLogger(__name__)


class YamYamOpsClient:
    """yamyam-ops API 클라이언트"""

    def __init__(self, base_url: str, timeout: float = 10.0):
        """
        Args:
            base_url: yamyam-ops API 베이스 URL
            timeout: 요청 타임아웃 (초)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get_firebase_token(self) -> Optional[str]:
        """세션에서 JWT Access Token 또는 Firebase ID Token 가져오기 (yamyam-ops용)"""
        try:
            # 먼저 JWT Access Token 확인 (yamyam-ops API용)
            if (
                hasattr(st.session_state, "jwt_access_token")
                and st.session_state.jwt_access_token
            ):
                # JWT 토큰 만료 확인 (5분 여유를 둠)
                if (
                    hasattr(st.session_state, "jwt_expires_at")
                    and st.session_state.jwt_expires_at
                ):
                    buffer_time = timedelta(minutes=5)
                    if datetime.now() + buffer_time < st.session_state.jwt_expires_at:
                        return st.session_state.jwt_access_token
                    else:
                        # JWT 토큰이 만료되었거나 곧 만료될 예정이면 갱신 시도
                        logger.info(
                            "JWT 토큰이 만료되었거나 곧 만료될 예정입니다. 갱신 시도 중..."
                        )
                        if self._refresh_jwt_token():
                            return st.session_state.jwt_access_token
                        else:
                            logger.warning(
                                "JWT 토큰 갱신 실패. Firebase ID Token으로 폴백합니다."
                            )
                else:
                    # 만료 시간 정보가 없으면 그냥 사용 (하위 호환성)
                    return st.session_state.jwt_access_token

            # JWT 토큰이 없거나 만료된 경우, Firebase ID Token으로 폴백
            # (하위 호환성을 위해)
            from utils.auth import get_current_user

            user_info = get_current_user()
            if user_info:
                # Firebase ID Token 가져오기
                if (
                    hasattr(st.session_state, "auth_token")
                    and st.session_state.auth_token
                ):
                    return st.session_state.auth_token

            return None
        except Exception as e:
            logger.error(f"Token 가져오기 실패: {e}")
            return None

    def _refresh_jwt_token(self) -> bool:
        """JWT Refresh Token으로 Access Token 갱신"""
        try:
            from utils.session_manager import get_session_manager

            session_manager = get_session_manager()

            # 세션 상태 또는 쿠키에서 JWT Refresh Token 가져오기
            jwt_refresh_token = None
            if (
                hasattr(st.session_state, "jwt_refresh_token")
                and st.session_state.jwt_refresh_token
            ):
                jwt_refresh_token = st.session_state.jwt_refresh_token
            else:
                # 쿠키에서 가져오기
                try:
                    all_cookies = session_manager.cookie_manager.get_all()
                    jwt_refresh_token = all_cookies.get(
                        session_manager.jwt_refresh_cookie_key
                    )
                except Exception:
                    pass

            if not jwt_refresh_token:
                return False

            api_url = st.secrets.get("API_URL")
            if not api_url:
                return False

            url = f"{api_url.rstrip('/')}/auth/refresh"
            payload = {"refresh_token": jwt_refresh_token}

            response = httpx.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                new_access_token = data.get("access_token")
                expires_in = data.get("expires_in")

                # 세션 상태에 저장
                st.session_state.jwt_access_token = new_access_token
                if expires_in:
                    st.session_state.jwt_expires_at = datetime.now() + timedelta(
                        seconds=expires_in
                    )

                # 쿠키에도 저장 (7일 유효)
                try:
                    if "cookie_set_counter" not in st.session_state:
                        st.session_state.cookie_set_counter = 0
                    st.session_state.cookie_set_counter += 1
                    counter = st.session_state.cookie_set_counter

                    session_manager.cookie_manager.set(
                        session_manager.jwt_access_cookie_key,
                        new_access_token,
                        expires_at=datetime.now() + timedelta(days=7),
                        key=f"cookie_set_{session_manager.jwt_access_cookie_key}_{counter}",
                    )
                except Exception as cookie_error:
                    logger.warning(f"JWT Access Token 쿠키 저장 실패: {cookie_error}")

                return True
            else:
                logger.error(
                    f"JWT 토큰 갱신 실패: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"JWT 토큰 갱신 중 오류: {e}")
            return False

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Optional[dict[str, Any]]:
        """
        API 요청 실행 (재시도 로직 포함)

        Args:
            method: HTTP 메서드 (GET, POST, PATCH 등)
            endpoint: API 엔드포인트
            data: 요청 데이터 (POST, PATCH용)
            params: 쿼리 파라미터 (GET용)
            max_retries: 최대 재시도 횟수

        Returns:
            응답 데이터 또는 None (실패 시)
        """
        token = self._get_firebase_token()
        if not token:
            logger.error("Firebase token을 가져올 수 없습니다.")
            return None

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, headers=headers, params=params)
                    elif method.upper() == "POST":
                        response = await client.post(
                            url, headers=headers, json=data, params=params
                        )
                    elif method.upper() == "PATCH":
                        response = await client.patch(
                            url, headers=headers, json=data, params=params
                        )
                    else:
                        logger.error(f"지원하지 않는 HTTP 메서드: {method}")
                        return None

                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP 에러 (시도 {attempt + 1}/{max_retries}): {method} {url} - {e.response.status_code} - {e.response.text}"
                )
                if e.response.status_code == 409:  # Conflict (중복 사용자)
                    # 중복은 에러가 아니므로 응답 반환
                    return e.response.json()
                if attempt == max_retries - 1:
                    return None

            except httpx.TimeoutException:
                logger.error(f"타임아웃 (시도 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return None

            except Exception as e:
                logger.error(f"요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return None

        return None

    async def sync_user_from_firebase(
        self, firebase_uid: str, email: Optional[str], name: str
    ) -> bool:
        """
        Firebase 회원가입 직후 PostgreSQL에 사용자 생성

        Args:
            firebase_uid: Firebase UID
            email: 이메일
            name: 이름

        Returns:
            성공 여부
        """
        try:
            result = await self._make_request(
                "POST",
                "/users/sync-from-firebase",
                data={"firebase_uid": firebase_uid, "email": email, "name": name},
            )

            if result:
                logger.info(f"사용자 동기화 성공: {firebase_uid}")
                return True
            else:
                logger.error(f"사용자 동기화 실패: {firebase_uid}")
                return False

        except Exception as e:
            logger.error(f"사용자 동기화 중 예외 발생: {e}")
            return False

    async def get_restaurants(
        self,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        radius_km: Optional[float] = None,
        large_categories: Optional[list] = None,
        middle_categories: Optional[list] = None,
        sort_by: str = "popularity",
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> Optional[list]:
        """
        음식점 목록 조회 (필터링 및 정렬) [DEPRECATED]

        Args:
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            radius_km: 검색 반경 (km)
            large_categories: 대분류 카테고리 리스트
            middle_categories: 중분류 카테고리 리스트
            sort_by: 정렬 기준 (rating, distance, review_count 등)
            limit: 최대 결과 수
            offset: 페이지네이션 오프셋

        Returns:
            음식점 리스트 또는 None

        Note:
            이 메서드는 deprecated 되었습니다. get_filtered_restaurants와 sort_restaurants를 사용하세요.
        """
        try:
            # 쿼리 파라미터 구성
            params = {}
            if user_lat is not None:
                params["user_lat"] = user_lat
            if user_lon is not None:
                params["user_lon"] = user_lon
            if radius_km is not None:
                params["radius_km"] = radius_km
            if large_categories:
                # 여러 카테고리를 지원하도록 리스트 전체를 전달 (FastAPI가 자동 처리)
                params["diner_category_large"] = large_categories
            if middle_categories:
                # 여러 카테고리를 지원하도록 리스트 전체를 전달 (FastAPI가 자동 처리)
                params["diner_category_middle"] = middle_categories
            if sort_by:
                params["sort_by"] = sort_by
            if limit is not None:
                params["limit"] = limit
            if offset and offset > 0:
                params["offset"] = offset

            # GET 요청 (httpx가 쿼리 파라미터를 자동으로 URL 인코딩)
            # FastAPI는 trailing slash를 리다이렉트하므로 슬래시 추가
            result = await self._make_request("GET", "/kakao/diners/", params=params)
            return result if result else []

        except Exception as e:
            logger.error(f"음식점 조회 중 예외 발생: {e}")
            return None

    async def get_filtered_restaurants(
        self,
        user_lat: float,
        user_lon: float,
        radius_km: float,
        large_categories: Optional[list[str]] = None,
        middle_categories: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> tuple[list[str], list[int], dict[str, float]]:
        """
        음식점 필터링 (지역/카테고리)

        Args:
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            radius_km: 검색 반경 (km)
            large_categories: 대분류 카테고리 리스트
            middle_categories: 중분류 카테고리 리스트
            limit: 최대 결과 수

        Returns:
            (diner_ids 리스트, diner_idx 리스트, 거리 딕셔너리) 튜플
            거리 딕셔너리: {id: distance} 형식
            결과가 없을 경우: ([], [], {})
        """
        try:
            params = {
                "user_lat": user_lat,
                "user_lon": user_lon,
                "radius_km": radius_km,
            }

            # 카테고리 파라미터 추가 (여러 카테고리를 지원하도록 리스트 전체를 전달)
            if large_categories and len(large_categories) > 0:
                params["diner_category_large"] = large_categories

            if middle_categories and len(middle_categories) > 0:
                params["diner_category_middle"] = middle_categories

            if limit is not None:
                params["limit"] = limit

            result = await self._make_request(
                "GET", "/kakao/diners/filtered", params=params
            )

            if not result:
                return ([], [], {})

            # diner_ids 리스트와 거리 딕셔너리 추출
            diner_ids = [item["id"] for item in result]
            diner_idx = [item["diner_idx"] for item in result]
            distance_dict = {item["id"]: float(item["distance"]) for item in result}
            distance_dict_idx = {
                item["diner_idx"]: float(item["distance"]) for item in result
            }

            return diner_ids, diner_idx, distance_dict, distance_dict_idx

        except Exception as e:
            logger.error(f"음식점 필터링 중 예외 발생: {e}")
            return ([], [], {})

    async def sort_restaurants(
        self,
        diner_ids: list[str],
        sort_by: str = "popularity",
        user_id: Optional[str] = None,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        min_rating: Optional[float] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Optional[list]:
        """
        음식점 정렬/필터링

        Args:
            diner_ids: 정렬할 음식점 ID 리스트 (ULID)
            sort_by: 정렬 기준 (personalization, popularity, hidden_gem, rating, distance, review_count)
            user_id: 사용자 ID (개인화 정렬용)
            user_lat: 사용자 위도 (거리 정렬용)
            user_lon: 사용자 경도 (거리 정렬용)
            min_rating: 최소 평점
            limit: 최대 결과 수
            offset: 페이지네이션 오프셋

        Returns:
            정렬된 음식점 리스트 또는 None
        """
        try:
            data = {
                "diner_ids": diner_ids,
                "sort_by": sort_by,
            }

            if user_id:
                data["user_id"] = user_id
            if user_lat is not None:
                data["user_lat"] = user_lat
            if user_lon is not None:
                data["user_lon"] = user_lon
            if min_rating is not None:
                data["min_rating"] = min_rating
            if limit is not None:
                data["limit"] = limit
            if offset is not None:
                data["offset"] = offset

            result = await self._make_request("POST", "/kakao/diners/sorted", data=data)
            return result if result else []

        except Exception as e:
            logger.error(f"음식점 정렬 중 예외 발생: {e}")
            return None

    async def get_restaurant_by_idx(self, diner_idx: int) -> Optional[dict[str, Any]]:
        """
        특정 음식점 상세 조회

        Args:
            diner_idx: 음식점 인덱스

        Returns:
            음식점 정보 또는 None
        """
        try:
            result = await self._make_request("GET", f"/kakao/diners/{diner_idx}")
            return result

        except Exception as e:
            logger.error(f"음식점 상세 조회 중 예외 발생: {e}")
            return None

    async def search_restaurants(
        self,
        query: str,
        limit: int = 10,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        radius_km: Optional[float] = None,
    ) -> Optional[list]:
        """
        음식점 이름으로 검색

        Args:
            query: 검색어 (최소 2자)
            limit: 반환할 최대 결과 수
            user_lat: 사용자 위도 (거리 계산용)
            user_lon: 사용자 경도 (거리 계산용)
            radius_km: 검색 반경 (km)

        Returns:
            검색 결과 리스트 또는 None
        """
        try:
            params = {
                "query": query,
                "limit": limit,
            }

            if user_lat is not None:
                params["user_lat"] = user_lat
            if user_lon is not None:
                params["user_lon"] = user_lon
            if radius_km is not None:
                params["radius_km"] = radius_km

            result = await self._make_request(
                "GET", "/kakao/diners/search", params=params
            )
            return result if result else []

        except Exception as e:
            logger.error(f"음식점 검색 중 예외 발생: {e}")
            return None

    async def get_category_statistics(
        self, category_type: str, parent_category: Optional[str] = None
    ) -> Optional[list]:
        """
        카테고리별 음식점 수 통계 조회

        Args:
            category_type: "large" 또는 "middle"
            parent_category: 중분류 조회 시 대분류 카테고리명

        Returns:
            카테고리 통계 리스트 또는 None
        """
        try:
            params = {"category_type": category_type}
            if category_type == "large":
                endpoint = "/kakao/diners/categories"
            elif category_type == "middle":
                if not parent_category:
                    logger.error("중분류 조회 시 parent_category 필수")
                    return None
                endpoint = "/kakao/diners/categories"
                params["large_category"] = parent_category
            else:
                logger.error(f"잘못된 category_type: {category_type}")
                return None

            result = await self._make_request("GET", endpoint, params=params)
            return result if result else []

        except Exception as e:
            logger.error(f"카테고리 통계 조회 중 예외 발생: {e}")
            return None

    async def get_current_user_info(self) -> Optional[dict[str, Any]]:
        """
        현재 사용자 정보 조회 (has_completed_onboarding, is_personalization_enabled 포함)

        Returns:
            사용자 정보 딕셔너리 또는 None
        """
        try:
            result = await self._make_request("GET", "/users/me")

            if result:
                logger.info("사용자 정보 조회 성공")
                return result
            else:
                logger.error("사용자 정보 조회 실패")
                return None

        except Exception as e:
            logger.error(f"사용자 정보 조회 중 예외 발생: {e}")
            return None

    async def save_onboarding_data(
        self, profile_data: dict[str, Any], ratings_data: dict[str, int]
    ) -> bool:
        """
        온보딩 완료 시 프로필 데이터를 PostgreSQL에 저장

        Args:
            profile_data: 온보딩 프로필 데이터
            ratings_data: 음식점 평가 데이터

        Returns:
            성공 여부
        """
        try:
            # 데이터 변환 (What2Eat 형식 → yamyam-ops 형식)
            onboarding_data = {
                "location": profile_data.get("location"),
                "location_method": profile_data.get("location_method"),
                "user_lat": st.session_state.get("user_lat"),
                "user_lon": st.session_state.get("user_lon"),
                "birth_year": profile_data.get("birth_year"),
                "gender": profile_data.get("gender"),
                "dining_companions": profile_data.get("dining_companions"),
                "regular_budget": profile_data.get("regular_budget"),
                "special_budget": profile_data.get("special_budget"),
                "spice_level": profile_data.get("spice_level"),
                "allergies": profile_data.get("allergies"),
                "dislikes": profile_data.get("dislikes"),
                "food_preferences_large": profile_data.get("food_preferences_large"),
                "food_preferences_middle": profile_data.get("food_preferences_middle"),
                "restaurant_ratings": ratings_data,
            }

            result = await self._make_request(
                "PATCH", "/users/me/onboarding", data=onboarding_data
            )

            if result:
                logger.info("온보딩 데이터 저장 성공")
                return True
            else:
                logger.error("온보딩 데이터 저장 실패")
                return False

        except Exception as e:
            logger.error(f"온보딩 데이터 저장 중 예외 발생: {e}")
            return False


def get_yamyam_ops_client() -> Optional[YamYamOpsClient]:
    """yamyam-ops API 클라이언트 싱글톤 인스턴스 가져오기"""
    try:
        # secrets에서 API URL 가져오기
        api_url = st.secrets.get("API_URL")
        if not api_url:
            logger.warning("API_URL이 설정되지 않았습니다.")
            return None

        return YamYamOpsClient(api_url)

    except Exception as e:
        logger.error(f"yamyam-ops 클라이언트 초기화 실패: {e}")
        return None
