from rest_framework.exceptions import APIException
from rest_framework import status


class AttendanceConfigurationError(APIException):
    """
    Domain-level attendance configuration exception.
    Raised when required working calendar, shift assignments, or configuration
    rules are missing or invalid for attendance calculations.
    Maps to HTTP 400 Bad Request in DRF views.
    """
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Attendance configuration error.'
    default_code = 'attendance_configuration_error'

    def __init__(self, detail=None, code=None):
        if detail is not None:
            self.detail = str(detail)
        else:
            self.detail = self.default_detail
        if code is not None:
            self.default_code = code
        super().__init__(self.detail, code=self.default_code)
