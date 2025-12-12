# src/utils/folium_map_utils.py
"""Folium 지도 시각화 유틸리티"""

import folium
import pandas as pd
from streamlit_folium import st_folium


class FoliumMapRenderer:
    """Folium 지도 렌더링 클래스"""

    def __init__(self):
        self.default_zoom = 14
        self.tile_style = "OpenStreetMap"

    def create_map(
        self, center_lat: float, center_lon: float, zoom_start: int = None
    ) -> folium.Map:
        """기본 지도 생성"""
        if zoom_start is None:
            zoom_start = self.default_zoom

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_start,
            tiles=self.tile_style,
        )

        return m

    def add_restaurant_markers(
        self, m: folium.Map, df_restaurants: pd.DataFrame
    ) -> folium.Map:
        """음식점 마커 추가"""
        for idx, row in df_restaurants.iterrows():
            # 등급에 따른 마커 색상
            grade = row.get("diner_grade", 1)
            if grade >= 3:
                color = "red"
                icon = "star"
            elif grade == 2:
                color = "orange"
                icon = "star"
            else:
                color = "lightred"
                icon = "cutlery"

            # 팝업 HTML 생성
            popup_html = f"""
            <div style="width: 250px; font-family: Arial;">
                <h4 style="margin-bottom: 10px;">{row["diner_name"]}</h4>
                <p style="margin: 5px 0;">
                    <strong>카테고리:</strong> {row.get("diner_category_middle", row.get("diner_category_large", "N/A"))}
                </p>
                <p style="margin: 5px 0;">
                    <strong>등급:</strong> {"⭐" * int(grade)}
                </p>
                <p style="margin: 5px 0;">
                    <strong>리뷰:</strong> {row.get("diner_review_cnt", 0)}개
                </p>
                <p style="margin: 10px 0;">
                    <a href="https://place.map.kakao.com/{row["diner_idx"]}" 
                       target="_blank" 
                       style="background-color: #FEE500; 
                              color: #000; 
                              padding: 8px 16px; 
                              text-decoration: none; 
                              border-radius: 4px;
                              display: inline-block;
                              font-weight: bold;">
                        카카오맵에서 보기
                    </a>
                </p>
            </div>
            """

            # 마커 추가
            folium.Marker(
                location=[row["diner_lat"], row["diner_lon"]],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row["diner_name"],
                icon=folium.Icon(color=color, icon=icon, prefix="fa"),
            ).add_to(m)

        return m

    def add_user_marker(
        self, m: folium.Map, user_lat: float, user_lon: float
    ) -> folium.Map:
        """사용자 위치 마커 추가"""
        folium.Marker(
            location=[user_lat, user_lon],
            popup="현재 위치",
            tooltip="현재 위치",
            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
        ).add_to(m)

        return m

    def render_map(
        self,
        df_restaurants: pd.DataFrame,
        user_lat: float,
        user_lon: float,
        show_user_location: bool = True,
        map_height: int = 600,
    ) -> dict:
        """지도 렌더링 및 상호작용 처리"""
        # 지도 중심점 계산
        if len(df_restaurants) > 0:
            center_lat = (df_restaurants["diner_lat"].mean() + user_lat) / 2
            center_lon = (df_restaurants["diner_lon"].mean() + user_lon) / 2
        else:
            center_lat = user_lat
            center_lon = user_lon

        # 지도 생성
        m = self.create_map(center_lat, center_lon)

        # 사용자 위치 마커 추가
        if show_user_location:
            m = self.add_user_marker(m, user_lat, user_lon)

        # 음식점 마커 추가
        if len(df_restaurants) > 0:
            m = self.add_restaurant_markers(m, df_restaurants)

        # 지도 렌더링 및 상호작용 데이터 반환
        map_data = st_folium(
            m,
            width=None,
            height=map_height,
            returned_objects=["last_clicked", "center", "zoom", "bounds"],
        )

        return map_data
