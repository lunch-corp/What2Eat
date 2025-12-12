# utils/auth.py
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import extra_streamlit_components as stx
import streamlit as st

from utils.language import get_text

from .api import API, AdminUser


class AuthManager:
    def __init__(self, api: API):
        self.api = api
        self.cookie_manager = stx.CookieManager()
        self.cookie_key = "auth_token"

    def init_session_state(self):
        """세션 상태 초기화 및 쿠키에서 인증 상태 복원"""
        # 세션 상태 초기화
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False
        if "token" not in st.session_state:
            st.session_state.token = None
        if "user" not in st.session_state:
            st.session_state.user = None
        if "user_info" not in st.session_state:
            st.session_state.user_info = []

        # 이미 로그인된 경우 토큰 유효성 검증
        if st.session_state.logged_in and st.session_state.token:
            try:
                token_data = self.api.verify_token()
                if not token_data:
                    self.clear_auth_state()
            except Exception:
                self.clear_auth_state()
            return

        # 로그인된 상태가 아닐 때만 쿠키 복원 시도
        if not st.session_state.logged_in:
            # 쿠키에서 토큰 복원
            token = self.cookie_manager.get(self.cookie_key)
            if token:
                try:
                    self.api.set_token(token)
                    token_data = self.api.verify_token()

                    if token_data:
                        st.session_state.token = token
                        st.session_state.logged_in = True
                        st.session_state.user = AdminUser(**token_data)
                        st.session_state.last_login = datetime.now(
                            ZoneInfo("Asia/Tokyo")
                        ).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        # 토큰이 유효하지 않을 경우
                        self.clear_auth_state()
                except Exception:
                    # 예외 발생 시 인증 상태 초기화
                    self.clear_auth_state()

    def clear_auth_state(self):
        """인증 관련 세션 상태와 쿠키 초기화"""
        # 쿠키 삭제
        try:
            if self.cookie_manager.get(self.cookie_key):
                self.cookie_manager.delete(self.cookie_key)
        except Exception:
            pass

        # 세션 상태 초기화
        st.session_state.logged_in = False
        st.session_state.token = None
        st.session_state.user = None
        st.session_state.user_info = []

    def check_authentication(self) -> bool:
        """세션의 인증 상태를 확인하고 필요한 경우 토큰을 갱신"""
        if not st.session_state.logged_in or not st.session_state.token:
            return False

        try:
            # 토큰 유효성 검증
            token_data = self.api.verify_token()
            if not token_data:
                # 토큰이 만료되었거나 유효하지 않은 경우 갱신 시도
                refresh_response = asyncio.run(self.api.refresh_token())
                self.api.set_token(refresh_response.get("access_token"))
                st.session_state.token = refresh_response.get("access_token")

            return True
        except Exception:
            # 토큰 갱신 실패 시 로그아웃 처리
            self.logout()
            return False

    def login(self, username: str, password: str) -> bool:
        """사용자 로그인을 처리"""
        try:
            # asyncio.run()을 사용하여 코루틴 실행
            login_response = asyncio.run(self.api.login(username, password))

            # 연결 오류인 경우
            if login_response.get("status") == 500 and "error" in login_response:
                error_msg = login_response.get("error", "")
                if "Connection refused" in error_msg:
                    raise ValueError(
                        "API 서버 연결 오류. 서버가 실행 중인지 확인하세요."
                    )
                else:
                    raise ValueError(login_response.get("message", "로그인 실패"))

            if login_response.get("status") == 401:
                raise ValueError(get_text("id_double_check"))
            elif login_response.get("status") == 402:
                raise ValueError(get_text("pw_double_check"))
            elif login_response.get("status") == 403:
                raise ValueError(get_text("active_double_check"))
            elif login_response.get("status") != 200:
                print("login_response", login_response)
                raise ValueError(login_response.get("message", "로그인 실패"))

            access_token = login_response.get("access_token")

            if not access_token:
                raise ValueError("토큰 발급 실패. 서버 응답을 확인하세요.")

            self.api.set_token(access_token)
            decoded_token = AdminUser(**self.api.verify_token())

            # 관리자 권한 체크를 먼저 수행
            if not decoded_token.is_admin:
                raise ValueError(get_text("not_admin_account"))

            # 관리자 권한이 있을 경우에만 사용자 정보 조회 진행
            user_response = asyncio.run(self.api.get_users())

            if not user_response:
                raise ValueError(get_text("user_info_fetch_failed"))

            # 세션 상태 업데이트
            st.session_state.logged_in = True
            st.session_state.token = access_token
            st.session_state.user = decoded_token
            st.session_state.user_info = user_response
            st.session_state.last_login = datetime.now(ZoneInfo("Asia/Tokyo")).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            return True

        except ValueError as e:
            st.error(str(e))
            return False
        except Exception as e:
            st.error(f"로그인 중 오류가 발생했습니다: {str(e)}")
            return False

    def logout(self):
        """사용자 로그아웃을 처리"""
        try:
            if st.session_state.token:
                asyncio.run(self.api.logout())
        except Exception:
            pass
        finally:
            # 새로 추가한 clear_auth_state 메서드 활용
            self.clear_auth_state()

    # def require_auth(self, page_func):
    #     """인증이 필요한 페이지를 위한 데코레이터"""
    #     def wrapper(*args, **kwargs):
    #         self.init_session_state()

    #         if not self.check_authentication():
    #             st.warning("로그인이 필요합니다.")
    #             st.switch_page("app.py")  # app.py로 리다이렉트
    #             return

    #         return page_func(*args, **kwargs)
    #     return wrapper
