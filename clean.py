import os

def clean_trailing_whitespace(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    cleaned_lines = [line.rstrip() + '\n' for line in lines]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(cleaned_lines)

clean_trailing_whitespace('backend/apps/attendance/models.py')
clean_trailing_whitespace('backend/apps/attendance/serializers.py')
