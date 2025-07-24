from django.db import models

# Create your models here.

class Texts(models.Model):
    date = models.DateField()
    text = models.TextField()

    class Meta:
        managed = True
        db_table = 'diary_texts'