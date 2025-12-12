# utils/similar_restaurants.py

from typing import Any, Optional

import pandas as pd
import requests
import streamlit as st

from utils.data_processing import haversine


class SimilarRestaurantFetcher:
    """유사 식당 조회를 위한 공유 클래스"""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or st.secrets.get("API_URL", "")

    def get_similar_restaurants(
        self,
        diner_idx: int,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        use_item_cf: bool = True,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """
        유사 식당 조회

        Args:
            diner_idx: 기준 식당 ID
            user_lat: 사용자 위도
            user_lon: 사용자 경도
            use_item_cf: True면 API(item-cf) 사용, False면 카테고리 기반
            limit: 반환할 최대 개수

        Returns:
            유사 식당 정보 리스트
        """
        if use_item_cf:
            return self._get_from_api(diner_idx, user_lat, user_lon, limit)
        else:
            return self._get_by_category(diner_idx, user_lat, user_lon, limit)

    def _get_from_api(
        self,
        diner_idx: int,
        user_lat: Optional[float],
        user_lon: Optional[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        """API로 유사 식당 가져오기"""
        if not self.api_url:
            return []

        try:
            # Redis에서 유사 식당 ID 리스트 가져오기
            key = f"diner:{diner_idx}:similar_diner_ids"
            response = requests.post(
                self.api_url + "/redis/read", json={"keys": [key]}, timeout=3
            )
            if response.status_code != 200:
                return []

            similar_ids = response.json().get("data", {}).get(key, [])
            if not similar_ids or not isinstance(similar_ids, list):
                return []
            # 각 ID에 대해 상세 정보 가져오기
            restaurants = []
            for kakao_place_id in similar_ids[:limit]:
                restaurant_info = self._fetch_restaurant_from_api(
                    kakao_place_id, user_lat, user_lon
                )
                if restaurant_info:
                    restaurants.append(restaurant_info)
            return restaurants

        except Exception as e:
            print(f"API 조회 실패: {e}")
            return []

    def _fetch_restaurant_from_api(
        self,
        kakao_place_id: str,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
    ) -> Optional[dict[str, Any]]:
        """API로부터 개별 식당 정보 가져오기"""
        try:
            url = f"{self.api_url}/kakao/diners/{kakao_place_id}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                api_data = response.json()
                return self._convert_api_response_to_dict(api_data, user_lat, user_lon)

            return None

        except Exception as e:
            print(f"식당 정보 API 호출 실패 (ID: {kakao_place_id}): {e}")
            return None

    def _convert_api_response_to_dict(
        self,
        api_data: dict[str, Any],
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
    ) -> dict[str, Any]:
        """API 응답을 표준 식당 정보 딕셔너리로 변환"""
        # 메뉴 파싱
        menu_names = api_data.get("diner_menu_name", "")
        specialties = (
            [m.strip() for m in menu_names.split(",")][:2] if menu_names else []
        )
        # 평점
        rating = float(api_data.get("diner_review_avg", 0) or 0)
        # 리뷰 수
        try:
            review_count = int(api_data.get("diner_review_cnt") or 0)
        except (ValueError, TypeError):
            review_count = 0
        # 거리 계산
        distance = 0.0
        if user_lat and user_lon:
            diner_lat = api_data.get("diner_lat")
            diner_lon = api_data.get("diner_lon")
            if diner_lat and diner_lon:
                try:
                    distance = round(
                        haversine(user_lat, user_lon, diner_lat, diner_lon), 1
                    )
                except Exception:
                    distance = 0.0
        return {
            "id": str(api_data.get("diner_idx", "")),
            "name": api_data.get("diner_name", ""),
            "category": api_data.get("diner_category_large", "카테고리 정보 없음"),
            "rating": rating,
            "specialties": specialties,
            "distance": distance,
            "review_count": review_count,
        }

    def _get_by_category(
        self,
        diner_idx: int,
        user_lat: Optional[float],
        user_lon: Optional[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        """같은 카테고리 기반으로 유사 식당 찾기"""
        if user_lat is None or user_lon is None:
            return []

        try:
            from utils.data_processing import get_filtered_data

            # 기준 식당 정보 찾기
            selected = self.df_diner[
                self.df_diner["diner_idx"].astype(str) == str(diner_idx)
            ]
            if selected.empty:
                return []

            category = selected.iloc[0]["diner_category_large"]

            # 10km 반경 내 같은 카테고리 식당 필터링
            df_filtered = get_filtered_data(
                self.df_diner, user_lat, user_lon, max_radius=10
            )
            df_filtered = df_filtered[df_filtered["diner_category_large"] == category]
            df_filtered = df_filtered[
                df_filtered["diner_idx"].astype(str) != str(diner_idx)
            ]
            df_filtered = df_filtered[df_filtered["diner_grade"].notna()]
            df_filtered = df_filtered[df_filtered["diner_grade"] >= 1]
            df_sorted = df_filtered.sort_values(by="diner_grade", ascending=False)

            return [
                self._convert_row_to_dict(row)
                for _, row in df_sorted.head(limit).iterrows()
            ]

        except Exception as e:
            print(f"카테고리 기반 조회 실패: {e}")
            return []

    def _convert_row_to_dict(self, row: pd.Series) -> dict[str, Any]:
        """DataFrame row를 딕셔너리로 변환"""
        return {
            "id": str(row.get("diner_idx", "")),
            "name": row.get("diner_name", ""),
            "category": row.get("diner_category_large", ""),
            "rating": float(row.get("diner_grade", 0))
            if pd.notna(row.get("diner_grade"))
            else 0.0,
            "specialties": row.get("diner_menu_name", [])[:2]
            if isinstance(row.get("diner_menu_name"), list)
            else [],
            "distance": round(float(row.get("distance", 0)), 1)
            if pd.notna(row.get("distance"))
            else 0.0,
            "review_count": int(row.get("diner_review_cnt", 0))
            if pd.notna(row.get("diner_review_cnt"))
            else 0,
        }


SimilarRestaurantFetcher()
