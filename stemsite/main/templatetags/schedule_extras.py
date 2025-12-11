# main/templatetags/schedule_extras.py
from django import template
from itertools import groupby
from operator import attrgetter

register = template.Library()

@register.filter
def groupby_date(queryset, date_field):
    """Groups a queryset by a date field (returns a list of (date, items) tuples)."""
    sorted_qs = sorted(queryset, key=attrgetter(date_field))
    return [(key, list(group)) for key, group in groupby(sorted_qs, key=attrgetter(date_field))]

