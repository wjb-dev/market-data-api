#########################################################
#                    Python FastAPI                     #
#########################################################
FROM python:3.12-slim
# --------------------------------------------------
# Environment Setup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8
# --------------------------------------------------
# Working Directory
WORKDIR /app
# --------------------------------------------------
# Install System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl netcat-openbsd gcc libpq-dev build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# --------------------------------------------------
# Install Python Dependencies (cache efficient)
COPY requirements.txt .
RUN pip install -r requirements.txt
# --------------------------------------------------
# Copy Application Source
COPY src /app/src
# --------------------------------------------------
# Entrypoint
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
