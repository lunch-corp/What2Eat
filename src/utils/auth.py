import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import firebase_admin
import requests
import streamlit as st
from firebase_admin import auth, firestore

from config.firebase_config import initialize_firebase_admin
from utils.firebase_logger import get_firebase_logger
from utils.session_manager import get_session_manager


class AuthManager:
    """인증 관리 클래스 - 쿠키 기반 세션 관리"""
    
    def __init__(self):
        self.session_manager = get_session_manager()
        self.cookie_manager = self.session_manager.cookie_manager
        self.cookie_key = "jwt_access_token"  # JWT Access Token 쿠키 키
    
    def init_session_state(self):
        """세션 상태 초기화 및 쿠키에서 인증 상태 복원"""
        # 세션 상태 초기화는 SessionManager에서 처리
        self.session_manager._initialize_session_state()
        
        # 이미 로그인된 경우 토큰 유효성 검증
        if st.session_state.get("is_authenticated", False):
            if not self.check_authentication():
                self.clear_auth_state()
            return
        
        # 로그인된 상태가 아닐 때만 쿠키 복원 시도
        if not st.session_state.get("is_authenticated", False):
            # 쿠키 복원 시도 플래그 확인 (한 번만 시도)
            if st.session_state.get("_cookie_restore_attempted", False):
                return
            
            # 쿠키 복원 시도 플래그 설정
            st.session_state._cookie_restore_attempted = True
            
            try:
                # 레퍼런스 패턴: 단일 쿠키만 읽기 (get_all()은 무한 반복 발생)
                jwt_token = self.cookie_manager.get(self.cookie_key)
                
                # JWT 토큰이 있으면 복원 시도
                if jwt_token:

                    # JWT 토큰을 세션 상태에 저장
                    st.session_state.jwt_access_token = jwt_token
                    
                    # JWT 토큰 검증 (내부에서 get_all() 호출하지 않도록 직접 검증)
                    if self.session_manager._verify_jwt_token_with_yamyam_ops():
                        st.session_state.is_authenticated = True
                         # 복원 성공 시 페이지 재실행 (한 번만)
                        if not st.session_state.get("_cookie_restore_rerun", False):
                            st.session_state._cookie_restore_rerun = True
                            st.rerun()
                    else:
                         self.clear_auth_state()
                else:
                    print("[AuthManager] 쿠키에 JWT 토큰 없음")
            except Exception as e:
                print(f"[AuthManager] 쿠키 복원 중 오류: {e}")
                self.clear_auth_state()
    
    def clear_auth_state(self):
        """인증 관련 세션 상태와 쿠키 초기화"""
        try:
            # 쿠키 삭제 (레퍼런스 패턴: key 파라미터 없이 사용)
            # JWT Access Token 쿠키 삭제
            try:
                if self.cookie_manager.get(self.cookie_key):
                    self.cookie_manager.delete(self.cookie_key)
            except Exception:
                pass
            # JWT Refresh Token 쿠키 삭제
            try:
                if self.cookie_manager.get(self.session_manager.jwt_refresh_cookie_key):
                    self.cookie_manager.delete(self.session_manager.jwt_refresh_cookie_key)
            except Exception:
                pass
        except Exception:
            pass
        
        # 세션 상태 초기화
        st.session_state.is_authenticated = False
        st.session_state.auth_token = None
        st.session_state.user_info = None
        st.session_state.jwt_access_token = None
        st.session_state.jwt_refresh_token = None
        # 쿠키 복원 시도 플래그도 초기화
        st.session_state._cookie_restore_attempted = False
        st.session_state._cookie_restore_rerun = False
    
    def check_authentication(self) -> bool:
        """세션의 인증 상태를 확인"""
        return self.session_manager.check_authentication()
    
    def save_user_session(
        self,
        user_data: Dict[str, Any],
        id_token: str,
        refresh_token: str = None,
        jwt_access_token: str = None,
        jwt_refresh_token: str = None,
        jwt_expires_in: int = None,
    ):
        """사용자 세션 정보 저장 (쿠키 포함)"""
        return self.session_manager.save_user_session(
            user_data,
            id_token,
            refresh_token,
            jwt_access_token,
            jwt_refresh_token,
            jwt_expires_in,
        )


def map_kr_jamo_to_en(text: str) -> str:
    """한글(두벌식) 자모를 대응하는 QWERTY 영문 키로 변환합니다.

    - 단일 자모는 1:1 매핑 (예: ㅋ -> 'z', ㅈ -> 'w')
    - 합성 모음은 실제 키 입력 두 글자로 매핑 (예: ㅘ -> 'hk', ㅝ -> 'nj')
    - 영문/숫자/기호는 그대로 유지
    """
    mapping = {
        # 자음/모음 (단일)
        "ㅂ": "q", "ㅈ": "w", "ㄷ": "e", "ㄱ": "r", "ㅅ": "t",
        "ㅛ": "y", "ㅕ": "u", "ㅑ": "i", "ㅐ": "o", "ㅔ": "p",
        "ㅁ": "a", "ㄴ": "s", "ㅇ": "d", "ㄹ": "f", "ㅎ": "g",
        "ㅗ": "h", "ㅓ": "j", "ㅏ": "k", "ㅣ": "l",
        "ㅋ": "z", "ㅌ": "x", "ㅊ": "c", "ㅍ": "v", "ㅠ": "b",
        "ㅜ": "n", "ㅡ": "m",
        # 된소리 (Shift)
        "ㅃ": "Q", "ㅉ": "W", "ㄸ": "E", "ㄲ": "R", "ㅆ": "T",
        # 합성 모음
        "ㅘ": "hk", "ㅙ": "ho", "ㅚ": "hl",
        "ㅝ": "nj", "ㅞ": "np", "ㅟ": "nl",
        "ㅢ": "ml",
        # 드문 모음
        "ㅒ": "O", "ㅖ": "P",
    }

    if not re.search(r"[\u3131-\u318E]", text):
        return text
    out = []
    for ch in text:
        out.append(mapping.get(ch, ch))
    return "".join(out)


class FirebaseAuth:
    """Firebase Authentication을 관리하는 클래스"""

    def __init__(self):
        self.auth_manager = AuthManager()
        self.session_manager = self.auth_manager.session_manager

        # if not is_firebase_configured():
        #     st.error("❌ Firebase가 설정되지 않았습니다. 설정을 확인해주세요.")
        #     return

        try:
            # Firebase Admin SDK 초기화
            if not initialize_firebase_admin():
                st.error("❌ Firebase Admin SDK 초기화에 실패했습니다.")
                return
        except Exception as e:
            st.error(f"❌ Firebase 초기화 중 오류가 발생했습니다: {str(e)}")

    def is_available(self) -> bool:
        """Firebase Auth가 사용 가능한지 확인"""
        try:
            firebase_admin.get_app()
            return True
        except ValueError:
            return False

    def sign_up_with_email(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """이메일과 비밀번호로 회원가입"""
        try:
            user = auth.create_user(
                email=email, password=password, email_verified=False, disabled=False
            )

            # 회원가입 성공 시 로그 기록
            logger = get_firebase_logger()
            logger.log_signup(user.uid, "email")

            user_data = {
                "localId": user.uid,
                "email": user.email,
                "emailVerified": user.email_verified,
                "displayName": user.display_name or email.split("@")[0],
                "photoUrl": user.photo_url,
                "disabled": user.disabled,
                "metadata": {
                    "creationTime": user.user_metadata.creation_timestamp,
                    "lastSignInTime": user.user_metadata.last_sign_in_timestamp,
                },
            }

            # 회원가입 후 자동 로그인을 위해 토큰 생성
            custom_token = auth.create_custom_token(user.uid)
            
            # Custom Token을 Firebase ID Token으로 교환
            firebase_id_token = None
            refresh_token = None
            try:
                import requests
                
                FIREBASE_WEB_API_KEY = st.secrets.get("FIREBASE_WEB_API_KEY")
                if FIREBASE_WEB_API_KEY:
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_WEB_API_KEY}"
                    payload = {
                        "token": custom_token.decode(),
                        "returnSecureToken": True
                    }
                    response = requests.post(url, json=payload)
                    if response.status_code == 200:
                        token_data = response.json()
                        firebase_id_token = token_data.get("idToken")
                        refresh_token = token_data.get("refreshToken")
            except Exception:
                pass  # Custom Token 교환 실패해도 회원가입은 성공
            
            # JWT 토큰 받기 (Firebase ID Token이 있는 경우)
            jwt_tokens = None
            if firebase_id_token:
                jwt_tokens = self._get_jwt_tokens_from_yamyam_ops(firebase_id_token)

            # 세션에 저장 (AuthManager를 통해 쿠키도 함께 저장)
            self.auth_manager.save_user_session(
                user_data,
                firebase_id_token or custom_token.decode(),
                refresh_token,
                jwt_access_token=jwt_tokens.get("access_token") if jwt_tokens else None,
                jwt_refresh_token=jwt_tokens.get("refresh_token") if jwt_tokens else None,
                jwt_expires_in=jwt_tokens.get("expires_in") if jwt_tokens else None,
            )

            # PostgreSQL에 사용자 동기화 (비동기 처리)
            try:
                import asyncio

                from utils.api_client import get_yamyam_ops_client

                client = get_yamyam_ops_client()
                if client:
                    # 비동기 함수를 동기적으로 실행
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    success = loop.run_until_complete(
                        client.sync_user_from_firebase(
                            user.uid, user.email, user.display_name or email.split("@")[0]
                        )
                    )
                    loop.close()

                    if success:
                        st.success("✅ 사용자 정보가 동기화되었습니다.")
                    else:
                        st.warning(
                            "⚠️ 사용자 정보 동기화에 실패했습니다. 나중에 다시 시도됩니다."
                        )
                else:
                    st.warning("⚠️ API 클라이언트를 초기화할 수 없습니다.")
            except Exception as sync_error:
                # 동기화 실패해도 회원가입은 성공으로 처리
                st.warning(f"⚠️ 사용자 정보 동기화 중 오류: {str(sync_error)}")

            return user_data

        except auth.EmailAlreadyExistsError:
            st.error("❌ 이미 존재하는 이메일입니다.")
        except auth.InvalidPasswordError:
            st.error("❌ 비밀번호가 너무 약합니다. 6자 이상으로 설정해주세요.")
        except auth.InvalidEmailError:
            st.error("❌ 유효하지 않은 이메일 형식입니다.")
        except Exception as e:
            st.error(f"❌ 회원가입 중 오류가 발생했습니다: {str(e)}")
        return None

    def sign_in_with_email(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """이메일과 비밀번호로 로그인 (Firebase REST API 사용)"""
        try:
            # KR→EN 키보드 매핑 적용 비밀번호 생성
            mapped_password = map_kr_jamo_to_en(password)
            
            # Firebase Web API Key 가져오기
            FIREBASE_WEB_API_KEY = st.secrets["FIREBASE_WEB_API_KEY"]

            if not FIREBASE_WEB_API_KEY:
                st.error("❌ Firebase Web API Key가 설정되지 않았습니다.")
                return None

            # Firebase Authentication REST API를 사용하여 인증
            # 1) 원본 비밀번호 시도
            auth_result = self._authenticate_user_with_rest_api(
                email, password, FIREBASE_WEB_API_KEY
            )

            # 2) 실패했고, 매핑 비밀번호가 다르면 매핑 비밀번호로 재시도
            if (not auth_result.get("success")) and mapped_password != password:
                auth_result = self._authenticate_user_with_rest_api(
                    email, mapped_password, FIREBASE_WEB_API_KEY
                )

            if auth_result["success"]:
                user_data = {
                    "localId": auth_result["uid"],
                    "email": auth_result["email"],
                    "emailVerified": True,
                    "displayName": auth_result["email"].split("@")[0],
                    "photoUrl": None,
                    "idToken": auth_result["id_token"],
                    "refreshToken": auth_result["refresh_token"],
                    "expiresIn": int((datetime.now() + timedelta(hours=1)).timestamp()),
                    "disabled": False,
                }

                # yamyam-ops의 /login 엔드포인트 호출하여 JWT 토큰 받기
                jwt_tokens = self._get_jwt_tokens_from_yamyam_ops(auth_result["id_token"])
                
                # 세션 매니저를 통해 로그인 상태 저장 (AuthManager를 통해 쿠키도 함께 저장)
                if self.auth_manager.save_user_session(
                    user_data, 
                    auth_result["id_token"], 
                    auth_result["refresh_token"],
                    jwt_access_token=jwt_tokens.get("access_token") if jwt_tokens else None,
                    jwt_refresh_token=jwt_tokens.get("refresh_token") if jwt_tokens else None,
                    jwt_expires_in=jwt_tokens.get("expires_in") if jwt_tokens else None,
                ):
                    if jwt_tokens:
                        st.success("✅ 로그인되었습니다!")
                    else:
                        st.warning("⚠️ 로그인되었지만 JWT 토큰 발급에 실패했습니다. 일부 기능이 제한될 수 있습니다.")
                    return user_data
                else:
                    st.error("❌ 세션 저장에 실패했습니다.")
                    return None
            else:
                st.error(f"❌ 로그인 실패: {auth_result['error']}")
                return None

        except Exception as e:
            st.error(f"❌ 로그인 중 오류가 발생했습니다: {str(e)}")
            return None

    def _get_jwt_tokens_from_yamyam_ops(self, firebase_id_token: str) -> Optional[Dict[str, Any]]:
        """yamyam-ops의 /login 엔드포인트를 호출하여 JWT 토큰 받기"""
        try:
            api_url = st.secrets.get("API_URL")
            if not api_url:
                logger = get_firebase_logger()
                logger.log_user_activity(
                    None, "error", {"message": "API_URL이 설정되지 않았습니다."}
                )
                return None

            url = f"{api_url.rstrip('/')}/auth/login"
            payload = {"firebase_token": firebase_id_token}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token"),
                    "token_type": data.get("token_type", "bearer"),
                    "expires_in": data.get("expires_in"),
                }
            else:
                # 로그인 실패는 경고만 표시 (Firebase 로그인은 성공했으므로)
                error_msg = response.text
                logger = get_firebase_logger()
                logger.log_user_activity(
                    None, "error", {"message": f"yamyam-ops JWT 토큰 발급 실패: {error_msg}"}
                )
                return None
                
        except Exception as e:
            # 예외 발생해도 Firebase 로그인은 성공했으므로 경고만 표시
            logger = get_firebase_logger()
            logger.log_user_activity(
                None, "error", {"message": f"yamyam-ops JWT 토큰 발급 중 오류: {str(e)}"}
            )
            return None

    def _authenticate_user_with_rest_api(
        self, email: str, password: str, api_key: str
    ) -> Dict[str, Any]:
        """Firebase Authentication REST API를 사용하여 이메일/비밀번호 인증"""
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"

        payload = {"email": email, "password": password, "returnSecureToken": True}

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            return {
                "success": True,
                "uid": data.get("localId"),
                "email": data.get("email"),
                "id_token": data.get("idToken"),
                "refresh_token": data.get("refreshToken"),
            }
        except requests.exceptions.RequestException as e:
            if response.status_code == 400:
                error_data = response.json()
                error_message = error_data.get("error", {}).get(
                    "message", "알 수 없는 오류"
                )
                if "INVALID_LOGIN_CREDENTIALS" in error_message:
                    return {
                        "success": False,
                        "error": "잘못된 이메일 또는 비밀번호입니다.",
                    }
                elif "INVALID_PASSWORD" in error_message:
                    return {"success": False, "error": "잘못된 비밀번호입니다."}
                elif "EMAIL_NOT_FOUND" in error_message:
                    return {"success": False, "error": "존재하지 않는 이메일입니다."}
                elif "INVALID_EMAIL" in error_message:
                    return {"success": False, "error": "잘못된 이메일 형식입니다."}
                else:
                    return {"success": False, "error": f"{error_message}"}
            return {"success": False, "error": f"네트워크 오류: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"인증 실패: {str(e)}"}

    def reset_password(self, email: str) -> bool:
        """비밀번호 재설정 이메일 전송 (Firebase REST API 사용)"""
        try:
            # Firebase Web API Key 가져오기
            FIREBASE_WEB_API_KEY = st.secrets["FIREBASE_WEB_API_KEY"]

            if not FIREBASE_WEB_API_KEY:
                st.error("❌ Firebase Web API Key가 설정되지 않았습니다.")
                return False

            # Firebase REST API를 사용하여 비밀번호 재설정 이메일 전송
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"

            payload = {
                "requestType": "PASSWORD_RESET",
                "email": email
            }

            response = requests.post(url, json=payload)

            if response.status_code == 200:
                return True
            else:
                # 에러 응답 처리
                error_data = response.json()
                error_message = error_data.get("error", {}).get("message", "알 수 없는 오류")
                
                if "EMAIL_NOT_FOUND" in error_message:
                    st.error("❌ 등록되지 않은 이메일입니다.")
                elif "INVALID_EMAIL" in error_message:
                    st.error("❌ 유효하지 않은 이메일 형식입니다.")
                elif "MISSING_EMAIL" in error_message:
                    st.error("❌ 이메일을 입력해주세요.")
                else:
                    st.error(f"❌ 비밀번호 재설정 중 오류가 발생했습니다: {error_message}")
                return False

        except Exception as e:
            st.error(f"❌ 비밀번호 재설정 중 오류가 발생했습니다: {str(e)}")
            return False

    def sign_out(self):
        """로그아웃"""
        self.auth_manager.clear_auth_state()
        self.session_manager.logout()

    def verify_id_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """ID 토큰 검증"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            st.error(f"❌ 토큰 검증 중 오류가 발생했습니다: {str(e)}")
            return None


def auth_form():
    """통합 인증 폼 (로그인/회원가입/비밀번호 재설정)"""
    firebase_auth = FirebaseAuth()

    if not firebase_auth.is_available():
        st.error("❌ Firebase Authentication이 설정되지 않았습니다.")
        return False

    # 탭 생성
    login_tab, signup_tab, reset_tab = st.tabs(
        [
            "🔑 로그인",
            "👤 회원가입",
            "🔄 비밀번호 재설정",
        ]
    )

    with login_tab:
        st.subheader("로그인")

        # # Google 로그인
        # st.write("**Google 계정으로 로그인:**")
        # google_auth_component()

        # st.divider()

        # 이메일/비밀번호 로그인
        st.write("**이메일로 로그인:**")
        with st.form("login_form"):
            email = st.text_input("이메일", placeholder="example@email.com")
            password = st.text_input("비밀번호", type="password")
            submit_button = st.form_submit_button("로그인", use_container_width=True)

            if submit_button:
                if email and password:
                    user = firebase_auth.sign_in_with_email(email, password)
                    if user:
                        # 로그인 성공 시 자동으로 페이지 새로고침
                        st.rerun()
                else:
                    st.error("❌ 이메일과 비밀번호를 입력해주세요.")

    with signup_tab:
        st.subheader("회원가입")
        with st.form("signup_form"):
            email = st.text_input("이메일", placeholder="example@email.com")
            password = st.text_input(
                "비밀번호", type="password", help="6자 이상 입력해주세요"
            )
            confirm_password = st.text_input("비밀번호 확인", type="password")
            submit_button = st.form_submit_button("회원가입", use_container_width=True)

            if submit_button:
                if email and password and confirm_password:
                    if password != confirm_password:
                        st.error("❌ 비밀번호가 일치하지 않습니다.")
                    elif len(password) < 6:
                        st.error("❌ 비밀번호는 6자 이상이어야 합니다.")
                    else:
                        user = firebase_auth.sign_up_with_email(email, password)
                        if user:
                            st.success("✅ 회원가입 성공! 자동으로 로그인됩니다.")
                            st.balloons()
                            # 회원가입 후 자동 로그인되므로 페이지 새로고침
                            st.rerun()
                else:
                    st.error("❌ 모든 필드를 입력해주세요.")

    with reset_tab:
        st.subheader("비밀번호 재설정")
        with st.form("reset_form"):
            email = st.text_input("이메일", placeholder="example@email.com")
            submit_button = st.form_submit_button(
                "재설정 이메일 보내기", use_container_width=True
            )

            if submit_button:
                if email:
                    if firebase_auth.reset_password(email):
                        st.success(
                            "✅ 비밀번호 재설정 이메일을 보냈습니다. 이메일을 확인해주세요."
                        )
                else:
                    st.error("❌ 이메일을 입력해주세요.")

    return st.session_state.get("is_authenticated", False)


def check_authentication():
    """인증 상태 확인 및 세션 복원"""
    session_manager = get_session_manager()
    return session_manager.check_authentication()


def get_current_user():
    """현재 로그인된 사용자 정보 반환"""
    session_manager = get_session_manager()
    return session_manager.get_current_user()


def logout():
    """로그아웃"""
    # 사용자 정보 캐시 삭제
    clear_user_info_cache()
    
    session_manager = get_session_manager()
    session_manager.logout()


def is_first_login() -> bool:
    """현재 사용자가 첫 로그인인지 확인"""
    try:
        user_info = get_current_user()
        if not user_info:
            return False

        uid = user_info.get("localId")
        if not uid:
            return False

        logger = get_firebase_logger()
        if not logger.is_available():
            return False

        # auth_logs에서 해당 사용자의 login 타입 로그를 조회
        login_logs = logger.get_user_logs(uid, limit=10, collection_name="auth_logs")

        # login 타입의 로그만 필터링
        login_records = [log for log in login_logs if log.get("type") == "login"]

        # 첫 번째 로그인이면 True
        return len(login_records) <= 1

    except Exception as e:
        st.error(f"첫 로그인 확인 중 오류: {str(e)}")
        return False


def has_completed_onboarding() -> bool:
    """사용자가 온보딩을 완료했는지 확인 (PostgreSQL API 기반)"""
    try:
        # 캐시된 사용자 정보 사용
        cached_info = get_cached_user_info()
        if cached_info:
            return cached_info.get("has_completed_onboarding", False)
        
        # 캐시 조회 실패 시 Firestore 폴백
        return _check_onboarding_from_firestore()

    except Exception as e:
        st.error(f"온보딩 완료 확인 중 오류: {str(e)}")
        return False


def _check_onboarding_from_firestore() -> bool:
    """Firestore에서 온보딩 완료 여부 확인 (폴백 메서드)"""
    try:
        user_info = get_current_user()
        if not user_info:
            return False

        uid = user_info.get("localId")
        if not uid:
            return False

        logger = get_firebase_logger()
        if not logger.is_available():
            return False

        # onboarding_completed 로그가 있는지 확인
        onboarding_logs = logger.get_user_logs(
            uid, limit=5, collection_name="onboarding_logs"
        )

        for log in onboarding_logs:
            if log.get("type") == "onboarding_completed":
                return True

        return False

    except Exception:
        return False


def get_cached_user_info() -> Optional[Dict[str, Any]]:
    """
    캐시된 사용자 정보 반환 (API 중복 호출 방지)
    
    캐시가 없거나 만료된 경우 API를 호출하여 새로 가져옵니다.
    
    Returns:
        사용자 정보 딕셔너리 또는 None
    """
    from datetime import datetime, timedelta
    
    try:
        # 캐시 유효 시간 (5분)
        cache_validity = timedelta(minutes=5)
        
        # 캐시된 정보 확인
        if "cached_user_info" in st.session_state and "cached_user_info_time" in st.session_state:
            cache_time = st.session_state.cached_user_info_time
            if datetime.now() - cache_time < cache_validity:
                return st.session_state.cached_user_info
        
        # 캐시가 없거나 만료된 경우 API 호출
        user_info = get_current_user()
        if not user_info:
            return None
        
        try:
            import asyncio

            from utils.api_client import get_yamyam_ops_client
            
            client = get_yamyam_ops_client()
            if not client:
                return None
            
            # 비동기 API 호출을 동기적으로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            user_data = loop.run_until_complete(client.get_current_user_info())
            loop.close()
            
            if user_data:
                # 캐시에 저장
                st.session_state.cached_user_info = user_data
                st.session_state.cached_user_info_time = datetime.now()
                return user_data
            
            return None
            
        except Exception as api_error:
            logger = get_firebase_logger()
            if logger.is_available():
                logger.log_error("get_cached_user_info", str(api_error))
            return None
    
    except Exception as e:
        return None


def clear_user_info_cache():
    """사용자 정보 캐시 삭제 (로그아웃 시 또는 온보딩 완료 시 호출)"""
    if "cached_user_info" in st.session_state:
        del st.session_state.cached_user_info
    if "cached_user_info_time" in st.session_state:
        del st.session_state.cached_user_info_time


def get_user_personalization_status() -> Dict[str, Any]:
    """
    사용자 개인화 설정 상태 조회
    
    Returns:
        has_completed_onboarding, is_personalization_enabled 등을 포함한 딕셔너리
    """
    try:
        # 캐시된 사용자 정보 사용
        cached_info = get_cached_user_info()
        if cached_info:
            return {
                "has_completed_onboarding": cached_info.get("has_completed_onboarding", False),
                "is_personalization_enabled": cached_info.get("is_personalization_enabled", False),
            }
        
        # 캐시 조회 실패 시 기본값 반환
        return {
            "has_completed_onboarding": False,
            "is_personalization_enabled": False,
        }

    except Exception as e:
        st.error(f"개인화 설정 확인 중 오류: {str(e)}")
        return {
            "has_completed_onboarding": False,
            "is_personalization_enabled": False,
        }


def require_auth(func):
    """인증이 필요한 페이지에 사용하는 데코레이터"""

    def wrapper(*args, **kwargs):
        if not check_authentication():
            st.warning("⚠️ 로그인이 필요한 서비스입니다.")
            auth_form()
            return
        return func(*args, **kwargs)

    return wrapper


def get_user_profile_from_firestore(uid: str = None) -> Optional[Dict[str, Any]]:
    """Firestore에서 사용자 프로필 데이터를 조회"""
    try:
        # uid가 제공되지 않은 경우 현재 로그인된 사용자의 uid 사용
        if uid is None:
            user_info = get_current_user()
            if not user_info:
                return None
            uid = user_info.get("localId")
            if not uid:
                return None

        # Firebase Admin SDK가 초기화되었는지 확인
        try:
            firebase_admin.get_app()
        except ValueError:
            # Firebase Admin SDK 초기화
            if not initialize_firebase_admin():
                st.error("❌ Firebase Admin SDK 초기화에 실패했습니다.")
                return None

        db = firestore.client()

        # onboarding_logs/profile 문서에서 직접 프로필 데이터 조회
        profile_doc = (
            db.collection("users")
            .document(uid)
            .collection("onboarding_logs")
            .document("profile")
            .get()
        )

        if profile_doc.exists:
            return profile_doc.to_dict()

        return None

    except Exception as e:
        st.error(f"❌ 프로필 데이터 조회 중 오류가 발생했습니다: {str(e)}")
        return None


def organize_user_profile_data(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Firestore에서 가져온 프로필 데이터를 정리하는 헬퍼 함수"""
    if not profile_data:
        return {}

    try:
        # 직접 저장된 프로필 데이터 (detail 래핑 없음)
        organized_data = {
            # 기본 정보
            "basic_info": {
                "age": profile_data.get("birth_year"),
                "gender": profile_data.get("gender"),
                "user_id": profile_data.get("user_id"),
                "created_at": profile_data.get("created_at"),
                "updated_at": profile_data.get("updated_at"),
                "onboarding_version": profile_data.get("onboarding_version", "1.0"),
            },
            # 예산 정보
            "budget_info": {
                "regular_budget": profile_data.get("regular_budget"),
                "special_budget": profile_data.get("special_budget"),
            },
            # 맵기 정보
            "spice_level": profile_data.get("spice_level"),
            # 식사 동반자 정보
            "dining_companions": profile_data.get("dining_companions", []),
            # 못 먹는 것들
            "dislikes": profile_data.get("dislikes", []),
            # 알러지 정보
            "allergies": profile_data.get("allergies", []),
            # 선호 카테고리 (대분류)
            "food_preferences_large": profile_data.get("food_preferences_large", []),
            # 선호 카테고리 (중분류) - 기존 호환성
            "food_preferences": profile_data.get("food_preferences", []),
            # 평점 정보
            "ratings": profile_data.get("ratings", {}),
            # 메타 정보
            "metadata": {
                "created_at": profile_data.get("created_at"),
                "updated_at": profile_data.get("updated_at"),
                "onboarding_version": profile_data.get("onboarding_version"),
            },
        }

        return organized_data

    except Exception as e:
        st.error(f"❌ 프로필 데이터 정리 중 오류가 발생했습니다: {str(e)}")
        return {}


def get_organized_user_profile(uid: str = None) -> Dict[str, Any]:
    """사용자 프로필 데이터를 조회하고 정리해서 반환하는 통합 함수"""
    profile_data = get_user_profile_from_firestore(uid)
    if not profile_data:
        return {}

    return organize_user_profile_data(profile_data)


def get_user_ratings_summary(uid: str = None) -> Dict[str, Any]:
    """사용자 평점 정보를 요약해서 반환"""
    try:
        organized_profile = get_organized_user_profile(uid)
        if not organized_profile:
            return {}

        ratings = organized_profile.get("ratings", {})
        if not ratings:
            return {
                "total_rated": 0,
                "average_rating": 0,
                "rating_distribution": {},
                "rated_restaurants": [],
            }

        # 평점 통계 계산
        rated_restaurants = []
        rating_values = []
        rating_distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}

        for restaurant_idx, rating in ratings.items():
            if rating is not None:
                diner_idx_str = restaurant_idx.split("_")[-1]
                diner_idx = int(diner_idx_str)
                rated_restaurants.append(
                    {
                        "diner_idx": diner_idx,
                        "rating": rating,
                    }
                )
                rating_values.append(rating)
                rating_distribution[str(rating)] += 1

        average_rating = sum(rating_values) / len(rating_values) if rating_values else 0

        return {
            "total_rated": len(rated_restaurants),
            "average_rating": round(average_rating, 2),
            "rating_distribution": rating_distribution,
            "rated_restaurants": sorted(
                rated_restaurants, key=lambda x: x.get("timestamp", ""), reverse=True
            ),
        }

    except Exception as e:
        st.error(f"❌ 평점 요약 생성 중 오류가 발생했습니다: {str(e)}")
        return {}


def get_user_preferences_summary(uid: str = None) -> Dict[str, Any]:
    """사용자 선호도 정보를 요약해서 반환"""
    try:
        organized_profile = get_organized_user_profile(uid)
        if not organized_profile:
            return {}

        return {
            "spice_level": organized_profile.get("spice_level"),
            "budget_range": {
                "regular": organized_profile.get("budget_info", {}).get(
                    "regular_budget"
                ),
                "special": organized_profile.get("budget_info", {}).get(
                    "special_budget"
                ),
            },
            "dining_companions": organized_profile.get("dining_companions", []),
            "food_preferences_large": organized_profile.get(
                "food_preferences_large", []
            ),
            "food_preferences": organized_profile.get("food_preferences", []),
            "dislikes": organized_profile.get("dislikes", []),
            "allergies": organized_profile.get("allergies", []),
            "demographic": {
                "age": organized_profile.get("basic_info", {}).get("age"),
                "gender": organized_profile.get("basic_info", {}).get("gender"),
            },
        }

    except Exception as e:
        st.error(f"❌ 선호도 요약 생성 중 오류가 발생했습니다: {str(e)}")
        return {}
