FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for Playwright and Selenium
RUN apt-get update && apt-get install -y \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libnspr4 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxss1 \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy application files
COPY main.py .
COPY stealthninja.py .

# Set default port (Render overrides with $PORT)
ENV PORT=8000

# Use shell form to ensure $PORT substitution
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
