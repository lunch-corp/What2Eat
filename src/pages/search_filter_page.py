# src/pages/search_filter_page.py
"""맛집 검색 필터 페이지 (목록 표시)"""

import pandas as pd
import streamlit as st

from pages import search_map_page
from utils.api import APIRequester
from utils.app import What2EatApp
from utils.auth import get_current_user, get_user_personalization_status
from utils.dialogs import change_location
from utils.firebase_logger import get_firebase_logger
from utils.search_filter import SearchFilter


def _log_user_activity(activity_type: str, detail: dict) -> bool:
    """사용자 활동 로깅 헬퍼 메서드"""
    logger = get_firebase_logger()
    if "user_info" not in st.session_state or not st.session_state.user_info:
        return False

    uid = st.session_state.user_info.get("localId")
    if not uid:
        return False

    return logger.log_user_activity(uid, activity_type, detail)


def initialize_session_state():
    """세션 상태 초기화"""
    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    if "search_display_count" not in st.session_state:
        st.session_state.search_display_count = 15
    if "search_filters" not in st.session_state:
        st.session_state.search_filters = {
            "radius_km": 5.0,
            "large_categories": [],
            "middle_categories": [],
            "sort_by": "개인화",
        }
    if "filtered_restaurant_ids" not in st.session_state:
        st.session_state.filtered_restaurant_ids = []
    if "filtered_restaurant_ids_all" not in st.session_state:
        st.session_state.filtered_restaurant_ids_all = []  # 30km 범위의 전체 데이터
    if "filter_cache_key" not in st.session_state:
        st.session_state.filter_cache_key = None
    if "total_results_count" not in st.session_state:
        st.session_state.total_results_count = 0
    if "filtered_distance_id_mapping" not in st.session_state:
        st.session_state.filtered_distance_id_mapping = {}
    if "filtered_distance_id_mapping_all" not in st.session_state:
        st.session_state.filtered_distance_id_mapping_all = {}  # 30km 범위의 전체 거리 데이터


def render_filter_ui(app: What2EatApp, search_filter: SearchFilter):
    """필터 UI 렌더링 (폼 기반)"""
    st.subheader("🔍 검색 필터")

    # 위치 설정 (폼 외부)
    col1, col2 = st.columns([3, 1])
    with col1:
        if "address" in st.session_state:
            st.info(f"📍 현재 위치: {st.session_state.address}")
        else:
            st.warning("⚠️ 위치를 설정해주세요")
    with col2:
        if st.button("위치 변경", use_container_width=True):
            change_location()
            _log_user_activity("location_change", {"from_page": "search_filter"})

    st.markdown("---")

    # # 카테고리 선택 (폼 외부 - 동적 업데이트를 위해)
    # st.markdown("### 🍽️ 카테고리")

    # # 대분류 카테고리
    # large_categories = [cat for cat in LARGE_CATEGORIES if cat not in LARGE_CATEGORIES_NOT_USED]
    # selected_large = st.multiselect(
    #     "대분류 카테고리",
    #     options=large_categories,
    #     default=st.session_state.search_filters["large_categories"],
    #     help="대분류를 선택하면 해당하는 중분류만 표시됩니다",
    #     key="large_category_filter"
    # )

    # # 중분류 카테고리 (대분류 선택에 따라 동적으로 필터링)
    # if selected_large:
    #     df_filtered_by_large = app.df_diner[
    #         app.df_diner["diner_category_large"].isin(selected_large)
    #     ]
    #     middle_categories = sorted(
    #         df_filtered_by_large["diner_category_middle"].dropna().unique()
    #     )

    #     # 이전에 선택된 중분류 중 현재 대분류에 해당하는 것만 유지
    #     valid_middle_defaults = [
    #         cat
    #         for cat in st.session_state.search_filters["middle_categories"]
    #         if cat in middle_categories
    #     ]

    #     selected_middle = st.multiselect(
    #         "중분류 카테고리",
    #         options=middle_categories,
    #         default=valid_middle_defaults,
    #         help=f"{len(middle_categories)}개의 중분류 카테고리 사용 가능",
    #         key="middle_category_filter"
    #     )
    # else:
    #     # 대분류가 선택되지 않은 경우 빈 목록 표시
    #     selected_middle = st.multiselect(
    #         "중분류 카테고리",
    #         options=[],
    #         default=[],
    #         disabled=True,
    #         help="먼저 대분류 카테고리를 선택해주세요",
    #         key="middle_category_filter"
    #     )

    # st.markdown("---")

    # 폼으로 나머지 필터 감싸기
    with st.form("search_filter_form", clear_on_submit=False):
        # 반경 설정
        radius_km = st.slider(
            "검색 반경 (km)",
            min_value=0.3,
            max_value=50.0,
            value=st.session_state.search_filters["radius_km"],
            step=0.3,
        )

        # 카테고리 선택
        st.markdown("### 🍽️ 카테고리")

        # 대분류 카테고리 (API에서 가져오기)
        from utils.category_manager import get_category_manager

        category_manager = get_category_manager()
        large_categories_data = category_manager.get_large_categories()
        large_categories = [cat["name"] for cat in large_categories_data]

        selected_large = st.multiselect(
            "대분류 카테고리",
            options=large_categories,
            default=st.session_state.search_filters["large_categories"],
        )

        # 중분류 카테고리 (대분류 선택 시 활성화)
        middle_categories = []
        if selected_large:
            # 선택된 대분류 카테고리별로 중분류 가져오기
            all_middle = []
            for large_cat in selected_large:
                middle_data = category_manager.get_middle_categories(large_cat)
                all_middle.extend([cat["name"] for cat in middle_data])
            middle_categories = sorted(list(set(all_middle)))  # 중복 제거

            selected_middle = st.multiselect(
                "중분류 카테고리",
                options=middle_categories,
                default=[
                    cat
                    for cat in st.session_state.search_filters["middle_categories"]
                    if cat in middle_categories
                ],
            )
        else:
            selected_middle = []

        # 정렬 기준
        st.markdown("### 📊 정렬 기준")

        # 사용자 개인화 설정 확인
        user_status = get_user_personalization_status()
        is_personalization_enabled = user_status.get(
            "is_personalization_enabled", False
        )

        # 정렬 옵션 동적 생성
        sort_options = []
        if is_personalization_enabled:
            sort_options.append("개인화")
        sort_options.extend(["인기도", "숨찐맛", "거리순"])

        # 현재 선택된 정렬 방식이 옵션에 없으면 기본값으로 변경
        current_sort = st.session_state.search_filters["sort_by"]
        if current_sort not in sort_options:
            current_sort = sort_options[0]
            st.session_state.search_filters["sort_by"] = current_sort

        sort_by = st.radio(
            "정렬 방식",
            options=sort_options,
            index=sort_options.index(current_sort),
            horizontal=True,
        )

        # 개인화가 비활성화되어 있고 사용자가 개인화를 선택하려 하면 안내 메시지
        if not is_personalization_enabled and "개인화" not in sort_options:
            st.info("💡 개인화 추천을 이용하려면 초기 취향 탐색을 완료해주세요!")

        # 검색 버튼
        st.markdown("---")
        submitted = st.form_submit_button(
            "🔍 검색하기", type="primary", use_container_width=True
        )

        if submitted:
            # 폼 제출 시 세션 상태 업데이트 (카테고리는 폼 외부에서 이미 처리됨)
            st.session_state.search_filters["radius_km"] = radius_km
            st.session_state.search_filters["large_categories"] = selected_large
            st.session_state.search_filters["middle_categories"] = selected_middle
            st.session_state.search_filters["sort_by"] = sort_by

            # 활동 로그 기록
            try:
                from utils.activity_logger import get_activity_logger

                logger = get_activity_logger()
                logger.log_filter_change(
                    address=st.session_state.address,
                    lat=st.session_state.user_lat,
                    lon=st.session_state.user_lon,
                    radius=radius_km,
                    large_categories=selected_large,
                    middle_categories=selected_middle,
                    sort_by=sort_by,
                    location_method=st.session_state.get("location_method"),
                    page="search_filter",
                )
            except Exception:
                # 로깅 실패해도 계속 진행
                pass

            return True

    return False


def render_restaurant_dataframe(df_results, total_count=None):
    """음식점 목록을 DataFrame으로 렌더링"""
    if total_count is None:
        total_count = len(df_results)
    st.subheader(f"📋 검색 결과 ({total_count}개)")

    if len(df_results) == 0:
        st.info("검색 결과가 없습니다. 필터 조건을 변경해보세요.")
        return

    # 표시할 개수 (현재까지 가져온 데이터만 표시)
    display_count = min(st.session_state.search_display_count, len(df_results))
    df_display = df_results.head(display_count).copy()
    df_display["카테고리"] = df_display["diner_category_middle"].fillna(
        df_display["diner_category_large"]
    )

    # 정렬 기준 가져오기
    sort_by = st.session_state.search_filters.get("sort_by", "인기도")

    # 정렬 기준에 따른 컬럼 헤더 및 표시 정보 결정
    if sort_by == "숨찐맛":
        col4_label = "숨찐맛 점수"
        col5_label = "거리"
    elif sort_by == "개인화":
        col4_label = "개인화 점수"
        col5_label = "거리"
    elif sort_by == "인기도":
        col4_label = "인기도 점수"
        col5_label = "거리"
    elif sort_by == "거리순":
        col4_label = "리뷰 수"
        col5_label = "거리"
    else:  # 개인화 또는 기본값
        col4_label = "리뷰 수"
        col5_label = "거리"

    # 컬럼 헤더 표시
    col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 1, 1, 1])
    with col1:
        st.write("**음식점명**")
    with col2:
        st.write("**카테고리**")
    with col3:
        st.write("**등급**")
    with col4:
        st.write(f"**{col4_label}**")
    with col5:
        st.write(f"**{col5_label}**")
    with col6:
        st.write("**보기**")

    st.divider()

    # 각 음식점을 개별 행으로 렌더링하여 클릭 감지 가능하게 만들기
    from utils.activity_logger import get_activity_logger

    for list_idx, (df_idx, row) in enumerate(df_display.iterrows()):
        diner_idx = row["diner_idx"]
        diner_name = row["diner_name"]
        diner_url = f"https://place.map.kakao.com/{diner_idx}"

        col1, col2, col3, col4, col5, col6 = st.columns([3, 2, 1, 1, 1, 1])

        with col1:
            st.write(f"**{diner_name}**")
        with col2:
            st.write(row["카테고리"])
        with col3:
            st.write(
                "⭐" * int(row["diner_grade"])
                if pd.notna(row["diner_grade"]) and row["diner_grade"]
                else ""
            )
        with col4:
            # 정렬 기준에 따라 다른 정보 표시
            if sort_by == "숨찐맛":
                if "hidden_score" in row and pd.notna(row["hidden_score"]):
                    st.write(f"{row['hidden_score']:.2f}")
                else:
                    st.write("-")
            elif sort_by == "인기도":
                if "bayesian_score" in row and pd.notna(row["bayesian_score"]):
                    st.write(f"{row['bayesian_score']:.2f}")
                else:
                    st.write("-")
            elif sort_by == "개인화":
                if "personalized_score" in row and pd.notna(row["personalized_score"]):
                    st.write(f"{row['personalized_score']:.2f}")
                else:
                    st.write("-")
            else:  # 개인화 또는 기본값
                st.write(
                    int(row["diner_review_cnt"])
                    if pd.notna(row["diner_review_cnt"])
                    else 0
                )
        with col5:
            if "distance" in row and pd.notna(row["distance"]):
                st.write(f"{row['distance']:.1f}km")
            else:
                st.write("-")
        with col6:
            # 버튼 클릭 시 로그 기록 후 링크로 이동
            button_key = f"view_diner_{diner_idx}_{list_idx}"
            if st.button("보기", key=button_key, use_container_width=True):
                try:
                    logger = get_activity_logger()
                    logger.log_diner_click(
                        diner_idx=str(diner_idx),
                        diner_name=diner_name,
                        position=list_idx + 1,
                        page="search_filter",
                    )
                except Exception:
                    # 로깅 실패해도 계속 진행
                    pass

                # HTML과 JavaScript를 사용하여 새 탭에서 URL 열기
                st.components.v1.html(
                    f"""
                    <script>
                        window.open("{diner_url}", "_blank");
                    </script>
                    """,
                    height=0,
                )
        if list_idx < len(df_display) - 1:
            st.divider()

    # 더보기 버튼
    total_count = st.session_state.get("total_results_count", len(df_results))
    current_display_count = min(st.session_state.search_display_count, len(df_results))

    if current_display_count < total_count:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(
                f"더보기 ({current_display_count}/{total_count}개 표시 중)",
                use_container_width=True,
                type="secondary",
            ):
                # 다음 페이지 데이터 가져오기
                from utils.app import What2EatApp
                from utils.search_filter import SearchFilter

                if "app" not in st.session_state:
                    st.session_state.app = What2EatApp()
                search_filter = SearchFilter(st.session_state.app.df_diner)

                filters = st.session_state.search_filters
                user_id = None
                if "user_info" in st.session_state and st.session_state.user_info:
                    user_id = st.session_state.user_info.get("localId")

                # 개인화인 경우와 아닌 경우를 구분하여 처리
                if filters["sort_by"] == "개인화":
                    # 개인화인 경우: 세션에 저장된 전체 정렬된 결과에서 다음 페이지 가져오기
                    if "personalized_all_results" in st.session_state:
                        personalized_all = st.session_state.personalized_all_results
                        next_page_results = personalized_all.iloc[
                            current_display_count : current_display_count + 15
                        ].copy()

                        if len(next_page_results) > 0:
                            # 기존 결과에 추가
                            st.session_state.search_results = pd.concat(
                                [st.session_state.search_results, next_page_results],
                                ignore_index=True,
                            )
                            st.session_state.search_display_count += 15
                        else:
                            st.warning("더 이상 표시할 결과가 없습니다.")
                    else:
                        st.warning("개인화 결과를 찾을 수 없습니다.")
                else:
                    # 개인화가 아닌 경우: 기존 로직 사용
                    diner_ids = st.session_state.filtered_restaurant_ids

                    # 다음 페이지 가져오기 (현재까지 표시한 개수를 offset으로 사용)
                    next_page_results = search_filter.sort_restaurants(
                        diner_ids=diner_ids,
                        sort_by=filters["sort_by"],
                        user_lat=st.session_state.user_lat,
                        user_lon=st.session_state.user_lon,
                        user_id=user_id,
                        limit=15,
                        offset=current_display_count,
                    )

                    if next_page_results is not None and len(next_page_results) > 0:
                        # 거리값 매핑
                        if (
                            "id" in next_page_results.columns
                            and "filtered_distance_dict" in st.session_state
                        ):
                            next_page_results["distance"] = next_page_results["id"].map(
                                st.session_state.filtered_distance_dict
                            )

                        # 기존 결과에 추가
                        st.session_state.search_results = pd.concat(
                            [st.session_state.search_results, next_page_results],
                            ignore_index=True,
                        )
                        st.session_state.search_display_count += 15
                    else:
                        st.warning("더 이상 표시할 결과가 없습니다.")
                st.rerun()
    else:
        st.success(f"✅ 모든 {total_count}개 음식점을 표시했습니다.")


def render():
    """검색 필터 페이지 렌더링"""
    # 페이지 방문 로그
    _log_user_activity("page_visit", {"page_name": "search_filter"})

    # 앱 인스턴스 가져오기
    if "app" not in st.session_state:
        st.session_state.app = What2EatApp()
    app = st.session_state.app

    # 세션 상태 초기화
    initialize_session_state()

    # 검색 필터 인스턴스
    search_filter = SearchFilter(app.df_diner)

    st.title("🔍 맛집 검색")

    # 위치 확인
    if "address" not in st.session_state or "user_lat" not in st.session_state:
        st.warning("⚠️ 위치를 먼저 설정해주세요.")
        if st.button("위치 설정하기"):
            change_location()

        return

    # 필터 UI (폼 기반, 단일 레이아웃)
    with st.expander("🔍 검색 필터 설정", expanded=True):
        search_clicked = render_filter_ui(app, search_filter)

    # 검색 실행
    if search_clicked or st.session_state.search_results is not None:
        if search_clicked:
            filters = st.session_state.search_filters

            # API 호출 시 radius_km를 30으로 고정 (최적화: 더 많은 데이터를 한 번에 가져오기)
            api_radius_km = max(30.0, filters["radius_km"])

            # 필터 조건으로 캐시 키 생성 (API 호출 기준: 30으로 고정)
            current_cache_key = search_filter._generate_filter_cache_key(
                user_lat=st.session_state.user_lat,
                user_lon=st.session_state.user_lon,
                radius_km=api_radius_km,  # API 호출 기준으로 30 사용
                large_categories=filters["large_categories"] or [],
                middle_categories=filters["middle_categories"] or [],
            )

            # 필터 조건이 변경되었는지 확인
            filter_changed = (
                st.session_state.filter_cache_key is None
                or st.session_state.filter_cache_key != current_cache_key
            )

            if filter_changed:
                # 필터가 변경되면 개인화 결과 초기화
                if "personalized_all_results" in st.session_state:
                    del st.session_state.personalized_all_results

                # 필터링 API 호출 (30km로 고정하여 더 많은 데이터 가져오기)
                diner_ids, diner_idx, distance_dict, distance_dict_idx = (
                    search_filter.get_filtered_restaurants(
                        user_lat=st.session_state.user_lat,
                        user_lon=st.session_state.user_lon,
                        radius_km=api_radius_km,  # 30으로 고정
                        large_categories=filters["large_categories"]
                        if filters["large_categories"]
                        else None,
                        middle_categories=filters["middle_categories"]
                        if filters["middle_categories"]
                        else None,
                    )
                )

                if diner_ids is not None and len(diner_ids) > 0:
                    # 전체 데이터를 캐시에 저장 (30km 범위의 모든 데이터)
                    st.session_state.filtered_restaurant_ids_all = diner_ids
                    st.session_state.filtered_restaurant_idx_all = diner_idx
                    st.session_state.filtered_distance_id_mapping_all = (
                        distance_dict or {}
                    )
                    st.session_state.filtered_distance_idx_mapping_all = (
                        distance_dict_idx or {}
                    )
                    st.session_state.filter_cache_key = current_cache_key
                else:
                    st.error("❌ 필터링된 음식점을 가져올 수 없습니다.")
                    return
            diner_id_to_idx = dict(
                zip(
                    st.session_state.filtered_restaurant_ids_all,
                    st.session_state.filtered_restaurant_idx_all,
                )
            )
            # 클라이언트 사이드에서 사용자가 선택한 반경으로 필터링
            user_radius_km = filters["radius_km"]

            # 전체 데이터가 있는지 확인
            if not st.session_state.filtered_restaurant_ids_all:
                st.error("❌ 필터링된 음식점 데이터가 없습니다.")
                return

            filtered_diner_ids = [
                diner_id
                for diner_id in st.session_state.filtered_restaurant_ids_all
                if st.session_state.filtered_distance_id_mapping_all.get(
                    diner_id, float("inf")
                )
                <= user_radius_km
            ]
            filtered_diner_idx = [
                diner_id_to_idx[diner_id] for diner_id in filtered_diner_ids
            ]
            filtered_distance_id_mapping = {
                diner_id: st.session_state.filtered_distance_id_mapping_all[diner_id]
                for diner_id in filtered_diner_ids
            }
            filtered_distance_idx_mapping = {
                diner_id_to_idx[
                    diner_id
                ]: st.session_state.filtered_distance_id_mapping_all[diner_id]
                for diner_id in filtered_diner_ids
            }

            # 필터링된 결과 사용
            diner_ids = filtered_diner_ids
            diner_idx = filtered_diner_idx
            st.session_state.filtered_restaurant_ids = filtered_diner_ids
            st.session_state.filtered_restaurant_idx = filtered_diner_idx
            st.session_state.filtered_distance_id_mapping = filtered_distance_id_mapping
            st.session_state.filtered_distance_idx_mapping = (
                filtered_distance_idx_mapping
            )

            # 전체 결과 개수 저장
            st.session_state.total_results_count = len(diner_ids)

            # 개인화는 한번에 가져와서 표출할 때에 페이지네이션을 한다.
            if filters["sort_by"] == "개인화":
                # 개인화 정렬: API를 직접 호출하여 개인화된 순서로 재정렬
                firebase_uid = get_current_user()["localId"]

                try:
                    all_df_results = search_filter.apply_filters(
                        user_lat=st.session_state.user_lat,
                        user_lon=st.session_state.user_lon,
                        radius_km=filters["radius_km"],
                        large_categories=filters["large_categories"]
                        if filters["large_categories"]
                        else None,
                        middle_categories=filters["middle_categories"]
                        if filters["middle_categories"]
                        else None,
                        sort_by=filters["sort_by"],
                    )
                    diner_idx_list = all_df_results["diner_idx"].tolist()

                    if all_df_results is not None and len(all_df_results) > 0:
                        # Call personal recommendation API
                        api = APIRequester(endpoint=st.secrets["API_URL"])
                        response = api.post(
                            "/rec/personal",
                            data={
                                "diner_ids": diner_idx_list,
                                "firebase_uid": firebase_uid,
                            },
                        ).json()

                        personalized_diner_ids = response["diner_ids"]
                        personalized_scores = response["scores"]

                        # Handle case where response has fewer items than original
                        if len(personalized_diner_ids) < len(diner_idx_list):
                            # Get remaining diner_ids not in personalized response
                            # These diners are **cold-start** diners, not in train data
                            remaining_ids = [
                                id
                                for id in diner_idx_list
                                if id not in personalized_diner_ids
                            ]
                            # Combine personalized + remaining in original order
                            final_diner_ids = personalized_diner_ids + remaining_ids
                            scores = personalized_scores + ["NA"] * len(remaining_ids)
                        else:
                            final_diner_ids = personalized_diner_ids.copy()
                            scores = personalized_scores.copy()

                        # Reorder all_df_results based on personalized order
                        all_df_results = (
                            all_df_results.set_index("diner_idx")
                            .reindex(final_diner_ids)
                            .reset_index()
                        )
                        all_df_results["personalized_score"] = scores
                        all_df_results["distance"] = all_df_results["id"].map(
                            st.session_state.filtered_distance_id_mapping
                        )
                        # 전체 결과를 세션 상태에 저장 (페이지네이션을 위해)
                        st.session_state.personalized_all_results = all_df_results
                        # 전체 결과 개수 업데이트
                        st.session_state.total_results_count = len(all_df_results)
                        # 첫 페이지는 15개만 표시
                        df_results = all_df_results[:15]

                except Exception as e:
                    st.warning(
                        f"개인화 추천을 불러오는데 실패했습니다. 기본 정렬을 사용합니다: {e}"
                    )
                    # Fallback to default sorting
                    df_results = search_filter.sort_restaurants(
                        diner_ids=diner_ids,
                        sort_by="인기도",
                        limit=15,
                        offset=0,
                    )
            else:
                # 개인화가 아닌 경우: 기존 정렬 로직 사용
                df_results = search_filter.sort_restaurants(
                    diner_ids=diner_ids,
                    sort_by=filters["sort_by"],
                    limit=15,
                    offset=0,
                )

                if (
                    "id" in df_results.columns
                    and "filtered_distance_id_mapping" in st.session_state
                ):
                    df_results["distance"] = df_results["id"].map(
                        st.session_state.filtered_distance_id_mapping
                    )

            if df_results is None:
                st.error("❌ 음식점 정렬 중 오류가 발생했습니다.")
                return

            # 거리값 매핑 (filtered_distance_id_mapping에서 가져오기)
            # 개인화인 경우는 이미 거리 매핑을 완료했으므로 건너뜀

            # 결과 저장
            st.session_state.search_results = df_results
            # 표시 개수 초기화
            st.session_state.search_display_count = 15

            # 로깅
            _log_user_activity(
                "search_executed",
                {
                    "filters": filters,
                    "results_count": len(df_results),
                    "filter_changed": filter_changed,
                },
            )

        # 결과 표시
        df_results = st.session_state.search_results

        # 지도 보기 버튼
        if len(df_results) > 0:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button(
                    "🗺️ 지도에서 보기", use_container_width=True, type="primary"
                ):
                    search_map_page.render_dialog()
                    # CHECKLIST: 지도 페이지 렌더링 버전 말고  지도 페이지로 이동시
                    # st.switch_page(st.Page(search_map_page.render, url_path="map", title="지도 보기", icon="🗺️"))

        st.markdown("---")

        # 목록 표시 (DataFrame)
        total_count = st.session_state.get("total_results_count", len(df_results))
        render_restaurant_dataframe(df_results, total_count=total_count)
    else:
        st.info("👆 위에서 필터를 설정하고 검색해보세요!")
