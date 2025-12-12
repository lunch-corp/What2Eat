import json
import os
from pathlib import Path
from typing import Any, Optional

import firebase_admin
import streamlit as st
from firebase_admin import credentials


def get_service_account_path() -> Optional[str]:
    """
    Firebase Admin SDK 서비스 계정 키 파일 경로를 반환합니다.
    우선순위: 환경변수 > 기본 경로
    """
    # 환경변수에서 경로 확인
    if service_account_path := os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH"):
        return service_account_path

    # 기본 경로 확인
    default_path = Path(__file__).parent / "firebase-service-account.json"
    return str(default_path) if default_path.exists() else None


def get_service_account_info() -> Optional[dict[str, Any]]:
    """
    Firebase Admin SDK 서비스 계정 정보를 반환합니다.
    우선순위: Streamlit secrets > 파일 > None
    """
    # Streamlit secrets에서 확인
    if hasattr(st, "secrets") and "FIREBASE_KEY" in st.secrets:
        firebase_key = json.loads(st.secrets["FIREBASE_KEY"])
        return firebase_key

    # 서비스 계정 키 파일에서 확인
    if service_account_path := get_service_account_path():
        try:
            with open(service_account_path, "r") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"❌ 서비스 계정 키 파일을 읽는 중 오류가 발생했습니다: {str(e)}")
            return None

    return None


def initialize_firebase_admin() -> bool:
    """
    Firebase Admin SDK를 초기화합니다.
    """
    try:
        # 이미 초기화되었는지 확인
        firebase_admin.get_app()
        return True
    except ValueError:
        # 서비스 계정 정보 가져오기
        if service_account_info := get_service_account_info():
            try:
                # Firebase Admin SDK 초기화
                cred = credentials.Certificate(service_account_info)
                firebase_admin.initialize_app(cred)
                return True
            except Exception as e:
                st.error(
                    f"❌ Firebase Admin SDK 초기화 중 오류가 발생했습니다: {str(e)}"
                )
                return False
        else:
            st.error("❌ Firebase 서비스 계정 정보를 찾을 수 없습니다.")
            return False


def get_firebase_web_config() -> dict[str, Any]:
    """
    Firebase Web SDK 설정 정보를 반환합니다. (Google 로그인용)
    우선순위: streamlit secrets > 환경변수 > 기본값
    """
    # Streamlit secrets에서 Firebase 설정 가져오기
    if hasattr(st, "secrets") and "firebase" in st.secrets:
        return {
            "apiKey": st.secrets.firebase.api_key,
            "authDomain": st.secrets.firebase.auth_domain,
            "projectId": st.secrets.firebase.project_id,
            "storageBucket": st.secrets.firebase.storage_bucket,
            "messagingSenderId": st.secrets.firebase.messaging_sender_id,
            "appId": st.secrets.firebase.app_id,
            "databaseURL": st.secrets.firebase.get("database_url", ""),
        }

    # 환경변수에서 Firebase 설정 가져오기
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", ""),
        "databaseURL": os.getenv("FIREBASE_DATABASE_URL", ""),
    }


def is_firebase_configured() -> bool:
    """
    Firebase가 올바르게 설정되었는지 확인합니다.
    """
    # Admin SDK 설정 확인
    if not get_service_account_info():
        return False

    # Web SDK 설정 확인 (Google 로그인용)
    web_config = get_firebase_web_config()
    required_fields = ["apiKey", "authDomain", "projectId"]
    if not all(web_config.get(field) for field in required_fields):
        return False

    return True
