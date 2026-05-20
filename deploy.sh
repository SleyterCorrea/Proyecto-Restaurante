#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Seeding data..."
# Run seed data to ensure users and basic config exist
python seed_data.py

echo "Starting Gunicorn..."
gunicorn restaurant.wsgi --bind 0.0.0.0:$PORT
