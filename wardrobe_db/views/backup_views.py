from django.http import HttpResponse
from wardrobe_db.models import BackupRecords
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
import json
import requests
from django.conf import settings
import subprocess

BACKUP_PATH = settings.BACKUP_PATH

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_backups(request):
    backups = BackupRecords.objects.all().order_by('-timestamp')
    backup_list = [
        {
            'timestamp': backup.timestamp,
            'comment': backup.comment
        }
        for backup in backups
    ]
    return HttpResponse(json.dumps(backup_list), content_type="application/json")

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_backup(request):
    try:
        result = subprocess.run([settings.BACKUP_SCRIPT_PATH], check=True, text=True, capture_output=True)
        timestamp = result.stdout.strip()
        comment = request.data.get('comment', '')
        BackupRecords.objects.create(timestamp=timestamp, comment=comment)
        return HttpResponse(json.dumps({'status': 'success'}), content_type="application/json")
    except subprocess.CalledProcessError as e:
        return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), content_type="application/json", status=500)

@api_view(['GET'])
@permission_classes([])
def download_backup(request):
    timestamp = request.GET.get('timestamp')
    token = request.GET.get('token')

    if not timestamp:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Timestamp is required'}), content_type="application/json", status=400)
    
    if not token:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Token is required'}), content_type="application/json", status=401)

    try:
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        if not user or not user.is_authenticated:
             return HttpResponse(json.dumps({'status': 'error', 'message': 'Authentication failed'}), content_type="application/json", status=401)
    except Exception:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Invalid token'}), content_type="application/json", status=401)
    
    backup_file_path = f"{BACKUP_PATH}/backups/{timestamp}.tar.gz"
    try:
        with open(backup_file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/gzip')
            response['Content-Disposition'] = f'attachment; filename="{timestamp}.tar.gz"'
            return response
    except FileNotFoundError:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Backup file not found'}), content_type="application/json", status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_backup(request):
    timestamp = request.data.get('timestamp')
    if not timestamp:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Timestamp is required'}), content_type="application/json", status=400)
    
    try:
        backup_record = BackupRecords.objects.get(timestamp=timestamp)
        backup_record.delete()
        
        backup_file_path = f"{BACKUP_PATH}/backups/{timestamp}.tar.gz"
        subprocess.run(['rm', '-f', backup_file_path], check=True)
        
        return HttpResponse(json.dumps({'status': 'success'}), content_type="application/json")
    except BackupRecords.DoesNotExist:
        return HttpResponse(json.dumps({'status': 'error', 'message': 'Backup record not found'}), content_type="application/json", status=404)
    except subprocess.CalledProcessError as e:
        return HttpResponse(json.dumps({'status': 'error', 'message': str(e)}), content_type="application/json", status=500)