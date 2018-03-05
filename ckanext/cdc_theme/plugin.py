
from collections import OrderedDict

import pylons

from jinja2 import Undefined
from six import text_type

import ckan.plugins as plugins
import ckan.plugins.toolkit as tk

import ckan.model as model
from sqlalchemy import Table, select, join, func, and_



from ckan.lib.activity_streams import \
    activity_stream_string_functions as activity_streams

from feedback_model import init_db, UnpublishedFeedback

from ckan.lib.plugins import DefaultTranslation

def table(name):
    return Table(name, model.meta.metadata, autoload=True)


def top_rated_datasets(limit=3):
    # NB Not using sqlalchemy as sqla 0.4 doesn't work using both group_by
    # and apply_avg 
	
    print "top rated init"    

    package = table('package')
    rating = table('review')
    sql = select([package.c.id, func.avg(rating.c.rating), func.count(rating.c.rating)], from_obj=[package.join(rating)]).\
          where(and_(package.c.private==False, package.c.state=='active')). \
          group_by(package.c.id).\
          order_by(func.avg(rating.c.rating).desc(), func.count(rating.c.rating).desc()).\
          limit(limit)
    res_ids = model.Session.execute(sql).fetchall()
    # res_pkgs = [(model.Session.query(model.Package).get(text_type(pkg_id)), avg, num) for pkg_id, avg, num in res_ids]
	
    res_pkgs = [(tk.get_action('package_show')(data_dict={'id': model.Session.query(model.Package).get(text_type(package_id))})) for package_id,avg,num in res_ids]
	
    return res_pkgs

def most_recent_datasets(num=3):
    """Return a list of most recent modified datasets."""

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

    print datasets[:num]	 
    return datasets[:num]


def most_new_datasets(num=3):
	
    """Return a list of most new datasets."""
    search_dict = {
        'sort': 'metadata_created desc',
        'rows': num
    }

    items = tk.get_action('package_search')({}, search_dict)

    result = []
    for item in items['results']:
        result.append({
            'title': item['title'],
            'metadata_created': item['metadata_created'],
            'href': '/' + item['type'] + '/' + item['name']
     })

    return result



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
        #result = tk.get_action('resource_search')({},{'query':'name:'})
        #return result('count')

        ds = dataset_list()
        count = 0
        for dsname in ds:
                data_dict2 = {'id':dsname,'include_tracking': True}
                ds_item = tk.get_action('package_show')(data_dict=data_dict2)
                count = count + ds_item['num_tags']
        return count

def showcase_count():
	return tk.get_action('package_search')({}, {"rows": 1, 'fq': 'dataset_type:showcase'})['count']

def groups():
    """Return a list of groups"""

    return tk.get_action('group_list')({}, {'all_fields': True, 'include_dataset_count': True})


def organizations():
    """Return a list of organizations"""

    return tk.get_action('organization_list')({}, {'all_fields': True })


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
		'cdc_theme_most_new_datasets': most_new_datasets,
                'cdc_theme_popular_datasets': get_summary_list,
		'cdc_theme_top_rated_datasets': top_rated_datasets,
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
	additional_info_controller = 'ckanext.cdc_theme.controller:AdditionalInfoController'
	cdc_showcase_controller = 'ckanext.cdc_theme.controller:CDC_ShowcaseController'

        map.connect('view_feedback', '/dataset/{id}/feedback', action='view_feedback',
                    controller=unpublished_feedback_controller)
        map.connect('view_org', '/unpublished_report/{org_id}', action='view_org',
                    controller=unpublished_report_controller)	
	map.connect('read_carousel','/showcase/carousel_view/{id}', action='read_carousel', 
		    controller=cdc_showcase_controller)
	
	map.connect('dataset_additional_info','/dataset/additional_info/{id}', action='additional_info', 
		    controller=additional_info_controller, ckan_icon='info')
        return map
