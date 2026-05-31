FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
RUN playwright install chromium --with-deps
COPY scraper/ ./scraper/
CMD ["python", "-m", "scraper.worker"]
