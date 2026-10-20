# Build from the repo root:  docker build -f backend/Dockerfile -t lab2-backend .
FROM python:3.12-slim
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY analysis/follow_counts.py /srv/analysis/follow_counts.py
ENV LOCAL_SCRIPT=/srv/analysis/follow_counts.py
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
