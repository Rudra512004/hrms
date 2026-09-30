from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeSelfServiceView, ProvisionEmployeeView, WFHRequestViewSet, EmployeeManagementViewSet, EmployeeDocumentViewSet
from .review_views import ReviewCycleViewSet, PerformanceReviewViewSet

router = DefaultRouter()
router.register(r'management', EmployeeManagementViewSet, basename='employee-management')
router.register(r'wfh-requests', WFHRequestViewSet, basename='wfh-request')
router.register(r'documents', EmployeeDocumentViewSet, basename='employee-documents')
router.register(r'review-cycles', ReviewCycleViewSet, basename='review-cycle')
router.register(r'reviews', PerformanceReviewViewSet, basename='performance-review')

urlpatterns = [
    path('me/', EmployeeSelfServiceView.as_view(), name='employee-me'),
    path('', ProvisionEmployeeView.as_view(), name='employee-provision'),
    path('', include(router.urls)),
]
