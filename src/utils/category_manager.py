# utils/category_manager.py

import asyncio
from typing import Any

from utils.api_client import get_yamyam_ops_client


class CategoryManager:
    """음식점 카테고리 관리 클래스 (API 기반)"""

    def __init__(self, app=None):
        self.app = app
        self._large_categories_cache = None
        self._middle_categories_cache = {}

    def get_large_categories(self) -> list[dict[str, Any]]:
        """
        대분류 카테고리 목록을 diner_count 높은 순으로 반환 (API 호출)
        """
        # 캐시가 있으면 반환
        if self._large_categories_cache is not None:
            return self._large_categories_cache

        try:
            # API 클라이언트 가져오기
            client = get_yamyam_ops_client()
            if not client:
                return self._get_fallback_large_categories()

            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            categories = loop.run_until_complete(
                client.get_category_statistics("large")
            )
            loop.close()

            if categories:
                self._large_categories_cache = categories
                return categories
            else:
                return self._get_fallback_large_categories()

        except Exception as e:
            print(f"대분류 카테고리 조회 실패: {e}")
            return self._get_fallback_large_categories()

    def get_middle_categories(self, large_category: str) -> list[dict[str, Any]]:
        """
        특정 대분류의 중분류 카테고리 목록을 diner_count 높은 순으로 반환 (API 호출)
        """
        # 캐시가 있으면 반환
        if large_category in self._middle_categories_cache:
            return self._middle_categories_cache[large_category]

        try:
            # API 클라이언트 가져오기
            client = get_yamyam_ops_client()
            if not client:
                return []

            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            categories = loop.run_until_complete(
                client.get_category_statistics("middle", large_category)
            )
            loop.close()

            if categories:
                self._middle_categories_cache[large_category] = categories
                return categories
            else:
                return []

        except Exception as e:
            print(f"중분류 카테고리 조회 실패: {e}")
            return []

    def _get_fallback_large_categories(self) -> list[dict[str, Any]]:
        """API 호출 실패 시 기본 카테고리 반환"""
        return [
            {"name": "한식", "count": 107138},
            {"name": "양식", "count": 30445},
            {"name": "카페", "count": 16327},
            {"name": "간식", "count": 19746},
            {"name": "일식", "count": 12034},
            {"name": "중식", "count": 10861},
            {"name": "술집", "count": 28703},
            {"name": "아시아음식", "count": 2764},
            {"name": "기타", "count": 3932},
        ]

    def get_category_display_name(self, category_name: str, count: int) -> str:
        """카테고리 표시용 이름 생성"""
        return f"{category_name} ({count:,}개)"


def get_category_manager(app=None) -> CategoryManager:
    """카테고리 매니저 인스턴스 반환"""
    return CategoryManager(app)
