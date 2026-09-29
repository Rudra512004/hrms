from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CandidateViewSet,
    HRCandidateDocumentView,
    HRCandidateDocumentVerifyView,
    LetterTemplateViewSet,
    CandidatePortalMeView,
    CandidatePortalDocumentsView,
    CandidatePortalDocumentDetailView,
    CandidatePortalSubmitView,
    CandidatePortalLettersView,
    CandidatePortalActivateView,
)

router = DefaultRouter()
router.register(r'', CandidateViewSet, basename='candidate')
router.register(r'letters/templates', LetterTemplateViewSet, basename='letter-template')

urlpatterns = [
    # Candidate portal (restricted self-service — candidate-only)
    path('portal/activate/',           CandidatePortalActivateView.as_view(),       name='candidate-portal-activate'),
    path('portal/me/',                 CandidatePortalMeView.as_view(),             name='candidate-portal-me'),
    path('portal/documents/',          CandidatePortalDocumentsView.as_view(),      name='candidate-portal-documents'),
    path('portal/documents/<int:document_id>/', CandidatePortalDocumentDetailView.as_view(), name='candidate-portal-document-detail'),
    path('portal/submit/',             CandidatePortalSubmitView.as_view(),         name='candidate-portal-submit'),
    path('portal/letters/',            CandidatePortalLettersView.as_view(),        name='candidate-portal-letters'),

    # HR document management
    path('<int:candidate_id>/documents/',                          HRCandidateDocumentView.as_view(),       name='hr-candidate-documents'),
    path('<int:candidate_id>/documents/<int:document_id>/verify/', HRCandidateDocumentVerifyView.as_view(), name='hr-candidate-document-verify'),

    # Candidate CRUD + actions
    path('', include(router.urls)),
]
