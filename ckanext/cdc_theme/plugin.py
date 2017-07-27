
from collections import OrderedDict

import pylons

from jinja2 import Undefined

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk


from ckan.lib.activity_streams import \
    activity_stream_string_functions as activity_streams

from feedback_model import init_db, UnpublishedFeedback

from ckan.lib.plugins import DefaultTranslation

def most_recent_datasets(num=3):
    """Return a list of recent datasets."""

    # the current_package_list_with_resources action returns private resources
    # which need to be filtered

    # TO BE FIXED. When number of datasets with resources is less than num=3. 	

    datasets = []
    i = 0
    while len(datasets) < num:
        datasets += filter(lambda ds: not ds['private'],
                           tk.get_action('current_package_list_with_resources')({},
                                         {'limit': num, 'offset': i * num}))
        i += 1

    return datasets[:num]


def get_summary_list(num_packages):

    list_without_summary = tk.get_action('package_search')(data_dict={'rows':num_packages,'sort':'metadata_modified desc'})['results']
    list_with_summary = []
    for package in list_without_summary:
        list_with_summary.append(tk.get_action('package_show')(
                                 data_dict={'id':package['name'],'include_tracking':True})
                                 )
    return list_with_summary


def showcases(num_packages):

    list_without_summary = tk.get_action('package_search')(data_dict={'rows':num_packages,'fq': 'dataset_type:showcase'})['results']
    list_with_summary = []
    for package in list_without_summary:
        list_with_summary.append(tk.get_action('package_show')(
                                 data_dict={'id':package['name'],'include_tracking':True})
                                 )
    return list_with_summary


def apps(featured_only=True):
    """Return apps for all datasets."""

    apps = tk.get_action('related_list')({}, {'type_filter': 'application',
                                              'featured': featured_only})

    return apps


# dataset_list: Devuelve la lista de datasets 
# dataset_list: Returns datasets name list
def dataset_list():
	return tk.get_action('package_list')(data_dict={})

def dataset_count():
    """Return a count of all datasets"""

    result = tk.get_action('package_search')({}, {'rows': 1})
    return result['count']


def resource_count():
	ds = dataset_list()
	count = 0
	for dsname in ds:
		data_dict = {'id':dsname}
		dsitem = tk.get_action('package_show')(data_dict=data_dict)
		# count = count + dsitem['num_resources']
		 
	return count

def showcase_count():
	return tk.get_action('package_search')({}, {"rows": 1, 'fq': 'dataset_type:showcase'})['count']

def groups():
    """Return a list of groups"""

    return tk.get_action('group_list')({}, {'all_fields': True})


def organizations():
    """Return a list of organizations"""

    return tk.get_action('organization_list')({}, {'all_fields': True})


def user_feedback(pkgid, userid):
    """Return user feedback for a dataset"""

    if isinstance(userid, Undefined):
        return None
    feedback = UnpublishedFeedback.get(dataset=pkgid, user=userid)
    if feedback is None:
        feedback = UnpublishedFeedback()
    return feedback


def feedback_for_pkg(pkgid):
    """Return all feedback for a dataset"""

    return UnpublishedFeedback.get_for_package(pkgid).all()


# monkeypatch activity streams
activity_streams['changed group'] = (
    lambda c, a: tk._("{actor} updated the topic {group}")
)

activity_streams['deleted group'] = (
    lambda c, a: tk._("{actor} deleted the topic {group}")
)

activity_streams['new group'] = (
    lambda c, a: tk._("{actor} created the topic {group}")
)



class CDCThemePlugin(plugins.SingletonPlugin, DefaultTranslation):
    """Coruna Open Data theme plugin based on OpenDataPhilly theme plugin.

    """

    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)    
    plugins.implements(plugins.IRoutes)
    plugins.implements(plugins.ITranslation)

   

    def update_config(self, config):
        """Register this plugin's template dir"""

        tk.add_template_directory(config, 'templates')

        # this adds directories to make public so we can include custom CSS
        # and javascript.
        # see http://docs.ckan.org/en/latest/theming/fanstatic.html
        tk.add_public_directory(config, 'public')
        tk.add_resource('fanstatic', 'cdc_theme')
        init_db()

    def get_helpers(self):
        """Register cdc_theme_* helper functions"""

        return {'cdc_theme_most_recent_datasets': most_recent_datasets,
                'cdc_theme_popular_datasets': get_summary_list,
                'cdc_theme_dataset_count': dataset_count,
                'cdc_theme_dataset_list': dataset_list,
                'cdc_theme_resource_count': resource_count,
		'cdc_theme_showcase_count': showcase_count,		
                'cdc_theme_groups': groups,
                'cdc_theme_organizations': organizations,
		'cdc_theme_showcases': showcases,
                'cdc_theme_apps': apps,
                'unpublished_count': UnpublishedFeedback.count_for_package,
                'user_feedback': user_feedback,
                'feedback_for_pkg': feedback_for_pkg}

    def before_map(self, map):
        return map

    def after_map(self, map):
        unpublished_feedback_controller = 'ckanext.cdc_theme.controller:UnpublishedFeedbackController'
        unpublished_report_controller = 'ckanext.cdc_theme.controller:UnpublishedReportController'

        map.connect('view_feedback', '/dataset/{id}/feedback', action='view_feedback',
                    controller=unpublished_feedback_controller)
        map.connect('view_org', '/unpublished_report/{org_id}', action='view_org',
                    controller=unpublished_report_controller)
        return map
