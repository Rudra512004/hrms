from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CompensationHistoryViewSet,
    PayrollPeriodViewSet,
    PayrollRecordViewSet,
    PayslipViewSet,
    PayslipVerificationView,
    OrganizationBankAccountViewSet,
    PaymentRoutingConfigurationViewSet,
    DisbursementBatchViewSet,
    FinalSettlementViewSet,
    FnFPolicyConfigurationViewSet,
)
from .views_reporting import PayrollReportingViewSet
from .salary_configuration_views import SalaryComponentViewSet, SalaryStructureViewSet
from .views_tax import (
    FinancialYearViewSet,
    TaxDeclarationCategoryViewSet,
    TaxDeclarationViewSet,
    TaxRuleConfigurationViewSet,
    TaxCalculationPreviewView,
)

router = DefaultRouter()
router.register(r'compensation', CompensationHistoryViewSet, basename='compensation')
router.register(r'periods', PayrollPeriodViewSet, basename='payroll-period')
router.register(r'records', PayrollRecordViewSet, basename='payroll-record')
router.register(r'payslips', PayslipViewSet, basename='payslip')
router.register(r'reports', PayrollReportingViewSet, basename='payroll-reports')
router.register(r'salary-components', SalaryComponentViewSet, basename='salary-component')
router.register(r'salary-structures', SalaryStructureViewSet, basename='salary-structure')
router.register(r'bank-accounts', OrganizationBankAccountViewSet, basename='organization-bank-account')
router.register(r'routing-configurations', PaymentRoutingConfigurationViewSet, basename='payment-routing-config')
router.register(r'disbursements', DisbursementBatchViewSet, basename='disbursement-batch')
router.register(r'fnf', FinalSettlementViewSet, basename='final-settlement')
router.register(r'fnf-policy', FnFPolicyConfigurationViewSet, basename='fnf-policy-config')
router.register(r'tax/financial-years', FinancialYearViewSet, basename='tax-financial-year')
router.register(r'tax/categories', TaxDeclarationCategoryViewSet, basename='tax-category')
router.register(r'tax/declarations', TaxDeclarationViewSet, basename='tax-declaration')
router.register(r'tax/rules', TaxRuleConfigurationViewSet, basename='tax-rule')
router.register(r'tax/engine', TaxCalculationPreviewView, basename='tax-engine')


urlpatterns = [
    path('payslips/verify/<str:token>/', PayslipVerificationView.as_view(), name='payslip-verify'),
    path('', include(router.urls)),
]

