from django.urls import path
from . import views

app_name = 'wardrobe_db'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('random/', views.random, name='random'),
    path('types/', views.getTypes, name='types'),
    path('set/image/', views.setImageDetail, name='setImageDetail'),
    path('get/image/', views.getImageDetail, name='getImageDetail'),
    path('set/text/', views.setImageText, name='setImageText'),
    path('statistics/', views.getStatistics, name='getStatistics'),
    path('new/image/', views.newImage, name='newImage'),
    path('new/type/', views.newType, name='newType'),
    path('get/ocrmission/', views.getOcrMission, name='getOcrMission'),
]