import csv
import logging
from typing import List, Dict, Any, Tuple
from django.db import transaction
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

class BaseCSVImporter:
    """
    Base framework for importing CSV templates.
    Provides generic validation, tenant isolation, and dry-run support.
    """
    
    EXPECTED_HEADERS: List[str] = []
    
    def __init__(self, import_obj, dry_run: bool = False):
        self.import_obj = import_obj
        self.dry_run = dry_run
        self.organization = import_obj.organization
        self.user = import_obj.uploaded_by
        self.errors = {}
        self.total_rows = 0
        self.successful_rows = 0
        self.failed_rows = 0

    def get_file_content(self):
        with default_storage.open(self.import_obj.file.name, 'r') as f:
            content = f.read()
        return content

    def validate_headers(self, headers: List[str]) -> bool:
        missing = [h for h in self.EXPECTED_HEADERS if h not in headers]
        if missing:
            self.add_error(0, f"Missing required columns: {', '.join(missing)}")
            return False
        return True

    def add_error(self, row_idx: int, message: str):
        if row_idx not in self.errors:
            self.errors[row_idx] = []
        self.errors[row_idx].append(message)

    def process_row(self, row_idx: int, row_data: Dict[str, Any]):
        """
        To be implemented by subclasses.
        Should raise ValueError if data is invalid, or handle saving.
        Must respect self.organization for tenant isolation.
        """
        raise NotImplementedError

    def run(self):
        try:
            content = self.get_file_content()
            reader = csv.DictReader(content.splitlines())
            
            if not reader.fieldnames:
                self.add_error(0, "CSV file is empty or missing headers.")
                self.finalize(status='failed')
                return

            if not self.validate_headers(reader.fieldnames):
                self.finalize(status='failed')
                return

            rows = list(reader)
            self.total_rows = len(rows)

            try:
                with transaction.atomic():
                    for idx, row_data in enumerate(rows, start=1):
                        try:
                            self.process_row(idx, row_data)
                            self.successful_rows += 1
                        except Exception as e:
                            self.add_error(idx, str(e))
                            self.failed_rows += 1
                            logger.exception(f"Error processing row {idx}")
                    
                    if self.dry_run or self.failed_rows > 0:
                        # Rollback if it's a dry run OR if there are any failures to ensure atomicity
                        transaction.set_rollback(True)
            except Exception as e:
                self.add_error(0, f"Critical error during import: {str(e)}")
                transaction.set_rollback(True)

            status = 'dry_run' if self.dry_run else ('completed' if self.failed_rows == 0 else 'failed')
            self.finalize(status=status)

        except Exception as e:
            logger.exception("Failed to run import")
            self.add_error(0, str(e))
            self.finalize(status='failed')

    def finalize(self, status: str):
        self.import_obj.status = status
        self.import_obj.total_rows = self.total_rows
        self.import_obj.successful_rows = self.successful_rows
        self.import_obj.failed_rows = self.failed_rows
        self.import_obj.error_log = self.errors
        self.import_obj.save(update_fields=['status', 'total_rows', 'successful_rows', 'failed_rows', 'error_log'])
