import datetime

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

class BlogPost(Model):
    title = models.CharField(max_length=200, blank=True, default='')
    kind = models.CharField(max_length=20, default='note')
    status = models.CharField(max_length=20, default='draft')
    date = models.DateField(default=datetime.date.today)
    content_json = models.JSONField(default=dict, blank=True)
    content_html = models.TextField(blank=True, default='')
    content_text = models.TextField(blank=True, default='')
    excerpt = models.CharField(max_length=500, blank=True, default='')
    cover_image_href = models.CharField(max_length=200, blank=True, null=True)
    word_count = models.IntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    legacy_diary_id = models.IntegerField(unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    tags = models.ManyToManyField('BlogTag', through='BlogPostTag', related_name='posts', blank=True)

    class Meta:
        managed = True
        db_table = 'blog_posts'
        ordering = ['-date', '-id']
        indexes = [
            models.Index(fields=['status', '-date', '-id'], name='blog_status_date_idx'),
            models.Index(fields=['-date', '-id'], name='blog_date_idx'),
        ]


class BlogTag(Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'blog_tags'
        ordering = ['name']


class BlogPostTag(Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, db_column='post_id', related_name='post_tags')
    tag = models.ForeignKey(BlogTag, on_delete=models.CASCADE, db_column='tag_id', related_name='post_tags')

    class Meta:
        managed = True
        db_table = 'blog_post_tags'
        constraints = [
            models.UniqueConstraint(fields=['post', 'tag'], name='uniq_blog_post_tag'),
        ]
        indexes = [
            models.Index(fields=['tag', 'post'], name='blog_tag_post_idx'),
        ]


class BlogPostImage(Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, db_column='post_id', related_name='image_links')
    image_href = models.CharField(max_length=200)
    collection_href = models.CharField(max_length=200, blank=True, null=True)
    role = models.CharField(max_length=20, default='inline')
    origin = models.CharField(max_length=20, default='library')
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'blog_post_images'
        constraints = [
            models.UniqueConstraint(fields=['post', 'image_href'], name='uniq_blog_post_image'),
        ]
        indexes = [
            models.Index(fields=['image_href'], name='blog_image_href_idx'),
            models.Index(fields=['post'], name='blog_image_post_idx'),
        ]


class BlogPostRevision(Model):
    id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, db_column='post_id', related_name='revisions')
    title = models.CharField(max_length=200, blank=True, default='')
    content_json = models.JSONField(default=dict, blank=True)
    content_html = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'blog_post_revisions'
        ordering = ['-created_at', '-id']
