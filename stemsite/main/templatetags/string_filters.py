from django import template

register = template.Library()

@register.filter
def split_by_comma(value):
    """Split a string by comma and return the list."""
    return [item.strip() for item in value.split(',')] if value else []

