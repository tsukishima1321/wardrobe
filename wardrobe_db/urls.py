from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.search, name='search'),
    path('random/', views.random, name='random'),
    path('types/', views.getTypes, name='types'),
    path('set/image/', views.setImageDetail, name='setImageDetail'),
    path('get/image/', views.getImageDetail, name='getImageDetail'),
    path('set/text/', views.setImageText, name='setImageText'),
    path('statistics/', views.getStatistics, name='getStatistics'),
]