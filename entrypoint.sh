#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
while ! nc -z postgres 5432; do
  sleep 0.1
done
echo "Database started"

# Wait for Redis to be ready
echo "Waiting for Redis..."
while ! nc -z redis 6379; do
  sleep 0.1
done
echo "Redis started"

# Run database migrations
echo "Running database migrations..."
python manage.py makemigrations
python manage.py migrate

# Create superuser if it doesn't exist
echo "Creating superuser..."
python manage.py shell << EOF
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created')
else:
    print('Superuser already exists')
EOF

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Download model weights if not present (you'll need to implement this)
echo "Checking for model weights..."
if [ ! -f "/app/models/diffhdr_weights.pth" ]; then
    echo "Model weights not found. You need to download them manually."
    echo "Place the DiffHDR model weights in /app/models/diffhdr_weights.pth"
fi

# Start the application
echo "Starting Django application..."
if [ "$1" = "celery" ]; then
    # Start Celery worker
    exec celery -A hdr_project worker -l info --concurrency=2
elif [ "$1" = "celery-beat" ]; then
    # Start Celery beat scheduler
    exec celery -A hdr_project beat -l info
else
    # Start Django with Gunicorn (changed from gevent to sync worker)
    exec gunicorn hdr_project.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --worker-class sync \
        --timeout 300 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --preload \
        --access-logfile - \
        --error-logfile - \
        --log-level info
fi