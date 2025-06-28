# Use slim Python image for minimal footprint
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application code
COPY stealthninja.py .

# Expose port for Render
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "stealthninja:app", "--host", "0.0.0.0", "--port", "8000"]
