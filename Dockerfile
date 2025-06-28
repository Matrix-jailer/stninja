FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    gcc g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/.playwright && chown -R appuser:appuser /app/.playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright
RUN useradd -m appuser
RUN PLAYWRIGHT_BROWSERS_PATH=/app/.playwright playwright install chromium
COPY stealthninja.py .
USER appuser
EXPOSE 8000
CMD ["uvicorn", "stealthninja:app", "--host", "0.0.0.0", "--port", "8000"]
