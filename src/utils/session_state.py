# src/utils/session_state.py

import streamlit as st

from config.constants import DEFAULT_ADDRESS_INFO_LIST


class SessionState:
    """세션 상태를 관리하는 클래스"""

    def __init__(self):
        # 사용자 기본 위치 정보 가져오기
        try:
            # 순환 import를 피하기 위해 함수 내부에서 import
            from utils.geolocation import get_user_default_location

            default_location = get_user_default_location()
        except ImportError:
            # import 실패 시 기본값 사용
            default_location = DEFAULT_ADDRESS_INFO_LIST

        self.states = {
            "generated": [],
            "past": [],
            "user_lat": default_location[2],
            "user_lon": default_location[1],
            "address": default_location[0],
            "result_queue": [],
            "previous_category_small": [],
            "consecutive_failures": 0,
            # 챗봇 관련 상태 추가
            "chat_step": "greeting",
            "avatar_style": None,
            "seed": None,
            "df_filtered": None,
            "radius_kilometers": None,
            "radius_distance": None,
            "search_option": None,
        }

    def initialize(self):
        """세션 상태 초기화"""
        for key, default_value in self.states.items():
            if key not in st.session_state:
                st.session_state[key] = default_value


def get_session_state():
    """세션 상태 인스턴스 반환"""
    return SessionState()
