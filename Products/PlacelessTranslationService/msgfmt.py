#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Written by Martin v. L�wis <loewis@informatik.hu-berlin.de>
#
# modified by Christian Heimes <heimes@faho.rwth-aachen.de> for the
# Placeless Translation Service

"""Generate binary message catalog from textual translation description.

This program converts a textual Uniforum-style message catalog (.po file) into
a binary GNU catalog (.mo file).  This is essentially the same function as the
GNU msgfmt program, however, it is a simpler implementation.

This file was taken from Python-2.3.2/Tools/i18n and altered in several ways. 
Now you can simply use it from another python module:

  from msgfmt import make
  po = open('mypofile.po').readlines()
  mo = make(po)

where po is list of strings (readlines of a po file) and mo is the compiled mo
file as string.

Exceptions:

  * IOError if the file couldn't be read
  
  * PoSyntaxError if the po file has syntax errors

"""

import struct
import array
#from PlacelessTranslationService import log

try:
    True
except NameError:
    True=1
    False=0

__version__ = "1.1pts"

MESSAGES = {}


class PoSyntaxError(Exception):
    """ Syntax error in a po file """
    def __init__(self, lno):
        self.lno = lno
        
    def __str__(self):
        return 'Po file syntax error on line %d' % self.lno



def add(id, str, fuzzy):
    "Add a non-fuzzy translation to the dictionary."
    global MESSAGES
    if not fuzzy and str:
        MESSAGES[id] = str



def generate():
    "Return the generated output."
    global MESSAGES
    keys = MESSAGES.keys()
    # the keys are sorted in the .mo file
    keys.sort()
    offsets = []
    ids = strs = ''
    for id in keys:
        # For each string, we need size and file offset.  Each string is NUL
        # terminated; the NUL does not count into the size.
        offsets.append((len(ids), len(id), len(strs), len(MESSAGES[id])))
        ids += id + '\0'
        strs += MESSAGES[id] + '\0'
    output = ''
    # The header is 7 32-bit unsigned integers.  We don't use hash tables, so
    # the keys start right after the index tables.
    # translated string.
    keystart = 7*4+16*len(keys)
    # and the values start after the keys
    valuestart = keystart + len(ids)
    koffsets = []
    voffsets = []
    # The string table first has the list of keys, then the list of values.
    # Each entry has first the size of the string, then the file offset.
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1+keystart]
        voffsets += [l2, o2+valuestart]
    offsets = koffsets + voffsets
    output = struct.pack("Iiiiiii",
                         0x950412deL,       # Magic
                         0,                 # Version
                         len(keys),         # # of entries
                         7*4,               # start of key index
                         7*4+len(keys)*8,   # start of value index
                         0, 0)              # size and offset of hash table
    output += array.array("i", offsets).tostring()
    output += ids
    output += strs
    return output


#def getCharset(lst):
#    for item in lst:
#        item.strip()
#        if not item:
#            continue
#        # remove enclosing '"'
#        item = item[1:-1]
#        if ':' in item:
#            k, v = item.split(':', 1)
#            k = k.strip().lower()
#            v = v.strip()
#            if k == 'content-type':
#                return v.split('charset=')[1]
        
def make(podata):
    ID = 1
    STR = 2

    section = None
    fuzzy = 0

    #charset = getCharset(podata)
    #if charset and charset.lower().startswith('utf'):
    #    isUTF = True
    #    #log("isUTF")
    #else:
    #    isUTF = False

    # Parse the catalog
    lno = 0
    for l in podata:
        lno += 1
        # If we get a comment line after a msgstr, this is a new entry
        if l[0] == '#' and section == STR:
            add(msgid, msgstr, fuzzy)
            section = None
            fuzzy = 0
        # Record a fuzzy mark
        if l[:2] == '#,' and l.find('fuzzy'):
            fuzzy = 1
        # Skip comments
        if l[0] == '#':
            continue
        # Now we are in a msgid section, output previous section
        if l.startswith('msgid'):
            if section == STR:
                add(msgid, msgstr, fuzzy)
            section = ID
            l = l[5:]
            msgid = msgstr = ''
        # Now we are in a msgstr section
        elif l.startswith('msgstr'):
            section = STR
            l = l[6:]
        # Skip empty lines
        l = l.strip()
        if not l:
            continue
        # XXX: Does this always follow Python escape semantics?
        l = eval(l)
        if section == ID:
            msgid += l
        elif section == STR:
            msgstr += l
        else:
            raise PoSyntaxError(lno)
    # Add last entry
    if section == STR:
        add(msgid, msgstr, fuzzy)

    # Compute output
    return generate()
                      

def main(pofile='plone-nl.po'):
    from gettext import GNUTranslations
    from tempfile import mktemp
    import os
    
    po = open(pofile)
    compileMo = make
    moData = compileMo(po)
    tro = None
    # I'm using a binary temp file because I had some problems
    # with cStringIO and unicode encoded data. But don't worry :)
    # Afaik operations on small temporary files are faster than
    # cStringIO - at least on linux :)
    tmp = mktemp(suffix="-%s.mo" % pofile)
    try:
        moFile = open(tmp, 'w+b') # open for writing and reading
        moFile.write(moData)      # write compiled mo data
        moFile.seek(0)            # rewind
        tro = GNUTranslations(moFile)
    finally:
        # and finally delete the temp file
        moFile.close()
        #os.unlink(tmp)
    return tro._charset    

if __name__ == '__main__':
    print main()
    
