"""
사용자 활동 로깅 유틸리티
ML 추천 모델 학습을 위한 사용자 행동 데이터 수집
"""

import logging
import uuid
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)


class ActivityLogger:
    """사용자 활동 로깅 클래스"""

    def __init__(self):
        """ActivityLogger 초기화"""
        # 세션 ID 생성 (세션당 한 번만)
        if "activity_session_id" not in st.session_state:
            st.session_state.activity_session_id = str(uuid.uuid4())

        self.session_id = st.session_state.activity_session_id

    def _get_api_client(self):
        """API 클라이언트 가져오기"""
        try:
            from utils.api_client import get_yamyam_ops_client

            return get_yamyam_ops_client()
        except Exception as e:
            logger.error(f"API 클라이언트 초기화 실패: {e}")
            return None

    def _get_firebase_uid(self) -> Optional[str]:
        """현재 사용자의 Firebase UID 가져오기"""
        try:
            from utils.auth import get_current_user

            user_info = get_current_user()
            if user_info:
                return user_info.get("localId")
        except Exception as e:
            logger.error(f"Firebase UID 가져오기 실패: {e}")
        return None

    async def _log_event(
        self,
        event_type: str,
        page: str,
        **kwargs,
    ) -> bool:
        """
        이벤트 로그 전송

        Args:
            event_type: 이벤트 유형
            page: 발생 페이지
            **kwargs: 추가 데이터

        Returns:
            성공 여부
        """
        try:
            firebase_uid = self._get_firebase_uid()
            if not firebase_uid:
                logger.warning(
                    "Firebase UID를 찾을 수 없습니다. 로그를 전송하지 않습니다."
                )
                return False

            client = self._get_api_client()
            if not client:
                logger.warning("API 클라이언트를 초기화할 수 없습니다.")
                return False

            log_data = {
                "firebase_uid": firebase_uid,
                "session_id": self.session_id,
                "event_type": event_type,
                "page": page,
                **kwargs,
            }

            # API 호출
            result = await client._make_request(
                "POST", "/activity-logs/", data=log_data
            )

            if result:
                logger.info(f"로그 전송 성공: {event_type} on {page}")
                return True
            else:
                logger.warning(f"로그 전송 실패: {event_type} on {page}")
                return False

        except Exception as e:
            logger.error(f"로그 전송 중 오류: {e}")
            return False

    def log_location_search(
        self,
        query: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        address: Optional[str] = None,
        method: str = "search",
        page: str = "onboarding",
    ):
        """위치 검색 로그"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._log_event(
                    event_type="location_search",
                    page=page,
                    location_query=query,
                    location_address=address,
                    location_lat=lat,
                    location_lon=lon,
                    location_method=method,
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"위치 검색 로그 실패: {e}")

    def log_location_set(
        self,
        address: str,
        lat: float,
        lon: float,
        method: str = "search",
        page: str = "onboarding",
    ):
        """위치 설정 완료 로그"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._log_event(
                    event_type="location_set",
                    page=page,
                    location_address=address,
                    location_lat=lat,
                    location_lon=lon,
                    location_method=method,
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"위치 설정 로그 실패: {e}")

    def log_filter_change(
        self,
        address: str,
        lat: float,
        lon: float,
        radius: Optional[float] = None,
        large_categories: Optional[list[str]] = None,
        middle_categories: Optional[list[str]] = None,
        sort_by: Optional[str] = None,
        period: Optional[str] = None,
        location_method: Optional[str] = None,
        page: str = "search_filter",
    ):
        """검색 필터 변경 로그"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._log_event(
                    event_type="filter_change",
                    page=page,
                    location_address=address,
                    location_lat=lat,
                    location_lon=lon,
                    location_method=location_method,
                    search_radius_km=radius,
                    selected_large_categories=large_categories,
                    selected_middle_categories=middle_categories,
                    sort_by=sort_by,
                    period=period,
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"필터 변경 로그 실패: {e}")

    def log_sort_change(self, sort_by: str, page: str = "search_filter"):
        """정렬 방식 변경 로그"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._log_event(
                    event_type="sort_change",
                    page=page,
                    sort_by=sort_by,
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"정렬 변경 로그 실패: {e}")

    def log_category_select(
        self,
        large_categories: Optional[list[str]] = None,
        middle_categories: Optional[list[str]] = None,
        page: str = "search_filter",
    ):
        """카테고리 선택 로그"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._log_event(
                    event_type="category_select",
                    page=page,
                    selected_large_categories=large_categories,
                    selected_middle_categories=middle_categories,
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"카테고리 선택 로그 실패: {e}")

    def log_diner_click(
        self,
        diner_idx: str,
        diner_name: str,
        position: Optional[int] = None,
        page: str = "search_filter",
    ):
        """음식점 클릭 로그"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._log_event(
                    event_type="diner_click",
                    page=page,
                    clicked_diner_idx=diner_idx,
                    clicked_diner_name=diner_name,
                    display_position=position,
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"음식점 클릭 로그 실패: {e}")

    def log_ranking_view(
        self,
        city: Optional[str] = None,
        region: Optional[str] = None,
        grades: Optional[list[str]] = None,
        large_category: Optional[str] = None,
        middle_category: Optional[str] = None,
    ):
        """랭킹 페이지 조회 로그"""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._log_event(
                    event_type="ranking_view",
                    page="ranking",
                    selected_city=city,
                    selected_region=region,
                    selected_grades=grades,
                    selected_large_categories=[large_category]
                    if large_category
                    else None,
                    selected_middle_categories=[middle_category]
                    if middle_category
                    else None,
                )
            )
            loop.close()
        except Exception as e:
            logger.error(f"랭킹 조회 로그 실패: {e}")


def get_activity_logger() -> ActivityLogger:
    """ActivityLogger 싱글톤 인스턴스 가져오기"""
    if "activity_logger" not in st.session_state:
        st.session_state.activity_logger = ActivityLogger()
    return st.session_state.activity_logger
