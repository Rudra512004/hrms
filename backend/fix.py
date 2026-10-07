import re

with open('D:/hrms/hrms/backend/apps/employees/views.py', 'r') as f:
    content = f.read()

# Add get_permissions to each ViewSet if missing
for vs in ['EmployeeDependentViewSet', 'EmployeeEducationViewSet', 'EmployeePriorExperienceViewSet']:
    if 'def get_permissions(self):' not in content.split(f'class {vs}')[1].split('class ')[0]:
        replacement = f'''class {vs}(viewsets.ModelViewSet):
    serializer_class = {vs.replace("ViewSet", "Serializer")}

    def get_permissions(self):
        return [IsAuthenticated()]
'''
        content = content.replace(f'''class {vs}(viewsets.ModelViewSet):
    serializer_class = {vs.replace("ViewSet", "Serializer")}''', replacement)

with open('D:/hrms/hrms/backend/apps/employees/views.py', 'w') as f:
    f.write(content)
