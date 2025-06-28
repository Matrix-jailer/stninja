# Use a slim Python 3.10 base image for efficiency
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright and Selenium
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libcups2 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium)
RUN playwright install chromium

# Copy the script
COPY stealth_payment_detector.py .

# Set the start command for Render (using Uvicorn)
CMD ["uvicorn", "stealth_payment_detector:app", "--host", "0.0.0.0", "--port", "80"]