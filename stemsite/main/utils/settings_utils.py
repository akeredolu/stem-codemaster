# main/utils/settings_utils.py
from main.models import SiteSetting

def get_setting(key, default=None):
    try:
        return SiteSetting.objects.get(key=key).value
    except SiteSetting.DoesNotExist:
        return default

