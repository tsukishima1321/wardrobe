import json
import logging
from django.conf import settings
from wardrobe_db.models import Messages
from django.utils import timezone

logger = logging.getLogger('db')
LOCALHOST = settings.LOCALHOST

def _extract_body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            return {}
    return request.POST

def create_message(level, message_type, text, status='unread', link=''):
    today = timezone.now().date()
    if Messages.objects.filter(text=text, timestamp__date=today).exists():
        logger.info(f'Message already exists for today: {text}')
        return
    msg = Messages(level=level, message_type=message_type, text=text, status=status, link=link)
    msg.save()
    logger.info(f'Created message: {text} with level: {level}, type: {message_type}, status: {status}, link: {link}')
    return msg
