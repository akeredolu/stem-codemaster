from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Safely return dictionary.get(key). If dictionary is None or not a mapping, return None.
    Usage: {{ mydict|get_item:key }}
    """
    try:
        if dictionary is None:
            return None
        # If it's a QueryDict or mapping-like object, use get
        return dictionary.get(key)
    except Exception:
        # Safe fallback: if it supports indexing, try that, otherwise return None
        try:
            return dictionary[key]
        except Exception:
            return None
