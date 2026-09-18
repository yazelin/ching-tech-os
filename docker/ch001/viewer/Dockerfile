FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.34.0" psycopg2-binary==2.9.10
COPY main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
