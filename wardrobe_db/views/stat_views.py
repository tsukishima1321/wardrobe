from django.http import HttpResponse
from wardrobe_db.models import Statistics, StatisticsByKeyword, DiaryTexts, BackupRecords, Pictures, Keywords, Messages, Properties
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from django.db import connections
from django.db.models import Max
from .common import create_message
import datetime

def updateStatistics():
    connection = connections['business']
    with connection.cursor() as cursor:
        cursor.callproc('updatestat')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generateTips(request):
    lastDiaryDate = DiaryTexts.objects.aggregate(max_date=Max('date'))['max_date']
    if lastDiaryDate:
        daysSinceLastDiary = (datetime.datetime.now().date() - lastDiaryDate).days
        if daysSinceLastDiary >= 3:
            create_message(
                level='tips',
                message_type='Diary',
                text=f'It has been {daysSinceLastDiary} days since your last diary entry.', link='/diary'
            )

    lastBackupDate = BackupRecords.objects.aggregate(max_timestamp=Max('timestamp'))['max_timestamp']
    if lastBackupDate:
        lastBackupDatetime = datetime.datetime.strptime(lastBackupDate, '%Y%m%d%H%M%S')
        daysSinceLastBackup = (datetime.datetime.now() - lastBackupDatetime).days
        if daysSinceLastBackup >= 5:
            create_message(
                level='warning',
                message_type='Backup',
                text=f'It has been {daysSinceLastBackup} days since your last backup. Please check the auto backup status!', link='/manage'
            )

    # 每月七号生成上月月报
    if datetime.datetime.now().day == 7:
        today = datetime.date.today()
        first_day_of_current_month = today.replace(day=1)
        last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
        year = last_day_of_previous_month.year
        month = last_day_of_previous_month.month

        # Generate monthly report text
        report_title = f"## Monthly Report for {year}-{month:02d}\n"
        
        # Check if a report for the previous month already exists
        if not Messages.objects.filter(message_type='Report', text__startswith=report_title).exists():
            updateStatistics()
            
            report_lines = [report_title]

            # Pictures summary
            pictures = Pictures.objects.filter(date__year=year, date__month=month)
            total_pictures = pictures.count()
            report_lines.append(f"### Pictures\n")
            report_lines.append(f"You added **{total_pictures}** new pictures in {year}-{month:02d}.\n\n")
            
            # Keywords summary
            keyword_counts = {}
            for pic in pictures:
                keywords = Keywords.objects.filter(href=pic.href)
                for kw in keywords:
                    keyword_counts[kw.keyword] = keyword_counts.get(kw.keyword, 0) + 1
            
            if keyword_counts:
                report_lines.append("#### Top 5 Keywords:\n")
                sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
                for kw, count in sorted_keywords[:5]:
                    report_lines.append(f"- **{kw}**: {count} times\n")
                report_lines.append("\n")

            property_counts = {}
            property_name_counts = {}
            for pic in pictures:
                properties = Properties.objects.filter(href=pic.href)
                for prop in properties:
                    property_name_counts[prop.property_name] = property_name_counts.get(prop.property_name, 0) + 1
                    if prop.property_name not in property_counts:
                        property_counts[prop.property_name] = {}
                    property_counts[prop.property_name][prop.value] = property_counts[prop.property_name].get(prop.value, 0) + 1

            if property_counts:
                print(property_counts)
                # display top 1 value for top 2 property names
                sorted_property_names = sorted(property_name_counts.items(), key=lambda x: x[1], reverse=True)
                for prop_name, _ in sorted_property_names[:2]:
                    # report_lines.append(f"- **{prop_name}**:\n")
                    report_lines.append(f"Your most common **{prop_name}** is ")
                    sorted_values = sorted(property_counts[prop_name].items(), key=lambda x: x[1], reverse=True)
                    top_value, top_count = sorted_values[0]
                    report_lines.append(f"**{top_value}** for **{top_count}** times. \n")
                report_lines.append("\n")

            # Diary summary
            diary_count = DiaryTexts.objects.filter(date__year=year, date__month=month).count()
            report_lines.append(f"### Diary\n")
            report_lines.append(f"You wrote **{diary_count}** diary entries.\n")
            
            report_text = "".join(report_lines)
            
            create_message(
            level='tips',
            message_type='Report',
            text=report_text,
            link='/search?dateFrom={}-{:02d}-01&dateTo={}-{:02d}-{}'.format(year, month, year, month, last_day_of_previous_month.day)
            )
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

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
