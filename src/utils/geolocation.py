# src/utils/geolocation.py

import random
import string

import requests
import streamlit as st
from geopy.exc import GeocoderUnavailable
from geopy.geocoders import Nominatim

from config.constants import DEFAULT_ADDRESS_INFO_LIST, KAKAO_API_HEADERS, KAKAO_API_URL
from utils.activity_logger import get_activity_logger
from utils.auth import get_current_user
from utils.firebase_logger import get_firebase_logger


def get_user_default_location():
    """사용자의 기본 위치 정보를 가져오기 (Firestore -> 기본값 순)"""
    # 로그인된 사용자인 경우 Firestore에서 마지막 위치 조회
    user_info = get_current_user()
    if user_info:
        logger = get_firebase_logger()
        if logger.is_available():
            uid = user_info.get("localId")
            if uid:
                saved_location = logger.get_user_location(uid)
                if saved_location:
                    return [
                        saved_location["address"],
                        saved_location["lon"],
                        saved_location["lat"],
                    ]

    # 저장된 위치가 없거나 로그인하지 않은 경우 기본값 사용
    return DEFAULT_ADDRESS_INFO_LIST


def save_user_location(address: str, lat: float, lon: float):
    """사용자 위치를 Firestore에 저장"""
    user_info = get_current_user()
    if user_info:
        logger = get_firebase_logger()
        if logger.is_available():
            uid = user_info.get("localId")
            if uid:
                return logger.save_user_location(uid, address, lat, lon)
    return False


def generate_user_agent():
    random_string = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    user_agent = f"What2Eat_{random_string}"
    return user_agent


def geocode(longitude, latitude):
    user_agent = generate_user_agent()

    geolocator = Nominatim(user_agent=user_agent)
    # deplot_latitude, deplot_longitude = 37.5074423, 127.0567474
    try:
        location = geolocator.reverse((latitude, longitude))

    except GeocoderUnavailable:
        st.warning(
            "Geocoding 서비스가 현재 사용 불가능합니다.\n 키워드 검색으로 현위치를 찾아주세요."
        )
        default_location = get_user_default_location()
        return default_location[0]
    except Exception:
        st.error(
            "Geocoding 서비스가 현재 사용 불가능합니다.\n 키워드 검색으로 현위치를 찾아주세요."
        )
        default_location = get_user_default_location()
        return default_location[0]
    # print(location)
    address_components = location.raw["address"]

    # print(address_components.get('city'))

    if "city" in address_components:
        city_name = address_components.get("city")
    else:
        city_name = ""

    if "borough" in address_components:
        neighbourhood = address_components.get("borough")
    else:
        neighbourhood = ""

    if "suburb" in address_components:
        suburb = address_components.get("suburb")
    else:
        suburb = ""

    return f"{city_name} {neighbourhood} {suburb}에 있구나!"


def search_your_address():
    # session_state 초기화
    if "last_search" not in st.session_state:
        st.session_state.last_search = ""

    search_region_text = st.text_input("주소나 키워드로 입력해줘")
    search_clicked = st.button("검색")

    # 검색 버튼을 클릭했거나 새로운 검색어로 엔터를 눌렀을 때
    if search_clicked or (
        search_region_text and search_region_text != st.session_state.last_search
    ):
        st.session_state.last_search = search_region_text

        params = {"query": search_region_text, "size": 1}

        response = requests.get(KAKAO_API_URL, headers=KAKAO_API_HEADERS, params=params)

        if response.status_code == 200:
            response_json = response.json()
            response_doc_list = response_json["documents"]
            if response_doc_list:
                response_doc = response_doc_list[0]
                address_info_list = [
                    response_doc["address_name"],
                    (float(response_doc["x"]), float(response_doc["y"])),
                ]
                st.session_state.address = address_info_list[0]
                st.session_state.user_lat, st.session_state.user_lon = (
                    address_info_list[1][1],
                    address_info_list[1][0],
                )

                # Firestore에 위치 저장
                save_user_location(
                    st.session_state.address,
                    st.session_state.user_lat,
                    st.session_state.user_lon,
                )

                # session_state에 location_method 저장
                st.session_state.location_method = "search"

                # 활동 로그 기록
                try:
                    logger = get_activity_logger()
                    # 위치 검색 로그
                    logger.log_location_search(
                        query=search_region_text,
                        lat=st.session_state.user_lat,
                        lon=st.session_state.user_lon,
                        address=st.session_state.address,
                        method="search",
                        page="search_filter",
                    )
                    # 위치 설정 완료 로그
                    logger.log_location_set(
                        address=st.session_state.address,
                        lat=st.session_state.user_lat,
                        lon=st.session_state.user_lon,
                        method="search",
                        page="search_filter",
                    )
                except Exception:
                    # 로깅 실패해도 계속 진행
                    pass

                st.rerun()
            else:
                st.write("다른 검색어를 입력해봐... 먄")

        else:
            st.write("다른 검색어를 입력해봐... 먄")
