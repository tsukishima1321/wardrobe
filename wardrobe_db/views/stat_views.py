from django.http import HttpResponse
from wardrobe_db.models import Statistics, StatisticsByKeyword
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from django.db import connections

def updateStatistics():
    connection = connections['business']
    with connection.cursor() as cursor:
        cursor.callproc('updatestat')
        return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getStatistics(request):
    updateStatistics()
    statistics = Statistics.objects.get()
    overall = {'totalAmount': statistics.totalamount, 'lastYearAmount': statistics.lastyearamount, 'lastMonthAmount': statistics.lastmonthamount}
    statisticsByKeyword = StatisticsByKeyword.objects.all()
    typeList = []
    for s in statisticsByKeyword:
        typename = s.keyword
        typeList.append({'type': typename, 'totalAmount': s.totalamount, 'lastYearAmount': s.lastyearamount, 'lastMonthAmount': s.lastmonthamount})
    response = {'overall': overall, 'types': typeList}
    return HttpResponse(json.dumps(response), content_type='application/json')
