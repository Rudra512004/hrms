import os

filepath = 'backend/apps/attendance/serializers.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_validate = '''        # Verify cross-tenant
        if employee and shift and employee.organization_id != shift.organization_id:
            raise serializers.ValidationError("Employee and Shift must belong to the same organization.")

        # Ensure we do not allow assigning an employee from another tenant
        request = self.context.get('request')
        if request and hasattr(request.user, 'employee'):
            org_id = request.user.employee.organization_id
            if employee and employee.organization_id != org_id:
                raise serializers.ValidationError("Cannot assign employee from another organization.")
            if shift and shift.organization_id != org_id:
                raise serializers.ValidationError("Cannot assign shift from another organization.")
                
        return attrs'''

new_validate = '''        # Verify cross-tenant
        if employee and shift and employee.organization_id != shift.organization_id:
            raise serializers.ValidationError({"employee": "Employee and Shift must belong to the same organization."})

        # Ensure we do not allow assigning an employee from another tenant
        request = self.context.get('request')
        if request and hasattr(request.user, 'employee'):
            org_id = request.user.employee.organization_id
            if employee and employee.organization_id != org_id:
                raise serializers.ValidationError({"employee": "Cannot assign employee from another organization."})
            if shift and shift.organization_id != org_id:
                raise serializers.ValidationError({"shift": "Cannot assign shift from another organization."})
                
        effective_from = attrs.get('effective_from', getattr(self.instance, 'effective_from', None))
        effective_to = attrs.get('effective_to', getattr(self.instance, 'effective_to', None))
        
        if effective_to and effective_from and effective_to < effective_from:
            raise serializers.ValidationError({"effective_to": "effective_to cannot be earlier than effective_from."})
            
        # Model clean for overlap validation
        instance = EmployeeShiftAssignment(**attrs)
        if self.instance:
            instance.pk = self.instance.pk
            if 'employee' not in attrs:
                instance.employee = self.instance.employee
            if 'shift' not in attrs:
                instance.shift = self.instance.shift
            if 'effective_from' not in attrs:
                instance.effective_from = self.instance.effective_from
        
        try:
            instance.clean()
        except serializers.ValidationError as e:
            raise e
        except Exception as e:
            # Django ValidationError
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                raise serializers.ValidationError(e.message_dict if hasattr(e, 'message_dict') else list(e.messages))
            raise e
            
        return attrs'''

content = content.replace(old_validate, new_validate)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
