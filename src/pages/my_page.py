# src/pages/my_page.py
"""마이페이지"""

from datetime import datetime

import streamlit as st

from utils.auth import get_current_user, get_user_ratings_summary
from utils.my_page_helpers import get_restaurant_history


def render():
    """마이페이지 렌더링"""
    st.title("👤 마이페이지")

    user_info = get_current_user()
    if not user_info:
        st.error("❌ 로그인이 필요합니다.")
        return

    uid = user_info.get("localId")

    # 공통 데이터 미리 로드
    ratings_summary = get_user_ratings_summary(uid)
    restaurant_history = get_restaurant_history(uid)

    # 사용자 기본 정보 표시
    st.header("👋 환영합니다!")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.info(f"📧 **이메일:** {user_info.get('email', '알 수 없음')}")
        st.info(f"👤 **닉네임:** {user_info.get('displayName', '사용자')}")

    with col2:
        # 가입일 표시
        metadata = user_info.get("metadata", {})
        if metadata.get("creationTime"):
            creation_time = datetime.fromtimestamp(metadata["creationTime"] / 1000)
            st.metric("🗓️ 가입일", creation_time.strftime("%Y.%m.%d"))

    with col3:
        # 마지막 로그인 표시
        if metadata.get("lastSignInTime"):
            last_signin = datetime.fromtimestamp(metadata["lastSignInTime"] / 1000)
            st.metric("🔐 마지막 로그인", last_signin.strftime("%m.%d %H:%M"))

    st.divider()

    # 간단한 활동 요약 대시보드
    st.subheader("📊 활동 요약")

    # 메트릭 표시
    col1, col2 = st.columns(2)

    with col1:
        rated_count = ratings_summary.get("total_rated", 0) if ratings_summary else 0
        st.metric("⭐ 평가한 음식점", f"{rated_count}개")

    with col2:
        visited_count = len(restaurant_history) if restaurant_history else 0
        st.metric("🍽️ 클릭한 음식점", f"{visited_count}개")

    st.divider()

    # 탭으로 구분
    rating_tab, restaurant_tab = st.tabs(["⭐ 평가한 음식점", "🍽️ 클릭한 음식점"])

    with rating_tab:
        st.subheader("⭐ 내가 평가한 음식점")

        if ratings_summary and ratings_summary.get("total_rated", 0) > 0:
            # 요약 통계
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("🍽️ 평가한 음식점", f"{ratings_summary['total_rated']}개")

            with col2:
                st.metric("⭐ 평균 평점", f"{ratings_summary['average_rating']:.1f}점")

            with col3:
                # 가장 많이 준 평점
                distribution = ratings_summary["rating_distribution"]
                if distribution:
                    most_common = max(distribution.items(), key=lambda x: x[1])
                    st.metric("🎯 선호 평점", f"{most_common[0]}점")

            st.divider()

            # 평점 분포 차트
            st.markdown("### 📊 평점 분포")
            if distribution:
                try:
                    import pandas as pd

                    chart_data = pd.DataFrame(
                        [
                            {"평점": f"{star}⭐", "개수": count}
                            for star, count in distribution.items()
                            if count > 0
                        ]
                    )

                    if not chart_data.empty:
                        st.bar_chart(chart_data.set_index("평점"))
                except ImportError:
                    st.error("pandas 라이브러리가 필요합니다.")

            st.divider()

            # 평가한 음식점 목록
            st.markdown("### 🏪 평가한 음식점 목록")
            rated_restaurants = ratings_summary.get("rated_restaurants", [])

            if rated_restaurants:
                # 평점별로 필터링 옵션
                all_ratings = sorted(
                    set(r["rating"] for r in rated_restaurants), reverse=True
                )
                selected_rating = st.selectbox(
                    "평점별 필터", ["전체"] + [f"{r}점" for r in all_ratings], index=0
                )

                # 필터링
                if selected_rating != "전체":
                    target_rating = int(selected_rating.replace("점", ""))
                    filtered_restaurants = [
                        r for r in rated_restaurants if r["rating"] == target_rating
                    ]
                else:
                    filtered_restaurants = rated_restaurants

                st.info(
                    f"📊 {len(filtered_restaurants)}개 음식점 (총 {len(rated_restaurants)}개 중)"
                )

                # 음식점 목록 표시
                for i, restaurant in enumerate(filtered_restaurants[:20]):
                    with st.container():
                        col1, col2 = st.columns([1, 3])

                        with col1:
                            # 평점을 별로 표시
                            rating = restaurant["rating"]
                            stars = "⭐" * rating
                            st.write(f"**{stars}**")
                            st.caption(f"{rating}점")

                        with col2:
                            diner_idx = restaurant.get("diner_idx", "알 수 없음")
                            st.write(f"**음식점 ID:** {diner_idx}")
                            st.caption("온보딩에서 평가한 음식점입니다.")

                        if i < len(filtered_restaurants) - 1:
                            st.divider()

                if len(filtered_restaurants) > 20:
                    st.info(
                        f"💡 {len(filtered_restaurants) - 20}개 음식점이 더 있습니다."
                    )

            else:
                st.info("📝 아직 평가한 음식점이 없습니다.")

        else:
            st.info("⭐ 아직 평가한 음식점이 없습니다.")
            st.markdown(
                """
            **💡 음식점을 평가하는 방법:**
            1. 온보딩에서 취향 평가하기
            2. 추천받은 음식점에 평점 남기기
            """
            )

    with restaurant_tab:
        st.subheader("🍽️ 클릭한 음식점 이력")

        if restaurant_history:
            st.info(f"🍽️ 총 {len(restaurant_history)}개의 음식점과 상호작용했습니다.")

            # 최근 방문한 음식점들을 카드 형태로 표시
            for i, restaurant in enumerate(restaurant_history[:15]):
                with st.container():
                    col1, col2, col3, col4 = st.columns([1, 3, 1, 1])

                    with col1:
                        if restaurant["type"] == "음식점 클릭":
                            st.success("👆 클릭")
                        else:
                            st.info("👀 상세보기")

                    with col2:
                        st.write(f"**{restaurant['restaurant_name']}**")
                        details = []
                        if restaurant.get("category"):
                            details.append(restaurant["category"])
                        if restaurant.get("location"):
                            details.append(restaurant["location"])
                        if details:
                            st.caption(" | ".join(details))

                        # 등급 표시
                        if restaurant.get("grade"):
                            grade = restaurant["grade"]
                            stars = "⭐" * int(grade) if grade else ""
                            st.caption(f"등급: {stars} ({grade}점)")

                    with col3:
                        if restaurant.get("from_page"):
                            page_emoji = {"chat": "💬", "ranking": "🏆", "search": "🔍"}
                            emoji = page_emoji.get(restaurant["from_page"], "📱")
                            st.write(f"{emoji}")
                            st.caption(restaurant["from_page"])

                    with col4:
                        if restaurant["timestamp"]:
                            st.caption(restaurant["timestamp"])

                        # 음식점 URL이 있으면 버튼 표시
                        if restaurant.get("url"):
                            st.link_button(
                                "🔗", restaurant["url"], use_container_width=True
                            )

                    if i < len(restaurant_history) - 1:
                        st.divider()
        else:
            st.info("🍽️ 아직 클릭한 음식점이 없습니다. 맛집을 찾아보세요!")
