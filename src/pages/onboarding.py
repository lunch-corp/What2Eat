# pages/onboarding.py

import asyncio

import requests
import streamlit as st

from utils.api import APIRequester
from utils.api_client import get_yamyam_ops_client
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
        self.api_requester = APIRequester(endpoint=st.secrets["API_URL"])

        # 온보딩 단계 초기화
        if "onboarding_step" not in st.session_state:
            st.session_state.onboarding_step = 0

        # 사용자 데이터 초기화
        if "user_profile" not in st.session_state:
            st.session_state.user_profile = {}

        if "restaurant_ratings" not in st.session_state:
            st.session_state.restaurant_ratings = {}

    def _handle_feedback(self, rating_key, feedback_value, current_rating=0):
        """
        피드백을 처리하고 저장하는 helper 메서드

        Args:
            rating_key: 세션 상태에서 사용할 평가 키
            feedback_value: st.feedback()에서 반환된 값 (0-4)
            current_rating: 현재 저장된 평가값

        Returns:
            bool: 평가가 업데이트되었는지 여부
        """
        if feedback_value is not None:
            # st.feedback은 0-indexed (0-4)를 반환하므로 1을 더해서 1-5로 변환
            feedback_value = feedback_value + 1

            # 현재 평점 여부에 따라 다른 메시지 표시
            if current_rating == 0:
                st.success(f"✅ {feedback_value}점을 주셨습니다!")
            else:
                st.success(f"✅ 평가를 {feedback_value}점으로 수정하셨습니다!")

            # 세션 상태에 저장
            st.session_state.restaurant_ratings[rating_key] = feedback_value
            return True
        return False


    @st.dialog("🔍 음식점 검색")
    def search_restaurant_dialog(self):
        """음식점 검색 다이얼로그"""
        st.subheader("🔍 음식점 검색")

        # 검색 입력
        query = st.text_input(
            "🔍 음식점 이름을 입력하세요",
            placeholder="예: 남춘천닭갈비, 스시로, 피자헛, 떡볶이...",
            help="정확한 매칭, 부분 매칭, 자모 매칭을 지원합니다.",
            key="onboarding_search_input",
        )

        # 검색 결과 표시
        if query and len(query) >= 2:
            # API 클라이언트를 사용하여 검색
            client = get_yamyam_ops_client()
            if not client:
                st.error("❌ API 클라이언트를 초기화할 수 없습니다.")
                return

            # 사용자 위치 정보 가져오기
            user_lat = st.session_state.get("user_lat")
            user_lon = st.session_state.get("user_lon")
            radius_km = None  # 검색 반경은 제한하지 않음 (전체 검색)

            # 비동기 함수를 동기적으로 실행
            with st.spinner("🔍 검색 중..."):
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    results = loop.run_until_complete(
                        client.search_restaurants(
                            query=query,
                            limit=10,
                            user_lat=user_lat,
                            user_lon=user_lon,
                            radius_km=radius_km,
                        )
                    )
                    loop.close()
                except Exception as e:
                    st.error(f"❌ 검색 중 오류가 발생했습니다: {str(e)}")
                    return

            if not results:
                st.warning("검색 결과가 없습니다.")
            else:
                st.success(f"✅ 검색 완료! {len(results)}개 결과를 찾았습니다.")

                # 검색 결과 표시 및 평가
                for i, result in enumerate(results, 1):
                    diner_name = result.get("diner_name", "")
                    diner_idx = result.get("diner_idx", "")
                    match_type = result.get("match_type", "")
                    distance = result.get("distance")
                    diner_num_address = result.get("diner_num_address")

                    with st.expander(f"🍽️ {i}. {diner_name} ({match_type})"):
                        st.markdown(
                            f"**📍 [카카오맵에서 보기](https://place.map.kakao.com/{diner_idx})**"
                        )
                        st.markdown(f"**매칭 타입:** {match_type}")

                        # 거리 정보 표시 (있는 경우)
                        if distance is not None:
                            st.markdown(f"**🚶‍♂️ 거리:** {distance:.1f}km")

                        # 주소 정보 표시 (있는 경우)
                        if diner_num_address:
                            st.markdown(f"**🏠 주소:** {diner_num_address}")

                        # 평가 섹션
                        st.markdown("---")
                        st.markdown("**⭐ 평가하기**")
                        # 평가 키 생성
                        rating_key = f"rating_search_{diner_idx}"
                        current_rating = st.session_state.restaurant_ratings.get(
                            rating_key, 0
                        )

                        # 이미 평가한 경우 수정 가능하도록 안내
                        if current_rating > 0:
                            st.success(
                                f"✅ 이미 {current_rating}점을 주셨습니다! (별점을 다시 클릭하면 수정할 수 있어요)"
                            )

                        # st.feedback 사용 (수정 가능)
                        feedback = st.feedback(
                            options="stars",
                            key=f"feedback_search_{diner_idx}_{i}",
                        )

                        # 피드백 처리 (helper 메서드 사용)
                        self._handle_feedback(rating_key, feedback, current_rating)

    def _handle_current_location(self):
        """현재 위치 찾기 helper 함수"""
        try:
            from streamlit_geolocation import streamlit_geolocation
        except ImportError:
            st.error("streamlit_geolocation 패키지가 설치되지 않았습니다.")
            return

        from utils.activity_logger import get_activity_logger
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

                # 활동 로그 기록
                try:
                    logger = get_activity_logger()
                    logger.log_location_set(
                        address=st.session_state.address,
                        lat=st.session_state.user_lat,
                        lon=st.session_state.user_lon,
                        method="geolocation",
                        page="onboarding",
                    )
                except Exception:
                    # 로깅 실패해도 계속 진행
                    pass

                st.success("✅ 위치를 찾았습니다!")
            else:
                st.error("위 버튼을 눌러 현위치를 확인해보세요.")

    def _handle_keyword_search(self, search_text):
        """키워드 검색 처리 helper 함수"""
        import requests

        from config.constants import KAKAO_API_HEADERS, KAKAO_API_URL
        from utils.activity_logger import get_activity_logger
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

                # 활동 로그 기록
                try:
                    logger = get_activity_logger()
                    logger.log_location_search(
                        query=search_text,
                        lat=lat,
                        lon=lon,
                        address=address,
                        method="search",
                        page="onboarding",
                    )
                    logger.log_location_set(
                        address=address,
                        lat=lat,
                        lon=lon,
                        method="search",
                        page="onboarding",
                    )
                except Exception:
                    # 로깅 실패해도 계속 진행
                    pass

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
                if st.session_state.onboarding_step == 3:
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

        # 디버깅 로그
        current_step = st.session_state.get("onboarding_step", 0)

        # 진행 상태 표시
        self._render_progress_bar()

        # 현재 단계에 따른 페이지 렌더링
        if st.session_state.onboarding_step == 0:
            self._render_welcome_step()
        elif st.session_state.onboarding_step == 1:
            self._render_location_step()
        elif st.session_state.onboarding_step == 2:
            self._render_simplified_preferences_step()
        elif st.session_state.onboarding_step == 3:
            self._render_restaurant_rating_step()
        elif st.session_state.onboarding_step == 4:
            self._render_completion_step()

    def _render_progress_bar(self):
        """진행 상태 바 렌더링"""
        steps = ["환영", "위치", "선호", "평가", "완료"]
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
        ### 맞춤형 음식점 추천을 위해 간단한 정보가 필요해요
        
        **넷플릭스에서 영화를, 스포티파이에서 음악을 추천받듯이**  
        What2Eat에서는 당신만의 맛집을 추천해드려요! 🍽️
        
        #### 📝 설정 과정 (약 2-3분 소요)
        1. **위치 정보** - 주로 방문하는 지역
        2. **선호 음식** - 좋아하는 음식 종류 (선택사항)
        3. **음식점 평가** - 몇 개 음식점에 대한 평가
        
        설정을 완료하면 당신만을 위한 **개인화된 맛집 추천**을 받을 수 있어요!
        """)

        if st.button("🚀 시작하기", use_container_width=True, type="primary"):
            st.session_state.onboarding_step = 1
            st.rerun()

    def _render_location_step(self):
        """위치 정보 수집 단계"""
        st.markdown("# 📍 주로 어디서 식사하시나요?")

        st.markdown("""
        방문하셨던 음식점을 조사하기 위해 주요 활동 지역을 알려주세요.
        현재 위치 또는 자주 가시는 동네(거주지, 직장 근처 등)를 입력해주시면 됩니다.
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
        self._render_navigation_buttons(1, 2)

    def _render_simplified_preferences_step(self):
        """간소화된 선호 카테고리 단계"""
        # 디버깅 로그
        
        st.markdown("# 🍽️ 어떤 음식을 좋아하시나요?")

        st.markdown("""
        좋아하는 음식 종류를 선택해주세요.  
        선택하신 카테고리를 바탕으로 맞춤 음식점을 추천해드립니다!
        """)

        # 카테고리 매니저에서 대분류 카테고리 가져오기
        large_categories = self.category_manager.get_large_categories()

        # 사용자 선택 상태 초기화
        if "selected_large_categories" not in st.session_state:
            st.session_state.selected_large_categories = []

        st.markdown("### 🏷️ 선호하는 음식 종류")
        st.caption(
            "관심 있는 음식 종류를 선택해주세요 (복수 선택 가능, 선택 안 해도 됩니다)"
        )

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
                    key=f"simple_large_cat_{category['name']}",
                )

                if is_selected:
                    selected_large.append(category["name"])

        # 프로필에 저장
        st.session_state.user_profile["food_preferences_large"] = selected_large
        st.session_state.user_profile["food_preferences"] = selected_large

        # 기본값 설정 (누락된 필드)
        if "spice_level" not in st.session_state.user_profile:
            st.session_state.user_profile["spice_level"] = 2
        if "allergies" not in st.session_state.user_profile:
            st.session_state.user_profile["allergies"] = ""
        if "dislikes" not in st.session_state.user_profile:
            st.session_state.user_profile["dislikes"] = ""
        if "food_preferences_middle" not in st.session_state.user_profile:
            st.session_state.user_profile["food_preferences_middle"] = {}

        # 디버깅 로그

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
        self._render_navigation_buttons(1, 3)

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
            선호하신 **{", ".join(preferred_categories)}** 카테고리를 우선으로 보여드려요. 📍  
            경험해보신 곳이 있다면 1-5점으로 평가해주세요. (최소 {self.min_ratings_required}개 평가 필요)
            """)
        else:
            st.markdown(f"""
            설정하신 지역 **'{st.session_state.user_profile.get("location", "")}'** 주변의 인기 음식점들입니다.  
            경험해보신 곳이 있다면 1-5점으로 평가해주세요. (최소 {self.min_ratings_required}개 평가 필요)
            """)

        # 검색 기능 추가
        st.markdown("### 🔍 원하는 음식점을 검색해서 평가하기")

        # 검색 안내 메시지
        st.info("""
        💡 **검색 팁!**
        - 현재 목록은 설정한 위치 주변의 음식점들만 보여드려요
        - 검색을 통해 **원하는 음식점**을 찾아서 평가할 수 있어요 🎯
        """)

        # 검색 버튼을 더 눈에 띄게 배치
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(
                "🔍 음식점 검색하기", type="primary", use_container_width=True
            ):
                self.search_restaurant_dialog()

        st.markdown("---")

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
                f"{restaurant['category']}"
                if is_preferred
                else f"🏷️ {restaurant['category']}"
            )

            with st.expander(f"🍽️ {restaurant['name']} - {category_badge}"):
                # 이미지 제거하고 정보만 표시
                st.markdown(
                    f"[{restaurant['name']}](https://place.map.kakao.com/{restaurant['id']})"
                )
                if is_preferred:
                    st.markdown("**선호 카테고리**")
                st.markdown(f"📍 {restaurant['address']}")
                st.markdown(f"{category_badge}")
                # st.markdown(
                #     f"⭐ 평점: {restaurant['rating']} ({restaurant['review_count']}개 리뷰)"
                # )
                if restaurant.get("distance"):
                    st.markdown(f"🚶‍♂️ 거리: {restaurant['distance']}km")

                # 평가 (st.feedback 사용)
                rating_key = f"{restaurant['id']}"
                current_rating = st.session_state.restaurant_ratings.get(rating_key, 0)

                # 이미 평가한 경우 수정 가능하도록 안내
                if current_rating > 0:
                    st.success(f"✅ {current_rating}점을 주셨습니다!")
                    rated_count += 1

                # st.feedback 사용 (수정 가능)
                feedback = st.feedback(
                    options="stars",
                    key=f"feedback_{restaurant['id']}_{i}",
                )

                # 피드백 처리 (helper 메서드 사용)
                if feedback is not None:
                    # 평가가 업데이트되었는지 확인
                    was_new = current_rating == 0
                    self._handle_feedback(rating_key, feedback, current_rating)

                    if was_new:
                        rated_count += 1

                    # 높은 점수를 준 음식점의 유사 음식점 표시
                    current_rating = st.session_state.restaurant_ratings.get(
                        rating_key, 0
                    )
                    if current_rating >= 4:
                        st.success(
                            f"👍 {current_rating}점! 비슷한 음식점도 함께 평가해보세요:"
                        )
                        similar_restaurants = (
                            self.onboarding_manager.get_similar_restaurants(
                                restaurant["id"],
                                limit=3,
                                use_item_cf=True
                            )
                        )
                        for idx, similar in enumerate(similar_restaurants):
                            # 유사 음식점 정보 표시
                            with st.expander(
                                f"🔗 {similar['name']}",
                                expanded=False,
                            ):



                                st.markdown(f"**{similar['name']}**")
                                st.markdown(f"🏷️ {similar['category']}")
                                if similar.get("distance"):
                                    st.markdown(
                                        f"🚶‍♂️ 거리: {similar['distance']}km"
                                    )
                                if similar.get("rating"):
                                    st.markdown(f"⭐ 평점: {similar['rating']}")

                                # 평가 키 생성
                                similar_key = f"rating_similar_{similar['id']}"

                                # 현재 평가 상태 표시
                                current_similar_rating = (
                                    st.session_state.restaurant_ratings.get(
                                        similar_key, 0
                                    )
                                )
                                if current_similar_rating > 0:
                                    st.success(
                                        f"✅ 이미 {current_similar_rating}점을 주셨습니다!"
                                    )
                                    rated_count += 1

                                # st.feedback 사용
                                similar_feedback = st.feedback(
                                    options="stars",
                                    key=f"feedback_similar_{similar['id']}_{restaurant['id']}_{idx}",
                                )

                                # 피드백 처리 (helper 메서드 사용)
                                if similar_feedback is not None:
                                    was_new_similar = current_similar_rating == 0
                                    self._handle_feedback(
                                        similar_key,
                                        similar_feedback,
                                        current_similar_rating,
                                    )

                                    if was_new_similar:
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

        # 진행 상황 표시 (모든 평가 유형 포함) - 성능 최적화
        if "total_rated_count" not in st.session_state:
            st.session_state.total_rated_count = 0

        # 평가 개수 계산 (캐시된 값 사용)
        current_total = sum(
            1 for rating in st.session_state.restaurant_ratings.values() if rating > 0
        )

        # 변경사항이 있을 때만 업데이트
        if current_total != st.session_state.total_rated_count:
            st.session_state.total_rated_count = current_total

        if st.session_state.total_rated_count >= self.min_ratings_required:
            st.success(
                f"✅ {st.session_state.total_rated_count}개 음식점 평가 완료! 다음 단계로 진행할 수 있습니다."
            )
        else:
            st.warning(
                f"⚠️ {st.session_state.total_rated_count}/{self.min_ratings_required}개 평가 완료. {self.min_ratings_required - st.session_state.total_rated_count}개 더 평가해주세요."
            )

        # 다음 단계 버튼
        self._render_navigation_buttons(
            prev_step=2,
            next_step=4,
            next_condition=st.session_state.total_rated_count
            >= self.min_ratings_required,
            next_label="완료 ▶",
            disabled_label=f"{self.min_ratings_required - st.session_state.total_rated_count}개 더 평가 필요",
        )

    def _render_completion_step(self):
        """완료 단계"""
        st.markdown("# 🎉 설정이 완료되었습니다!")

        st.markdown("""
        ### 축하합니다! 이제 당신만을 위한 맞춤 추천을 받을 수 있어요.
        
        #### 📊 설정하신 정보:
        """)

        # 설정 정보 요약
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**📍 위치 정보**")
            st.write(
                f"• 주요 지역: {st.session_state.user_profile.get('location', '미설정')}"
            )
        
        with col2:
            st.markdown("**🍙 취향 정보**")
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
        
        with col3:
            st.markdown("**⭐ 평가 정보**")
            rated_count = sum(
                1
                for rating in st.session_state.restaurant_ratings.values()
                if rating > 0
            )
            st.write(f"• 평가한 음식점: {rated_count}개")
            for key, rating in st.session_state.restaurant_ratings.items():
                diner_id = key.split("_")[-1]
                diner_name = self._get_diner_name(diner_id)
                st.write(f"• {diner_name} 식당에 {rating}점을 주셨어요.")

        # 평가 유형별 통계 (캐시된 값 사용)
        if "rating_stats" not in st.session_state:
            st.session_state.rating_stats = {"regular": 0, "search": 0, "similar": 0}

        # 평가 통계 계산 (변경사항이 있을 때만)
        current_stats = {
            "regular": sum(
                1
                for key, rating in st.session_state.restaurant_ratings.items()
                if rating > 0
                and not key.startswith("rating_search_")
                and not key.startswith("rating_similar_")
            ),
            "search": sum(
                1
                for key, rating in st.session_state.restaurant_ratings.items()
                if rating > 0 and key.startswith("rating_search_")
            ),
            "similar": sum(
                1
                for key, rating in st.session_state.restaurant_ratings.items()
                if rating > 0 and key.startswith("rating_similar_")
            ),
        }

        # 변경사항이 있을 때만 업데이트
        if current_stats != st.session_state.rating_stats:
            st.session_state.rating_stats = current_stats

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

            # 누락된 필드에 기본값 설정
            if "birth_year" not in st.session_state.user_profile:
                st.session_state.user_profile["birth_year"] = None
            if "gender" not in st.session_state.user_profile:
                st.session_state.user_profile["gender"] = "선택 안함"
            if "dining_companions" not in st.session_state.user_profile:
                st.session_state.user_profile["dining_companions"] = []
            if "regular_budget" not in st.session_state.user_profile:
                st.session_state.user_profile["regular_budget"] = None
            if "special_budget" not in st.session_state.user_profile:
                st.session_state.user_profile["special_budget"] = None
            if "spice_level" not in st.session_state.user_profile:
                st.session_state.user_profile["spice_level"] = 2
            if "allergies" not in st.session_state.user_profile:
                st.session_state.user_profile["allergies"] = ""
            if "dislikes" not in st.session_state.user_profile:
                st.session_state.user_profile["dislikes"] = ""
            if "food_preferences_middle" not in st.session_state.user_profile:
                st.session_state.user_profile["food_preferences_middle"] = {}

            # 데이터 저장
            if self.onboarding_manager.save_user_profile(
                st.session_state.user_profile, st.session_state.restaurant_ratings
            ):
                # st.success("✅ 설정이 저장되었습니다!")

                # 온보딩 완료 로그 기록
                self._log_onboarding_completion()

                # PostgreSQL에 온보딩 데이터 저장
                try:
                    import asyncio

                    from utils.api_client import get_yamyam_ops_client

                    client = get_yamyam_ops_client()
                    if client:
                        # 비동기 함수를 동기적으로 실행
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        success = loop.run_until_complete(
                            client.save_onboarding_data(
                                st.session_state.user_profile,
                                st.session_state.restaurant_ratings,
                            )
                        )
                        loop.close()

                        if success:
                            # 온보딩 완료 후 사용자 정보 캐시 삭제 (최신 정보로 갱신)
                            from utils.auth import clear_user_info_cache

                            clear_user_info_cache()
                        else:
                            st.warning(
                                "⚠️ 온보딩 데이터 저장에 실패했습니다. Firestore에는 저장되었습니다."
                            )
                    else:
                        st.warning("⚠️ API 클라이언트를 초기화할 수 없습니다.")
                except Exception as sync_error:
                    # 동기화 실패해도 Firestore에는 저장되었으므로 계속 진행
                    st.warning(f"⚠️ PostgreSQL 저장 중 오류: {str(sync_error)}")
                    # st.info("Firestore에는 정상적으로 저장되었습니다.")

                # /rec/user/similar API 호출 (진행 상황 표시)
                with st.spinner("🔄 유사한 사용자 찾는 중... (최대 5분 소요)", show_time=True):
                    try:
                        # get most similar kakao_reviewer_id using /rec/user/similar
                        request_body = {
                            "liked_diner_ids": [
                                int(diner_id.split("_")[-1])
                                for diner_id in st.session_state.restaurant_ratings.keys()
                            ],
                            "scores_of_liked_diner_ids": [
                                score
                                for score in st.session_state.restaurant_ratings.values()
                            ],
                        }

                        response = self.api_requester.post(
                            api_path="/rec/user/similar",
                            data=request_body,
                            timeout=310,  # 5분 타임아웃
                        ).json()

                        # update matched kakao_reviewer_id into db
                        kakao_reviewer_id = response["reviewer_id"]
                        firebase_uid = get_current_user()["localId"]
                        self.api_requester.put(
                            api_path=f"/users/{firebase_uid}",
                            data={"kakao_reviewer_id": str(kakao_reviewer_id)},
                            params={"user_id_type": "firebase_uid"},
                        )
                        st.success("✅ 유사 사용자 매칭이 완료되었습니다!")
                    except requests.exceptions.Timeout:
                        st.warning(
                            "⚠️ 유사 사용자 매칭이 시간 초과되었습니다. (5분 초과)"
                        )
                        st.info(
                            "배치 프로그램으로 추후 완료됩니다. 개인화 추천은 아직 이용할 수 없지만, 다른 맛집 추천은 가능합니다."
                        )
                    except Exception as api_error:
                        st.warning(
                            f"⚠️ 유사 사용자 매칭 중 오류가 발생했습니다: {str(api_error)}"
                        )
                        st.info(
                            "배치 프로그램으로 추후 완료됩니다. 개인화 추천은 아직 이용할 수 없지만, 다른 맛집 추천은 가능합니다."
                        )

                # 온보딩 완료 플래그 설정 및 페이지 이동
                st.balloons()
                st.success("🎉 온보딩이 완료되었습니다! 잠시 후 메인 페이지로 이동합니다...")

                # 온보딩 완료 플래그 설정 (세션 클리어 전에 설정)
                onboarding_completed = True
                
                # 온보딩 관련 세션 상태만 초기화 (필요한 정보는 유지)
                onboarding_keys = [
                    "onboarding_step",
                    "user_profile",
                    "restaurant_ratings",
                    "loaded_restaurants",
                    "restaurants_offset",
                    "total_rated_count",
                    "rating_stats",
                ]
                for key in onboarding_keys:
                    if key in st.session_state:
                        del st.session_state[key]

                # 온보딩 완료 플래그 설정
                st.session_state.onboarding_just_completed = onboarding_completed

                # 페이지 리디렉트를 위해 rerun
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
    
    def _get_diner_name(self, diner_id: str) -> str:
        # call GET /kakao/diners/{diner_id} API
        response = self.api_requester.get(api_path=f"/kakao/diners/{diner_id}").json()
        return response["diner_name"]