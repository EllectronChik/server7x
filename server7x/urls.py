"""server7x URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from main import views
from rest_framework import routers

router = routers.DefaultRouter()
router.register(r'teams', views.TeamsViewSet)
router.register(r'players', views.PlayersViewSet)
router.register(r'managers', views.ManagersViewSet)
router.register(r'manager_contacts', views.ManagerContactsViewSet)
router.register(r'team_resources', views.TeamResourcesViewSet)
router.register(r'stages', views.StagesViewSet)
router.register(r'regions', views.RegionsViewSet)
router.register(r'matches', views.MatchesViewSet)
router.register(r'races', views.RaceViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),

]
