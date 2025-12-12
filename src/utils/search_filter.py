# src/utils/search_filter.py
"""검색 필터링 로직 (API 기반)"""

import asyncio
from typing import Optional

import pandas as pd
import streamlit as st

from utils.api_client import get_yamyam_ops_client


class SearchFilter:
    """검색 필터링을 담당하는 클래스 (API 기반)"""

    def __init__(self, df_diner: pd.DataFrame = None):
        """
        Args:
            df_diner: 레거시 호환성을 위한 파라미터 (사용하지 않음)
        """
        self.df_diner = df_diner  # 레거시 호환성

    def _map_sort_by(self, sort_by: str) -> str:
        """What2Eat 정렬 기준을 yamyam-ops API 형식으로 변환"""
        sort_mapping = {
            "개인화": "personalization",
            "숨찐맛": "hidden_gem",
            "인기도": "popularity",
            "거리순": "distance",
        }
        return sort_mapping.get(sort_by, "popularity")

    def _generate_filter_cache_key(
        self,
        user_lat: float,
        user_lon: float,
        radius_km: float,
        large_categories: Optional[list[str]],
        middle_categories: Optional[list[str]],
    ) -> int:
        """필터 조건의 해시값 생성"""
        key_parts = [
            f"lat:{user_lat:.6f}",
            f"lon:{user_lon:.6f}",
            f"radius:{radius_km:.1f}",
            f"large:{sorted(large_categories) if large_categories else []}",
            f"middle:{sorted(middle_categories) if middle_categories else []}",
        ]
        return hash(tuple(key_parts))

    def get_filtered_restaurants(
        self,
        user_lat: float,
        user_lon: float,
        radius_km: float,
        large_categories: Optional[list[str]] = None,
        middle_categories: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> tuple[Optional[list[str]], Optional[list[int]], Optional[dict[str, float]]]:
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
            (음식점 ID 리스트, diner_idx 리스트, 거리 딕셔너리) 또는 (None, None, None)
            거리 딕셔너리: {id: distance} 형식
        """
        try:
            # API 클라이언트 가져오기
            client = get_yamyam_ops_client()
            if not client:
                st.error("❌ API 클라이언트를 초기화할 수 없습니다.")
                return None, None, None

            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            diner_ids, diner_idx, distance_dict, distance_dict_idx = (
                loop.run_until_complete(
                    client.get_filtered_restaurants(
                        user_lat=user_lat,
                        user_lon=user_lon,
                        radius_km=radius_km,
                        large_categories=large_categories,
                        middle_categories=middle_categories,
                        limit=limit,
                    )
                )
            )
            loop.close()

            return diner_ids, diner_idx, distance_dict, distance_dict_idx

        except Exception as e:
            st.error(f"❌ 음식점 필터링 중 오류가 발생했습니다: {str(e)}")
            return None, None, None

    def sort_restaurants(
        self,
        diner_ids: list[str],
        sort_by: str,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Optional[pd.DataFrame]:
        """
        음식점 정렬

        Args:
            diner_ids: 정렬할 음식점 ID 리스트 (ULID)
            sort_by: 정렬 기준 (What2Eat 형식: "개인화", "숨찐맛", "인기도", "거리순")
            user_lat: 사용자 위도 (거리 정렬용)
            user_lon: 사용자 경도 (거리 정렬용)
            user_id: 사용자 ID (개인화 정렬용)
            limit: 최대 결과 수
            offset: 페이지네이션 오프셋

        Returns:
            정렬된 음식점 DataFrame 또는 None
        """
        try:
            # API 클라이언트 가져오기
            client = get_yamyam_ops_client()
            if not client:
                st.error("❌ API 클라이언트를 초기화할 수 없습니다.")
                return None

            # 정렬 기준 변환
            api_sort_by = self._map_sort_by(sort_by)

            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            restaurants = loop.run_until_complete(
                client.sort_restaurants(
                    diner_ids=diner_ids,
                    sort_by=api_sort_by,
                    user_id=user_id,
                    limit=limit,
                    offset=offset,
                )
            )
            loop.close()

            if not restaurants:
                return pd.DataFrame()

            # DataFrame으로 변환
            df_results = pd.DataFrame(restaurants)

            # 카카오맵 URL 추가 (없는 경우)
            if (
                "diner_url" not in df_results.columns
                and "diner_idx" in df_results.columns
            ):
                df_results["diner_url"] = df_results["diner_idx"].apply(
                    lambda idx: f"https://place.map.kakao.com/{idx}"
                )

            return df_results

        except Exception as e:
            st.error(f"❌ 음식점 정렬 중 오류가 발생했습니다: {str(e)}")
            return None

    def apply_filters(
        self,
        user_lat: float,
        user_lon: float,
        radius_km: float = 5.0,
        large_categories: Optional[list[str]] = None,
        middle_categories: Optional[list[str]] = None,
        sort_by: str = "인기도",
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        모든 필터 적용 (API 호출) [DEPRECATED]

        Args:
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            radius_km: 검색 반경 (km)
            large_categories: 대분류 카테고리 리스트
            middle_categories: 중분류 카테고리 리스트
            sort_by: 정렬 기준
            limit: 최대 결과 수

        Returns:
            필터링된 음식점 DataFrame

        Note:
            이 메서드는 deprecated 되었습니다. get_filtered_restaurants와 sort_restaurants를 사용하세요.
        """
        try:
            # API 클라이언트 가져오기
            client = get_yamyam_ops_client()
            if not client:
                st.error("❌ API 클라이언트를 초기화할 수 없습니다.")
                return pd.DataFrame()

            # 정렬 기준 변환
            api_sort_by = self._map_sort_by(sort_by)

            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            restaurants = loop.run_until_complete(
                client.get_restaurants(
                    user_lat=user_lat,
                    user_lon=user_lon,
                    radius_km=radius_km,
                    large_categories=large_categories,
                    middle_categories=middle_categories,
                    sort_by=api_sort_by,
                    limit=limit,
                )
            )
            loop.close()

            if not restaurants:
                return pd.DataFrame()

            # DataFrame으로 변환
            df_results = pd.DataFrame(restaurants)

            # 카카오맵 URL 추가 (없는 경우)
            if (
                "diner_url" not in df_results.columns
                and "diner_idx" in df_results.columns
            ):
                df_results["diner_url"] = df_results["diner_idx"].apply(
                    lambda idx: f"https://place.map.kakao.com/{idx}"
                )

            return df_results

        except Exception as e:
            st.error(f"❌ 음식점 조회 중 오류가 발생했습니다: {str(e)}")
            return pd.DataFrame()
