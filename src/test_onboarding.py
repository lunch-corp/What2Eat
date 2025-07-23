# test_onboarding.py
"""
온보딩 시스템 테스트용 페이지
"""

import streamlit as st


from utils.auth import get_current_user, has_completed_onboarding, is_first_login

from utils.auth import get_current_user, has_completed_onboarding, is_first_login


def main():
    st.set_page_config(page_title="온보딩 테스트", page_icon="🧪", layout="wide")

    st.title("🧪 온보딩 시스템 테스트")

    # 현재 사용자 정보 표시
    user_info = get_current_user()
    if user_info:
        st.success(f"✅ 로그인된 사용자: {user_info.get('email', '알 수 없음')}")

        # 온보딩 상태 확인
        col1, col2 = st.columns(2)

        with col1:
            if is_first_login():
                st.info("🆕 첫 로그인 사용자입니다")
            else:
                st.info("👋 재방문 사용자입니다")

        with col2:
            if has_completed_onboarding():
                st.success("✅ 온보딩 완료됨")
            else:
                st.warning("⚠️ 온보딩 필요")

        # 테스트 버튼들
        st.markdown("---")
        st.subheader("🔧 테스트 옵션")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("온보딩 시작", use_container_width=True):
                # 온보딩 상태 초기화
                for key in list(st.session_state.keys()):
                    if (
                        key.startswith("onboarding")
                        or key.startswith("user_profile")
                        or key.startswith("restaurant")
                    ):
                        del st.session_state[key]

                st.session_state.force_onboarding = True
                st.rerun()

        with col2:
            if st.button("세션 초기화", use_container_width=True):
                st.session_state.clear()
                st.success("세션이 초기화되었습니다.")
                st.rerun()

        with col3:
            if st.button("상태 새로고침", use_container_width=True):
                st.rerun()

        # 강제 온보딩 또는 조건에 맞는 경우 온보딩 페이지 표시
        if st.session_state.get("force_onboarding", False) or (
            is_first_login() and not has_completed_onboarding()
        ):
            st.markdown("---")
            st.info("온보딩 페이지를 표시합니다...")

            onboarding_page = OnboardingPage()
            onboarding_page.render()
        else:
            st.markdown("---")
            st.markdown("### 📊 현재 세션 상태")

            # 세션 상태 표시
            if st.session_state:
                with st.expander("세션 상태 보기"):
                    for key, value in st.session_state.items():
                        st.write(f"**{key}**: {value}")
            else:
                st.info("세션 상태가 비어있습니다.")

    else:
        st.error("❌ 로그인이 필요합니다.")
        st.info("메인 앱에서 로그인 후 다시 시도해주세요.")


if __name__ == "__main__":
    main()
