# src/utils/dialogs.py

import pandas as pd
import pydeck as pdk
import streamlit as st
from streamlit_geolocation import streamlit_geolocation

from utils.activity_logger import get_activity_logger
from utils.geolocation import (
    geocode,
    get_user_default_location,
    save_user_location,
    search_your_address,
)


@st.dialog("음식점 위치")
def show_restaurant_map(restaurant):
    """음식점 상세정보와 위치를 보여주는 다이얼로그"""
    # 음식점 상세 정보 표시
    num_address = restaurant.get("diner_num_address", None)
    road_address = restaurant.get("diner_road_address", None)

    st.subheader(f"🏪 {restaurant['diner_name']}")
    if num_address:
        st.write(f"📍 {num_address}")
    if road_address:
        st.write(f"📍 {road_address}")

    if restaurant["diner_menu_name"]:
        st.write(f"🍴 메뉴: {'/'.join(restaurant['diner_menu_name'][:5])}")
    if restaurant["diner_tag"]:
        st.write(f"🏷️ 태그: {'/'.join(restaurant['diner_tag'][:5])}")

    st.write("---")

    # 현재 위치 확인
    if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
        location = streamlit_geolocation()
        if location["latitude"] is not None and location["longitude"] is not None:
            st.session_state.user_lat = location["latitude"]
            st.session_state.user_lon = location["longitude"]
        else:
            # 사용자 기본 위치 사용
            default_location = get_user_default_location()
            st.session_state.user_lat = default_location[2]
            st.session_state.user_lon = default_location[1]

    # 현재 위치와 음식점 위치를 포함하는 데이터 생성
    map_data = pd.DataFrame(
        {
            "lat": [st.session_state.user_lat, restaurant["diner_lat"]],
            "lon": [st.session_state.user_lon, restaurant["diner_lon"]],
            "name": ["현재 위치", restaurant["diner_name"]],
            "color": [[0, 0, 255], [255, 0, 0]],  # 파란색(현재위치), 빨간색(음식점)
        }
    )

    # 지도 설정
    view_state = pdk.ViewState(
        latitude=(st.session_state.user_lat + restaurant["diner_lat"]) / 2,
        longitude=(st.session_state.user_lon + restaurant["diner_lon"]) / 2,
        zoom=11,
        pitch=50,
    )

    # 레이어 설정
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_data,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=50,
        pickable=True,
        radiusScale=2,
    )

    # 지도 렌더링
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "{name}"},
        map_style="mapbox://styles/mapbox/light-v10",
    )

    st.pydeck_chart(deck, use_container_width=True)
    if st.button("닫기"):
        st.session_state.show_map = False
        st.session_state.selected_restaurant = None
        st.rerun()


@st.dialog("위치 변경")
def change_location():
    """위치 변경을 위한 다이얼로그"""
    option = st.radio(
        "위치를 선택하세요",
        ("키워드로 검색으로 찾기(강남역 or 강남대로 328)", "주변에서 찾기"),
    )
    if option == "주변에서 찾기":
        with st.spinner("📍 현재 위치를 찾는 중입니다..."):
            location = streamlit_geolocation()
            if location["latitude"] is not None or location["longitude"] is not None:
                st.session_state.user_lat, st.session_state.user_lon = (
                    location["latitude"],
                    location["longitude"],
                )
                st.session_state.address = geocode(
                    st.session_state.user_lon, st.session_state.user_lat
                )

                # Firestore에 위치 저장
                save_user_location(
                    st.session_state.address,
                    st.session_state.user_lat,
                    st.session_state.user_lon,
                )

                # session_state에 location_method 저장
                st.session_state.location_method = "geolocation"

                # 활동 로그 기록
                try:
                    logger = get_activity_logger()
                    logger.log_location_set(
                        address=st.session_state.address,
                        lat=st.session_state.user_lat,
                        lon=st.session_state.user_lon,
                        method="geolocation",
                        page="search_filter",
                    )
                except Exception:
                    # 로깅 실패해도 계속 진행
                    pass

                st.success("✅ 위치를 찾았습니다!")
                st.rerun()
    elif option == "키워드로 검색으로 찾기(강남역 or 강남대로 328)":
        search_your_address()

    return (
        st.session_state.user_lat,
        st.session_state.user_lon,
        st.session_state.address,
    )
