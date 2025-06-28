FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    gcc g++ && rm -rf /var/lib/apt/lists/*

# Create the user BEFORE chown
RUN useradd -m appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set Playwright browser path and set ownership
RUN mkdir -p /app/.playwright && chown -R appuser:appuser /app/.playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

# Install Playwright browser(s)
RUN PLAYWRIGHT_BROWSERS_PATH=/app/.playwright playwright install chromium

# Copy your app code
COPY stealthninja.py .

# Use non-root user
USER appuser

# Expose port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "stealthninja:app", "--host", "0.0.0.0", "--port", "8000"]
