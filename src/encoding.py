import sys

_fallbacklocalecharset = "iso-8859-1"

try:
    # works only in python > 2.3
    _localecharset = locale.getpreferredencoding()
except:
    try:
        _localecharset = locale.getdefaultlocale()[1]
    except:
        try:
            _localecharset = sys.getdefaultencoding()
        except:
            _localecharset = _fallbacklocalecharset
if _localecharset in [None, 'ascii', 'ANSI_X3.4-1968']:
    _localecharset = _fallbacklocalecharset

_fs_encoding = sys.getfilesystemencoding()

# exported functions

def encode(ustring):
    return ustring.encode(_localecharset, "replace")

def decode_path(path):
    return path.decode(_fs_encoding)
