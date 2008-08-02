import logging
import os
from os.path import isdir

from zope.deprecation import deprecate

import Globals
from Globals import package_home
pts_globals = globals()

CACHE_PATH = os.path.join(INSTANCE_HOME, 'var', 'pts')

from AccessControl import ModuleSecurityInfo, allow_module
from AccessControl.Permissions import view

from Products.PlacelessTranslationService.load import (
    _load_i18n_dir, _remove_mo_cache)
from Products.PlacelessTranslationService.utils import log

# # Apply import time patches
if not bool(os.getenv('DISABLE_PTS')):
    import patches

# BBB
import warnings
showwarning = warnings.showwarning
warnings.showwarning = lambda *a, **k: None
# ignore deprecation warnings on import
from Products.PlacelessTranslationService.PlacelessTranslationService import (
    PlacelessTranslationService, PTSWrapper, PTS_IS_RTL)
# restore warning machinery
warnings.showwarning = showwarning

# id to use in the Control Panel
cp_id = 'TranslationService'

# module level translation service
translation_service = None

# icon
misc_ = {
    'PlacelessTranslationService.png':
    Globals.ImageFile('www/PlacelessTranslationService.png', globals()),
    'GettextMessageCatalog.png':
    Globals.ImageFile('www/GettextMessageCatalog.png', globals()),
    }

# set product-wide attrs for importing
security = ModuleSecurityInfo('Products.PlacelessTranslationService')
allow_module('Products.PlacelessTranslationService')

security.declareProtected(view, 'getTranslationService')
@deprecate("The getTranslationService method of PTS is deprecated and "
           "will be removed in the next major version of PTS.")
def getTranslationService():
    """returns the PTS instance
    """
    return translation_service

@deprecate("The make_translation_service method of PTS is deprecated and "
           "will be removed in the next major version of PTS.")
def make_translation_service(cp):
    """Control_Panel translation service
    """
    global translation_service
    translation_service = PlacelessTranslationService('default')
    translation_service.id = cp_id
    cp._setObject(cp_id, translation_service)
    translation_service = PTSWrapper()
    return getattr(cp, cp_id)


def initialize(context):
    # allow for disabling PTS entirely by setting an environment variable.
    if bool(os.getenv('DISABLE_PTS')):
        log('Disabled by environment variable "DISABLE_PTS".', logging.WARNING)
        return

    cp = context._ProductContext__app.Control_Panel # argh
    if cp_id in cp.objectIds():
        cp_ts = getattr(cp, cp_id, None)
        # Clean up ourselves
        if cp_ts is not None:
            cp._delObject(cp_id)
            _remove_mo_cache(CACHE_PATH)

    # load translation files from all products
    products = [getattr(p, 'package_name', 'Products.' + p.id) for
                p in cp.Products.objectValues() if
                getattr(p, 'thisIsAnInstalledProduct', False)]
    # Sort the products by lower-cased package name to gurantee a stable
    # load order
    products.sort(key=lambda p: p.lower())
    log('products: %r' % products, logging.DEBUG)
    for prod in products:
        # prod is a package name, we fake a globals dict with it
        prod_path = package_home({'__name__' : prod})
        i18n_dir = os.path.join(prod_path, 'i18n')
        if isdir(i18n_dir):
            _load_i18n_dir(i18n_dir)
