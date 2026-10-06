# Phase 4: PayrollPeriod -> PayrollRun rename + new domain models
# This migration:
#  1. Renames PayrollPeriod -> PayrollRun (both model state and DB table)
#  2. Adds run_type to PayrollRun for parallel payroll support
#  3. Updates unique_together to (organization, year, month, run_type)
#  4. Adds aggregate columns to PayrollRecord
#  5. Adds FINALIZED status to PayrollRun and PayrollRecord
#  6. Adds salary_structure FK to CompensationHistory
#  7. Adds calculation_type to SalaryStructureComponent
#  8. Creates PayrollAdjustment and PayrollLineItem

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0014_alter_employee_employee_code_and_more'),
        ('organization', '0012_organizationmembership'),
        ('payroll', '0006_salarycomponent_salarystructure_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Step 1: Rename the model (and DB table) from PayrollPeriod -> PayrollRun
        migrations.RenameModel(
            old_name='PayrollPeriod',
            new_name='PayrollRun',
        ),

        # Step 2: Drop old unique_together (org, year, month) before adding run_type
        migrations.AlterUniqueTogether(
            name='payrollrun',
            unique_together=set(),
        ),

        # Step 3: Add run_type field
        migrations.AddField(
            model_name='payrollrun',
            name='run_type',
            field=models.CharField(default='REGULAR', max_length=50),
        ),

        # Step 4: Re-add unique_together with run_type
        migrations.AlterUniqueTogether(
            name='payrollrun',
            unique_together={('organization', 'year', 'month', 'run_type')},
        ),

        # Step 5: Update status choices on PayrollRun to add FINALIZED
        migrations.AlterField(
            model_name='payrollrun',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('approved', 'Approved'),
                    ('finalized', 'Finalized'),
                ],
                default='draft',
                max_length=20,
            ),
        ),

        # Step 6: Update status choices on PayrollRecord to add FINALIZED
        migrations.AlterField(
            model_name='payrollrecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('approved', 'Approved'),
                    ('finalized', 'Finalized'),
                ],
                default='draft',
                max_length=20,
            ),
        ),

        # Step 7: Add aggregate summary columns to PayrollRecord
        migrations.AddField(
            model_name='payrollrecord',
            name='total_earnings',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12),
        ),
        migrations.AddField(
            model_name='payrollrecord',
            name='total_deductions',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12),
        ),
        migrations.AddField(
            model_name='payrollrecord',
            name='employer_contributions',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12),
        ),
        migrations.AddField(
            model_name='payrollrecord',
            name='total_tax',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12),
        ),

        # Step 8: Add salary_structure FK to CompensationHistory
        migrations.AddField(
            model_name='compensationhistory',
            name='salary_structure',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='compensation_history',
                to='payroll.salarystructure',
            ),
        ),

        # Step 9: Expand SalaryComponent.kind choices + increase max_length
        migrations.AlterField(
            model_name='salarycomponent',
            name='kind',
            field=models.CharField(
                choices=[
                    ('earning', 'Earning'),
                    ('deduction', 'Deduction'),
                    ('employer_contribution', 'Employer Contribution'),
                    ('tax', 'Tax'),
                ],
                max_length=30,
            ),
        ),

        # Step 10: Add calculation_type to SalaryStructureComponent
        migrations.AddField(
            model_name='salarystructurecomponent',
            name='calculation_type',
            field=models.CharField(
                choices=[
                    ('FIXED_AMOUNT', 'Fixed Amount'),
                    ('PERCENTAGE_OF_BASIC', 'Percentage of Basic'),
                ],
                default='FIXED_AMOUNT',
                max_length=50,
            ),
        ),

        # Step 11: Create PayrollAdjustment
        migrations.CreateModel(
            name='PayrollAdjustment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('period_year', models.PositiveSmallIntegerField()),
                ('period_month', models.PositiveSmallIntegerField()),
                ('reason', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('approved', 'Approved'),
                        ('processed', 'Processed'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('component', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='payroll.salarycomponent')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payroll_adjustments', to='employees.employee')),
            ],
        ),

        # Step 12: Create PayrollLineItem
        migrations.CreateModel(
            name='PayrollLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    choices=[
                        ('EARNING', 'Earning'),
                        ('DEDUCTION', 'Deduction'),
                        ('EMPLOYER_CONTRIBUTION', 'Employer Contribution'),
                        ('TAX', 'Tax'),
                    ],
                    max_length=50,
                )),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('is_backfilled', models.BooleanField(default=False)),
                ('calculation_metadata', models.JSONField(blank=True, default=dict)),
                ('component', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='payroll.salarycomponent')),
                ('payroll_record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='payroll.payrollrecord')),
                ('source_adjustment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='payroll.payrolladjustment')),
                ('source_structure_component', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='payroll.salarystructurecomponent')),
            ],
        ),
    ]
