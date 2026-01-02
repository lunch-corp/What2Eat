# What2Eat 🍽️

## 소개

What2Eat는 카카오 리뷰 데이터에 기반하여 인기도 기반 식당 추천과 ML 모델을 활용한 개인화 추천 서비스를 제공합니다.

What2Eat 서비스는 현재 streamlit을 사용하여 서빙되고 있으며 [이 페이지](https://what2eat.streamlit.app/)에서 서비스를 이용하실 수 있습니다.

## 관련 프로젝트

What2Eat에서 사용하는 API는 [yamyam-ops](https://github.com/lunch-corp/yamyam-ops/tree/main) 레포지토리에서 개발합니다.

또한 추천에 사용되는 로직은 [yamyam-labs](https://github.com/lunch-corp/yamyam-lab) 레포지토리에서 개발합니다.

저희는 Open-Source 프로젝트를 지향하기 때문에 개발자 분들의 contribution은 언제든 환영입니다.

## 빠른 시작

### 1. 의존성 설치
```bash
make install
```

### 2. Secret 변수 설정

`.streamlit/secrets.toml`에 환경 변수를 설정해야 합니다. issue에 이메일을 남겨주시면 설정해야하는 환경 변수를 전달드리겠습니다.

### 3. 애플리케이션 실행
```bash
make run
```

## 참고 자료
이 프로젝트는 모두의 연구소의 지원을 받고 진행되었습니다. 저희는 [2025 모두콘](https://moducon.modulabs.co.kr/session/10-07)에서 1년간 저희가 진행한 프로젝트의 결과물을 발표했습니다.