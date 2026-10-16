FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 libapache2-mod-php8.2 php8.2-curl ca-certificates supervisor \
    && a2enmod rewrite && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-render.txt ./
RUN pip install --no-cache-dir -r requirements-render.txt
COPY app ./app
COPY web ./web
COPY deploy ./deploy
COPY wsgi.py ./
COPY manage_admin.py ./
COPY asgi.py worker.py ./
RUN cp deploy/php.ini /etc/php/8.2/apache2/conf.d/99-photo.ini
EXPOSE 10000
CMD ["python", "deploy/start.py"]
