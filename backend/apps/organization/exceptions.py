from rest_framework.exceptions import APIException
from rest_framework import status


class WorkingCalendarConfigurationError(APIException):
    """
    Domain-level working calendar configuration exception.
    Raised when required working calendar or configuration
    rules are missing or invalid for calendar evaluations.
    Maps to HTTP 400 Bad Request in DRF views.
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Working calendar configuration error.'
    default_code = 'working_calendar_configuration_error'

    def __init__(self, detail=None, code=None):
        if detail is not None:
            self.detail = str(detail)
        else:
            self.detail = self.default_detail
        if code is not None:
            self.default_code = code
        super().__init__(self.detail, code=self.default_code)
