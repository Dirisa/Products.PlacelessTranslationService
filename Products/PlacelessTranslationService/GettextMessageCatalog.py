##############################################################################
#    Copyright (C) 2001, 2002, 2003 Lalo Martins <lalo@laranja.org>,
#                  Zope Corporation and Contributors

#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307, USA
"""A simple implementation of a Message Catalog.

$Id: GettextMessageCatalog.py,v 1.3.2.2 2003/12/23 13:31:36 tiran Exp $
"""

from gettext import GNUTranslations, NullTranslations
import os, types, codecs
from types import DictType, StringType, UnicodeType
from OFS.Traversable import Traversable
from Persistence import Persistent
from Acquisition import Implicit
from App.Management import Tabs
import re
from PlacelessTranslationService import log, Registry
from tempfile import mktemp
from msgfmt import make as compileMo
from DateTime import DateTime
import Globals

try:
    True
except NameError:
    True=1
    False=0

try:
    from Products.OpenPT.OpenPTFile import OpenPTFile as ptFile
except ImportError:
    from Products.PageTemplates.PageTemplateFile import PageTemplateFile
    from Globals import package_home
    def ptFile(id, *filename):
        if type(filename[0]) is types.DictType:
            filename = list(filename)
            filename[0] = package_home(filename[0])
        filename = os.path.join(*filename)
        if not os.path.splitext(filename)[1]:
            filename = filename + '.pt'
        return PageTemplateFile(filename, '', __name__=id)

# template to use to write missing entries to .missing
missing_template = u"""msgid "%(id)s"
msgstr ""
"""

orig_text_template = u"""
#. %(text)s
"""

orig_text_line_joiner = u"\n#. "

permission = 'View management screens'

translationRegistry = Registry()
registerTranslation = translationRegistry.register

def getMessage(catalog, id, orig_text=None):
    """
    """
    msg = catalog.gettext(id)
    if msg is id:
        raise KeyError
    if type(msg) is StringType:
        msg = unicode(msg, catalog._charset)
    return msg

class GettextMessageCatalog(Persistent, Implicit, Traversable, Tabs):
    """
    Message catalog that wraps a .po file in the filesystem and stores
    the compiled po file in the zodb
    """
    meta_type = title = 'Gettext Message Catalog'
    icon = 'misc_/PlacelessTranslationService/GettextMessageCatalog.png'
    __roles__=('Manager',)
    title__roles__=__roles__
    
    _file_mod_time = 0
    _parsed = 0
    
    def __init__(self, pofile):
        """Initialize the message catalog"""
        self._pofile = pofile
        self.id = os.path.split(self._pofile)[-1].split('.')[0]
        self._prepareTranslations()

    def _prepareTranslations(self):
        """ """
        # XXX self._updateFromFS()
        tro = None
        if getattr(self, '_v_tro', None) is None:
            self._v_tro = tro = translationRegistry.get(self.id, None)
        if tro is None:
            tro = self._getTro()
            self._language = (tro._info.get('language-code', None) # new way
                           or tro._info.get('language', None)) # old way
            self._domain = tro._info.get('domain', None)
            if self._language is None or self._domain is None:
                raise ValueError, 'potfile has no metadata'
            self._language = self._language.lower().replace('_', '-')
            self._other_languages = tro._info.get('x-is-fallback-for', '').split()
            self.preferred_encodings = tro._info.get('preferred-encodings', '').split()
            self.name = unicode(tro._info.get('language-name', ''), tro._charset)
            self.default_zope_data_encoding = tro._charset
            translationRegistry[self.id] = self._v_tro = tro
            # XXX check it
            missingFileName = self._pofile[:-2] + 'missing'
            if os.access(missingFileName, os.W_OK):
                self._missing = MissingIds(missingFileName, self._v_tro._charset)
            else:
                self._missing = None
            if self.name:
                self.title = '%s language (%s) for %s' % (self._language, self.name, self._domain)
            else:
                self.title = '%s language for %s' % (self._language, self._domain)

    def filtered_manage_options(self, REQUEST=None):
        return self.manage_options

    def reload(self, REQUEST=None):
        "Forcibly re-read the file"
        if self.id in translationRegistry.keys():
            del translationRegistry[self.id]
        if hasattr(self, '_v_tro'):
            del self._v_tro
        self._prepareTranslations()
        log('reloading %s: %s' % (self.id, self.title))
        if hasattr(REQUEST, 'RESPONSE'):
            if not REQUEST.form.has_key('noredir'):
                REQUEST.RESPONSE.redirect(self.absolute_url())

    def _log_missing(self, id, orig_text):
        if self._missing is None:
            return
        self._missing.log(id, orig_text)

    def getMessage(self, id, orig_text=None, testing=False):
        """
        """
        self._prepareTranslations()
        try:
            msg = getMessage(self._v_tro, id, orig_text)
        except KeyError:
            if not testing:
                self._log_missing(id, orig_text)
            raise
        return msg

    queryMessage__roles__=None # Public
    def queryMessage(self, id, default=None):
        """
        """
        try:
            return self.getMessage(id, default, testing=True)
        except KeyError:
            if default is None:
                default = id
            return default

    def getLanguage(self):
        """
        """
        return self._language

    def getLanguageName(self):
        """
        """
        return self.name or self._language

    def getOtherLanguages(self):
        """
        """
        return self._other_languages

    def getDomain(self):
        """
        """
        return self._domain

    def getIdentifier(self):
        """
        """
        return self.id

    def getId(self):
        """
        """
        return self.id

    def getInfo(self, name):
        """
        """
        self._prepareTranslations()
        return self._v_tro._info.get(name, None)

    Title__roles__ = __roles__
    def Title(self):
        return self.title
        
    def _getTro(self):
        """ returns the translation object """
        # XXX self._updateFromFS()
        moData = compileMo(self._readFile())
        tro = None
        # I'm using a binary temp file because I had some problems
        # with cStringIO and unicode encoded data. But don't worry :)
        # Afaik operations on small temporary files are faster than
        # cStringIO - at least on linux :)
        tmp = mktemp(suffix="-%s.mo" % self.getId())
        try:
            moFile = open(tmp, 'w+b') # open for writing and reading
            moFile.write(moData)      # write compiled mo data
            moFile.seek(0)            # rewind
            tro = GNUTranslations(moFile)
            moFile.close()
        finally:
            # and finally delete the temp file
            os.unlink(tmp)
            
        if not tro:
            return NullTranslations()
        else:
            return tro
        
    def _readFile(self, reparse=False):
        """Read the data from the filesystem.
        
        Read the file indicated by exandpath(self._pofile), and parse the
        data if necessary.  'reparse' is set when reading the second
        time and beyond.
        """ 
        file = open(self._pofile, 'rb')
        try:
             data = file.readlines()
        finally:
             file.close()
        #if reparse:
        #    # XXX right?
        #    #self.reload()
        #    pass
        return data 
        
    # Refresh our contents from the filesystem if that is newer and we are
    # running in debug mode.
    def _updateFromFS(self):
        parsed = self._parsed
        if not parsed or Globals.DevelopmentMode:
            # XXX right?
            #self.reload()
            try:
                mtime=os.stat(self._pofile)[8]
            except:
                mtime=0
            if not parsed or mtime != self._file_mod_time:
                # if we have to read the file again, remove the cache
                self._readFile(1)
                self._file_mod_time = mtime
                self._parsed = 1    

    def get_size(self):
        """Get the size of the underlying file."""
        return os.path.getsize(self._pofile)

    def getModTime(self):
        """Return the last_modified date of the file we represent.

        Returns a DateTime instance.
        """
        # XXX self._updateFromFS()
        return DateTime(self._file_mod_time)

    def getObjectFSPath(self):
        """Return the path of the file we represent"""
        # XXX self._updateFromFS()
        return self._pofile

    ############################################################
    # Zope/OFS integration

    def manage_afterAdd(self, item, container): pass
    def manage_beforeDelete(self, item, container): pass
    def manage_afterClone(self, item): pass

    manage_options = (
        {'label':'Info', 'action':''},
        {'label':'Test', 'action':'zmi_test'},
        )

    index_html = ptFile('index_html', globals(), 'www', 'catalog_info')

    zmi_test = ptFile('zmi_test', globals(), 'www', 'catalog_test')

    file_exists__roles__ = __roles__
    def file_exists(self):
        try:
            file = open(self._pofile, 'rb')
        except:
            return False
        return True

    displayInfo__roles__ = __roles__
    def displayInfo(self):
        self._prepareTranslations()
        info = self._v_tro._info
        keys = info.keys()
        keys.sort()
        return [{'name': k, 'value': info[k]} for k in keys] + [
            {'name': 'full path', 'value': self._pofile},
            ]
    #
    ############################################################

class MissingIds(Persistent):
    def __init__(self, fileName, charset):
        self._fileName = fileName
        self._charset = charset
        self._ids = {}
        self._pattern = re.compile('msgid "(.*)"$')
        self.parseFile()
        self._v_file = None

    def parseFile(self):
        file = codecs.open(self._fileName, 'r', self._charset)
        for line in file.xreadlines():
            match = self._pattern.search(line)
            if match:
                msgid = match.group(1)
                self._ids[msgid] = 1
        file.close()

    def log(self, msgid, orig_text):
        if not self._ids.has_key(msgid):
            if getattr(self, '_v_file', None) is None:
              self._v_file = codecs.open(self._fileName, 'a', self._charset)
            if orig_text:
                orig_text = orig_text_line_joiner.join(orig_text.split('\n'))
                self._v_file.write(orig_text_template % {'text': orig_text})
            self._v_file.write(missing_template % {'id':msgid.replace('"', r'\"')})
            self._v_file.flush()
            self._ids[msgid]=1

