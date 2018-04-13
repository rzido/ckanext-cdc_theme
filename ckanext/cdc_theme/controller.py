

from ckanext.showcase.controller import ShowcaseController

import datetime

import ckan.plugins as p
import ckan.model as model
from ckan.plugins import toolkit as tk
from ckan.common import c






class CDC_ShowcaseController(ShowcaseController):
       def read_carousel(self, id, format='html'):
        '''
        Carousel view for a single showcase
        '''

        context = {'model': model, 'session': model.Session,
                   'user': c.user or c.author, 'for_view': True,
                   'auth_user_obj': c.userobj}
        data_dict = {'id': id}

        # check if showcase exists
        try:
            c.pkg_dict = tk.get_action('package_show')(context, data_dict)
        except tk.ObjectNotFound:
            tk.abort(404, tk._('Showcase not found'))
        except tk.NotAuthorized:
            tk.abort(404, tk._('Showcase not found'))
        # get showcase packages
        c.showcase_pkgs = tk.get_action('ckanext_showcase_package_list')(context, {'showcase_id': c.pkg_dict['id']})
       
        return tk.render("cdc_showcase/read.html",
        extra_vars={'dataset_type': 'showcase'})



class AdditionalInfoController(p.toolkit.BaseController):
    controller = 'ckanext.cdc_theme.controller:AdditionalInfoController' 
    def additional_info(self, id): 
        
        context = {'model': model, 'session': model.Session,
                   'user': c.user, 'for_view': True,
                   'auth_user_obj': c.userobj}
        data_dict = {'id': id, 'include_tracking': True}

        try:
           """ check_access('package_update', context, data_dict) """
        
        except tk.ObjectNotFound:
             tk.abort(404, tk._('Dataset not found'))
        except tk.NotAuthorized:
             tk.abort(401, tk._('Unauthorized to read package'))
        # check if package exists
        try:
            c.pkg_dict = tk.get_action('package_show')(context, data_dict)
            c.pkg = context['package']
        except (tk.ObjectNotFound, tk.NotAuthorized):
            tk.abort(404, tk._('Dataset not found'))

        package_type = c.pkg_dict['type'] or 'dataset'
        """ self._setup_template_variables(context, {'id': id},    """
        """                               package_type=package_type)  """

        return tk.render('package/additional_info.html',
                      extra_vars={'dataset_type': package_type})      
                
