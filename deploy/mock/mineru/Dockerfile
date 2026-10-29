# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install fastapi==0.141.1 "uvicorn[standard]==0.35.0" "python-multipart==0.0.20" "PyMuPDF==1.26.6"
COPY deploy/mock/mineru/main.py main.py
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
