# src/utils/pages.py

import streamlit as st

from config.constants import GRADE_MAP, PRIORITY_ORDER
from utils.data_processing import (
    category_filters,
    get_filtered_data,
    grade_to_stars,
    search_menu,
    select_radius,
)
from utils.dialogs import change_location, show_restaurant_map
from utils.firebase_logger import get_firebase_logger
from utils.onboarding import get_onboarding_manager
from utils.ui_components import choice_avatar, display_results, my_chat_message
from utils.worldcup import get_worldcup_manager


class PageManager:
    """페이지 관리 클래스"""

    def __init__(self, app):
        self.app = app
        self.logger = get_firebase_logger()

    def _log_user_activity(self, activity_type: str, detail: dict) -> bool:
        """사용자 활동 로깅 헬퍼 메서드"""
        if "user_info" not in st.session_state or not st.session_state.user_info:
            return False

        uid = st.session_state.user_info.get("localId")
        if not uid:
            return False

        return self.logger.log_user_activity(uid, activity_type, detail)

    def ranking_page(self):
        """랭킹 페이지"""
        # 페이지 방문 로그
        self._log_user_activity("page_visit", {"page_name": "ranking"})

        st.title("지역별 카테고리 랭킹")

        # 현재 위치 표시 및 수정 옵션
        st.subheader("📍 현재 위치")
        if "address" not in st.session_state:
            change_location()
        else:
            st.write(st.session_state.address)
            if st.button("위치 변경"):
                change_location()
                # 위치 변경 로그
                self._log_user_activity("location_change", {"from_page": "ranking"})

        # 쩝슐랭 등급 선택
        st.subheader("🏅 쩝슐랭 등급 선택")
        selected_grades = st.multiselect(
            "보고 싶은 쩝슐랭 등급을 선택하세요 (다중 선택 가능)",
            options=["🌟", "🌟🌟", "🌟🌟🌟"],
            default=["🌟🌟🌟"],
        )
        selected_grade_values = [GRADE_MAP[grade] for grade in selected_grades]

        # 지역 선택
        self.app.df_diner[["city", "region"]] = (
            self.app.df_diner["diner_num_address"]
            .str.split(" ", n=2, expand=True)
            .iloc[:, :2]
        )

        ZONE_LIST = list(self.app.df_diner["city"].unique())
        zone = st.selectbox("지역을 선택하세요", ZONE_LIST, index=0)
        selected_zone_all = f"{zone} 전체"

        # 선택한 지역의 데이터 필터링
        filtered_zone_df = self.app.df_diner[self.app.df_diner["city"] == zone]

        # 상세 지역 선택
        city_options = list(filtered_zone_df["region"].dropna().unique())
        city_label = st.selectbox(
            "상세 지역을 선택하세요", [selected_zone_all] + city_options
        )

        if city_label:
            filtered_zone_df["diner_category_large"] = filtered_zone_df[
                "diner_category_large"
            ].fillna("기타")
            if city_label == selected_zone_all:
                filtered_city_df = filtered_zone_df
            else:
                filtered_city_df = filtered_zone_df[
                    filtered_zone_df["region"] == city_label
                ]

            # 중간 카테고리 선택 및 필터링
            available_categories = filtered_city_df["diner_category_large"].unique()
            selected_category = st.selectbox(
                "중간 카테고리를 선택하세요", ["전체"] + list(available_categories)
            )

            if selected_category != "전체":
                filtered_city_df = filtered_city_df[
                    filtered_city_df["diner_category_large"] == selected_category
                ]
                # 카테고리 필터링 로그
                self._log_user_activity(
                    "category_filter",
                    {
                        "category": selected_category,
                        "location": city_label,
                        "from_page": "ranking",
                    },
                )

            # 세부 카테고리 선택 및 필터링
            available_small_categories = (
                filtered_city_df["diner_category_middle"].fillna("기타").unique()
            )
            selected_small_category = st.selectbox(
                "세부 카테고리를 선택하세요",
                ["전체"] + list(available_small_categories),
            )

            if selected_small_category != "전체":
                filtered_city_df = filtered_city_df[
                    filtered_city_df["diner_category_middle"] == selected_small_category
                ]

            # 쩝슐랭 등급 필터링
            filtered_city_df = filtered_city_df[
                filtered_city_df["diner_grade"].isin(selected_grade_values)
            ]

            # 랭킹 조회 로그
            self._log_user_activity(
                "ranking_view",
                {
                    "location": city_label,
                    "category": selected_category,
                    "small_category": selected_small_category,
                    "grades": selected_grades,
                    "results_count": len(filtered_city_df),
                },
            )

            # 세부 카테고리별 랭킹 표시
            st.subheader(
                f"{selected_category if selected_category != '전체' else '전체 중간 카테고리'} 카테고리 ({selected_small_category if selected_small_category != '전체' else '전체'}) 랭킹"
            )

            # 수정: 복사본을 만들고 fillna 적용
            filtered_city_df_copy = filtered_city_df.copy()
            filtered_city_df_copy["diner_category_middle"] = filtered_city_df_copy[
                "diner_category_middle"
            ].fillna(filtered_city_df_copy["diner_category_large"])

            ranked_df = filtered_city_df_copy.sort_values(
                by="bayesian_score", ascending=False
            )[
                [
                    "diner_name",
                    "diner_url",
                    "diner_category_middle",
                    "diner_grade",
                    "diner_lat",
                    "diner_lon",
                    "diner_menu_name",
                    "diner_tag",
                    "diner_num_address",
                    "region",
                ]
            ]

            if not ranked_df.empty:
                # 지도 다이얼로그를 위한 상태 추가
                if "show_map" not in st.session_state:
                    st.session_state.show_map = False
                if "selected_restaurant" not in st.session_state:
                    st.session_state.selected_restaurant = None

                # 음식점 목록을 카드 형태로 표시
                ranked_df = ranked_df[:100]
                for _, row in ranked_df.iterrows():
                    with st.container():
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col1:
                            st.write(grade_to_stars(row["diner_grade"]))
                        with col2:
                            # 음식점 링크 클릭 로그
                            if st.button(
                                f"**{row['diner_name']}** | {row['diner_category_middle']} | {row['region']}",
                                key=f"link_{row['diner_name']}",
                            ):
                                # 강화된 음식점 클릭 로깅
                                logger = get_firebase_logger()
                                if (
                                    "user_info" in st.session_state
                                    and st.session_state.user_info
                                ):
                                    uid = st.session_state.user_info.get("localId")
                                    if uid:
                                        logger.log_restaurant_click(
                                            uid=uid,
                                            restaurant_name=row["diner_name"],
                                            restaurant_url=row["diner_url"],
                                            restaurant_idx=str(
                                                row.get("diner_idx", "")
                                            ),
                                            category=row["diner_category_middle"],
                                            location=row["region"],
                                            grade=row.get("diner_grade"),
                                            review_count=row.get("diner_review_cnt"),
                                            distance=row.get("distance"),
                                            from_page="ranking",
                                        )
                                st.link_button("음식점 보기", row["diner_url"])
                        with col3:
                            if st.button("상세정보", key=f"map_{row['diner_name']}"):
                                st.session_state.show_map = True
                                st.session_state.selected_restaurant = row
                                # 상세정보 조회 로그
                                logger = get_firebase_logger()
                                if (
                                    "user_info" in st.session_state
                                    and st.session_state.user_info
                                ):
                                    uid = st.session_state.user_info.get("localId")
                                    if uid:
                                        logger.log_restaurant_detail_view(
                                            uid=uid,
                                            restaurant_name=row["diner_name"],
                                            restaurant_idx=str(
                                                row.get("diner_idx", "")
                                            ),
                                            from_page="ranking",
                                        )
                                show_restaurant_map(
                                    st.session_state.selected_restaurant
                                )
                        st.divider()
            else:
                st.warning("해당 조건의 랭킹 데이터가 없습니다.")

    def chat_page(self):
        """채팅 페이지"""
        # 페이지 방문 로그
        self._log_user_activity("page_visit", {"page_name": "chat"})

        # 아바타 선택 및 초기화
        if st.session_state.avatar_style is None:
            st.session_state.avatar_style, st.session_state.seed = choice_avatar()

        avatar_style = st.session_state.avatar_style
        seed = st.session_state.seed

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
                    # 위치 변경 로그
                    self._log_user_activity("location_change", {"from_page": "chat"})
            with col2:
                if st.button("다음 단계로", use_container_width=True):
                    st.session_state.chat_step = "select_radius"
                    # 단계 진행 로그
                    self._log_user_activity(
                        "chat_step_progress", {"step": "select_radius"}
                    )
                    st.rerun()

        # 단계 2: 반경 선택
        elif st.session_state.chat_step == "select_radius":
            my_chat_message("어디까지 갈겨?", avatar_style, seed)
            radius_kilometers, radius_distance = select_radius(avatar_style, seed)

            # 반경 내 데이터 필터링
            df_geo_filtered = get_filtered_data(
                self.app.df_diner, st.session_state.user_lat, st.session_state.user_lon
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

            df_geo_filtered = df_quality

            if len(df_geo_filtered):
                df_geo_filtered_radius = df_geo_filtered[
                    df_geo_filtered["distance"] <= radius_kilometers
                ]
                st.session_state.df_filtered = df_geo_filtered_radius[
                    df_geo_filtered_radius["bayesian_score"].notna()
                ]

                if len(st.session_state.df_filtered):
                    # 반경 선택 로그
                    self._log_user_activity(
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
                            # 단계 진행 로그
                            self._log_user_activity(
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
                    "헉.. 주변에 맛집이 없대.. \n다른 위치를 찾아볼까?",
                    avatar_style,
                    seed,
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
                # 검색 방법 선택 로그
                self._log_user_activity(
                    "search_method_selection", {"method": search_option}
                )
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
                    # 메뉴 검색 로그
                    self._log_user_activity(
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
                    result = self.app.search_manager.get_random_recommendations(
                        st.session_state.df_filtered
                    )
                    if result:
                        # 랜덤 추천 로그
                        self._log_user_activity(
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
                    onboarding_manager = get_onboarding_manager(self.app)
                    user_profile = onboarding_manager.load_user_profile()
                    if user_profile:
                        # 새로운 구조 우선, 기존 구조 fallback
                        preferred_categories = user_profile.get(
                            "food_preferences_large",
                            user_profile.get("food_preferences", []),
                        )
                        # 실제 데이터에 존재하는 카테고리만 필터링
                        default_categories = [
                            cat
                            for cat in preferred_categories
                            if cat in sorted_diner_category_lst
                        ]
                except Exception:
                    # 온보딩 정보 로드 실패 시 빈 리스트 사용
                    default_categories = []

                if sorted_diner_category_lst:
                    diner_category = st.multiselect(
                        label="첫번째 업태",
                        options=sorted_diner_category_lst,
                        default=default_categories,
                        label_visibility="hidden",
                    )
                    if bool(diner_category):
                        # 카테고리 선택 로그
                        self._log_user_activity(
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
                                # 최종 검색 결과 로그
                                self._log_user_activity(
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
        if st.session_state.chat_step not in [
            "greeting",
            "select_radius",
            "search_method",
        ]:
            if st.button("처음부터 다시 찾기"):
                st.session_state.chat_step = "greeting"
                # 검색 초기화 로그
                self._log_user_activity("search_reset", {"from_page": "chat"})
                st.rerun()

    def worldcup_page(self):
        # 페이지 방문 로그
        self._log_user_activity("page_visit", {"page_name": "worldcup"})

        # WorldCupManager 사용
        worldcup_manager = get_worldcup_manager(self.app.df_diner)
        worldcup_manager.render_worldcup_page()
