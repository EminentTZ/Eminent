FROM python:3.11-slim

WORKDIR /app

# System deps needed to build psycopg2-binary's wheel dependencies on some
# base images and for general TLS support.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Uploaded documents (driver licenses, vehicle docs, POD photos) are written
# here at runtime. Without a persistent disk mounted at this path, anything
# written here is lost on restart/redeploy -- fine for a free-tier trial,
# but attach a Render persistent disk at this path (or move to S3-compatible
# storage) before relying on uploads in real production use.
RUN mkdir -p /app/app/uploads

EXPOSE 8000

# Render (and most PaaS) inject the port to bind via $PORT; default to 8000
# for running the image locally/elsewhere.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
