import os

filepath = 'backend/apps/attendance/tests_shift.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "'effective_to': None",
    "'effective_to': ''"
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
