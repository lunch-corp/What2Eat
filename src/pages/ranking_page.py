# src/pages/ranking_page.py
"""랭킹 페이지"""

import streamlit as st

from config.constants import GRADE_MAP
from utils.app import What2EatApp
from utils.dialogs import change_location
from utils.firebase_logger import get_firebase_logger


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
    """랭킹 페이지 렌더링"""
    # 페이지 방문 로그
    _log_user_activity("page_visit", {"page_name": "ranking"})

    # 앱 인스턴스 가져오기
    if "app" not in st.session_state:
        st.session_state.app = What2EatApp()

    st.title("지역별 카테고리 랭킹")

    # 현재 위치 표시 및 수정 옵션
    st.subheader("📍 현재 위치")
    if "address" not in st.session_state:
        change_location()
    else:
        st.write(st.session_state.address)
        if st.button("위치 변경"):
            change_location()
            _log_user_activity("location_change", {"from_page": "ranking"})

    # 쩝슐랭 등급 선택
    st.subheader("🏅 쩝슐랭 등급 선택")
    selected_grades = st.multiselect(
        "보고 싶은 쩝슐랭 등급을 선택하세요 (다중 선택 가능)",
        options=["🌟", "🌟🌟", "🌟🌟🌟"],
        default=["🌟🌟🌟"],
    )
    selected_grade_values = [GRADE_MAP[grade] for grade in selected_grades]

    # 지역 선택 (간소화 - API 기반으로 변경)
    st.info(
        "💡 랭킹 페이지는 현재 위치 기반으로 조회됩니다. API 기반으로 업데이트되었습니다."
    )

    # 현재 위치 정보 가져오기
    if "user_lat" not in st.session_state or "user_lon" not in st.session_state:
        st.warning("⚠️ 위치 정보가 없습니다. 위치를 설정해주세요.")
        change_location()
        return

    user_lat = st.session_state.user_lat
    user_lon = st.session_state.user_lon

    # 카테고리 선택
    from utils.category_manager import get_category_manager

    category_manager = get_category_manager()
    large_categories = category_manager.get_large_categories()

    category_names = ["전체"] + [cat["name"] for cat in large_categories]
    selected_category = st.selectbox("카테고리를 선택하세요", category_names)

    # 중분류 카테고리 선택
    selected_small_category = "전체"
    if selected_category != "전체":
        middle_categories = category_manager.get_middle_categories(selected_category)
        if middle_categories:
            middle_names = ["전체"] + [cat["name"] for cat in middle_categories]
            selected_small_category = st.selectbox(
                "세부 카테고리를 선택하세요", middle_names
            )

        _log_user_activity(
            "category_filter",
            {
                "category": selected_category,
                "from_page": "ranking",
            },
        )

    # API를 통해 음식점 데이터 가져오기
    import asyncio

    import pandas as pd

    from utils.api_client import get_yamyam_ops_client

    try:
        client = get_yamyam_ops_client()
        if not client:
            st.error("❌ API 클라이언트를 초기화할 수 없습니다.")
            return

        # 비동기 API 호출
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        restaurants = loop.run_until_complete(
            client.get_restaurants(
                user_lat=user_lat,
                user_lon=user_lon,
                radius_km=10.0,  # 10km 반경
                large_categories=[selected_category]
                if selected_category != "전체"
                else None,
                middle_categories=[selected_small_category]
                if selected_small_category != "전체"
                else None,
                sort_by="rating",
                limit=100,
            )
        )
        loop.close()

        if not restaurants:
            st.warning("⚠️ 조건에 맞는 음식점이 없습니다.")
            return

        filtered_city_df = pd.DataFrame(restaurants)

        # 등급 필터링 (API 응답에 diner_grade가 있는 경우)
        if "diner_grade" in filtered_city_df.columns:
            filtered_city_df = filtered_city_df[
                filtered_city_df["diner_grade"].isin(selected_grade_values)
            ]

    except Exception as e:
        st.error(f"❌ 음식점 조회 중 오류가 발생했습니다: {str(e)}")
        return

    # 활동 로그 기록
    try:
        from utils.activity_logger import get_activity_logger

        logger = get_activity_logger()
        logger.log_ranking_view(
            city=None,
            region=None,
            grades=selected_grades,
            large_category=selected_category if selected_category != "전체" else None,
            middle_category=selected_small_category
            if selected_small_category != "전체"
            else None,
        )
    except Exception:
        # 로깅 실패해도 계속 진행
        pass

    # 랭킹 조회 로그
    _log_user_activity(
        "ranking_view",
        {
            "category": selected_category,
            "small_category": selected_small_category,
            "grades": selected_grades,
            "results_count": len(filtered_city_df),
        },
    )

    # 세부 카테고리별 랭킹 표시
    st.subheader(
        f"{selected_category if selected_category != '전체' else '전체'} 카테고리 ({selected_small_category if selected_small_category != '전체' else '전체'}) 랭킹"
    )

    # 복사본을 만들고 fillna 적용
    filtered_city_df_copy = filtered_city_df.copy()
    if "diner_category_middle" in filtered_city_df_copy.columns:
        filtered_city_df_copy["diner_category_middle"] = filtered_city_df_copy[
            "diner_category_middle"
        ].fillna(filtered_city_df_copy.get("diner_category_large", "기타"))

    # 필요한 컬럼만 선택 (API 응답에 있는 컬럼만)
    available_columns = filtered_city_df_copy.columns.tolist()
    display_columns = []
    for col in [
        "diner_name",
        "diner_url",
        "diner_category_middle",
        "diner_grade",
        "diner_review_cnt",
        "diner_menu_name",
        "diner_tag",
        "diner_num_address",
    ]:
        if col in available_columns:
            display_columns.append(col)

    # 정렬 (bayesian_score가 있으면 사용, 없으면 diner_review_avg 사용)
    sort_column = (
        "bayesian_score"
        if "bayesian_score" in available_columns
        else "diner_review_avg"
    )
    if sort_column in available_columns:
        ranked_df = filtered_city_df_copy.sort_values(by=sort_column, ascending=False)[
            display_columns
        ]
    else:
        ranked_df = filtered_city_df_copy[display_columns]

    if not ranked_df.empty:
        # 지도 다이얼로그를 위한 상태 추가
        if "show_map" not in st.session_state:
            st.session_state.show_map = False
        if "selected_restaurant" not in st.session_state:
            st.session_state.selected_restaurant = None
            ranked_df_100 = ranked_df[:100].reset_index(drop=True)
            ranked_df_100["순위"] = ranked_df_100.index + 1

            # diner_idx를 먼저 저장 (rename 전)
            if "diner_idx" in ranked_df_100.columns:
                ranked_df_100["원본_diner_idx"] = ranked_df_100["diner_idx"]

            ranked_df_100.rename(
                columns={
                    "diner_grade": "등급",
                    "diner_name": "음식점명",
                    "diner_url": "링크",
                    "diner_category_middle": "카테고리",
                    "diner_menu_name": "메뉴",
                    "diner_tag": "태그",
                    "diner_num_address": "주소",
                    "region": "지역",
                    "diner_review_cnt": "리뷰수",
                    "distance": "거리(km)",
                },
                inplace=True,
            )

            # 각 음식점을 개별 행으로 렌더링하여 클릭 감지 가능하게 만들기
            import re

            import pandas as pd

            from utils.activity_logger import get_activity_logger

            for list_idx, (df_idx, row) in enumerate(ranked_df_100.iterrows()):
                # diner_idx 추출
                diner_idx = str(row.get("원본_diner_idx", ""))
                if not diner_idx and "링크" in row:
                    # 링크에서 diner_idx 추출
                    match = re.search(r"/(\d+)$", str(row["링크"]))
                    if match:
                        diner_idx = match.group(1)

                diner_name = row["음식점명"]
                diner_url = row.get("링크", f"https://place.map.kakao.com/{diner_idx}")

                col1, col2, col3, col4, col5, col6, col7 = st.columns(
                    [0.5, 3, 2, 1, 1, 1, 1]
                )

                with col1:
                    st.write(f"**{int(row['순위'])}**")
                with col2:
                    st.write(f"**{diner_name}**")
                with col3:
                    st.write(row["카테고리"])
                with col4:
                    st.write(
                        "⭐" * int(row["등급"])
                        if pd.notna(row["등급"]) and row["등급"]
                        else ""
                    )
                with col5:
                    st.write(int(row["리뷰수"]) if pd.notna(row["리뷰수"]) else 0)
                with col6:
                    if pd.notna(row.get("거리(km)")):
                        st.write(f"{row['거리(km)']:.1f}km")
                    else:
                        st.write("-")
                with col7:
                    # 직접 링크도 제공 (백업)
                    st.link_button("보기", diner_url)
                    # 활동 로그 기록
                    try:
                        logger = get_activity_logger()
                        logger.log_diner_click(
                            diner_idx=diner_idx,
                            diner_name=diner_name,
                            position=int(row["순위"]),
                            page="ranking",
                        )
                    except Exception:
                        # 로깅 실패해도 계속 진행
                        pass
                if list_idx < len(ranked_df_100) - 1:
                    st.divider()

            st.divider()
