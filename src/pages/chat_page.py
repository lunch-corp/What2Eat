# src/pages/chat_page.py
"""채팅 페이지"""

import streamlit as st

from config.constants import PRIORITY_ORDER
from utils.app import What2EatApp
from utils.data_processing import (
    category_filters,
    get_filtered_data,
    search_menu,
    select_radius,
)
from utils.dialogs import change_location, show_restaurant_map
from utils.firebase_logger import get_firebase_logger
from utils.onboarding import get_onboarding_manager
from utils.ui_components import choice_avatar, display_results, my_chat_message


def _log_user_activity(activity_type: str, detail: dict) -> bool:
    """사용자 활동 로깅 헬퍼 메서드"""
    logger = get_firebase_logger()
    if "user_info" not in st.session_state or not st.session_state.user_info:
        return False

    uid = st.session_state.user_info.get("localId")
    if not uid:
        return False

    return logger.log_user_activity(uid, activity_type, detail)


def render():
    """채팅 페이지 렌더링"""
    # 페이지 방문 로그
    _log_user_activity("page_visit", {"page_name": "chat"})

    # 앱 인스턴스 가져오기
    if "app" not in st.session_state:
        st.session_state.app = What2EatApp()
    app = st.session_state.app

    # 아바타 선택 및 초기화
    if "avatar_style" not in st.session_state or st.session_state.avatar_style is None:
        st.session_state.avatar_style, st.session_state.seed = choice_avatar()

    avatar_style = st.session_state.avatar_style
    seed = st.session_state.seed

    # chat_step 초기화
    if "chat_step" not in st.session_state:
        st.session_state.chat_step = "greeting"

    # 단계 1: 인사 및 위치 확인
    if st.session_state.chat_step == "greeting":
        my_chat_message("안녕! 오늘 머먹?", avatar_style, seed)

        if "address" not in st.session_state:
            change_location()

        my_chat_message(
            f"{st.session_state.address} 근처에서 찾아볼게! 만약 다른 위치에서 찾고 싶다면 아래 버튼을 눌러!",
            avatar_style,
            seed,
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("위치 변경", use_container_width=True):
                change_location()
                _log_user_activity("location_change", {"from_page": "chat"})
        with col2:
            if st.button("다음 단계로", use_container_width=True):
                st.session_state.chat_step = "select_radius"
                _log_user_activity("chat_step_progress", {"step": "select_radius"})
                st.rerun()

    # 단계 2: 반경 선택
    elif st.session_state.chat_step == "select_radius":
        my_chat_message("어디까지 갈겨?", avatar_style, seed)
        radius_kilometers, radius_distance = select_radius(avatar_style, seed)

        # 반경 내 데이터 필터링
        df_geo_filtered = get_filtered_data(
            app.df_diner, st.session_state.user_lat, st.session_state.user_lon
        )

        df_geo_filtered = df_geo_filtered[(df_geo_filtered["diner_grade"].notna())]

        # diner_grade 값 확인 (1 이상인지)
        df_quality = df_geo_filtered[df_geo_filtered["diner_grade"] >= 1]

        # 찐맛집(diner_grade >= 1)이 있는지 확인
        if len(df_quality) == 0:
            my_chat_message(
                "찐맛집이 근처에 없어... 😢\n반경을 좀 더 넓게 설정해볼까?",
                avatar_style,
                seed,
            )
            return

        if len(df_quality):
            df_geo_filtered_radius = df_quality[
                df_quality["distance"] <= radius_kilometers
            ]
            st.session_state.df_filtered = df_geo_filtered_radius[
                df_geo_filtered_radius["bayesian_score"].notna()
            ]

            if len(st.session_state.df_filtered):
                # 반경 선택 로그
                _log_user_activity(
                    "radius_selection",
                    {
                        "radius_km": radius_kilometers,
                        "radius_distance": radius_distance,
                        "restaurants_found": len(st.session_state.df_filtered),
                    },
                )

                radius_col1, radius_col2 = st.columns([2, 1])
                with radius_col2:
                    if st.session_state.chat_step != "greeting":
                        if st.button("처음으로"):
                            st.session_state.chat_step = "greeting"
                            st.rerun()
                with radius_col1:
                    if st.button("다음 단계로", use_container_width=True):
                        st.session_state.chat_step = "search_method"
                        _log_user_activity(
                            "chat_step_progress", {"step": "search_method"}
                        )
                        st.rerun()
            else:
                my_chat_message(
                    "헉.. 이 반경에는 찐맛집이 없네..😢\n다른 반경을 선택해볼까?",
                    avatar_style,
                    seed,
                )
        else:
            my_chat_message(
                "헉.. 주변에 맛집이 없대.. \n다른 위치를 찾아볼까?", avatar_style, seed
            )
            if st.button("위치 다시 선택하기", use_container_width=True):
                st.session_state.chat_step = "greeting"
                st.rerun()

    # 단계 3: 검색 방법 선택
    elif st.session_state.chat_step == "search_method":
        search_option = st.radio(
            "검색 방법을 선택하세요",
            ("카테고리로 찾기", "메뉴로 찾기", "랜덤 추천 받기"),
            index=0,
        )

        if st.button("선택 완료", use_container_width=True):
            st.session_state.search_option = search_option
            st.session_state.chat_step = "search"
            _log_user_activity("search_method_selection", {"method": search_option})
            st.rerun()

    # 단계 4: 검색 실행
    elif st.session_state.chat_step == "search":
        if st.session_state.search_option == "메뉴로 찾기":
            menu_search = st.text_input("찾고 싶은 메뉴를 입력하세요")
            if menu_search:
                df_menu_filtered = st.session_state.df_filtered[
                    st.session_state.df_filtered.apply(
                        lambda row: search_menu(row, menu_search), axis=1
                    )
                ]
                _log_user_activity(
                    "menu_search",
                    {
                        "search_term": menu_search,
                        "results_count": len(df_menu_filtered),
                    },
                )
                display_results(
                    df_menu_filtered,
                    st.session_state.radius_kilometers,
                    st.session_state.radius_distance,
                    avatar_style,
                    seed,
                )

        elif st.session_state.search_option == "랜덤 추천 받기":
            if st.button("랜덤 뽑기", use_container_width=True):
                result = app.search_manager.get_random_recommendations(
                    st.session_state.df_filtered
                )
                if result:
                    _log_user_activity(
                        "random_recommendation",
                        {"restaurant_name": result.get("diner_name", "Unknown")},
                    )
                    show_restaurant_map(result)

        else:  # 카테고리로 찾기
            my_chat_message("뭐 먹을겨?", avatar_style, seed)
            diner_category_lst = list(
                st.session_state.df_filtered["diner_category_large"].unique()
            )
            sorted_diner_category_lst = sorted(
                diner_category_lst, key=lambda x: PRIORITY_ORDER.get(x, 3)
            )

            # 온보딩에서 선택한 선호 카테고리를 기본값으로 설정
            default_categories = []
            try:
                onboarding_manager = get_onboarding_manager(app)
                user_profile = onboarding_manager.load_user_profile()
                if user_profile:
                    preferred_categories = user_profile.get(
                        "food_preferences_large",
                        user_profile.get("food_preferences", []),
                    )
                    default_categories = [
                        cat
                        for cat in preferred_categories
                        if cat in sorted_diner_category_lst
                    ]
            except Exception:
                default_categories = []

            if sorted_diner_category_lst:
                diner_category = st.multiselect(
                    label="첫번째 업태",
                    options=sorted_diner_category_lst,
                    default=default_categories,
                    label_visibility="hidden",
                )
                if bool(diner_category):
                    _log_user_activity(
                        "category_selection",
                        {"categories": diner_category, "from_page": "chat"},
                    )

                    df_geo_mid_category_filtered = category_filters(
                        diner_category, st.session_state.df_filtered
                    )
                    if len(df_geo_mid_category_filtered):
                        my_chat_message(
                            "세부 업종에서 안 당기는 건 빼!", avatar_style, seed
                        )
                        unique_categories = (
                            df_geo_mid_category_filtered["diner_category_middle"]
                            .unique()
                            .tolist()
                        )
                        selected_category = st.multiselect(
                            label="세부 카테고리",
                            options=unique_categories,
                            default=unique_categories,
                        )
                        if selected_category:
                            df_geo_small_category_filtered = (
                                df_geo_mid_category_filtered[
                                    df_geo_mid_category_filtered[
                                        "diner_category_middle"
                                    ].isin(selected_category)
                                ].sort_values(by="bayesian_score", ascending=False)
                            )
                            _log_user_activity(
                                "search_results",
                                {
                                    "search_type": "category",
                                    "large_categories": diner_category,
                                    "small_categories": selected_category,
                                    "results_count": len(
                                        df_geo_small_category_filtered
                                    ),
                                },
                            )
                            display_results(
                                df_geo_small_category_filtered,
                                st.session_state.radius_kilometers,
                                st.session_state.radius_distance,
                                avatar_style,
                                seed,
                            )
            else:
                my_chat_message(
                    "헉.. 주변에 찐맛집이 없대.. \n 다른 메뉴를 골라봐",
                    avatar_style,
                    seed,
                )
    else:
        my_chat_message(
            "헉.. 주변에 맛집이 없대.. \n 다른 위치를 찾아봐", avatar_style, seed
        )

    # 검색 초기화 버튼
    if st.session_state.chat_step not in ["greeting", "select_radius", "search_method"]:
        if st.button("처음부터 다시 찾기"):
            st.session_state.chat_step = "greeting"
            _log_user_activity("search_reset", {"from_page": "chat"})
            st.rerun()
