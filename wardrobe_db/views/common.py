import json
import logging
from django.conf import settings

logger = logging.getLogger('db')
LOCALHOST = settings.LOCALHOST

def _extract_body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            return {}
    return request.POST
