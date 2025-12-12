from datetime import datetime, timedelta
from typing import Any, Optional

import extra_streamlit_components as stx
import streamlit as st
from firebase_admin import auth

from utils.firebase_logger import get_firebase_logger


class SessionManager:
    """로그인 세션 관리 클래스"""

    def __init__(self):
        self.logger = get_firebase_logger()
        # CookieManager 초기화
        # CookieManager는 Streamlit 컴포넌트이므로 페이지에 렌더링되어야 작동함
        # get_all() 또는 set() 호출 시 자동으로 렌더링됨
        self.cookie_manager = stx.CookieManager()
        self.cookie_key = "auth_token"
        self.refresh_cookie_key = "refresh_token"
        self.jwt_access_cookie_key = "jwt_access_token"
        self.jwt_refresh_cookie_key = "jwt_refresh_token"
        self._initialize_session_state()

    def _initialize_session_state(self):
        """세션 상태 초기화"""
        if "user_info" not in st.session_state:
            st.session_state.user_info = None
        if "is_authenticated" not in st.session_state:
            st.session_state.is_authenticated = False
        if "auth_token" not in st.session_state:
            st.session_state.auth_token = None
        if "token_expires_at" not in st.session_state:
            st.session_state.token_expires_at = None
        if "refresh_token" not in st.session_state:
            st.session_state.refresh_token = None
        if "jwt_access_token" not in st.session_state:
            st.session_state.jwt_access_token = None
        if "jwt_refresh_token" not in st.session_state:
            st.session_state.jwt_refresh_token = None
        if "jwt_expires_at" not in st.session_state:
            st.session_state.jwt_expires_at = None
        if "cookie_set_counter" not in st.session_state:
            st.session_state.cookie_set_counter = 0

    def save_user_session(
        self,
        user_data: dict[str, Any],
        id_token: str,
        refresh_token: str = None,
        jwt_access_token: str = None,
        jwt_refresh_token: str = None,
        jwt_expires_in: int = None,
    ):
        """사용자 세션 정보 저장"""
        try:
            # Firebase 토큰 만료 시간 설정 (1시간)
            expires_at = datetime.now() + timedelta(hours=1)

            # 세션 상태에 저장
            st.session_state.user_info = user_data
            st.session_state.is_authenticated = True
            st.session_state.auth_token = id_token
            st.session_state.token_expires_at = expires_at
            st.session_state.refresh_token = refresh_token

            # JWT 토큰 저장
            if jwt_access_token:
                st.session_state.jwt_access_token = jwt_access_token
            if jwt_refresh_token:
                st.session_state.jwt_refresh_token = jwt_refresh_token
            if jwt_expires_in:
                # JWT 만료 시간 설정 (expires_in은 초 단위)
                st.session_state.jwt_expires_at = datetime.now() + timedelta(
                    seconds=jwt_expires_in
                )

            # 쿠키에도 저장 (새로고침 시 세션 복원용)
            try:
                # 각 set() 호출에 고유한 key 제공 (Streamlit 컴포넌트 요구사항)
                # 타임스탬프와 랜덤 값을 사용하여 고유성 보장
                import random
                import time

                if "cookie_set_counter" not in st.session_state:
                    st.session_state.cookie_set_counter = 0

                # Firebase 토큰을 쿠키에 저장 (30일 유효)
                st.session_state.cookie_set_counter += 1
                unique_key_1 = f"cookie_set_{self.cookie_key}_{st.session_state.cookie_set_counter}_{time.time()}_{random.randint(1000, 9999)}"
                try:
                    self.cookie_manager.set(
                        self.cookie_key,
                        id_token,
                        expires_at=datetime.now() + timedelta(days=30),
                        key=unique_key_1,
                    )
                except Exception as e:
                    st.warning(f"Firebase 토큰 쿠키 저장 실패: {str(e)}")
                    if self.logger.is_available():
                        self.logger.log_user_activity(
                            user_data.get("localId"),
                            "cookie_set_error",
                            {
                                "cookie_key": self.cookie_key,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )

                if refresh_token:
                    st.session_state.cookie_set_counter += 1
                    unique_key_2 = f"cookie_set_{self.refresh_cookie_key}_{st.session_state.cookie_set_counter}_{time.time()}_{random.randint(1000, 9999)}"
                    try:
                        self.cookie_manager.set(
                            self.refresh_cookie_key,
                            refresh_token,
                            expires_at=datetime.now() + timedelta(days=30),
                            key=unique_key_2,
                        )
                    except Exception as e:
                        st.warning(f"Firebase Refresh 토큰 쿠키 저장 실패: {str(e)}")

                # JWT 토큰을 쿠키에 저장 (7일 유효, JWT Refresh Token 만료 시간과 동일)
                if jwt_access_token:
                    st.session_state.cookie_set_counter += 1
                    unique_key_3 = f"cookie_set_{self.jwt_access_cookie_key}_{st.session_state.cookie_set_counter}_{time.time()}_{random.randint(1000, 9999)}"
                    try:
                        self.cookie_manager.set(
                            self.jwt_access_cookie_key,
                            jwt_access_token,
                            expires_at=datetime.now() + timedelta(days=7),
                            key=unique_key_3,
                        )
                    except Exception as e:
                        st.warning(f"JWT Access 토큰 쿠키 저장 실패: {str(e)}")

                if jwt_refresh_token:
                    st.session_state.cookie_set_counter += 1
                    unique_key_4 = f"cookie_set_{self.jwt_refresh_cookie_key}_{st.session_state.cookie_set_counter}_{time.time()}_{random.randint(1000, 9999)}"
                    try:
                        self.cookie_manager.set(
                            self.jwt_refresh_cookie_key,
                            jwt_refresh_token,
                            expires_at=datetime.now() + timedelta(days=7),
                            key=unique_key_4,
                        )
                    except Exception as e:
                        st.warning(f"JWT Refresh 토큰 쿠키 저장 실패: {str(e)}")

                # 쿠키 저장 로깅 (레퍼런스 패턴: 확인 없이 저장만 수행)
                if self.logger.is_available():
                    self.logger.log_user_activity(
                        user_data.get("localId"),
                        "cookies_saved",
                        {
                            "has_firebase_token": bool(id_token),
                            "has_refresh_token": bool(refresh_token),
                            "has_jwt_access": bool(jwt_access_token),
                            "has_jwt_refresh": bool(jwt_refresh_token),
                        },
                    )
            except Exception as cookie_error:
                # 쿠키 저장 실패는 경고만 표시하고 계속 진행
                st.warning(f"쿠키 저장 실패 (세션은 유지됨): {str(cookie_error)}")
                if self.logger.is_available():
                    self.logger.log_user_activity(
                        user_data.get("localId"),
                        "cookie_save_error",
                        {"error": str(cookie_error)},
                    )

            # 로그인 로그 기록
            if self.logger.is_available():
                self.logger.log_login(user_data.get("localId"), "email")

            return True
        except Exception as e:
            st.error(f"❌ 세션 저장 중 오류가 발생했습니다: {str(e)}")
            return False

    def load_session_from_browser(self) -> bool:
        """브라우저에서 세션 복원 (쿠키 우선, Streamlit 세션 상태 기반)"""
        try:
            # 쿠키에서 토큰 가져오기
            token = self.cookie_manager.get(self.cookie_key)

            if token:
                # 쿠키에서 토큰을 찾았으면 복원 시도
                return self._restore_from_cookie(token)

            # 쿠키에 토큰이 없으면 Streamlit 세션 상태에서 복원 시도
            return self._restore_from_session_state()

        except Exception as e:
            # 쿠키 로드 실패 시에도 세션 상태에서 복원 시도
            if self.logger.is_available():
                self.logger.log_user_activity(
                    None, "cookie_load_error", {"error": str(e)}
                )
            return self._restore_from_session_state()

    def _restore_from_cookie(self, all_cookies: dict = None) -> bool:
        """쿠키에서 받은 JWT 토큰으로 세션 복원 (yamyam-ops JWT 토큰만 사용)"""
        try:
            print("[쿠키 복원] 🚀 시작 - 쿠키에서 JWT 토큰 복원 시도")

            # 쿠키에서 모든 토큰 가져오기 (이미 읽은 쿠키가 있으면 사용, 없으면 새로 읽기)
            if all_cookies is None:
                # 고유한 key를 사용하여 중복 키 오류 방지
                import random
                import time

                unique_key = f"get_all_{time.time()}_{random.randint(1000, 9999)}"
                try:
                    all_cookies = self.cookie_manager.get_all(key=unique_key)
                except Exception as e:
                    print(f"[쿠키 복원] ⚠️ get_all() 실패, 개별 get() 시도: {e}")
                    # get_all() 실패 시 개별 get() 사용
                    all_cookies = {}
                    try:
                        all_cookies[self.jwt_access_cookie_key] = (
                            self.cookie_manager.get(
                                self.jwt_access_cookie_key,
                                key=f"get_jwt_access_{time.time()}",
                            )
                        )
                    except:
                        pass
                    try:
                        all_cookies[self.jwt_refresh_cookie_key] = (
                            self.cookie_manager.get(
                                self.jwt_refresh_cookie_key,
                                key=f"get_jwt_refresh_{time.time()}",
                            )
                        )
                    except:
                        pass

            jwt_access_token = (
                all_cookies.get(self.jwt_access_cookie_key) if all_cookies else None
            )
            jwt_refresh_token = (
                all_cookies.get(self.jwt_refresh_cookie_key) if all_cookies else None
            )

            # JWT 토큰이 없으면 실패
            if not jwt_access_token:
                print("[쿠키 복원] ❌ JWT Access 토큰이 없음")
                return False

            # JWT 토큰을 세션 상태에 저장
            st.session_state.jwt_access_token = jwt_access_token
            if jwt_refresh_token:
                st.session_state.jwt_refresh_token = jwt_refresh_token
            st.session_state.jwt_expires_at = datetime.now() + timedelta(minutes=15)

            # JWT 토큰으로 yamyam-ops API 검증
            print("[쿠키 복원] 🔍 JWT 토큰 검증 시작")

            if self._verify_jwt_token_with_yamyam_ops():
                st.session_state.is_authenticated = True
                print("[쿠키 복원] ✅ 성공! JWT 토큰으로 로그인 완료")
                return True
            else:
                # JWT 토큰 검증 실패 시 JWT refresh_token으로 갱신 시도
                print(
                    f"[쿠키 복원] ❌ JWT 검증 실패. Refresh 토큰으로 갱신 시도: {bool(jwt_refresh_token)}"
                )

                if jwt_refresh_token:
                    from utils.api_client import get_yamyam_ops_client

                    client = get_yamyam_ops_client()
                    if client:
                        print("[쿠키 복원] 🔄 JWT Refresh 시작")

                        if client._refresh_jwt_token():
                            # JWT 갱신 성공 후 재검증
                            print("[쿠키 복원] ✅ JWT Refresh 성공. 재검증 시작")

                            if self._verify_jwt_token_with_yamyam_ops():
                                st.session_state.is_authenticated = True
                                print("[쿠키 복원] ✅ 성공! JWT Refresh 후 검증 완료")
                                return True
                            else:
                                print("[쿠키 복원] ❌ JWT Refresh 후 재검증 실패")
                        else:
                            print("[쿠키 복원] ❌ JWT Refresh 실패")
                    else:
                        print("[쿠키 복원] ❌ API 클라이언트를 사용할 수 없음")

            # JWT 토큰 검증 실패
            print(
                f"[쿠키 복원] ❌ 복원 실패 - JWT Access: {bool(jwt_access_token)}, JWT Refresh: {bool(jwt_refresh_token)}"
            )
            return False

        except Exception as e:
            print(f"[쿠키 복원] ❌ 예외 발생: {type(e).__name__}: {str(e)}")

            return False

    def _restore_from_session_state(self) -> bool:
        """Streamlit 세션 상태에서 복원 시도 (JWT 토큰만 사용)"""
        try:
            # JWT 토큰이 있으면 검증
            if st.session_state.jwt_access_token:
                if st.session_state.jwt_expires_at:
                    # 토큰 만료 확인
                    if datetime.now() < st.session_state.jwt_expires_at:
                        # 토큰이 유효하면 yamyam-ops로 검증
                        return self._verify_jwt_token_with_yamyam_ops()
                    else:
                        # 토큰이 만료되었으면 JWT refresh로 갱신 시도
                        from utils.api_client import get_yamyam_ops_client

                        client = get_yamyam_ops_client()
                        if client and client._refresh_jwt_token():
                            return self._verify_jwt_token_with_yamyam_ops()
                else:
                    # 만료 시간 정보가 없으면 바로 검증
                    return self._verify_jwt_token_with_yamyam_ops()

            return False

        except Exception as e:
            print(f"[세션 상태 복원] ❌ 예외 발생: {type(e).__name__}: {str(e)}")
            return False

    def _verify_jwt_token_with_yamyam_ops(self) -> bool:
        """yamyam-ops API를 통해 JWT 토큰 유효성 검증"""
        try:
            if not st.session_state.jwt_access_token:
                print("[JWT 검증] ❌ 세션에 JWT 토큰이 없습니다")
                return False

            api_url = st.secrets.get("API_URL")
            if not api_url:
                print("[JWT 검증] ❌ API_URL이 설정되지 않았습니다")
                return False

            import requests

            url = f"{api_url.rstrip('/')}/auth/verify"
            payload = {"token": st.session_state.jwt_access_token}

            response = requests.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("valid"):
                    # JWT 토큰이 유효하면 payload에서 사용자 정보 가져오기
                    payload_data = data.get("payload", {})

                    print(f"[JWT 검증] ✅ 토큰 유효! payload: {payload_data}")

                    # payload에서 사용자 정보 추출
                    firebase_uid = payload_data.get("firebase_uid")
                    user_id = payload_data.get("user_id")

                    if firebase_uid:
                        # Firebase에서 사용자 정보 가져오기 (표시용)
                        try:
                            user = auth.get_user(firebase_uid)
                            updated_user_info = {
                                "localId": user.uid,
                                "email": user.email,
                                "emailVerified": user.email_verified,
                                "displayName": user.display_name
                                or user.email.split("@")[0],
                                "photoUrl": user.photo_url,
                                "disabled": user.disabled,
                            }
                            st.session_state.user_info = updated_user_info
                        except Exception as firebase_error:
                            # Firebase에서 정보를 가져오지 못해도 JWT가 유효하면 로그인 성공
                            print(
                                f"[JWT 검증] ⚠️ Firebase 사용자 정보 가져오기 실패: {firebase_error}"
                            )
                            # 최소한의 사용자 정보 설정
                            st.session_state.user_info = {
                                "localId": firebase_uid,
                                "email": payload_data.get("email", ""),
                                "displayName": payload_data.get("name", ""),
                            }

                    print(
                        f"[JWT 검증] ✅ 검증 성공! user_id={user_id}, firebase_uid={firebase_uid}"
                    )
                    return True
                else:
                    error_message = data.get("message", "Unknown error")
                    print(f"[JWT 검증] ❌ 토큰 무효: {error_message}")
                    print(f"[JWT 검증] 응답 데이터: {data}")
                    return False
            else:
                error_text = (
                    response.text[:500] if response.text else "No response text"
                )
                print(f"[JWT 검증] ❌ HTTP 에러: status_code={response.status_code}")
                print(f"[JWT 검증] 에러 내용: {error_text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"[JWT 검증] ❌ 요청 예외 발생: {type(e).__name__}: {str(e)}")
            return False
        except Exception as e:
            print(f"[JWT 검증] ❌ 예상치 못한 예외: {type(e).__name__}: {str(e)}")
            return False

    def _verify_token_with_firebase(self) -> bool:
        """Firebase에서 토큰 유효성 검증"""
        try:
            if not st.session_state.auth_token:
                return False

            # Firebase Admin SDK로 토큰 검증
            decoded_token = auth.verify_id_token(st.session_state.auth_token)

            if decoded_token:
                # 사용자 정보 업데이트
                user = auth.get_user(decoded_token["uid"])

                updated_user_info = {
                    "localId": user.uid,
                    "email": user.email,
                    "emailVerified": user.email_verified,
                    "displayName": user.display_name or user.email.split("@")[0],
                    "photoUrl": user.photo_url,
                    "disabled": user.disabled,
                }

                st.session_state.user_info = updated_user_info
                return True

            return False

        except Exception as e:
            # 토큰이 유효하지 않은 경우 (만료 등)
            # 세션을 삭제하지 않고 False만 반환 (refresh_token으로 갱신 시도 가능하도록)
            if self.logger.is_available():
                error_msg = str(e)
                error_type = type(e).__name__
                self.logger.log_user_activity(
                    None,
                    "token_verification_failed",
                    {"error": error_msg, "error_type": error_type},
                )
            # 세션 상태는 유지 (refresh_token으로 갱신 시도 가능)
            return False

    def _refresh_token_if_possible(self) -> bool:
        """리프레시 토큰으로 새 토큰 발급"""
        try:
            # 세션 상태 또는 쿠키에서 refresh_token 가져오기
            refresh_token = st.session_state.refresh_token
            if not refresh_token:
                try:
                    all_cookies = self.cookie_manager.get_all()
                    refresh_token = (
                        all_cookies.get(self.refresh_cookie_key)
                        if all_cookies
                        else None
                    )
                except Exception as e:
                    if self.logger.is_available():
                        self.logger.log_user_activity(
                            None, "cookie_read_error", {"error": str(e)}
                        )
                    pass

            if not refresh_token:
                if self.logger.is_available():
                    self.logger.log_user_activity(None, "refresh_token_not_found", {})
                return False

            # Firebase REST API를 통해 토큰 갱신
            import requests

            api_key = st.secrets.get("FIREBASE_WEB_API_KEY")
            if not api_key:
                return False

            url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"

            payload = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }

            response = requests.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()

                # 새 토큰으로 세션 업데이트
                new_id_token = data.get("id_token")
                new_refresh_token = data.get("refresh_token")

                if new_id_token:
                    # 토큰 만료 시간 업데이트
                    st.session_state.auth_token = new_id_token
                    st.session_state.refresh_token = new_refresh_token
                    st.session_state.token_expires_at = datetime.now() + timedelta(
                        hours=1
                    )

                    # 쿠키에도 업데이트된 토큰 저장
                    try:
                        import random
                        import time

                        if "cookie_set_counter" not in st.session_state:
                            st.session_state.cookie_set_counter = 0
                        st.session_state.cookie_set_counter += 1
                        counter = st.session_state.cookie_set_counter
                        unique_key_1 = f"cookie_set_{self.cookie_key}_{counter}_{time.time()}_{random.randint(1000, 9999)}"

                        self.cookie_manager.set(
                            self.cookie_key,
                            new_id_token,
                            expires_at=datetime.now() + timedelta(days=30),
                            key=unique_key_1,
                        )
                        if new_refresh_token:
                            st.session_state.cookie_set_counter += 1
                            counter = st.session_state.cookie_set_counter
                            unique_key_2 = f"cookie_set_{self.refresh_cookie_key}_{counter}_{time.time()}_{random.randint(1000, 9999)}"
                            self.cookie_manager.set(
                                self.refresh_cookie_key,
                                new_refresh_token,
                                expires_at=datetime.now() + timedelta(days=30),
                                key=unique_key_2,
                            )
                    except Exception as e:
                        if self.logger.is_available():
                            self.logger.log_user_activity(
                                None, "cookie_update_error", {"error": str(e)}
                            )
                        pass  # 쿠키 저장 실패해도 세션은 업데이트됨

                    # 토큰 검증 및 인증 상태 설정
                    if self._verify_token_with_firebase():
                        st.session_state.is_authenticated = True
                        return True
                    return False

            return False

        except Exception as e:
            st.warning(f"토큰 갱신 실패: {str(e)}")
            return False

    def is_token_valid(self) -> bool:
        """현재 JWT 토큰이 유효한지 확인"""
        # JWT 토큰 우선 확인
        if st.session_state.jwt_access_token and st.session_state.jwt_expires_at:
            # 만료 시간 확인 (5분 여유를 둠)
            buffer_time = timedelta(minutes=5)
            return datetime.now() + buffer_time < st.session_state.jwt_expires_at

        # JWT 토큰이 없으면 False
        return False

    def get_current_user(self) -> Optional[dict[str, Any]]:
        """현재 로그인된 사용자 정보 반환"""
        if st.session_state.is_authenticated and st.session_state.user_info:
            return st.session_state.user_info
        return None

    def clear_session(self):
        """세션 정보 완전 삭제"""
        try:
            # 쿠키 삭제
            try:
                if "cookie_set_counter" not in st.session_state:
                    st.session_state.cookie_set_counter = 0

                # Firebase 토큰 쿠키 삭제
                if self.cookie_manager.get(self.cookie_key):
                    st.session_state.cookie_set_counter += 1
                    counter = st.session_state.cookie_set_counter
                    self.cookie_manager.delete(
                        self.cookie_key,
                        key=f"cookie_delete_{self.cookie_key}_{counter}",
                    )
                if self.cookie_manager.get(self.refresh_cookie_key):
                    st.session_state.cookie_set_counter += 1
                    counter = st.session_state.cookie_set_counter
                    self.cookie_manager.delete(
                        self.refresh_cookie_key,
                        key=f"cookie_delete_{self.refresh_cookie_key}_{counter}",
                    )

                # JWT 토큰 쿠키 삭제
                if self.cookie_manager.get(self.jwt_access_cookie_key):
                    st.session_state.cookie_set_counter += 1
                    counter = st.session_state.cookie_set_counter
                    self.cookie_manager.delete(
                        self.jwt_access_cookie_key,
                        key=f"cookie_delete_{self.jwt_access_cookie_key}_{counter}",
                    )
                if self.cookie_manager.get(self.jwt_refresh_cookie_key):
                    st.session_state.cookie_set_counter += 1
                    counter = st.session_state.cookie_set_counter
                    self.cookie_manager.delete(
                        self.jwt_refresh_cookie_key,
                        key=f"cookie_delete_{self.jwt_refresh_cookie_key}_{counter}",
                    )
            except Exception:
                pass

            # Streamlit 세션 상태 초기화
            st.session_state.user_info = None
            st.session_state.is_authenticated = False
            st.session_state.auth_token = None
            st.session_state.token_expires_at = None
            st.session_state.refresh_token = None
            st.session_state.jwt_access_token = None
            st.session_state.jwt_refresh_token = None
            st.session_state.jwt_expires_at = None

        except Exception as e:
            st.warning(f"세션 삭제 중 오류: {str(e)}")

    def check_authentication(self) -> bool:
        """인증 상태 확인 (JWT 토큰만 사용)"""
        try:
            # 세션 상태가 초기화되었는지 확인
            if not hasattr(st.session_state, "is_authenticated"):
                print("[인증 확인] ⚠️ 세션 상태 미초기화 - 초기화 수행")
                self._initialize_session_state()

            print("[인증 확인] 🔍 시작")
            is_authenticated = st.session_state.get("is_authenticated", False)
            user_info = st.session_state.get("user_info")
            jwt_token = st.session_state.get("jwt_access_token")

            print(f"  - 인증 상태: {is_authenticated}")
            print(f"  - 사용자 정보: {bool(user_info)}")
            print(f"  - JWT 토큰: {bool(jwt_token)}")

            # 이미 인증된 상태라면 JWT 토큰 유효성 확인
            if is_authenticated and user_info:
                if self.is_token_valid():
                    print("[인증 확인] ✅ 토큰 유효 - 인증 유지")
                    return True
                else:
                    # 토큰이 만료되었으면 JWT refresh로 갱신 시도
                    print("[인증 확인] ⏰ 토큰 만료 - Refresh 시도")

                    from utils.api_client import get_yamyam_ops_client

                    client = get_yamyam_ops_client()
                    if client and client._refresh_jwt_token():
                        # 갱신 후 재검증
                        if self._verify_jwt_token_with_yamyam_ops():
                            print("[인증 확인] ✅ Refresh 후 검증 성공")
                            return True

                    print("[인증 확인] ❌ Refresh 실패")
                    return False

            # 인증되지 않은 상태는 False 반환 (쿠키 확인은 main.py에서 직접 수행)
            print("[인증 확인] ❌ 인증되지 않음")
            return False

        except Exception as e:
            # 오류 발생 시 로그 기록 후 False 반환
            print(f"[인증 확인] ❌ 예외 발생: {type(e).__name__}: {str(e)}")

            return False

    def logout(self):
        """로그아웃 처리"""
        try:
            # 로그아웃 로그 기록
            if (
                self.logger.is_available()
                and st.session_state.user_info
                and st.session_state.user_info.get("localId")
            ):
                self.logger.log_user_activity(
                    st.session_state.user_info.get("localId"),
                    "logout",
                    {"method": "manual"},
                )

            # 세션 완전 삭제
            self.clear_session()

            st.success("✅ 로그아웃되었습니다.")
            st.rerun()

        except Exception as e:
            st.error(f"❌ 로그아웃 중 오류가 발생했습니다: {str(e)}")


# 전역 세션 매니저 인스턴스
_session_manager = None


def get_session_manager() -> SessionManager:
    """세션 매니저 인스턴스 반환 (싱글톤 패턴)"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
