from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register('car-models', api_views.CarModelViewSet, basename='carmodel')
router.register('lead-sources', api_views.LeadSourceViewSet, basename='leadsource')
router.register('clients', api_views.ClientViewSet, basename='client')
router.register('deals', api_views.DealViewSet, basename='deal')
router.register('interactions', api_views.InteractionViewSet, basename='interaction')
router.register('tasks', api_views.TaskViewSet, basename='task')

urlpatterns = [
    path('analytics/summary/', api_views.AnalyticsView.as_view(), name='analytics-summary'),
    path('', include(router.urls)),
]