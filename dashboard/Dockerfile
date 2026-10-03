# Production dashboard image: Streamlit over the Postgres analytics layer.
# Build: docker compose build dashboard
FROM python:3.11-slim

WORKDIR /app
COPY dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dashboard/ ./dashboard/

EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "dashboard/home.py", "--server.port=8501", "--server.address=0.0.0.0"]
