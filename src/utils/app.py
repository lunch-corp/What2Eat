# src/utils/app.py

import pandas as pd
import streamlit as st

from utils.map_renderer import MapRenderer
from utils.search_manager import SearchManager
from utils.session_state import get_session_state


@st.cache_data
def load_app_data():
    """앱 데이터 로딩 (API 기반으로 변경됨, 레거시 호환성 유지)"""
    # API 기반으로 변경되어 빈 DataFrame 반환
    # 실제 데이터는 각 페이지에서 API를 통해 가져옴
    return pd.DataFrame()


class What2EatApp:
    """What2Eat 앱의 메인 클래스 (API 기반)"""

    def __init__(self):
        self.session_state = get_session_state()
        self.session_state.initialize()
        self.map_renderer = MapRenderer()
        # 레거시 호환성을 위해 빈 DataFrame 유지
        self.df_diner = load_app_data()
        self.search_manager = SearchManager(self.df_diner)
