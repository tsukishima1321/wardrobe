from django.urls import path
from . import views

app_name = 'wardrobe_db'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('searchhint/', views.searchHint, name='searchHint'),
    path('random/', views.random, name='random'),
    path('image/set/', views.setImageDetail, name='setImageDetail'),
    path('image/get/', views.getImageDetail, name='getImageDetail'),
    path('image/delete/', views.deleteImage, name='deleteImage'),
    path('text/set/', views.setImageText, name='setImageText'),
    path('keyword/list/', views.listKeywords, name='listKeywords'),
    path('keyword/create/', views.createKeyword, name='createKeyword'),
    path('keyword/delete/', views.deleteKeyword, name='deleteKeyword'),
    path('property/list/', views.listProperties, name='listProperties'),
    path('property/create/', views.createProperty, name='createProperty'),
    path('property/delete/', views.deleteProperty, name='deleteProperty'),
    path('statistics/', views.getStatistics, name='getStatistics'),
    path('image/new/', views.newImage, name='newImage'),
    path('ocrmission/get/', views.getOcrMission, name='getOcrMission'),
    path('ocrmission/new/', views.newOcrMission, name='newOcrMission'),
    path('ocrmission/reset/', views.resetOcrMission, name='resetOcrMission'),
    path('ocrmission/execute/', views.excuteOcrMission, name='excuteOcrMission'),
    path('ocrmission/executeall/', views.excuteAllOcrMission, name='excuteAllOcrMission'),
    path('savedsearch/create/', views.saveSearchFilter, name='createSavedSearch'),
    path('savedsearch/list/', views.listSavedSearchFilters, name='listSavedSearch'),
    path('savedsearch/delete/', views.deleteSavedSearch, name='deleteSavedSearch'),
    path('savedsearch/get/', views.getSavedSearchFilter, name='getSavedSearch'),
]