# src/pages/search_map_page.py
"""맛집 검색 지도 시각화 페이지"""

import streamlit as st

from utils.app import What2EatApp
from utils.firebase_logger import get_firebase_logger
from utils.folium_map_utils import FoliumMapRenderer
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


@st.dialog("🗺️ 지도에서 보기", width="large")
def render_dialog():
    """지도 모달 다이얼로그 렌더링"""
    # 페이지 방문 로그
    _log_user_activity("page_visit", {"page_name": "search_map_dialog"})

    # 앱 인스턴스 가져오기
    if "app" not in st.session_state:
        st.session_state.app = What2EatApp()

    # 위치 확인
    if "address" not in st.session_state or "user_lat" not in st.session_state:
        st.warning("⚠️ 위치를 먼저 설정해주세요.")
        st.info("💡 '맛집 검색' 페이지에서 위치를 설정하고 검색해주세요.")
        return

    # 검색 결과 확인
    if (
        "search_results" not in st.session_state
        or st.session_state.search_results is None
    ):
        st.warning("⚠️ 검색 결과가 없습니다.")
        st.info("💡 '맛집 검색' 페이지에서 먼저 검색을 실행해주세요.")
        return

    df_results = st.session_state.search_results

    if len(df_results) == 0:
        st.info("검색 결과가 없습니다. 필터 조건을 변경해보세요.")
        return

    # 상위 15개만 지도에 표시
    df_for_map = df_results.head(15)

    st.info(f"📍 상위 15개 음식점을 지도에 표시합니다. (전체 {len(df_results)}개 중)")

    # 지도 렌더러 인스턴스
    map_renderer = FoliumMapRenderer()

    # 지도 중심 변경 감지 및 재검색 기능을 위한 상태 확인
    if "map_center_lat" not in st.session_state:
        st.session_state.map_center_lat = st.session_state.user_lat
        st.session_state.map_center_lon = st.session_state.user_lon

    # 지도 렌더링 (모달에 맞게 높이 조정)
    map_data = map_renderer.render_map(
        df_for_map,
        st.session_state.user_lat,
        st.session_state.user_lon,
        show_user_location=True,
        map_height=300,
    )

    st.markdown('<hr style="margin: 8px 0;">', unsafe_allow_html=True)

    if map_data and "center" in map_data:
        new_center = map_data["center"]
        if new_center:
            # 중심이 크게 변경되었는지 확인 (0.01도 이상)
            lat_diff = abs(new_center["lat"] - st.session_state.map_center_lat)
            lon_diff = abs(new_center["lng"] - st.session_state.map_center_lon)

            if lat_diff > 0.01 or lon_diff > 0.01:
                st.warning(
                    f"📍 지도 중심이 변경되었습니다. (이동 거리: 약 {lat_diff * 111:.1f}km)"
                )

                if st.button(
                    "📍 현 위치에서 재검색",
                    use_container_width=True,
                    type="primary",
                    key="research_btn",
                ):
                    # 위치 업데이트 (사용자 위치는 고정, 검색 중심만 변경)
                    st.session_state.map_center_lat = new_center["lat"]
                    st.session_state.map_center_lon = new_center["lng"]

                    # 자동으로 재검색 실행
                    app = st.session_state.app
                    search_filter = SearchFilter(app.df_diner)

                    # 기존 필터 사용하여 재검색 (새로운 중심 좌표 사용)
                    if "search_filters" in st.session_state:
                        filters = st.session_state.search_filters
                        df_results = search_filter.apply_filters(
                            user_lat=new_center["lat"],
                            user_lon=new_center["lng"],
                            radius_km=filters["radius_km"],
                            large_categories=filters["large_categories"]
                            if filters["large_categories"]
                            else None,
                            middle_categories=filters["middle_categories"]
                            if filters["middle_categories"]
                            else None,
                            sort_by=filters["sort_by"],
                        )

                        # 결과 저장
                        st.session_state.search_results = df_results

                        # 로깅
                        _log_user_activity(
                            "map_center_changed_research",
                            {
                                "new_lat": new_center["lat"],
                                "new_lng": new_center["lng"],
                                "results_count": len(df_results),
                            },
                        )

                        st.success("✅ 재검색이 완료되었습니다!")
                        st.rerun()
                    else:
                        st.warning(
                            "⚠️ 검색 필터 정보가 없습니다. '맛집 검색' 페이지에서 먼저 검색해주세요."
                        )
            else:
                st.success("✅ 현재 위치에서 검색 중입니다.")
