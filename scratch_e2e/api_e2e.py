import requests

BASE_URL = 'http://localhost:8000/api/v1'

def run_e2e():
    print("1. Logging in as hr@demo.local...")
    res = requests.post(f"{BASE_URL}/auth/login/", json={
        "email": "hr@demo.local",
        "password": "DevPass123!"
    })
    res.raise_for_status()
    token = res.json()['token']
    headers = {"Authorization": f"Token {token}"}
    
    print("2. Fetching templates...")
    res = requests.get(f"{BASE_URL}/data-import/templates/", headers=headers)
    res.raise_for_status()
    templates = res.json()
    print(f"   Got {len(templates)} templates.")
    
    import csv
    print("3. Uploading employees_valid.csv...")
    employees_template = next(t for t in templates if t['key'] == 'employees')
    emp_headers = employees_template['headers']
    
    with open('scratch_e2e/employees_valid.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=emp_headers)
        writer.writeheader()
        writer.writerow({
            'employee_code': 'EMP-E2E-001', 'first_name': 'Alice', 'last_name': 'Tester',
            'email': 'alice.tester@example.com', 'gender': 'female', 'date_of_joining': '2026-10-01',
            'employment_status': 'PROBATION', 'status': 'active', 'branch_code': 'HQ'
        })
        writer.writerow({
            'employee_code': 'EMP-E2E-002', 'first_name': 'Bob', 'last_name': 'Builder',
            'email': 'bob.builder@example.com', 'gender': 'male', 'date_of_joining': '2026-10-02',
            'employment_status': 'FULL_TIME', 'status': 'active', 'branch_code': 'HQ'
        })
        
    with open('scratch_e2e/employees_invalid.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=emp_headers)
        writer.writeheader()
        writer.writerow({
            'employee_code': 'EMP-E2E-003', 'first_name': 'Charlie', 'last_name': 'Bad',
            'email': 'charlie', 'gender': 'INVALID', 'date_of_joining': '2026-15-99',
            'employment_status': 'NOT_A_STATUS'
        })
        
    with open('scratch_e2e/employees_valid.csv', 'rb') as f:
        res = requests.post(f"{BASE_URL}/data-import/jobs/", headers=headers, data={'template_key': 'employees'}, files={'file': f})
    if not res.ok:
        print(f"Error: {res.text}")
        res.raise_for_status()
    job_id = res.json()['id']
    print(f"   Created job {job_id}.")
    
    print("4. Validating employees_valid.csv...")
    res = requests.post(f"{BASE_URL}/data-import/jobs/{job_id}/validate/", headers=headers)
    if not res.ok:
        print(f"Error: {res.text}")
        res.raise_for_status()
    job = res.json()
    print(f"   Validation status: {job['status']}. Preview data length: {len(job['preview_data'])}")
    
    print("5. Executing employees_valid.csv...")
    res = requests.post(f"{BASE_URL}/data-import/jobs/{job_id}/execute/", headers=headers)
    if not res.ok:
        print(f"Error: {res.text}")
        res.raise_for_status()
    job = res.json()
    print(f"   Execution status: {job['status']}. Created: {job['created_count']}, Errors: {job['error_count']}")
    
    if job['error_count'] > 0:
        res = requests.get(f"{BASE_URL}/data-import/jobs/{job_id}/errors/", headers=headers)
        print("   Execution Errors:", res.json())

    print("6. Verifying employees in API...")
    res = requests.get(f"{BASE_URL}/employees/management/", headers=headers)
    res.raise_for_status()
    employees = res.json()
    if isinstance(employees, dict) and 'results' in employees:
        employees = employees['results']
    codes = [e['employee_code'] for e in employees]
    print(f"   Found employees: EMP-E2E-001 in codes? {'EMP-E2E-001' in codes}")
    
    print("7. Uploading employees_invalid.csv...")
    with open('scratch_e2e/employees_invalid.csv', 'rb') as f:
        res = requests.post(f"{BASE_URL}/data-import/jobs/", headers=headers, data={'template_key': 'employees'}, files={'file': f})
    if not res.ok:
        print(f"Error: {res.text}")
        res.raise_for_status()
    job_id_inv = res.json()['id']
    
    print("8. Validating employees_invalid.csv...")
    res = requests.post(f"{BASE_URL}/data-import/jobs/{job_id_inv}/validate/", headers=headers)
    if not res.ok:
        print(f"Error: {res.text}")
        res.raise_for_status()
    job_inv = res.json()
    print(f"   Invalid Validation status: {job_inv['status']}. Errors found: {job_inv['error_count']}")
    
    res = requests.get(f"{BASE_URL}/data-import/jobs/{job_id_inv}/errors/", headers=headers)
    res.raise_for_status()
    errors = res.json()
    print(f"   Row errors: {len(errors)}")
    for e in errors:
        print(f"     Row {e['row_number']}: {e['message']}")

if __name__ == '__main__':
    run_e2e()
