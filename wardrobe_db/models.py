# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = True` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Pictures(models.Model):
    href = models.CharField(primary_key=True, max_length=100)
    description = models.CharField(max_length=100, db_collation='utf8mb3_general_ci', blank=True, null=True)
    type = models.ForeignKey('Types', models.DO_NOTHING, db_column='type', to_field='typename')
    date = models.DateField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'pictures'


class PicturesOcr(models.Model):
    href = models.OneToOneField(Pictures, models.DO_NOTHING, db_column='href', primary_key=True)
    ocr_result = models.TextField()

    class Meta:
        managed = True
        db_table = 'pictures_ocr'


class Statistics(models.Model):
    totalamount = models.IntegerField()
    lastyearamount = models.IntegerField()
    lastmonthamount = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'statistics'


class StatisticsByType(models.Model):
    typename = models.CharField(unique=True, max_length=20, primary_key=True)
    totalamount = models.IntegerField()
    lastyearamount = models.IntegerField()
    lastmonthamount = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'statistics_by_type'

class Types(models.Model):
    typename = models.CharField(unique=True, max_length=20)

    class Meta:
        managed = True
        db_table = 'types'

class OcrMission(models.Model):
    id = models.AutoField(primary_key=True)
    href = models.ForeignKey(Pictures, models.DO_NOTHING, db_column='href')
    status = models.CharField(max_length=20)

    class Meta:
        managed = True
        db_table = 'ocr_mission'