# utils/category_manager.py

from typing import Any, Dict, List

import pandas as pd
import pandas as pd


class CategoryManager:
    """음식점 카테고리 관리 클래스"""

    def __init__(self, app=None):
        self.app = app
        self._category_data = None

    def load_category_data(self) -> pd.DataFrame:
        """카테고리 데이터 로드"""
        if self._category_data is None:
            try:
                # category_table.csv 파일 로드
                self._category_data = pd.read_csv("data/seoul_data/category_table.csv")
            except FileNotFoundError:
                # 파일이 없는 경우 빈 DataFrame 반환
                self._category_data = pd.DataFrame()
        return self._category_data

    def get_large_categories(self) -> List[Dict[str, Any]]:
        """
        diner_category_large 목록을 diner_count 높은 순으로 반환
        null값 제외, 중복 제거
        """
        df = self.load_category_data()

        if df.empty:
            # 기본 카테고리 반환 (fallback)
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

        # depth가 2이고 industry_category가 '음식점'인 데이터만 필터링
        filtered_df = df[
            (df["depth"] == 2)
            & (df["industry_category"] == "음식점")
            & (df["diner_category_large"].notna())
        ]

        # diner_category_large별로 그룹화하고 diner_count 합계 계산
        grouped = (
            filtered_df.groupby("diner_category_large")["diner_count"]
            .sum()
            .reset_index()
        )

        # diner_count 내림차순으로 정렬
        sorted_categories = grouped.sort_values("diner_count", ascending=False)

        # 리스트 형태로 변환
        categories = []
        for _, row in sorted_categories.iterrows():
            categories.append(
                {"name": row["diner_category_large"], "count": int(row["diner_count"])}
            )

        return categories

    def get_middle_categories(self, large_category: str) -> List[Dict[str, Any]]:
        """
        특정 diner_category_large의 diner_category_middle 목록을
        diner_count 높은 순으로 반환
        """
        df = self.load_category_data()

        if df.empty:
            return []

        # depth가 3이고, 지정된 large_category에 해당하는 데이터만 필터링
        filtered_df = df[
            (df["depth"] == 3)
            & (df["industry_category"] == "음식점")
            & (df["diner_category_large"] == large_category)
            & (df["diner_category_middle"].notna())
        ]

        if filtered_df.empty:
            return []

        # diner_category_middle별로 그룹화하고 diner_count 합계 계산
        grouped = (
            filtered_df.groupby("diner_category_middle")["diner_count"]
            .sum()
            .reset_index()
        )

        # diner_count 내림차순으로 정렬
        sorted_categories = grouped.sort_values("diner_count", ascending=False)

        # 리스트 형태로 변환
        categories = []
        for _, row in sorted_categories.iterrows():
            categories.append(
                {"name": row["diner_category_middle"], "count": int(row["diner_count"])}
            )

        return categories

    def get_category_display_name(self, category_name: str, count: int) -> str:
        """카테고리 표시용 이름 생성"""
        return f"{category_name} ({count:,}개)"


def get_category_manager(app=None) -> CategoryManager:
    """카테고리 매니저 인스턴스 반환"""
    return CategoryManager(app)
