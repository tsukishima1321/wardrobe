from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from wardrobe_db.models import Messages
from django.db.models import Max
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from asgiref.sync import sync_to_async
from typing import AsyncGenerator
import asyncio
import json
import time
from .common import _extract_body

async def streamMessages(request: HttpRequest) -> StreamingHttpResponse:
    if request.method != 'GET':
        return HttpResponse(status=405)
    token = request.GET.get('token')
    try:
        jwt_auth = JWTAuthentication()
        validated_token = await sync_to_async(jwt_auth.get_validated_token)(token)
        user = await sync_to_async(jwt_auth.get_user)(validated_token)
        if not user or not user.is_authenticated:
             return HttpResponse(json.dumps({'status': 'error', 'message': 'Authentication failed'}), content_type="application/json", status=401)
    except Exception:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Invalid token'}), content_type="application/json", status=401)
    
    async def event_stream() -> AsyncGenerator[str, None]:
        get_max_id = sync_to_async(lambda: Messages.objects.aggregate(max_id=Max('id'))['max_id'] or 0)
        last_id = await get_max_id()
        
        while True:
            def get_new_messages():
                return list(Messages.objects.filter(id__gt=last_id).order_by('id'))
            
            new_messages = await sync_to_async(get_new_messages)()
            has_new_messages = False
            for msg in new_messages:
                data = json.dumps({
                    'timestamp': msg.timestamp.isoformat(),
                    'level': msg.level,
                    'type': msg.message_type,
                    'text': msg.text,
                    'id': msg.id,
                    'status': msg.status,
                    'link': msg.link
                })
                yield f"data: {data}\n\n"
                last_id = msg.id
                has_new_messages = True
            
            if not has_new_messages:
                yield ": keep-alive\n\n"

            await asyncio.sleep(1)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Connection'] = 'keep-alive'
    return response

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listMessages(request: HttpRequest) -> HttpResponse:
    body = _extract_body(request)
    messages = Messages.objects.all()
    messages = messages.all().order_by('-timestamp')[:100]
    data = [{'timestamp': msg.timestamp.isoformat(), 'level': msg.level, 'type': msg.message_type, 'text': msg.text, 'id': msg.id, 'status': msg.status, 'link': msg.link} for msg in messages]
    return HttpResponse(json.dumps(data), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteMessage(request: HttpRequest) -> HttpResponse:
    body = _extract_body(request)
    msg_id = body.get('id')
    if not msg_id:
        return HttpResponse('Missing message id', status=400)
    deleted_count, _ = Messages.objects.filter(id=msg_id).delete()
    if not deleted_count:
        return HttpResponse('Message does not exist', status=404)
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def readMessage(request: HttpRequest) -> HttpResponse:
    body = _extract_body(request)
    msg_id = body.get('id')
    if not msg_id:
        return HttpResponse('Missing message id', status=400)
    try:
        msg = Messages.objects.get(id=msg_id)
        msg.status = 'read'
        msg.save()
    except Messages.DoesNotExist:
        return HttpResponse('Message does not exist', status=404)
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clearMessage(request: HttpRequest) -> HttpResponse:
    body = _extract_body(request)
    Messages.objects.filter(status='read').delete()
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')