class ImportValidationError(Exception):
    """Raised when an import fails validation at the file or header level."""
    pass

class RowValidationError(Exception):
    """Raised when a specific row fails validation during parsing or execution."""
    def __init__(self, field, error_type, message):
        self.field = field
        self.error_type = error_type
        self.message = message
        super().__init__(message)
