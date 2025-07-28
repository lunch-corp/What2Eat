# pages/onboarding.py

import streamlit as st

from utils.auth import get_current_user
from utils.category_manager import get_category_manager
from utils.firebase_logger import get_firebase_logger
from utils.onboarding import get_onboarding_manager


class OnboardingPage:
    """온보딩 페이지 클래스"""

    def __init__(self, app=None):
        self.logger = get_firebase_logger()
        self.onboarding_manager = get_onboarding_manager(app)
        self.category_manager = get_category_manager(app)
        self.min_ratings_required = 5  # 최소 평가 개수

        # 온보딩 단계 초기화
        if "onboarding_step" not in st.session_state:
            st.session_state.onboarding_step = 0

        # 사용자 데이터 초기화
        if "user_profile" not in st.session_state:
            st.session_state.user_profile = {}

        if "restaurant_ratings" not in st.session_state:
            st.session_state.restaurant_ratings = {}

    def _handle_current_location(self):
        """현재 위치 찾기 helper 함수"""
        from streamlit_geolocation import streamlit_geolocation

        from utils.geolocation import geocode, save_user_location

        with st.spinner("📍 현재 위치를 찾는 중입니다..."):
            location = streamlit_geolocation()
            if location["latitude"] is not None and location["longitude"] is not None:
                st.session_state.user_lat, st.session_state.user_lon = (
                    location["latitude"],
                    location["longitude"],
                )
                st.session_state.address = geocode(
                    st.session_state.user_lon, st.session_state.user_lat
                )

                # Firestore에 위치 저장
                save_user_location(
                    st.session_state.address,
                    st.session_state.user_lat,
                    st.session_state.user_lon,
                )

                # 온보딩 프로필에 저장
                self._save_location_to_profile(st.session_state.address, "geolocation")

                st.success("✅ 위치를 찾았습니다!")
            else:
                st.error("위 버튼을 눌러 현위치를 확인해보세요.")

    def _handle_keyword_search(self, search_text):
        """키워드 검색 처리 helper 함수"""
        import requests

        from config.constants import KAKAO_API_HEADERS, KAKAO_API_URL
        from utils.geolocation import save_user_location

        params = {"query": search_text, "size": 1}
        response = requests.get(KAKAO_API_URL, headers=KAKAO_API_HEADERS, params=params)

        if response.status_code == 200:
            response_json = response.json()
            response_doc_list = response_json["documents"]
            if response_doc_list:
                response_doc = response_doc_list[0]
                address = response_doc["address_name"]
                lat = float(response_doc["y"])
                lon = float(response_doc["x"])

                # 세션 상태에 저장
                st.session_state.address = address
                st.session_state.user_lat, st.session_state.user_lon = lat, lon

                # Firestore에 위치 저장
                save_user_location(address, lat, lon)

                # 온보딩 프로필에 저장
                self._save_location_to_profile(address, "search")

                st.success(f"✅ 위치를 찾았습니다: {address}")
                st.rerun()
            else:
                st.warning("다른 검색어를 입력해봐...")
        else:
            st.error("다른 검색어를 입력해봐...")

    def _save_location_to_profile(self, address, method):
        """온보딩 프로필에 위치 정보 저장 helper 함수"""
        st.session_state.user_profile["location"] = address
        st.session_state.user_profile["location_method"] = method

    def _render_location_controls(self):
        """위치 설정 컨트롤 렌더링 helper 함수"""
        option = st.radio(
            "위치를 선택하세요",
            ("키워드로 검색으로 찾기(강남역 or 강남대로 328)", "주변에서 찾기"),
            key="onboarding_location_option",
        )

        if option == "주변에서 찾기":
            self._handle_current_location()

        elif option == "키워드로 검색으로 찾기(강남역 or 강남대로 328)":
            # session_state 초기화
            if "onboarding_last_search" not in st.session_state:
                st.session_state.onboarding_last_search = ""

            search_region_text = st.text_input(
                "주소나 키워드로 입력해줘",
                key="onboarding_search_input",
                placeholder="예: 강남역, 강남대로 328, 마포구 홍대",
            )
            search_clicked = st.button("검색", key="onboarding_search_button")

            # 검색 버튼을 클릭했거나 새로운 검색어로 엔터를 눌렀을 때
            if search_clicked or (
                search_region_text
                and search_region_text != st.session_state.onboarding_last_search
            ):
                st.session_state.onboarding_last_search = search_region_text
                self._handle_keyword_search(search_region_text)

    def _render_navigation_buttons(
        self,
        prev_step,
        next_step,
        next_condition=True,
        next_label="다음 ▶",
        disabled_label=None,
    ):
        """네비게이션 버튼 렌더링 helper 함수"""
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("◀ 이전", use_container_width=True):
                # 음식점 평가 단계에서 이전으로 돌아갈 때 데이터 초기화
                if st.session_state.onboarding_step == 4:
                    if "loaded_restaurants" in st.session_state:
                        del st.session_state.loaded_restaurants
                    if "restaurants_offset" in st.session_state:
                        del st.session_state.restaurants_offset

                st.session_state.onboarding_step = prev_step
                st.rerun()

        with col2:
            if next_condition:
                if st.button(next_label, use_container_width=True, type="primary"):
                    st.session_state.onboarding_step = next_step
                    st.rerun()
            else:
                button_text = disabled_label or "조건을 먼저 완료해주세요"
                st.button(button_text, disabled=True, use_container_width=True)

    def render(self):
        """온보딩 페이지 렌더링"""
        st.set_page_config(
            page_title="What2Eat - 초기 설정", page_icon="🍽️", layout="wide"
        )

        # 진행 상태 표시
        self._render_progress_bar()

        # 현재 단계에 따른 페이지 렌더링
        if st.session_state.onboarding_step == 0:
            self._render_welcome_step()
        elif st.session_state.onboarding_step == 1:
            self._render_location_step()
        elif st.session_state.onboarding_step == 2:
            self._render_basic_info_step()
        elif st.session_state.onboarding_step == 3:
            self._render_taste_preferences_step()
        elif st.session_state.onboarding_step == 4:
            self._render_restaurant_rating_step()
        elif st.session_state.onboarding_step == 5:
            self._render_completion_step()

    def _render_progress_bar(self):
        """진행 상태 바 렌더링"""
        steps = ["환영", "위치", "기본정보", "취향", "평가", "완료"]
        current_step = st.session_state.onboarding_step

        # 진행률 계산
        progress = (current_step + 1) / len(steps)

        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.progress(progress)
            st.caption(f"단계 {current_step + 1}/{len(steps)}: {steps[current_step]}")

    def _render_welcome_step(self):
        """환영 단계"""
        st.markdown("# 🎉 What2Eat에 오신 것을 환영합니다!")

        st.markdown("""
        ### 맞춤형 음식점 추천을 위해 몇 가지 정보가 필요해요
        
        **넷플릭스에서 영화를, 스포티파이에서 음악을 추천받듯이**  
        What2Eat에서는 당신만의 맛집을 추천해드려요! 🍽️
        
        #### 📝 설정 과정 (약 3-5분 소요)
        1. **위치 정보** - 주로 방문하는 지역
        2. **기본 정보** - 연령, 성별, 식사 스타일
        3. **취향 정보** - 매운맛 정도, 알러지 등
        4. **음식점 평가** - 몇 개 음식점에 대한 평가
        
        설정을 완료하면 당신만을 위한 **개인화된 맛집 추천**을 받을 수 있어요!
        """)

        if st.button("🚀 시작하기", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 1
            st.rerun()

    def _render_location_step(self):
        """위치 정보 수집 단계"""
        st.markdown("# 📍 주로 어디서 식사하시나요?")

        st.markdown("""
        맛집 추천을 위해 주로 방문하시는 지역을 알려주세요.  
        현재 위치 또는 자주 가시는 동네를 입력해주시면 됩니다.
        """)

        # 기존 geolocation 함수들을 활용하여 위치를 설정합니다.
        st.markdown("#### 위치를 설정해주세요")

        self._render_location_controls()

        # 이미 위치가 설정되어 있다면 표시
        if st.session_state.user_profile.get("location"):
            st.info(f"✅ 현재 설정된 위치: {st.session_state.user_profile['location']}")

        # 다음 단계 버튼
        location_set = bool(st.session_state.user_profile.get("location"))
        self._render_navigation_buttons(
            0, 2, next_condition=location_set, disabled_label="위치를 먼저 설정해주세요"
        )

    def _render_basic_info_step(self):
        """기본 정보 수집 단계"""
        st.markdown("# 👤 기본 정보를 알려주세요")

        st.markdown("맞춤 추천을 위해 몇 가지 기본 정보가 필요해요.")

        col1, col2 = st.columns(2)

        with col1:
            # 출생연도
            birth_year = st.selectbox(
                "출생연도",
                options=list(range(2010, 1940, -1)),
                index=list(range(2010, 1940, -1)).index(
                    st.session_state.user_profile.get("birth_year", 1990)
                ),
            )
            st.session_state.user_profile["birth_year"] = birth_year

            # 성별
            gender = st.selectbox(
                "성별",
                ["선택 안함", "남성", "여성", "기타"],
                index=["선택 안함", "남성", "여성", "기타"].index(
                    st.session_state.user_profile.get("gender", "선택 안함")
                ),
            )
            st.session_state.user_profile["gender"] = gender

        with col2:
            # 동행 상황 (다중 선택)
            st.markdown("**주로 누구와 식사하시나요?** (복수 선택 가능)")

            dining_companions = st.session_state.user_profile.get(
                "dining_companions", []
            )

            solo = st.checkbox("혼밥", value="혼밥" in dining_companions)
            date = st.checkbox("데이트", value="데이트" in dining_companions)
            friends = st.checkbox("친구모임", value="친구모임" in dining_companions)
            family = st.checkbox("가족", value="가족" in dining_companions)
            business = st.checkbox("회식", value="회식" in dining_companions)

            # 선택된 동행 상황 업데이트
            companions = []
            if solo:
                companions.append("혼밥")
            if date:
                companions.append("데이트")
            if friends:
                companions.append("친구모임")
            if family:
                companions.append("가족")
            if business:
                companions.append("회식")

            st.session_state.user_profile["dining_companions"] = companions

        # 식사비 정보
        st.markdown("### 💰 평소 식사비는 어느 정도인가요?")

        col3, col4 = st.columns(2)
        with col3:
            regular_budget = st.selectbox(
                "평소 식사비 (1인 기준)",
                ["1만원 이하", "1-2만원", "2-3만원", "3-5만원", "5만원 이상"],
                index=[
                    "1만원 이하",
                    "1-2만원",
                    "2-3만원",
                    "3-5만원",
                    "5만원 이상",
                ].index(st.session_state.user_profile.get("regular_budget", "1-2만원")),
            )
            st.session_state.user_profile["regular_budget"] = regular_budget

        with col4:
            special_budget = st.selectbox(
                "특별한 날 식사비 (1인 기준)",
                ["2만원 이하", "2-5만원", "5-10만원", "10-20만원", "20만원 이상"],
                index=[
                    "2만원 이하",
                    "2-5만원",
                    "5-10만원",
                    "10-20만원",
                    "20만원 이상",
                ].index(st.session_state.user_profile.get("special_budget", "2-5만원")),
            )
            st.session_state.user_profile["special_budget"] = special_budget

        # 다음 단계 버튼
        self._render_navigation_buttons(1, 3)

    def _render_taste_preferences_step(self):
        """취향 정보 수집 단계"""
        st.markdown("# 🌶️ 취향 정보를 알려주세요")

        # 매운맛 정도
        st.markdown("### 매운맛은 어느 정도까지 드실 수 있나요?")

        spice_levels = {
            0: "매운맛을 못 먹어요",
            1: "진라면 순한맛 정도 (1단)",
            2: "신라면 정도 (2단)",
            3: "틈새라면 정도 (3단)",
            4: "불닭볶음면 정도 (4단)",
            5: "그보다 더 매운 것도 좋아요 (5단 이상)",
        }

        spice_level = st.select_slider(
            "매운맛 단계",
            options=list(spice_levels.keys()),
            format_func=lambda x: spice_levels[x],
            value=st.session_state.user_profile.get("spice_level", 2),
        )
        st.session_state.user_profile["spice_level"] = spice_level

        # 알러지 정보
        st.markdown("### 🚫 알러지나 못 드시는 음식이 있나요?")

        col1, col2 = st.columns(2)
        with col1:
            allergies = st.text_area(
                "알러지 정보",
                placeholder="예: 새우, 견과류, 갑각류 등",
                value=st.session_state.user_profile.get("allergies", ""),
                height=100,
            )
            st.session_state.user_profile["allergies"] = allergies

        with col2:
            dislikes = st.text_area(
                "못 드시는 음식",
                placeholder="예: 생선, 양념치킨, 파 등",
                value=st.session_state.user_profile.get("dislikes", ""),
                height=100,
            )
            st.session_state.user_profile["dislikes"] = dislikes

        # 선호하는 음식 유형
        st.markdown("### 🍽️ 어떤 음식을 주로 좋아하시나요?")

        # 카테고리 매니저에서 대분류 카테고리 가져오기
        large_categories = self.category_manager.get_large_categories()

        # 사용자 선택 상태 초기화
        if "selected_large_categories" not in st.session_state:
            st.session_state.selected_large_categories = []
        if "selected_middle_categories" not in st.session_state:
            st.session_state.selected_middle_categories = {}

        st.markdown("#### 🏷️ 주요 음식 카테고리")
        st.caption("관심 있는 음식 종류를 선택해주세요 (복수 선택 가능)")

        # 대분류 카테고리 선택
        selected_large = []

        # 3열로 구성하여 카테고리 표시
        cols = st.columns(3)
        for i, category in enumerate(large_categories):
            col_idx = i % 3
            with cols[col_idx]:
                display_name = self.category_manager.get_category_display_name(
                    category["name"], category["count"]
                )

                is_selected = st.checkbox(
                    display_name,
                    value=category["name"]
                    in st.session_state.user_profile.get("food_preferences_large", []),
                    key=f"large_cat_{category['name']}",
                )

                if is_selected:
                    selected_large.append(category["name"])

        # 선택된 대분류에 대한 중분류 선택
        st.session_state.selected_large_categories = selected_large

        selected_middle_all = {}

        if selected_large:
            st.markdown("#### 🎯 세부 카테고리")
            st.caption("선택한 음식 종류의 세부 카테고리를 추가로 선택할 수 있습니다")

            for large_cat in selected_large:
                middle_categories = self.category_manager.get_middle_categories(
                    large_cat
                )

                if middle_categories:
                    with st.expander(f"📂 {large_cat} 세부 카테고리", expanded=False):
                        selected_middle = []

                        # 중분류도 3열로 구성
                        middle_cols = st.columns(3)
                        for j, middle_cat in enumerate(middle_categories):
                            col_idx = j % 3
                            with middle_cols[col_idx]:
                                display_name = (
                                    self.category_manager.get_category_display_name(
                                        middle_cat["name"], middle_cat["count"]
                                    )
                                )

                                existing_middle = st.session_state.user_profile.get(
                                    "food_preferences_middle", {}
                                )
                                default_checked = middle_cat[
                                    "name"
                                ] in existing_middle.get(large_cat, [])

                                is_selected = st.checkbox(
                                    display_name,
                                    value=default_checked,
                                    key=f"middle_cat_{large_cat}_{middle_cat['name']}",
                                )

                                if is_selected:
                                    selected_middle.append(middle_cat["name"])

                        if selected_middle:
                            selected_middle_all[large_cat] = selected_middle

        # 프로필에 저장
        st.session_state.user_profile["food_preferences_large"] = selected_large
        st.session_state.user_profile["food_preferences_middle"] = selected_middle_all

        # 기존 food_preferences도 유지 (하위 호환성)
        st.session_state.user_profile["food_preferences"] = selected_large

        # 다음 단계 버튼
        self._render_navigation_buttons(2, 4)

    def _render_restaurant_rating_step(self):
        """음식점 평가 단계"""
        st.markdown("# ⭐ 음식점을 평가해주세요")

        # 선호 카테고리 정보 가져오기
        preferred_categories = st.session_state.user_profile.get(
            "food_preferences_large", []
        )

        if preferred_categories:
            st.markdown(f"""
            설정하신 지역 **'{st.session_state.user_profile.get("location", "")}'** 주변의 음식점들입니다.  
            선호하신 **{', '.join(preferred_categories)}** 카테고리를 우선으로 보여드려요. 📍  
            경험해보신 곳이 있다면 1-5점으로 평가해주세요. (최소 {self.min_ratings_required}개 평가 필요)
            """)
        else:
            st.markdown(f"""
            설정하신 지역 **'{st.session_state.user_profile.get("location", "")}'** 주변의 인기 음식점들입니다.  
            경험해보신 곳이 있다면 1-5점으로 평가해주세요. (최소 {self.min_ratings_required}개 평가 필요)
            """)

        # 페이징 상태 초기화
        if "restaurants_offset" not in st.session_state:
            st.session_state.restaurants_offset = 0
        if "loaded_restaurants" not in st.session_state:
            st.session_state.loaded_restaurants = []

        # 위치 기반 음식점 데이터 가져오기 (선호 카테고리 우선)
        location = st.session_state.user_profile.get("location", "")

        # 첫 로드이거나 새로고침 시 초기 데이터 로드
        if not st.session_state.loaded_restaurants:
            if preferred_categories:
                new_restaurants = (
                    self.onboarding_manager.get_restaurants_by_preferred_categories(
                        location, preferred_categories, offset=0, limit=10
                    )
                )
            else:
                new_restaurants = (
                    self.onboarding_manager.get_popular_restaurants_by_location(
                        location, limit=10
                    )
                )
            st.session_state.loaded_restaurants = new_restaurants
            st.session_state.restaurants_offset = len(new_restaurants)

        sample_restaurants = st.session_state.loaded_restaurants
        rated_count = 0

        for i, restaurant in enumerate(sample_restaurants):
            # 선호 카테고리인지 표시
            is_preferred = restaurant.get("is_preferred", False)
            category_badge = (
                f"💖 {restaurant['category']}"
                if is_preferred
                else f"🏷️ {restaurant['category']}"
            )

            with st.expander(f"🍽️ {restaurant['name']} - {category_badge}"):
                col1, col2 = st.columns([1, 2])

                with col1:
                    # 실제 이미지 URL 사용
                    st.image(
                        restaurant.get(
                            "image_url",
                            "https://via.placeholder.com/200x150/FF6B6B/FFFFFF?text=Restaurant",
                        ),
                        width=200,
                    )

                with col2:
                    st.markdown(f"[{restaurant['name']}](https://place.map.kakao.com/{restaurant['id']})")
                    if is_preferred:
                        st.markdown("💖 **선호 카테고리**")
                    st.markdown(f"📍 {restaurant['address']}")
                    st.markdown(f"{category_badge}")
                    st.markdown(
                        f"⭐ 평점: {restaurant['rating']} ({restaurant['review_count']}개 리뷰)"
                    )
                    if restaurant.get("distance"):
                        st.markdown(f"🚶‍♂️ 거리: {restaurant['distance']}km")

                    # 평가 슬라이더
                    rating_key = f"rating_{restaurant['id']}"
                    # 인덱스를 포함하여 키를 더 고유하게 만듦
                    unique_rating_key = f"slider_{rating_key}_{i}"

                    rating = st.select_slider(
                        f"{restaurant['name']} 평가",
                        options=[0, 1, 2, 3, 4, 5],
                        format_func=lambda x: "평가 안함"
                        if x == 0
                        else f"{x}점",
                        value=st.session_state.restaurant_ratings.get(rating_key, 0),
                        key=unique_rating_key,
                    )

                    st.session_state.restaurant_ratings[rating_key] = rating

                    if rating > 0:
                        rated_count += 1

                        # 높은 점수를 준 음식점의 유사 음식점 표시
                        if rating >= 4:
                            st.success(
                                f"👍 {rating}점! 비슷한 음식점도 함께 평가해보세요:"
                            )
                            similar_restaurants = (
                                self.onboarding_manager.get_similar_restaurants(
                                    restaurant["id"]
                                )
                            )

                            for idx, similar in enumerate(similar_restaurants):
                                similar_key = f"rating_similar_{similar['id']}"
                                # 부모 음식점 ID를 포함하여 키를 더 고유하게 만듦
                                unique_slider_key = (
                                    f"slider_{similar_key}_{restaurant['id']}_{idx}"
                                )
                                similar_rating = st.select_slider(
                                    f"🔗 {similar['name']} (유사 음식점)",
                                    options=[0, 1, 2, 3, 4, 5],
                                    format_func=lambda x: "평가 안함"
                                    if x == 0
                                    else f"{x}점",
                                    value=st.session_state.restaurant_ratings.get(
                                        similar_key, 0
                                    ),
                                    key=unique_slider_key,
                                )
                                st.session_state.restaurant_ratings[similar_key] = (
                                    similar_rating
                                )

                                if similar_rating > 0:
                                    rated_count += 1

        # 더 많은 음식점 불러오기 버튼
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            total_count = self.onboarding_manager.get_total_restaurants_count(
                location, preferred_categories
            )
            current_count = len(st.session_state.loaded_restaurants)

            if current_count < total_count:
                if st.button(
                    f"🔍 더 많은 음식점 보기 ({current_count}/{total_count})",
                    use_container_width=True,
                    type="secondary",
                ):
                    # 추가 음식점 로드
                    if preferred_categories:
                        new_restaurants = self.onboarding_manager.get_restaurants_by_preferred_categories(
                            location,
                            preferred_categories,
                            offset=st.session_state.restaurants_offset,
                            limit=10,
                        )
                    else:
                        new_restaurants = (
                            self.onboarding_manager.get_popular_restaurants_by_location(
                                location, limit=10
                            )
                        )

                    if new_restaurants:
                        st.session_state.loaded_restaurants.extend(new_restaurants)
                        st.session_state.restaurants_offset += len(new_restaurants)
                        st.rerun()
                    else:
                        st.info("더 이상 불러올 음식점이 없습니다.")
            else:
                st.info(f"모든 음식점을 표시했습니다 ({current_count}개)")

        st.markdown("---")

        # 진행 상황 표시
        if rated_count >= self.min_ratings_required:
            st.success(
                f"✅ {rated_count}개 음식점 평가 완료! 다음 단계로 진행할 수 있습니다."
            )
        else:
            st.warning(
                f"⚠️ {rated_count}/{self.min_ratings_required}개 평가 완료. {self.min_ratings_required - rated_count}개 더 평가해주세요."
            )

        # 다음 단계 버튼
        self._render_navigation_buttons(
            3,
            5,
            next_condition=rated_count >= self.min_ratings_required,
            next_label="완료 ▶",
            disabled_label=f"{self.min_ratings_required - rated_count}개 더 평가 필요",
        )

    def _render_completion_step(self):
        """완료 단계"""
        st.markdown("# 🎉 설정이 완료되었습니다!")

        st.markdown("""
        ### 축하합니다! 이제 당신만을 위한 맞춤 추천을 받을 수 있어요.
        
        #### 📊 설정하신 정보:
        """)

        # 설정 정보 요약
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**📍 위치 정보**")
            st.write(
                f"• 주요 지역: {st.session_state.user_profile.get('location', '미설정')}"
            )

            st.markdown("**👤 기본 정보**")
            # TODO: 연령대 계산 방법 수정
            st.write(
                f"• 연령대: {2025 - st.session_state.user_profile.get('birth_year', 2000)}세"
            )
            st.write(f"• 성별: {st.session_state.user_profile.get('gender', '미설정')}")
            st.write(
                f"• 동행 스타일: {', '.join(st.session_state.user_profile.get('dining_companions', []))}"
            )

        with col2:
            st.markdown("**🌶️ 취향 정보**")
            st.write(
                f"• 매운맛 단계: {st.session_state.user_profile.get('spice_level', 0)}단"
            )
            st.write(
                f"• 평소 식사비: {st.session_state.user_profile.get('regular_budget', '미설정')}"
            )

            # 선호 음식 카테고리 표시
            large_prefs = st.session_state.user_profile.get(
                "food_preferences_large", []
            )
            middle_prefs = st.session_state.user_profile.get(
                "food_preferences_middle", {}
            )

            if large_prefs:
                st.write(f"• 선호 음식 종류: {', '.join(large_prefs)}")

                # 세부 카테고리가 있는 경우 표시
                if middle_prefs:
                    for large_cat, middle_list in middle_prefs.items():
                        if middle_list:
                            st.write(f"  - {large_cat}: {', '.join(middle_list)}")
            else:
                st.write("• 선호 음식 종류: 미설정")

            st.markdown("**⭐ 평가 정보**")
            rated_count = sum(
                1
                for rating in st.session_state.restaurant_ratings.values()
                if rating > 0
            )
            st.write(f"• 평가한 음식점: {rated_count}개")

            # 데이터 저장
        if st.button("🚀 What2Eat 시작하기!", use_container_width=True, type="primary"):
            # 데이터 유효성 검사
            errors = self.onboarding_manager.validate_onboarding_data(
                st.session_state.user_profile, st.session_state.restaurant_ratings
            )

            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
                return

            # 데이터 저장
            if self.onboarding_manager.save_user_profile(
                st.session_state.user_profile, st.session_state.restaurant_ratings
            ):
                st.success("✅ 설정이 저장되었습니다!")

                # 온보딩 완료 로그 기록
                self._log_onboarding_completion()

                # 추천 미리보기 표시
                st.markdown("### 🎯 당신을 위한 추천 미리보기")
                preview_recommendations = (
                    self.onboarding_manager.get_recommendation_preview(
                        st.session_state.user_profile,
                        st.session_state.restaurant_ratings,
                    )
                )

                for rec in preview_recommendations:
                    st.info(
                        f"🍽️ **{rec['name']}** ({rec['category']}) - {rec['reason']}"
                    )

                # 메인 앱으로 이동 (5초 후 자동 이동)
                st.balloons()
                st.success("5초 후 메인 페이지로 이동합니다...")

                # JavaScript로 페이지 리디렉트 (임시 방법)
                st.markdown(
                    """
                <script>
                setTimeout(function() {
                    window.location.reload();
                }, 5000);
                </script>
                """,
                    unsafe_allow_html=True,
                )

                if st.button("지금 바로 시작하기"):
                    # 온보딩 완료 플래그 설정 (세션 클리어 전에 설정)
                    onboarding_completed = True
                    st.session_state.clear()  # 온보딩 상태 초기화
                    st.session_state.onboarding_just_completed = onboarding_completed  # 플래그 복원
                    st.rerun()
            else:
                st.error("❌ 저장 중 오류가 발생했습니다. 다시 시도해주세요.")

    def _log_onboarding_completion(self):
        """온보딩 완료 로그 기록"""
        if self.logger.is_available():
            user_info = get_current_user()
            if user_info:
                uid = user_info.get("localId")
                self.logger.log_user_activity(
                    uid,
                    "onboarding_completed",
                    {"profile_data": st.session_state.user_profile},
                )
