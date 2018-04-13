from ckan.plugins import toolkit
from ckan.lib.i18n import get_lang
import ckan.lib.i18n as i18n
from ckan.common import config
import ckan.logic as logic
import ckan.lib.base as base
import ckan.model as model
from ckan.model.package import Package
from ckan.lib.dictization.model_dictize import group_list_dictize
import re
import argparse
from google.cloud import translate
import six

NotFound = logic.NotFound
abort = base.abort

def translate_text(target, text):
    """Translates text into the target language.
    Target must be an ISO 639-1 language code.
    See https://g.co/cloud/translate/v2/translate-reference#supported_languages
    """
    translate_client = translate.Client()

    if isinstance(text, six.binary_type):
        text = text.decode('utf-8')

    # Text can also be a sequence of strings, in which case this method
    # will return a sequence of results for each text.
    result = translate_client.translate(
        text, target_language=target)
    
    return(result['translatedText'])
    

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

def get_current_date():
    import datetime
    return datetime.date.today().strftime("%d.%m.%Y")

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

_LOCALE_ALIASES = {'en_GB': 'en'}

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
