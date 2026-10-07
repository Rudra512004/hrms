import csv

def generate():
    # Employees valid
    with open('scratch_e2e/employees_valid.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['employee_code', 'first_name', 'last_name', 'email', 'employment_status', 'date_of_joining'])
        writer.writerow(['EMP-E2E-001', 'Alice', 'Tester', 'alice.tester@example.com', 'PROBATION', '2026-10-01'])
        writer.writerow(['EMP-E2E-002', 'Bob', 'Builder', 'bob.builder@example.com', 'FULL_TIME', '2026-10-02'])

    # Attendance valid
    with open('scratch_e2e/attendance_valid.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['employee_code', 'date', 'check_in', 'check_out', 'status'])
        writer.writerow(['EMP-E2E-001', '2026-10-06', '09:00', '18:00', 'PRESENT'])
        writer.writerow(['EMP-E2E-002', '2026-10-06', '09:15', '18:30', 'PRESENT'])

    # Leave Balances valid
    with open('scratch_e2e/leave_balances_valid.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['employee_code', 'leave_type_code', 'year', 'balance', 'used'])
        # Requires valid leave type code (like SICK or CASUAL)
        writer.writerow(['EMP-E2E-001', 'AL', '2026', '12', '2'])
        writer.writerow(['EMP-E2E-002', 'AL', '2026', '15', '0'])

    # Salary Structures valid
    with open('scratch_e2e/salary_structures_valid.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['employee_code', 'ctc_annual', 'effective_date', 'currency'])
        writer.writerow(['EMP-E2E-001', '1200000', '2026-10-01', 'INR'])
        writer.writerow(['EMP-E2E-002', '1500000', '2026-10-01', 'INR'])

    # Employees invalid
    with open('scratch_e2e/employees_invalid.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['employee_code', 'first_name', 'last_name', 'email', 'employment_status', 'date_of_joining'])
        writer.writerow(['EMP-E2E-003', 'Invalid', 'Status', 'invalid.status@example.com', 'FAKE_STATUS', '2026-10-01']) # Invalid enum
        writer.writerow(['EMP-E2E-004', 'Bad', 'Date', 'bad.date@example.com', 'FULL_TIME', '2026-30-50']) # Invalid date

if __name__ == "__main__":
    generate()
