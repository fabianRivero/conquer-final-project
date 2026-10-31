"""The WSGI entry point.

The Render run command is
`gunicorn config.wsgi:application --chdir backend --workers 1 --threads 2`
(design §18.1).
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
