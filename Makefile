.PHONY: install dev run test lint format clean help

# 기본 타겟
help:
	@echo "사용 가능한 명령어:"
	@echo "  install    - 의존성 설치"
	@echo "  dev        - 개발 의존성 포함하여 설치"
	@echo "  run        - Streamlit 애플리케이션 실행"
	@echo "  test       - 테스트 실행"
	@echo "  lint       - 코드 린팅"
	@echo "  format     - 코드 포맷팅"
	@echo "  clean      - 캐시 및 임시 파일 정리"

# 의존성 설치
install:
	uv sync

# 개발 의존성 포함 설치
dev:
	uv sync --all-extras

# 애플리케이션 실행
run:
	uv run streamlit run src/main.py

# 테스트 실행
test:
	uv run pytest

# 코드 린팅
lint:
	uv run flake8 src/
	uv run mypy src/

# 코드 포맷팅
format:
	uv run black src/
	uv run isort src/

# 정리
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 