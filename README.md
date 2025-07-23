# What2Eat - 음식점 추천 시스템

## 개요
사용자의 위치와 선호도를 기반으로 음식점을 추천하는 시스템입니다.

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. Firebase 설정

#### Firebase Web API Key 설정
실제 비밀번호 기반 로그인을 사용하려면 Firebase Web API Key가 필요합니다.

**방법 1: 환경 변수 사용 (권장)**
1. Firebase Console (https://console.firebase.google.com)에 접속
2. 프로젝트 선택
3. 프로젝트 설정 → 일반 탭
4. "웹 API 키" 값을 복사
5. `example.env` 파일을 `.env`로 복사하고 API 키 입력:
   ```bash
   cp example.env .env
   # .env 파일에서 FIREBASE_WEB_API_KEY 값을 실제 키로 교체
   ```
6. 환경 변수 로드:
   ```bash
   export $(cat .env | xargs)  # Linux/macOS
   ```

**방법 2: 직접 코드 수정**
`src/streamlit_test.py` 파일에서 다음 라인을 수정:
```python
FIREBASE_WEB_API_KEY = "your-actual-web-api-key-here"  # 실제 Web API Key로 교체
```

#### Firebase Authentication 활성화
1. Firebase Console → Authentication → Sign-in method
2. 이메일/비밀번호 로그인 방식 활성화

### 3. 실행
```bash
streamlit run src/streamlit_test.py
```

## 기능

### 인증 시스템
- **회원가입**: 이메일/비밀번호 기반 계정 생성
- **로그인**: Firebase Authentication REST API를 통한 실제 비밀번호 검증
- **로그아웃**: 세션 관리
- **보안**: 
  - 비밀번호 6자 이상 요구
  - 비밀번호 확인 검증
  - Firebase 보안 토큰 사용

### 활동 로그
- 위치 기반 검색 로그
- 카테고리 선택 로그  
- 음식점 클릭 로그
- 시간순 정렬된 활동 내역 조회

## 보안 주의사항
- Firebase Web API Key는 공개 저장소에 올리지 마세요
- 환경 변수나 별도 설정 파일을 사용하는 것을 권장합니다
- 프로덕션 환경에서는 Firebase 보안 규칙을 적절히 설정하세요 