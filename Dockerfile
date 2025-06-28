FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright & Chromium
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    gcc g++ wget curl unzip fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m appuser

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Prepare directory for Playwright browsers and give user permissions
RUN mkdir -p /app/.playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright

# Install Playwright browsers (Chromium only)
RUN PLAYWRIGHT_BROWSERS_PATH=/app/.playwright playwright install chromium

# Copy app code and fix permissions
COPY stealthninja.py .
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Run the FastAPI app with uvicorn
CMD ["uvicorn", "stealthninja:app", "--host", "0.0.0.0", "--port", "8000"]
