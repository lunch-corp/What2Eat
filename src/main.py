# src/main.py

import streamlit as st

from config.constants import LOGO_SMALL_IMG_PATH, LOGO_TITLE_IMG_PATH
from pages import (chat_page, my_page, ranking_page, search_filter_page,
                   worldcup_page)
from pages.onboarding import OnboardingPage
from utils.analytics import load_analytics
from utils.app import What2EatApp
from utils.auth import (AuthManager, auth_form, get_current_user,
                        has_completed_onboarding, logout)


def login_page():
    """로그인 페이지"""
    # 쿠키 확인 로직 제거 (main()에서 이미 처리됨)

    # 로고와 앱 소개
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(LOGO_TITLE_IMG_PATH, width=300)

    # 로그인 폼
    auth_form()


def configure_page(is_authenticated: bool = False):
    """페이지 설정"""
    st.set_page_config(
        page_title="머먹?",
        page_icon="🍽️",
        layout="wide",
        initial_sidebar_state="expanded" if is_authenticated else "collapsed",
    )
    st.logo(
        link="https://what2eat.streamlit.app/",
        image=LOGO_SMALL_IMG_PATH,
        icon_image=LOGO_TITLE_IMG_PATH,
    )


def setup_sidebar():
    """사이드바 설정"""
    with st.sidebar:
        # 사용자 정보 표시
        user_info = get_current_user()
        if user_info:
            st.success(f"👋 환영합니다, {user_info.get('displayName', '사용자')}님!")
            st.write(f"📧 {user_info.get('email', '')}")

            if st.button("🚪 로그아웃", use_container_width=True):
                logout()


@st.dialog("🎉 What2Eat에 오신 것을 환영합니다!")
def show_onboarding_dialog():
    """온보딩 시작 여부를 묻는 다이얼로그"""
    st.markdown("""
    ### 맞춤형 맛집 추천을 위한 초기 취향 탐색
    
    간단한 질문에 답하시면 당신만을 위한 맛집을 추천해드려요!
    - 소요 시간: 약 3-5분
    - 위치, 선호 음식, 음식점 평가 등
    
    **나중에 하기를 선택하시면 개인화 추천 없이 일반 검색만 이용하실 수 있습니다.**
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 시작하기", type="primary", use_container_width=True):
            st.session_state.start_onboarding = True
            st.session_state.onboarding_dialog_shown = True
            st.rerun()

    with col2:
        if st.button("나중에 하기", use_container_width=True):
            st.session_state.start_onboarding = False
            st.session_state.onboarding_dialog_shown = True
            st.rerun()


def main():
    """메인 함수"""
    # AuthManager를 통한 인증 관리
    auth_manager = AuthManager()

    # 세션 상태 초기화 및 쿠키에서 인증 상태 복원
    auth_manager.init_session_state()

    # 인증 상태 확인
    is_authenticated = auth_manager.check_authentication()

    # 페이지 설정 및 분석 로드
    configure_page(is_authenticated)
    load_analytics()

    # 로그인하지 않은 사용자는 로그인 페이지만 표시
    if not is_authenticated:
        login_page()
        st.stop()  # 로그인 페이지 표시 후 실행 중단
        return

    # 온보딩 플로우 처리
    force_onboarding = st.session_state.get("force_onboarding", False)

    # 강제 온보딩 또는 온보딩 미완료 상태 확인
    if not has_completed_onboarding() or force_onboarding:
        # 다이얼로그 표시 여부 플래그 초기화
        if "onboarding_dialog_shown" not in st.session_state:
            st.session_state.onboarding_dialog_shown = False

        # 온보딩 시작 여부 플래그 초기화
        if "start_onboarding" not in st.session_state:
            st.session_state.start_onboarding = False

        # 강제 온보딩인 경우 다이얼로그 없이 바로 시작
        if force_onboarding:
            st.info(
                "🔄 프로필을 다시 설정합니다. 더 정확한 추천을 위해 정보를 업데이트해주세요!"
            )
            # 강제 온보딩 플래그 리셋
            st.session_state["force_onboarding"] = False

            # 온보딩에서도 app 인스턴스가 필요하므로 먼저 생성
            app = What2EatApp()
            onboarding_page = OnboardingPage(app)
            onboarding_page.render()
            return

        # 다이얼로그를 아직 표시하지 않았으면 표시
        if not st.session_state.onboarding_dialog_shown:
            show_onboarding_dialog()
            # 다이얼로그 표시 후에는 메인 앱 렌더링 중단
            st.stop()

        # 사용자가 "시작하기"를 선택한 경우 온보딩 시작
        if st.session_state.start_onboarding:
            st.info(
                "🎉 머먹에 오신 것을 환영합니다! 맞춤 추천을 위한 간단한 설정을 진행해주세요."
            )
            # 온보딩에서도 app 인스턴스가 필요하므로 먼저 생성
            app = What2EatApp()
            onboarding_page = OnboardingPage(app)
            onboarding_page.render()
            return

        # 사용자가 "나중에 하기"를 선택한 경우 메인 앱으로 진행
        # (아래 코드 계속 실행)

    # 로그인된 사용자를 위한 메인 앱
    # 앱 초기화
    if "app" not in st.session_state:
        st.session_state.app = What2EatApp()

    # 사이드바 설정
    setup_sidebar()

    # 페이지 정의
    pages = [
        st.Page(
            search_filter_page.render, url_path="search", title="맛집 검색", icon="🔍"
        ),
        st.Page(
            ranking_page.render, url_path="ranking", title="니가 가본 그집", icon="🕺🏽"
        ),
        st.Page(my_page.render, url_path="mypage", title="마이페이지", icon="👤"),
        st.Page(
            worldcup_page.render,
            url_path="worldcup",
            title="맛집 이상형 월드컵",
            icon="⚽",
        ),
        st.Page(chat_page.render, url_path="chat", title="오늘 머먹?", icon="🤤"),
    ]

    # 온보딩 완료 직후라면 chat_page를 기본값으로 설정
    if (
        "onboarding_just_completed" in st.session_state
        and st.session_state.onboarding_just_completed
    ):
        st.success("🎉 온보딩이 완료되었습니다! 이제 맞춤 추천을 받아보세요.")
        st.session_state.onboarding_just_completed = False

    # 네비게이션 실행
    pg = st.navigation(pages)
    pg.run()


if __name__ == "__main__":
    main()
