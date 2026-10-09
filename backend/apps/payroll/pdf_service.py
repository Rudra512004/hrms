"""
Server-side Payslip PDF Generator using ReportLab.
Renders an immutable, professional PDF directly from the Payslip snapshot.
"""
import io
from decimal import Decimal
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.barcode.qr import QrCodeWidget


def generate_payslip_pdf(payslip, verification_base_url: str = "https://beyondsure.com/verify") -> bytes:
    """
    Renders a complete, professional payslip PDF from the snapshot data stored
    on the Payslip and its normalized PayslipLines.
    Returns raw PDF bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    # Typography styles
    sub_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#475569')
    )
    table_text = ParagraphStyle(
        'TText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )
    table_bold = ParagraphStyle(
        'TBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )

    story = []

    # 1. Organization & Header Metadata (Snapshot with live fallback)
    rec = getattr(payslip, 'payroll_record', None)
    live_emp = rec.employee if rec else None
    live_org = rec.period.organization if rec and rec.period else (live_emp.organization if live_emp else None)
    live_branch = live_emp.branch if live_emp else None

    org_name = payslip.organization_name or (live_org.name if live_org else "BeyondSure HRMS")
    legal_name = payslip.legal_name or org_name
    cin = payslip.cin or "N/A"
    branch_name = payslip.branch_name or (live_branch.name if live_branch else "Headquarters")
    branch_addr = payslip.branch_address or (
        f"{live_branch.address_line1}, {live_branch.city}".strip(", ") if live_branch and live_branch.address_line1 else ""
    )

    year = payslip.period_year or (rec.period.year if rec and rec.period else "")
    month = payslip.period_month or (rec.period.month if rec and rec.period else "")
    period_str = f"{year}/{month:02d}" if year and month else "N/A"
    payslip_num = payslip.payslip_number or "N/A"

    issue_date = payslip.issued_at.strftime("%d/%m/%Y") if payslip.issued_at else "N/A"

    hdr_left = f"<b>{org_name}</b><br/>{branch_name}"
    if branch_addr:
        hdr_left += f" — {branch_addr}"
    if cin and cin != "N/A":
        hdr_left += f"<br/>CIN: {cin}"

    hdr_right = (
        f"<font size=14><b>PAYSLIP</b></font><br/>"
        f"<b>Period:</b> {period_str}<br/>"
        f"<b>Payslip No:</b> {payslip_num}<br/>"
        f"<b>Issued:</b> {issue_date}"
    )

    hdr_table = Table(
        [[Paragraph(hdr_left, sub_style), Paragraph(hdr_right, sub_style)]],
        colWidths=[330, 190]
    )
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(hdr_table)
    story.append(Spacer(1, 8))

    # 2. Employee Details Table
    emp_code = payslip.employee_code or (live_emp.employee_code if live_emp else "N/A")
    emp_name = payslip.employee_name or (
        (live_emp.user.get_full_name() or live_emp.user.email) if live_emp and live_emp.user else "N/A"
    )
    dept_name = payslip.department_name or (
        (live_emp.department.name if live_emp.department else "N/A") if live_emp else "N/A"
    )
    desig_name = payslip.designation_name or (
        (live_emp.designation.name if live_emp.designation else "N/A") if live_emp else "N/A"
    )
    doj_str = payslip.joining_date.strftime("%d/%m/%Y") if payslip.joining_date else (
        live_emp.joining_date.strftime("%d/%m/%Y") if live_emp and live_emp.joining_date else "N/A"
    )
    pay_mode = payslip.payment_mode or "Bank Transfer"
    bank_name = payslip.bank_name or "N/A"
    bank_acc = payslip.masked_bank_account or "N/A"
    ifsc = payslip.bank_ifsc or "N/A"
    pan = payslip.masked_pan or "N/A"
    uan = payslip.uan or "N/A"
    esic = payslip.esic_number or "N/A"

    emp_data = [
        [Paragraph('<b>Employee Code:</b>', table_bold), Paragraph(emp_code, table_text), Paragraph('<b>Department:</b>', table_bold), Paragraph(dept_name, table_text)],
        [Paragraph('<b>Employee Name:</b>', table_bold), Paragraph(emp_name, table_text), Paragraph('<b>Designation:</b>', table_bold), Paragraph(desig_name, table_text)],
        [Paragraph('<b>Date of Joining:</b>', table_bold), Paragraph(doj_str, table_text), Paragraph('<b>Payment Mode:</b>', table_bold), Paragraph(pay_mode, table_text)],
        [Paragraph('<b>Bank Name:</b>', table_bold), Paragraph(bank_name, table_text), Paragraph('<b>Bank A/C:</b>', table_bold), Paragraph(bank_acc, table_text)],
        [Paragraph('<b>IFSC Code:</b>', table_bold), Paragraph(ifsc, table_text), Paragraph('<b>PAN:</b>', table_bold), Paragraph(pan, table_text)],
        [Paragraph('<b>UAN:</b>', table_bold), Paragraph(uan, table_text), Paragraph('<b>ESIC No:</b>', table_bold), Paragraph(esic, table_text)],
    ]
    t_emp = Table(emp_data, colWidths=[95, 165, 95, 165])
    t_emp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_emp)
    story.append(Spacer(1, 8))

    # 3. Attendance Summary
    cal_days = payslip.calendar_days or (
        (rec.period.end_date - rec.period.start_date).days + 1 if rec and rec.period else 0
    )
    work_days = payslip.working_days or (rec.working_days if rec else 0)
    pres_days = payslip.present_days or (rec.present_days if rec else Decimal('0.0'))
    leave_days = payslip.leave_days or (rec.leave_days if rec else Decimal('0.0'))
    eff_days = payslip.effective_days or (rec.effective_days if rec else Decimal('0.0'))
    lop_days = payslip.lop_days or (rec.lop_days if rec else Decimal('0.0'))

    att_data = [
        [
            Paragraph('<b>Calendar Days</b>', table_bold),
            Paragraph('<b>Working Days</b>', table_bold),
            Paragraph('<b>Present Days</b>', table_bold),
            Paragraph('<b>Leave Days</b>', table_bold),
            Paragraph('<b>Paid Days</b>', table_bold),
            Paragraph('<b>Loss of Pay (LOP)</b>', table_bold),
        ],
        [
            str(cal_days),
            str(work_days),
            f"{float(pres_days):.1f}" if pres_days is not None else "0.0",
            f"{float(leave_days):.1f}" if leave_days is not None else "0.0",
            f"{float(eff_days):.1f}" if eff_days is not None else "0.0",
            f"{float(lop_days):.1f}" if lop_days is not None else "0.0",
        ]
    ]
    t_att = Table(att_data, colWidths=[86]*6)
    t_att.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_att)
    story.append(Spacer(1, 8))

    # 4. Earnings & Deductions Normalized Side-by-Side
    earning_lines = list(payslip.lines.filter(category='earning').order_by('order', 'id'))
    deduction_lines = list(payslip.lines.filter(category='deduction').order_by('order', 'id'))

    # Fallback if no lines exist yet (e.g. legacy/stub records)
    gross_val = payslip.gross_earnings or (rec.gross_salary if rec else Decimal('0.00'))
    net_val = payslip.net_pay or (rec.net_salary if rec else Decimal('0.00'))
    ded_val = payslip.total_deductions or Decimal('0.00')

    if not earning_lines and gross_val > 0:
        class DummyLine:
            def __init__(self, name, amount):
                self.name = name
                self.amount = amount
        earning_lines = [DummyLine('Basic Salary', gross_val)]

    max_rows = max(len(earning_lines), len(deduction_lines), 1)
    ed_rows = [
        [
            Paragraph('<b>Earnings</b>', table_bold),
            Paragraph('<b>Amount (₹)</b>', table_bold),
            Paragraph('<b>Deductions</b>', table_bold),
            Paragraph('<b>Amount (₹)</b>', table_bold),
        ]
    ]

    for i in range(max_rows):
        e_name = Paragraph(earning_lines[i].name, table_text) if i < len(earning_lines) else ''
        e_amt = f"{earning_lines[i].amount:,.2f}" if i < len(earning_lines) else ''
        d_name = Paragraph(deduction_lines[i].name, table_text) if i < len(deduction_lines) else ''
        d_amt = f"{deduction_lines[i].amount:,.2f}" if i < len(deduction_lines) else ''
        ed_rows.append([e_name, e_amt, d_name, d_amt])

    # Totals row
    ed_rows.append([
        Paragraph('<b>Gross Earnings</b>', table_bold),
        Paragraph(f"<b>₹ {gross_val:,.2f}</b>", table_bold),
        Paragraph('<b>Total Deductions</b>', table_bold),
        Paragraph(f"<b>₹ {ded_val:,.2f}</b>", table_bold),
    ])

    t_ed = Table(ed_rows, colWidths=[180, 80, 180, 80])
    t_ed.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor('#F1F5F9')),
        ('BACKGROUND', (2,0), (3,0), colors.HexColor('#F1F5F9')),
        ('BACKGROUND', (0,-1), (1,-1), colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (2,-1), (3,-1), colors.HexColor('#E2E8F0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (1,1), (1,-1), 'RIGHT'),
        ('ALIGN', (3,1), (3,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_ed)
    story.append(Spacer(1, 8))

    # 5. Net Pay Summary
    words_val = payslip.net_pay_in_words
    if not words_val:
        from apps.payroll.currency_utils import amount_to_words_inr
        words_val = amount_to_words_inr(net_val)

    net_data = [
        [
            Paragraph(
                f"<font size=10><b>Net Pay: ₹ {net_val:,.2f}</b></font><br/>"
                f"<b>Amount in Words:</b> {words_val}",
                table_text
            )
        ]
    ]
    t_net = Table(net_data, colWidths=[520])
    t_net.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ECFDF5')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#10B981')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_net)
    story.append(Spacer(1, 10))

    # 6. Verification QR code and Sign-off Footer
    token_str = str(payslip.verification_token) if payslip.verification_token else ""
    verify_url = f"{verification_base_url}/{token_str}" if token_str else ""

    d = Drawing(55, 55)
    if verify_url:
        qr = QrCodeWidget(verify_url)
        qr.barWidth = 55
        qr.barHeight = 55
        qr.qrVersion = 1
        d.add(qr)

    ftr_data = [
        [
            d,
            Paragraph(
                "<b>Online Verification:</b><br/>"
                "Scan QR code to verify this payslip online.<br/>"
                "This document is electronically generated and verified.",
                sub_style
            ),
            Paragraph("<b>Authorized Signatory</b><br/><br/><br/>_____________________", sub_style)
        ]
    ]
    t_ftr = Table(ftr_data, colWidths=[65, 315, 140])
    t_ftr.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
    ]))
    story.append(t_ftr)

    # 7. Watermark Canvas Callback
    def draw_watermark(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica-Bold', 55)
        canvas.setFillColor(colors.Color(0.85, 0.85, 0.85, alpha=0.10))
        canvas.translate(300, 420)
        canvas.rotate(45)
        watermark_text = org_name if len(org_name) < 25 else "CONFIDENTIAL"
        canvas.drawCentredString(0, 0, watermark_text)
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_watermark)
    return buf.getvalue()
