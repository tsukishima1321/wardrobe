from django.db import models
from django.db.models import Model


class Pictures(Model):
    href = models.CharField(primary_key=True, max_length=100)
    description = models.CharField(max_length=100, db_collation='utf8mb3_general_ci', blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    is_collection = models.BooleanField(default=False)

    class Meta:
        managed = True
        db_table = 'pictures'


class CollectionItems(Model):
    id = models.AutoField(primary_key=True)
    collection = models.ForeignKey(Pictures, on_delete=models.CASCADE, db_column='collection_href', related_name='collection_items')
    image_href = models.CharField(max_length=200)
    sort_order = models.IntegerField(default=0)
    liked = models.BooleanField(default=False)

    class Meta:
        managed = True
        db_table = 'collection_items'
        ordering = ['-liked', 'sort_order']


class PicturesOcr(Model):
    href = models.OneToOneField(Pictures, models.DO_NOTHING, db_column='href', primary_key=True)
    ocr_result = models.TextField()

    class Meta:
        managed = True
        db_table = 'pictures_ocr'


class Keywords(Model):
    href = models.ForeignKey(Pictures, models.DO_NOTHING, db_column='href')
    keyword = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'keywords'


class Properties(Model):
    href = models.ForeignKey(Pictures, models.DO_NOTHING, db_column='href')
    property_name = models.CharField(max_length=50)
    value = models.CharField(max_length=100)

    class Meta:
        managed = True
        db_table = 'properties'


class Statistics(Model):
    totalamount = models.IntegerField()
    lastyearamount = models.IntegerField()
    lastmonthamount = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'statistics'


class StatisticsByKeyword(Model):
    keyword = models.CharField(unique=True, max_length=50, primary_key=True)
    totalamount = models.IntegerField()
    lastyearamount = models.IntegerField()
    lastmonthamount = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'statistics_by_keyword'


class StatisticsExpanded(Model):
    totalamount = models.IntegerField()
    lastyearamount = models.IntegerField()
    lastmonthamount = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'statistics_expanded'


class StatisticsByKeywordExpanded(Model):
    keyword = models.CharField(unique=True, max_length=50, primary_key=True)
    totalamount = models.IntegerField()
    lastyearamount = models.IntegerField()
    lastmonthamount = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'statistics_by_keyword_expanded'


class OcrMission(Model):
    id = models.AutoField(primary_key=True)
    href = models.ForeignKey(Pictures, models.DO_NOTHING, db_column='href')
    status = models.CharField(max_length=20)

    class Meta:
        managed = True
        db_table = 'ocr_mission'


class SavedSearch(Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    searchparams = models.TextField()

    class Meta:
        managed = True
        db_table = 'saved_search_filter'


class BackupRecords(Model):
    timestamp = models.CharField(primary_key=True)
    comment = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'backup_records'


class Messages(Model):
    id = models.AutoField(primary_key=True)
    message_type = models.CharField(max_length=50)
    text = models.TextField()
    level = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='unread')
    link = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'messages'


class DiaryTexts(Model):
    date = models.DateField()
    text = models.TextField()

    class Meta:
        managed = True
        db_table = 'diary_texts'


class BlankPictures(Model):
    href = models.CharField(primary_key=True, max_length=100)

    class Meta:
        managed = True
        db_table = 'blank_pictures'


class UserDictionary(Model):
    id = models.AutoField(primary_key=True)
    word = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'user_dictionary'