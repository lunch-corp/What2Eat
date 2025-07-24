# src/main.py

import streamlit as st

from config.constants import LOGO_SMALL_IMG_PATH, LOGO_TITLE_IMG_PATH
from pages.onboarding import OnboardingPage
from utils.analytics import load_analytics
from utils.app import What2EatApp
from utils.auth import (
    auth_form,
    check_authentication,
    get_current_user,
    has_completed_onboarding,
    is_first_login,
    logout,
)
from utils.firebase_logger import get_firebase_logger
from utils.pages import PageManager
from utils.session_manager import get_session_manager


def initialize_session_state():
    """Fragment 재실행 여부를 확인하기 위한 session_state 설정"""
    if "app_runs" not in st.session_state:
        st.session_state.app_runs = 0
    if "fragment_runs" not in st.session_state:
        st.session_state.fragment_runs = 0


@st.fragment
def login_page_fragment():
    """로그인 페이지 전용 fragment"""
    st.session_state.fragment_runs += 1

    # 로고와 앱 소개
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(LOGO_TITLE_IMG_PATH, width=300)

    st.markdown("---")

    # 앱 소개
    st.markdown("""
    ## 🍽️ What2Eat에 오신 것을 환영합니다!

    **What2Eat**은 당신의 맛집 탐험을 도와주는 똑똑한 음식점 추천 서비스입니다.

    ### ✨ 주요 기능
    - 🎯 **개인 맞춤 추천**: 위치와 취향을 고려한 맞춤형 음식점 추천
    - 🗺️ **지도 기반 검색**: 원하는 반경 내에서 맛집 찾기
    - 🏆 **쩝슐랭 랭킹**: 검증된 맛집들의 등급별 랭킹
    
    🚀
    """)

    st.markdown("---")

    # 로그인 폼
    auth_form()


@st.fragment
def chat_page_fragment(page_manager: PageManager):
    """chat_page 부분만 부분 재실행"""
    st.session_state.fragment_runs += 1
    page_manager.chat_page()


@st.fragment
def ranking_page_fragment(page_manager: PageManager):
    """ranking_page 부분만 부분 재실행"""
    st.session_state.fragment_runs += 1
    page_manager.ranking_page()


@st.fragment
def user_activity_logs_fragment():
    """사용자 활동 로그 페이지 부분만 부분 재실행"""
    st.session_state.fragment_runs += 1

    st.title("📊 내 활동 로그")

    logger = get_firebase_logger()
    user_info = get_current_user()

    if user_info and logger.is_available():
        uid = user_info.get("localId")

        # 탭으로 구분
        log_tab, stats_tab, collection_tab = st.tabs(
            ["📝 최근 활동", "📈 통계", "📂 컬렉션별 로그"]
        )

        with log_tab:
            st.subheader("최근 활동 로그")

            # 로그 개수 선택
            log_limit = st.selectbox("표시할 로그 개수", [10, 20, 50, 100], index=0)

            logs = logger.get_user_logs(uid, limit=log_limit)

            if logs:
                for i, log in enumerate(logs):
                    collection_name = log.get("collection", "unknown")
                    activity_type = log.get("type", "Unknown")
                    timestamp = log.get("timestamp", "No timestamp")

                    # 컬렉션별 이모지 추가
                    collection_emoji = {
                        "auth_logs": "🔐",
                        "navigation_logs": "🧭",
                        "search_logs": "🔍",
                        "interaction_logs": "⚡",
                        "restaurant_logs": "🍽️",
                        "activity_logs": "📋",
                    }.get(collection_name, "📝")

                    with st.expander(
                        f"{collection_emoji} {i + 1}. [{collection_name}] {activity_type} - {timestamp}"
                    ):
                        st.json(log.get("detail", {}))
            else:
                st.info("아직 활동 로그가 없습니다.")
                st.info("메인 페이지에서 활동을 해보세요!")

        with collection_tab:
            st.subheader("컬렉션별 로그 조회")

            # 컬렉션 선택
            collection_options = {
                "전체": None,
                "🔐 인증 로그": "auth_logs",
                "🧭 네비게이션 로그": "navigation_logs",
                "🔍 검색 로그": "search_logs",
                "⚡ 상호작용 로그": "interaction_logs",
                "🍽️ 음식점 로그": "restaurant_logs",
                "📋 기타 활동 로그": "activity_logs",
            }

            selected_collection_display = st.selectbox(
                "조회할 컬렉션 선택", list(collection_options.keys())
            )
            selected_collection = collection_options[selected_collection_display]

            # 로그 개수 선택
            collection_log_limit = st.selectbox(
                "표시할 로그 개수",
                [10, 20, 50, 100],
                index=0,
                key="collection_log_limit",
            )

            collection_logs = logger.get_user_logs(
                uid, limit=collection_log_limit, collection_name=selected_collection
            )

            if collection_logs:
                st.info(f"총 {len(collection_logs)}개의 로그를 찾았습니다.")

                for i, log in enumerate(collection_logs):
                    activity_type = log.get("type", "Unknown")
                    timestamp = log.get("timestamp", "No timestamp")
                    collection_name = log.get(
                        "collection", selected_collection or "unknown"
                    )

                    with st.expander(f"{i + 1}. {activity_type} - {timestamp}"):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.write(f"**컬렉션:** {collection_name}")
                            st.write(f"**타입:** {activity_type}")
                        with col2:
                            st.json(log.get("detail", {}))
            else:
                st.info(f"{selected_collection_display}에 해당하는 로그가 없습니다.")

        with stats_tab:
            st.subheader("활동 통계")

            stats = logger.get_user_statistics(uid)

            if stats:
                # 전체 통계
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("총 활동 수", stats.get("total_activities", 0))

                with col2:
                    most_active = stats.get("most_active_type", "없음")
                    st.metric("가장 많은 활동", most_active)

                with col3:
                    most_active_collection = stats.get("most_active_collection", "없음")
                    st.metric("가장 활발한 영역", most_active_collection)

                # 컬렉션별 통계
                st.subheader("📂 영역별 활동 분포")
                collection_stats = stats.get("collection_stats", {})

                if collection_stats:
                    import pandas as pd

                    # 컬렉션 이름을 한글로 변환
                    collection_names = {
                        "auth_logs": "🔐 인증",
                        "navigation_logs": "🧭 네비게이션",
                        "search_logs": "🔍 검색",
                        "interaction_logs": "⚡ 상호작용",
                        "restaurant_logs": "🍽️ 음식점",
                        "activity_logs": "📋 기타",
                    }

                    collection_data = []
                    for col_name, count in collection_stats.items():
                        display_name = collection_names.get(col_name, col_name)
                        collection_data.append([display_name, count])

                    df_collections = pd.DataFrame(
                        collection_data, columns=["영역", "활동 수"]
                    )
                    st.bar_chart(df_collections.set_index("영역"))

                st.subheader("🎯 세부 활동 유형별 분포")
                activity_types = stats.get("activity_types", {})

                if activity_types:
                    # 바차트로 표시
                    import pandas as pd

                    df = pd.DataFrame(
                        list(activity_types.items()), columns=["활동 유형", "횟수"]
                    )
                    # 상위 10개만 표시
                    df_top = df.nlargest(10, "횟수")
                    st.bar_chart(df_top.set_index("활동 유형"))

                    # 전체 활동 유형 표시
                    with st.expander("전체 활동 유형 보기"):
                        st.dataframe(
                            df.sort_values("횟수", ascending=False),
                            use_container_width=True,
                        )
                else:
                    st.info("세부 통계 데이터가 없습니다.")
            else:
                st.info("통계 데이터를 불러올 수 없습니다.")
    else:
        st.error("로그 시스템을 사용할 수 없습니다.")


def render_authenticated_sidebar():
    """인증된 사용자를 위한 사이드바 렌더링"""
    with st.sidebar:
        # 사용자 정보 표시
        user_info = get_current_user()
        if user_info:
            st.success(f"👋 환영합니다, {user_info.get('displayName', '사용자')}님!")
            st.write(f"📧 {user_info.get('email', '')}")

            # 토큰 상태 표시 (개발용)
            session_manager = get_session_manager()
            if session_manager.is_token_valid():
                st.success("🔐 세션 활성")
            else:
                st.warning("⚠️ 세션 만료 임박")

            if st.button("🚪 로그아웃", use_container_width=True):
                logout()

        st.divider()

        # 페이지 선택
        page_options = ["🤤 오늘 머먹?", "🕺🏽 니가 가본 그집", "📊 내 활동 로그"]
        selected_page = st.radio("페이지 선택", page_options)

        return selected_page


def configure_page():
    """페이지 설정"""
    st.set_page_config(
        page_title="머먹?",
        page_icon="🍽️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.logo(
        link="https://what2eat-chat.streamlit.app/",
        image=LOGO_SMALL_IMG_PATH,
        icon_image=LOGO_TITLE_IMG_PATH,
    )


def main():
    """메인 함수"""
    # 초기 설정 (session_state 초기화를 먼저 실행)
    initialize_session_state()

    # 전체 앱 실행 횟수 카운트
    st.session_state.app_runs += 1

    # 페이지 설정 및 분석 로드
    configure_page()
    load_analytics()

    # 인증 상태 확인 및 세션 복원
    is_authenticated = check_authentication()

    # 로그인하지 않은 사용자는 로그인 페이지만 표시
    if not is_authenticated:
        login_page_fragment()
        return

    # 첫 로그인 사용자이고 온보딩을 완료하지 않은 경우 온보딩 페이지 표시
    if is_first_login() and not has_completed_onboarding():
        st.info(
            "🎉 처음 방문하신 것을 환영합니다! 맞춤 추천을 위한 간단한 설정을 진행해주세요."
        )
        # 온보딩에서도 app 인스턴스가 필요하므로 먼저 생성
        app = What2EatApp()
        onboarding_page = OnboardingPage(app)
        onboarding_page.render()
        return

    # 로그인된 사용자를 위한 메인 앱
    # 앱 초기화
    app = What2EatApp()
    page_manager = PageManager(app)

    # 사이드바 렌더링 및 페이지 선택
    selected_page = render_authenticated_sidebar()

    # 선택된 페이지에 따라 해당 함수 호출
    if selected_page == "🤤 오늘 머먹?":
        chat_page_fragment(page_manager)
    elif selected_page == "🕺🏽 니가 가본 그집":
        ranking_page_fragment(page_manager)
    elif selected_page == "📊 내 활동 로그":
        user_activity_logs_fragment()


if __name__ == "__main__":
    main()
