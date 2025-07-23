from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import firebase_admin
import requests
import streamlit as st
from firebase_admin import auth

from config.firebase_config import initialize_firebase_admin
from utils.firebase_logger import get_firebase_logger
from utils.session_manager import get_session_manager


class FirebaseAuth:
    """Firebase Authentication을 관리하는 클래스"""

    def __init__(self):
        self.session_manager = get_session_manager()

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

            # 세션에 저장
            self.session_manager.save_user_session(
                user_data,
                custom_token.decode(),
                None,  # 회원가입 시에는 refresh_token이 없음
            )

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
            # Firebase Web API Key 가져오기
            FIREBASE_WEB_API_KEY = st.secrets["FIREBASE_WEB_API_KEY"]

            if not FIREBASE_WEB_API_KEY:
                st.error("❌ Firebase Web API Key가 설정되지 않았습니다.")
                return None

            # Firebase Authentication REST API를 사용하여 인증
            auth_result = self._authenticate_user_with_rest_api(
                email, password, FIREBASE_WEB_API_KEY
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

                # 세션 매니저를 통해 로그인 상태 저장
                if self.session_manager.save_user_session(
                    user_data, auth_result["id_token"], auth_result["refresh_token"]
                ):
                    st.success("✅ 로그인되었습니다!")
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
        """비밀번호 재설정 이메일 전송"""
        try:
            # 사용자 존재 여부 확인
            user = auth.get_user_by_email(email)

            # 비밀번호 재설정 링크 생성
            action_code_settings = auth.ActionCodeSettings(
                url=f"https://{st.get_option('browser.serverAddress')}/reset-password",
                handle_code_in_app=True,
            )

            # 재설정 링크 이메일 전송
            auth.generate_password_reset_link(
                email, action_code_settings=action_code_settings
            )
            return True
        except auth.UserNotFoundError:
            st.error("❌ 등록되지 않은 이메일입니다.")
        except Exception as e:
            st.error(f"❌ 비밀번호 재설정 중 오류가 발생했습니다: {str(e)}")
        return False

    def sign_out(self):
        """로그아웃"""
        self.session_manager.logout()

    def verify_id_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """ID 토큰 검증"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            st.error(f"❌ 토큰 검증 중 오류가 발생했습니다: {str(e)}")
            return None


# def google_auth_component():
#     """Google 로그인을 위한 HTML/JavaScript 컴포넌트"""
#     firebase_config = get_firebase_web_config()

#     if not firebase_config.get("apiKey"):
#         st.error("❌ Firebase 설정이 필요합니다.")
#         return None

#     html_code = f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <script src="https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js"></script>
#         <script src="https://www.gstatic.com/firebasejs/9.23.0/firebase-auth-compat.js"></script>
#         <style>
#             .auth-container {{
#                 max-width: 400px;
#                 margin: 0 auto;
#                 padding: 20px;
#                 font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
#             }}

#             .google-btn {{
#                 width: 100%;
#                 height: 50px;
#                 background-color: #4285f4;
#                 color: white;
#                 border: none;
#                 border-radius: 8px;
#                 font-size: 16px;
#                 font-weight: 500;
#                 cursor: pointer;
#                 display: flex;
#                 align-items: center;
#                 justify-content: center;
#                 gap: 10px;
#                 transition: all 0.2s ease;
#                 margin-bottom: 10px;
#             }}

#             .google-btn:hover {{
#                 background-color: #3367d6;
#                 box-shadow: 0 2px 8px rgba(66, 133, 244, 0.3);
#             }}

#             .google-btn:disabled {{
#                 background-color: #cccccc;
#                 cursor: not-allowed;
#             }}

#             .error-message {{
#                 color: #d93025;
#                 font-size: 14px;
#                 margin-top: 10px;
#                 padding: 10px;
#                 background-color: #fce8e6;
#                 border-radius: 4px;
#                 border-left: 3px solid #d93025;
#             }}

#             .success-message {{
#                 color: #137333;
#                 font-size: 14px;
#                 margin-top: 10px;
#                 padding: 10px;
#                 background-color: #e6f4ea;
#                 border-radius: 4px;
#                 border-left: 3px solid #137333;
#             }}
#         </style>
#     </head>
#     <body>
#         <div class="auth-container">
#             <button id="google-signin-btn" class="google-btn">
#                 <svg width="20" height="20" viewBox="0 0 24 24">
#                     <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
#                     <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
#                     <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
#                     <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
#                 </svg>
#                 Google로 로그인
#             </button>
#             <div id="message"></div>
#         </div>

#         <script>
#             const firebaseConfig = {json.dumps(firebase_config)};

#             // Firebase 초기화
#             firebase.initializeApp(firebaseConfig);
#             const auth = firebase.auth();

#             // Google 로그인 버튼 이벤트
#             document.getElementById('google-signin-btn').addEventListener('click', function() {{
#                 const provider = new firebase.auth.GoogleAuthProvider();
#                 provider.addScope('email');
#                 provider.addScope('profile');

#                 this.disabled = true;
#                 this.textContent = '로그인 중...';

#                 auth.signInWithPopup(provider)
#                     .then((result) => {{
#                         const user = result.user;
#                         const userInfo = {{
#                             uid: user.uid,
#                             email: user.email,
#                             displayName: user.displayName,
#                             photoURL: user.photoURL,
#                             emailVerified: user.emailVerified
#                         }};

#                         // Streamlit으로 사용자 정보 전달
#                         window.parent.postMessage({{
#                             type: 'GOOGLE_AUTH_SUCCESS',
#                             user: userInfo,
#                             idToken: result.credential.idToken
#                         }}, '*');

#                         document.getElementById('message').innerHTML =
#                             '<div class="success-message">✅ 로그인 성공!</div>';
#                     }})
#                     .catch((error) => {{
#                         console.error('로그인 오류:', error);
#                         document.getElementById('message').innerHTML =
#                             '<div class="error-message">❌ 로그인 실패: ' + error.message + '</div>';

#                         this.disabled = false;
#                         this.innerHTML = `
#                             <svg width="20" height="20" viewBox="0 0 24 24">
#                                 <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
#                                 <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
#                                 <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
#                                 <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
#                             </svg>
#                             Google로 로그인
#                         `;
#                     }});
#             }});

#             // 메시지 리스너 (Streamlit으로부터)
#             window.addEventListener('message', function(event) {{
#                 if (event.data.type === 'RESET_GOOGLE_AUTH') {{
#                     const btn = document.getElementById('google-signin-btn');
#                     btn.disabled = false;
#                     btn.innerHTML = `
#                         <svg width="20" height="20" viewBox="0 0 24 24">
#                             <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
#                             <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
#                             <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
#                             <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
#                         </svg>
#                         Google로 로그인
#                     `;
#                     document.getElementById('message').innerHTML = '';
#                 }}
#             }});
#         </script>
#     </body>
#     </html>
#     """

#     return components.html(html_code, height=150)


def auth_form():
    """통합 인증 폼 (로그인/회원가입/비밀번호 재설정)"""
    firebase_auth = FirebaseAuth()
    session_manager = get_session_manager()

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
    """사용자가 온보딩을 완료했는지 확인"""
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
            uid, limit=5, collection_name="activity_logs"
        )

        for log in onboarding_logs:
            if log.get("type") == "onboarding_completed":
                return True

        return False

    except Exception as e:
        st.error(f"온보딩 완료 확인 중 오류: {str(e)}")
        return False


def require_auth(func):
    """인증이 필요한 페이지에 사용하는 데코레이터"""

    def wrapper(*args, **kwargs):
        if not check_authentication():
            st.warning("⚠️ 로그인이 필요한 서비스입니다.")
            auth_form()
            return
        return func(*args, **kwargs)

    return wrapper
