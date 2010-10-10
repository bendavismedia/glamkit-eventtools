from datetime import datetime, time
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from django.conf import settings
from eventtools.conf.settings import CHECK_PERMISSION_FUNC

MIN = "start"
MAX = "end"

def datetimeify(d, t=None, clamp=MIN):
    # pass in a date or a date and a time or a datetime, pass out a datetime.
    if isinstance(d, datetime):
        return d
    if t:
        return datetime.combine(d, t)
    if clamp.lower()==MAX:
        return datetime.combine(d, time.max)
    return datetime.combine(d, time.min)

class OccurrenceReplacer(object):
    """
    When getting a list of occurrences, the last thing that needs to be done
    before passing it forward is to make sure all of the occurrences that
    have been stored in the database replace, in the list you are returning,
    the generated ones that are equivalent.  This class makes this easier.
    """
    def __init__(self, exceptional_occurrences):
        lookup = [((occ.event, occ.unvaried_timespan), occ) for occ in exceptional_occurrences]
        self.lookup = dict(lookup)

    def get_occurrence(self, occ):
        """
        Return a exceptional occurrences set matching the occ and remove it from lookup since it
        has already been matched
        """
        return self.lookup.pop((occ.event, occ.unvaried_timespan), occ)

    def has_occurrence(self, occ):
        return (occ.generator.event, occ.unvaried_timespan) in self.lookup.keys()

    def get_additional_occurrences(self, start_dt, end_dt):
        """
        Return exceptional occurrences which are now in the period
        """
        for key, occ in self.lookup.items():
            # omitted and occ.timespan.end_datetime >= start_dt - unneccessary.
            # other reasons, except cancelled, to omit?
            if (occ.timespan.start_datetime >= start_dt and occ.timespan.start_datetime <= end_dt and not occ.cancelled):
                yield occ

class check_event_permissions(object):

    def __init__(self, f):
        self.f = f
        self.contenttype = ContentType.objects.get(app_label='events', model='event')

    def __call__(self, request, *args, **kwargs):
        user = request.user
        object_id = kwargs.get('event_id', None)
        try:
            obj = self.contenttype.get_object_for_this_type(pk=object_id)
        except self.contenttype.model_class().DoesNotExist:
            obj = None
        allowed = CHECK_PERMISSION_FUNC(obj, user)
        if not allowed:
            return HttpResponseRedirect(settings.LOGIN_URL)
        return self.f(request, *args, **kwargs)


def coerce_date_dict(date_dict):
    """
    given a dictionary (presumed to be from request.GET) it returns a tuple
    that represents a date. It will return from year down to seconds until one
    is not found.  ie if year, month, and seconds are in the dictionary, only
    year and month will be returned, the rest will be returned as min. If none
    of the parts are found return an empty tuple.
    """
    keys = ['year', 'month', 'day', 'hour', 'minute', 'second']
    retVal = {
                'year': 1,
                'month': 1,
                'day': 1,
                'hour': 0,
                'minute': 0,
                'second': 0}
    modified = False
    for key in keys:
        try:
            retVal[key] = int(date_dict[key])
            modified = True
        except KeyError:
            break
    return modified and retVal or {}

