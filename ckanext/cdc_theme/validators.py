# From ckanext-sixodpscheming https://github.com/6aika/sixodp/


from ckan.common import _
import ckan.authz as authz
import ckan.plugins.toolkit as toolkit
import collections

import ckan.lib.helpers as h
import ckan.model as model
import ckan.logic.validators as validators
import ckan.lib.navl.dictization_functions as df
import re
import json
from ckan.logic import get_action


try:
    from ckanext.scheming.validation import (
        scheming_validator, validators_from_string)
except ImportError:
    # If scheming can't be imported, return a normal validator instead
    # of the scheming validator
    def scheming_validator(fn):
        def noop(key, data, errors, context):
            return fn(None, None)(key, data, errors, context)
        return noop
    validators_from_string = None

from ckan.common import config
Invalid = df.Invalid

import plugin

ObjectNotFound = toolkit.ObjectNotFound
c = toolkit.c

missing = toolkit.missing
ISO_639_LANGUAGE = u'^[a-z][a-z][a-z]?[a-z]?$'

def lower_if_exists(s):
    return s.lower() if s else s


def upper_if_exists(s):
    return s.upper() if s else s

def list_to_string(list):
    if isinstance(list, collections.Sequence) and not isinstance(list, basestring):
        return ','.join(list)
    return list

def tag_string_or_tags_required(key, data, errors, context):
    value = data.get(key)
    if not value or value is df.missing:
        data.pop(key, None)
        # Check existence of tags
        if any(k[0] == 'tags' for k in data):
                raise df.StopOnError
        else:
            errors[key].append((_('Missing value')))
            raise df.StopOnError


def set_private_if_not_admin(private):
    return True if not authz.is_sysadmin(c.user) else private

def convert_to_list(value):
    if isinstance(value, basestring):
        tags = [tag.strip() \
                for tag in value.split(',') \
                if tag.strip()]
    else:
        tags = value

    return tags



def create_tags(vocab):
    def callable(key, data, errors, context):

        value = data[key]

        if isinstance(value, list):
            add_to_vocab(context, value, vocab)
            data[key] = json.dumps(value)

    return callable

def create_fluent_tags(vocab):
    def callable(key, data, errors, context):
        value = data[key]
        if isinstance(value, str):
            value = json.loads(value)
        if isinstance(value, dict):
            for lang in value:
                add_to_vocab(context, value[lang], vocab + '_' + lang)
            data[key] = json.dumps(value)

    return callable

def add_to_vocab(context, tags, vocab):
    try:
        v = get_action('vocabulary_show')(context, {'id': vocab})
    except ObjectNotFound:
        v = plugin.create_vocabulary(vocab)

    context['vocabulary'] = model.Vocabulary.get(v.get('id'))

    for tag in tags:
        validators.tag_length_validator(tag, context)
        validators.tag_name_validator(tag, context)

        try:
            validators.tag_in_vocabulary_validator(tag, context)
        except Invalid:
            plugin.create_tag_to_vocabulary(tag, vocab)


def tag_list_output(value):
    if isinstance(value, dict) or len(value) is 0:
        return value
    return json.loads(value)

def repeating_text(key, data, errors, context):
    """
    Accept repeating text input in the following forms
    and convert to a json list for storage:
    1. a list of strings, eg.
       ["Person One", "Person Two"]
    2. a single string value to allow single text fields to be
       migrated to repeating text
       "Person One"
    3. separate fields per language (for form submissions):
       fieldname-0 = "Person One"
       fieldname-1 = "Person Two"
    """
    # just in case there was an error before our validator,
    # bail out here because our errors won't be useful
    if errors[key]:
        return

    value = data[key]
    # 1. list of strings or 2. single string
    if value is not toolkit.missing:
        if isinstance(value, basestring):
            value = [value]
        if not isinstance(value, list):
            errors[key].append(_('expecting list of strings'))
            return

        out = []
        for element in value:
            if not isinstance(element, basestring):
                errors[key].append(_('invalid type for repeating text: %r')
                                   % element)
                continue
            if isinstance(element, str):
                try:
                    element = element.decode('utf-8')
                except UnicodeDecodeError:
                    errors[key]. append(_('invalid encoding for "%s" value')
                                        % toolkit.lang)
                    continue
            out.append(element)

        if not errors[key]:
            data[key] = json.dumps(out)
        return

    # 3. separate fields
    found = {}
    prefix = key[-1] + '-'
    extras = data.get(key[:-1] + ('__extras',), {})

    for name, text in extras.iteritems():
        if not name.startswith(prefix):
            continue
        if not text:
            continue
        index = name.split('-', 1)[1]
        try:
            index = int(index)
        except ValueError:
            continue
        found[index] = text

    out = [found[i] for i in sorted(found)]
    data[key] = json.dumps(out)

def repeating_text_output(value):
    """
    Return stored json representation as a list, if
    value is already a list just pass it through.
    """
    if isinstance(value, list):
        return value
    if value is None:
        return []
    try:
        return json.loads(value)
    except ValueError:
        return [value]


@scheming_validator
def only_default_lang_required(field, schema):
    default_lang = ''
    if field and field.get('only_default_lang_required'):
        default_lang =  config.get('ckan.locale_default', 'en')

    def validator(key, data, errors, context):
        if errors[key]:
            return

        value = data[key]

        if value is not missing:
            if isinstance(value, basestring):
                try:
                    value = json.loads(value)
                except ValueError:
                    errors[key].append(_('Failed to decode JSON string'))
                    return
                except UnicodeDecodeError:
                    errors[key].append(_('Invalid encoding for JSON string'))
                    return
            if not isinstance(value, dict):
                errors[key].append(_('expecting JSON object'))
                return

            if field.get('only_default_lang_required') is not None and value.get(default_lang) is None:
                errors[key].append(_('Required language "%s" missing') % default_lang)
            return

        prefix = key[-1] + '-'
        extras = data.get(key[:-1] + ('__extras',), {})

        if extras.get(prefix + default_lang) == '' or extras.get(prefix + default_lang) is None:
            errors[key].append(_('Required language "%s" missing') % default_lang)

        return validator
    
    
"""
FIELD TYPE DATE PERIOD
"""
@scheming_validator
def date_period(field, schema):
    def validator(key, data, errors, context):
        """
        1. a JSON with dates, eg.
           {"1": {"to": "2016-05-28T00:00:00", "from": "2016-05-11T00:00:00"}}
        2. separate fields per date and time (for form submissions):
           fieldname-from-date-1 = "2012-09-11"
           fieldname-from-time-1 = "11:00"
           fieldname-from-date-2 = "2014-03-03"
           fieldname-from-time-2 = "09:45"
        """
        # just in case there was an error before that validator
        if errors[key]:
            return

        value = data[key]

        # 1. json
        if value is not missing:
            if isinstance(value, basestring):
                try:
                    value = json.loads(value)
                except ValueError, e:
                    errors[key].append(_('Invalid field structure, it is not a valid JSON'))
                    return
            if not isinstance(value, dict):
                 errors[key].append(_('Expecting valid JSON value'))
                 return

            out = {}
            for element in sorted(value):
                dates = value.get(element)
                with_date = False
                #if dates['from']:
                if 'from' in dates:
                    try:
                        date = h.date_str_to_datetime(dates['from'])
                        with_date = True
                    except (TypeError, ValueError), e:
                        errors[key].append(_('From value: Date format incorrect'))
                        continue
                #if dates['to']:
                if 'to' in dates:
                    try:
                        date = h.date_str_to_datetime(dates['to'])
                        with_date = True
                    except (TypeError, ValueError), e:
                        errors[key].append(_('To value: Date format incorrect'))
                        continue

                if not with_date:
                    errors[key]. append(_('Date period without from and to'))
                    continue
                out[str(element)] = dates

            if not errors[key]:
                data[key] = json.dumps(out)

            return

        # 3. separate fields
        found = {}
        short_prefix = key[-1] + '-'
        prefix = key[-1] + '-date-'
        extras = data.get(key[:-1] + ('__extras',), {})

        #Fase de validacion
        datetime_errors = False
        valid_indexes = []
        for name, text in extras.iteritems():
            if not name.startswith(prefix):
                continue
            if not text:
                continue

            datetime = text
            #Get time if exists
            index = name.split('-')[-1]
            type_field = name.split('-')[-2]
            time_value = extras.get(short_prefix+'time-'+type_field+'-'+index)
            #Add the time
            if time_value:
                datetime = text + ' ' + time_value

            #Create datetime and validation
            try:
                date = h.date_str_to_datetime(datetime)
                valid_indexes.append(index)
            except (TypeError, ValueError), e:
                errors[key].append(_('Date time format incorrect'))
                datetime_errors = True

        if datetime_errors:
            return

        valid_indexes = sorted(list(set(valid_indexes)))
        new_index = 1;
        for index in valid_indexes:
            period = {}

            #Get from
            date_from_value = extras.get(short_prefix+'date-from-'+index)
            if date_from_value:
                datetime = date_from_value
                time_from_value = extras.get(short_prefix+'time-from-'+index)
                if time_from_value:
                    datetime = date_from_value + " " + time_from_value
                try:
                    date = h.date_str_to_datetime(datetime)
                    period['from'] = date.strftime("%Y-%m-%dT%H:%M:%S")
                except (TypeError, ValueError), e:
                    continue

            date_to_value = extras.get(short_prefix+'date-to-'+index)
            if date_to_value:
                datetime = date_to_value
                time_to_value = extras.get(short_prefix+'time-to-'+index)
                if time_to_value:
                    datetime = date_to_value + " " + time_to_value
                try:
                    date = h.date_str_to_datetime(datetime)
                    period['to'] = date.strftime("%Y-%m-%dT%H:%M:%S")
                except (TypeError, ValueError), e:
                    continue

            if period:
                found[new_index] = period
                # only adds 1 to the new index with good periods
                new_index = new_index+1

        out = {}
        for i in sorted(found):
            out[i] = found[i]
        data[key] = json.dumps(out)

    return validator


def date_period_output(value):
    """
    Return stored json representation as a dict, if
    value is already a dict just pass it through.
    """
    if isinstance(value, dict):
        return value
    if value is None or isinstance(value, list):
        return {}
    try:
        return json.loads(value)
    except ValueError:
        return {}

    
"""
FIELD TYPE MULTIPLE URL
"""
@scheming_validator
def multiple_uri_text(field, schema):
    def validator(key, data, errors, context):
        """
        Accept repeating text input in the following forms
        and convert to a json list for storage:
        1. a list of strings, eg.
           ["http://url1", "http://url2"]
        2. a single string value to allow single text fields to be
           migrated to repeating text
           "http://url1"
        3. separate fields per language (for form submissions):
           fieldname-0 = "http://url1"
           fieldname-1 = "http://url2"
        """
        # just in case there was an error before that validator
        if errors[key]:
            return

        value = data[key]

        is_url = False
        if ('is_url' in field):
            is_url = field['is_url']

        # 1. list of strings or 2. single string
        if value is not missing:
            if isinstance(value, basestring):
                value = [value]
            if not isinstance(value, list):
                errors[key].append(_('Expecting list of strings'))
                return

            out = []
            for element in value:
                if not isinstance(element, basestring):
                    errors[key].append(_('Invalid type for repeating url text: %r')
                        % element)
                    continue
                    type(i)
                try:
                    if not isinstance(element, unicode):
                        element = element.decode('utf-8')
                    if element:
                        if is_url and not h.is_url(element):
                            errors[key].append(_('The URL format is not valid'))
                        else:
                            if not is_url and not dh.dge_is_uri(element):
                                errors[key].append(_('The URI format is not valid'))

                except UnicodeDecodeError:
                    errors[key]. append(_('Invalid encoding for "%s" value')
                        % lang)
                    continue
                out.append(element)

            if not errors[key]:
                data[key] = json.dumps(out)
            return

        # 3. separate fields
        found = {}
        prefix = key[-1] + '-'
        extras = data.get(key[:-1] + ('__extras',), {})

        #Validation
        url_errors = False
        for name, text in extras.iteritems():
            if not name.startswith(prefix):
                continue
            if not text:
                continue
            index = name.split('-', 1)[1]
            if text is not missing:
                if is_url and not h.is_url(text):
                    url_errors = True
                    name_error = key[:-1] + (name,)
                    errors[name_error] = [_('The URL format for "%s" is not valid') % text]
                else:
                    if not is_url and not dh.dge_is_uri(text):
                        url_errors = True
                        name_error = key[:-1] + (name,)
                        errors[name_error] = [_('The URI format for "%s" is not valid') % text]

        if url_errors:
            return

        for name, text in extras.iteritems():
            if not name.startswith(prefix):
                continue
            if not text:
                continue
            index = name.split('-', 1)[1]
            try:
                index = int(index)
            except ValueError:
                continue
            found[index] = text

        out = [found[i] for i in sorted(found)]
        data[key] = json.dumps(out)

    return validator

def multiple_uri_text_output(value):
    """
    Return stored json representation as a list, if
    value is already a list just pass it through.
    """
    if isinstance(value, list):
        return value
    if value is None:
        return []
    try:
        return json.loads(value)
    except ValueError:
        return [value]
