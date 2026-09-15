import re

filepath = 'backend/apps/attendance/serializers.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''    def validate_work_days(self, value):
        if value:
            days = value.split(',')
            for day in days:
                if not day.strip().isdigit() or int(day.strip()) < 0 or int(day.strip()) > 6:
                    raise serializers.ValidationError("work_days must be a comma-separated list of integers between 0 and 6.")
        return value'''

new_func = '''    def validate_work_days(self, value):
        if value:
            days = value.split(',')
            seen = set()
            for day in days:
                day_stripped = day.strip()
                if not day_stripped.isdigit() or int(day_stripped) < 0 or int(day_stripped) > 6:
                    raise serializers.ValidationError("work_days must be a comma-separated list of integers between 0 and 6.")
                if day_stripped in seen:
                    raise serializers.ValidationError("work_days cannot contain duplicate days.")
                seen.add(day_stripped)
        return value'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Could not find the function to replace")
