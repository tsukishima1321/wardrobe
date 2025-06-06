from django.urls import path
from . import views

app_name = 'wardrobe_db'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('random/', views.random, name='random'),
    path('types/', views.getTypes, name='types'),
    path('image/set/', views.setImageDetail, name='setImageDetail'),
    path('image/get/', views.getImageDetail, name='getImageDetail'),
    path('image/delete/', views.deleteImage, name='deleteImage'),
    path('text/get/', views.setImageText, name='setImageText'),
    path('statistics/', views.getStatistics, name='getStatistics'),
    path('image/new/', views.newImage, name='newImage'),
    path('type/new/', views.newType, name='newType'),
    path('type/rename/', views.renameType, name='renameType'),
    path('type/delete/', views.deleteType, name='deleteType'),
    path('ocrmission/get/', views.getOcrMission, name='getOcrMission'),
]