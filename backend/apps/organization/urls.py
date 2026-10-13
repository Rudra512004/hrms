from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OfficeNetworkViewSet,
    OrganizationViewSet,
    DepartmentViewSet,
    DesignationViewSet,
    BranchViewSet,
    WorkingCalendarViewSet,
    OrganizationSetupViewSet,
    TenantOrganizationSetupView,
    TeamViewSet,
    OrganizationWizardStartView,
    OrganizationWizardStatusView,
    OrganizationWizardStageView,
    OrganizationWizardStage2View,
    OrganizationWizardStage3View,
    OrganizationWizardStage4View,
    OrganizationWizardStage5View,
    OrganizationWizardStage6View,
    OrganizationWizardCompleteView,
    OrganizationWizardDraftView,
    OrganizationWizardReadinessView,
    OrganizationWizardStage6ResendView,
    OrganizationWizardStage6RevokeView,
    OrganizationInvitationVerifyView,
    OrganizationInvitationAcceptView,
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'teams', TeamViewSet, basename='team')
router.register(r'designations', DesignationViewSet, basename='designation')
router.register(r'office-networks', OfficeNetworkViewSet, basename='office-network')
router.register(r'branches', BranchViewSet, basename='branch')
router.register(r'working-calendars', WorkingCalendarViewSet, basename='working-calendar')
router.register(r'setup', OrganizationSetupViewSet, basename='setup')

urlpatterns = [
    path('self-setup/', TenantOrganizationSetupView.as_view(), name='tenant-organization-setup'),
    path('wizard/start/', OrganizationWizardStartView.as_view(), name='wizard-start'),
    path('wizard/status/', OrganizationWizardStatusView.as_view(), name='wizard-status'),
    path('wizard/stage/<int:stage_number>/', OrganizationWizardStageView.as_view(), name='wizard-stage'),
    path('wizard/stage-2/', OrganizationWizardStage2View.as_view(), name='wizard-stage-2'),
    path('wizard/stage-3/', OrganizationWizardStage3View.as_view(), name='wizard-stage-3'),
    path('wizard/stage-4/', OrganizationWizardStage4View.as_view(), name='wizard-stage-4'),
    path('wizard/stage-5/', OrganizationWizardStage5View.as_view(), name='wizard-stage-5'),
    path('wizard/stage-6/', OrganizationWizardStage6View.as_view(), name='wizard-stage-6'),
    path('wizard/stage-6/resend/', OrganizationWizardStage6ResendView.as_view(), name='wizard-stage-6-resend'),
    path('wizard/stage-6/revoke/', OrganizationWizardStage6RevokeView.as_view(), name='wizard-stage-6-revoke'),
    path('wizard/complete/', OrganizationWizardCompleteView.as_view(), name='wizard-complete'),
    path('wizard/draft/', OrganizationWizardDraftView.as_view(), name='wizard-draft'),
    path('wizard/readiness/', OrganizationWizardReadinessView.as_view(), name='wizard-readiness'),
    # Aliases under onboarding/
    path('onboarding/start/', OrganizationWizardStartView.as_view(), name='onboarding-start'),
    path('onboarding/status/', OrganizationWizardStatusView.as_view(), name='onboarding-status'),
    path('onboarding/stage/<int:stage_number>/', OrganizationWizardStageView.as_view(), name='onboarding-stage'),
    path('onboarding/stage-6/resend/', OrganizationWizardStage6ResendView.as_view(), name='onboarding-stage-6-resend'),
    path('onboarding/stage-6/revoke/', OrganizationWizardStage6RevokeView.as_view(), name='onboarding-stage-6-revoke'),
    path('onboarding/complete/', OrganizationWizardCompleteView.as_view(), name='onboarding-complete'),
    path('onboarding/draft/', OrganizationWizardDraftView.as_view(), name='onboarding-draft'),
    path('onboarding/readiness/', OrganizationWizardReadinessView.as_view(), name='onboarding-readiness'),
    # Invitation verification and acceptance
    path('invitations/verify/', OrganizationInvitationVerifyView.as_view(), name='invitations-verify'),
    path('invitations/accept/', OrganizationInvitationAcceptView.as_view(), name='invitations-accept'),
    path('wizard/invitations/verify/', OrganizationInvitationVerifyView.as_view(), name='wizard-invitations-verify'),
    path('wizard/invitations/accept/', OrganizationInvitationAcceptView.as_view(), name='wizard-invitations-accept'),
    path('onboarding/invitations/verify/', OrganizationInvitationVerifyView.as_view(), name='onboarding-invitations-verify'),
    path('onboarding/invitations/accept/', OrganizationInvitationAcceptView.as_view(), name='onboarding-invitations-accept'),
    path('', include(router.urls)),
]
