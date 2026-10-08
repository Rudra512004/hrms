import csv
import io
from datetime import datetime
from decimal import Decimal
from django.utils import timezone
from .models import PayrollRun, PayrollRecord, PayrollLineItem

def generate_payroll_csv(period: PayrollRun) -> str:
    """Generates a CSV string for a finalized or approved payroll run."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Define stable columns
    headers = [
        'Employee Code',
        'Employee Name',
        'Department',
        'Designation',
        'Payroll Period',
        'Basic Salary',
        'Total Earnings',
        'Gross Salary',
        'Total Deductions',
        'Total Tax',
        'Net Salary',
        'LOP Days',
        'LOP Amount',
        'Payroll Status'
    ]
    writer.writerow(headers)
    
    # Query all records
    records = PayrollRecord.objects.filter(period=period).select_related(
        'employee__department', 'employee__branch'
    ).order_by('employee__employee_code')
    
    for record in records:
        emp = record.employee
        dept_name = emp.department.name if emp.department else 'N/A'
        
        row = [
            emp.employee_code,
            f"{emp.user.first_name} {emp.user.last_name}".strip(),
            dept_name,
            emp.designation.name if hasattr(emp, 'designation') and emp.designation else 'N/A',
            f"{period.year}-{period.month:02d}",
            str(record.basic_salary),
            str(record.total_earnings),
            str(record.gross_salary),
            str(record.total_deductions),
            str(record.total_tax),
            str(record.net_salary),
            str(record.lop_days),
            str(record.lop_amount),
            record.status
        ]
        writer.writerow(row)
        
    return output.getvalue()


def generate_payroll_pdf(period: PayrollRun) -> bytes:
    """Generates a PDF byte string for a finalized or approved payroll run."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise Exception("reportlab is not installed.")
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    normal_style = styles['Normal']
    
    # Header
    org_name = period.organization.name if period.organization else "Organization"
    elements.append(Paragraph(f"{org_name} - Payroll Report", title_style))
    elements.append(Paragraph(f"Period: {period.year}-{period.month:02d}", normal_style))
    elements.append(Paragraph(f"Status: {period.status.upper()}", normal_style))
    elements.append(Paragraph(f"Generated at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    elements.append(Spacer(1, 20))
    
    # Table Data
    data = [[
        'Emp Code', 'Name', 'Basic', 'Gross', 'Deductions', 'Net Salary', 'LOP'
    ]]
    
    records = PayrollRecord.objects.filter(period=period).select_related('employee').order_by('employee__employee_code')
    
    total_basic = Decimal('0.00')
    total_gross = Decimal('0.00')
    total_deductions = Decimal('0.00')
    total_net = Decimal('0.00')
    
    for r in records:
        emp_name = f"{r.employee.user.first_name} {r.employee.user.last_name}".strip()
        data.append([
            r.employee.employee_code,
            emp_name,
            f"{r.basic_salary:,.2f}",
            f"{r.gross_salary:,.2f}",
            f"{r.total_deductions:,.2f}",
            f"{r.net_salary:,.2f}",
            f"{r.lop_days}"
        ])
        total_basic += r.basic_salary
        total_gross += r.gross_salary
        total_deductions += r.total_deductions
        total_net += r.net_salary
        
    # Totals Row
    data.append([
        'TOTAL', '',
        f"{total_basic:,.2f}",
        f"{total_gross:,.2f}",
        f"{total_deductions:,.2f}",
        f"{total_net:,.2f}",
        ''
    ])
    
    # Create Table
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(t)
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
