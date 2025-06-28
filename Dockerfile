# Use slim Python image for minimal footprint
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers as root
RUN playwright install chromium

# Create non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app

# Copy application code
COPY stealthninja.py .

# Switch to non-root user
USER appuser

# Expose port for Render
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "stealthninja:app", "--host", "0.0.0.0", "--port", "8000"]
