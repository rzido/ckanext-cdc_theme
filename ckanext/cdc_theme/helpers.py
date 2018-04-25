from ckan.plugins import toolkit
from ckan.lib.i18n import get_lang
import ckan.lib.i18n as i18n
from ckan.common import config,_, c
import ckan.logic as logic
import ckan.lib.base as base
import ckan.model as model
from ckan.model.package import Package
from ckan.lib.dictization.model_dictize import group_list_dictize
import re


NotFound = logic.NotFound
abort = base.abort



def call_toolkit_function(fn, args, kwargs):
    return getattr(toolkit,fn)(*args, **kwargs)


def add_locale_to_source(kwargs, locale):
    copy = kwargs.copy()
    source = copy.get('data-module-source', None)
    if source:
            copy.update({'data-module-source': source + '_' + locale})
            return copy
    return copy

def get_current_lang():
    return get_lang()


def scheming_field_only_default_required(field, lang):

    if field and field.get('only_default_lang_required') and lang == config.get('ckan.locale_default', 'en'):
        return True

    return False

def scheming_multiple_field_required(field, lang):
    """
    Return field['required'] or guess based on validators if not present.
    """
    if 'required' in field:
        return field['required']
    if 'required_language' in field and field['required_language'] == lang:
        return True
    return 'not_empty' in field.get('validators', '').split()


def get_current_date():
    import datetime
    return datetime.date.today().strftime("%d.%m.%Y")

# This function list packages for a group_type (group, collection,..)
def get_package_groups_by_type(package_id, group_type):
    context = {'model': model, 'session': model.Session,
               'for_view': True, 'use_cache': False}

    group_list = []

    data_dict = {
        'all_fields': True,
        'include_extras': True,
        'type': group_type
    }

    groups = logic.get_action('group_list')(context, data_dict)

    try:
        pkg_obj = Package.get(package_id)
        pkg_group_ids = set(group['id'] for group in group_list_dictize(pkg_obj.get_groups(group_type, None), context))
        group_list = [group
                      for group in groups if
                      group['id'] in pkg_group_ids]
    except (NotFound):
        abort(404, _('Dataset not found'))

    return group_list


# This is not the most efficient way of listing package groups that include all group schema fields, however
# at this point the only way without major CKAN core changes (6aika/sixodp)
def get_package_groups(package_id):
    context = {'model': model, 'session': model.Session,
               'for_view': True, 'use_cache': False}

    data_dict = {
        'all_fields': True,
        'include_extras': True
    }

    groups = logic.get_action('group_list')(context, data_dict)
    group_list = []

    try:
        pkg_obj = Package.get(package_id)
        pkg_group_ids = set(group['id'] for group
                        in group_list_dictize(pkg_obj.get_groups('group', None), context))

        group_list = [group
                     for group in groups if
                     group['id'] in pkg_group_ids]

        if c.user:
            context = {'model': model, 'session': model.Session,
                       'user': c.user, 'for_view': True,
                       'auth_user_obj': c.userobj, 'use_cache': False,
                       'is_member': True}

            data_dict = {'id': package_id}
            users_groups = logic.get_action('group_list_authz')(context, data_dict)

            user_group_ids = set(group['id'] for group
                                 in users_groups)

            for group in group_list:
                group['user_member'] = (group['id'] in user_group_ids)
                
                
            c.group_dropdown = [[group['id'], group]
                                 for group in group_list if
                                 group['id'] in pkg_group_ids]

    except (NotFound):
        abort(404, _('Dataset not found'))

    return group_list


_LOCALE_ALIASES = {'en_GB': 'en', 'es' : 'es', 'en': 'en', 'gl': 'gl'}

def get_lang_prefix():
    language = i18n.get_lang()
    if language in _LOCALE_ALIASES:
        language = _LOCALE_ALIASES[language]

    return language

def get_translated_or_default_locale(data_dict, field):
    language = i18n.get_lang()
    if language in _LOCALE_ALIASES:
        language = _LOCALE_ALIASES[language]

    try:
        value = data_dict[field+'_translated'][language]
        if value:
            return value
        else:
            return data_dict[field+'_translated'][config.get('ckan.locale_default', 'en')]
    except KeyError:
        return data_dict.get(field, '')


def show_qa():

    from ckan.plugins import plugin_loaded

    if plugin_loaded('qa'):
        return True

    return False


types = {
    'web': ('html', 'data', 'esri rest', 'gov', 'org', ''),
    'preview': ('csv', 'xls', 'txt', 'jpg', 'jpeg', 'png', 'gif'),
    # "web map application" is deprecated in favour of "arcgis online map"
    'map': ('wms', 'kml', 'kmz', 'georss', 'web map application', 'arcgis online map'),
    'plotly': ('csv', 'xls', 'excel', 'openxml', 'access', 'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv','text/tab-separated-values',
        'application/matlab-mattext/x-matlab', 'application/x-msaccess',
        'application/msaccess', 'application/x-hdf', 'application/x-bag'),
    'cartodb': ('csv', 'xls', 'excel', 'openxml', 'kml', 'geojson', 'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/csv', 'application/vnd.google-earth.kml+xml',
        'application/vnd.geo+json'),
    'arcgis': ('esri rest', 'wms', 'kml', 'kmz', 'application/vnd.google-earth.kml+xml', 'georss')
}

def is_type_format(type, resource):
    if resource and type in types:
        format = resource.get('format', 'data').lower()
        # TODO: convert mimetypes to formats so we dont have to do this.
        mimetype = resource.get('mimetype')
        if mimetype:
            mimetype = mimetype.lower()
        if format in types[type] or mimetype in types[type]:
            return True
    return False

def is_web_format(resource):
    return is_type_format('web', resource)

def is_preview_format(resource):
    return is_type_format('preview', resource)

def is_map_format(resource):
    return is_type_format('map', resource)

def is_plotly_format(resource):
    return is_type_format('plotly', resource)

def is_cartodb_format(resource):
    return is_type_format('cartodb', resource)

def is_arcgis_format(resource):
    return is_type_format('arcgis', resource)

def arcgis_format_query(resource):
    mimetype = resource.get('mimetype', None)
    kmlstring = re.compile('(kml|kmz)');
    if kmlstring.match(str(mimetype)):
        return 'kml'
    else:
        # wms, georss
        return mimetype

def convert_resource_format(format):
    if format: format = format.lower()
    formats = RESOURCE_MAPPING.keys()
    if format in formats:
        format = RESOURCE_MAPPING[format][1]
    else:
        format = 'Web Page'
    return format

