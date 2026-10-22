"""Celery entry point: `celery -A safer.worker worker`. Separate so importing jobs stays cheap."""

from safer.jobs import configure

app = configure()
