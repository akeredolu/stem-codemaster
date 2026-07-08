import re
from django.contrib.auth import get_user_model

User = get_user_model()

def generate_unique_username(full_name, enrollment_id):
    base_username = re.sub(r'\W+', '', full_name).lower()
    if not base_username:
        base_username = "student"

    username = f"{base_username}_{enrollment_id}"

    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{enrollment_id}_x"

    return username

