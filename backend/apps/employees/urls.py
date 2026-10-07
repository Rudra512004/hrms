from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmployeeSelfServiceView, EmployeeLettersView, EmployeeHolidaysView, EmployeeAnnouncementsView, ProvisionEmployeeView, WFHRequestViewSet, EmployeeManagementViewSet, EmployeeDocumentViewSet, EmployeeStatutoryAndBankViewSet, EmployeeDependentViewSet, EmployeeEducationViewSet, EmployeePriorExperienceViewSet
from .review_views import ReviewCycleViewSet, PerformanceReviewViewSet

router = DefaultRouter()
router.register(r'management', EmployeeManagementViewSet, basename='employee-management')
router.register(r'wfh-requests', WFHRequestViewSet, basename='wfh-request')
router.register(r'documents', EmployeeDocumentViewSet, basename='employee-documents')
router.register(r'statutory', EmployeeStatutoryAndBankViewSet, basename='employee-statutory')
router.register(r'dependents', EmployeeDependentViewSet, basename='employee-dependents')
router.register(r'education', EmployeeEducationViewSet, basename='employee-education')
router.register(r'experience', EmployeePriorExperienceViewSet, basename='employee-experience')
router.register(r'review-cycles', ReviewCycleViewSet, basename='review-cycle')
router.register(r'reviews', PerformanceReviewViewSet, basename='performance-review')
from .views import ApprovalDelegationViewSet, LetterRequestViewSet
router.register(r'approval-delegations', ApprovalDelegationViewSet, basename='approval-delegation')
router.register(r'letter-requests', LetterRequestViewSet, basename='letter-request')
urlpatterns = [
    path('me/', EmployeeSelfServiceView.as_view(), name='employee-me'),
    path('me/letters/', EmployeeLettersView.as_view(), name='employee-letters'),
    path('me/holidays/', EmployeeHolidaysView.as_view(), name='employee-holidays'),
    path('me/announcements/', EmployeeAnnouncementsView.as_view(), name='employee-announcements'),
    path('', ProvisionEmployeeView.as_view(), name='employee-provision'),
    path('', include(router.urls)),
]
