from django.urls import path
from . import views

app_name = 'wardrobe_diary'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('get/',views.getDiaryTexts, name='getDiaryTexts'),
    path('new/', views.newDiaryText, name='newDiaryText'),
    path('delete/', views.deleteDiaryText, name='deleteDiaryText'),
    path('edit/', views.editDiaryText, name='editDiaryText'),
]