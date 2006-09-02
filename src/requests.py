# -*- coding: ISO-8859-1 -*-

# Copyright (C) 2002 J�rg Lehmann <joerg@luga.de>
#
# This file is part of PyTone (http://www.luga.de/pytone/)
#
# PyTone is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2
# as published by the Free Software Foundation.
#
# PyTone is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PyTone; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import item

class request:
    def __repr__(self):
        return self.__class__.__name__

    __repr__ = __repr__

#
# database requests
#

class dbrequest:
    def __init__(self, songdbid):
        self.songdbid = songdbid

    def __repr__(self):
        return "%r->%r" % (self.__class__.__name__, self.songdbid)

    def __cmp__(self, other):
        cmp(hash(self), hash(other))

    def __hash__(self):
        # for the cashing system every dbrequest has to be hashable
        # by default we rely on self.__repr__ for computing the hash value
        return hash(repr(self))

class dbrequestsingle(dbrequest):
    """ db request yielding a single result (not a list) and requiring a
    specific songdb to work on
    """
    pass

class dbrequestsongs(dbrequest):
    """ db request yielding a list of songs, which have to be merged when querying multiple databases

    Note that the resulting list must not be changed by the caller,
    with the exception that the order of the items may be changed at
    will (for instance by sorting)

    """

    def __init__(self, songdbid, random=False, sort=False, filters=None):
        self.songdbid = songdbid
        self.sort = sort
        self.random = random
        self.filters = filters

    def __repr__(self):
        return "%r(%r, %r, random=%r)->%r" % (self.__class__.__name__, self.sort, self.filters, self.random, self.songdbid)
        

class dbrequestlist(dbrequest):
    """ db request yielding a result list (not containing songs),
    which have to be merged when querying multiple databases

    Note that the resulting list must not be changed by the caller!
    """
    def __init__(self, songdbid, sort=False, filters=None):
        self.songdbid = songdbid
        self.sort = sort
        self.filters = filters

    def __repr__(self):
        return "%r(%r, %r)->%r" % (self.__class__.__name__, self.sort, self.filters, self.songdbid)

#
# database requests which yield a single result
#

class getdatabasestats(dbrequest):
    """ return songdbstats instance for database """
    pass


class queryregistersong(dbrequestsingle):
    def __init__(self, songdbid, path):
        self.songdbid = songdbid
        self.path = path

    def __repr__(self):
        return "%r(%r)->%r" % (self.__class__.__name__, self.path, self.songdbid)


class getsong(dbrequestsingle):
    def __init__(self, songdbid, id):
        self.songdbid = songdbid
        self.id = id

    def __repr__(self):
        return "%r(%r)->%r" % (self.__class__.__name__, self.id, self.songdbid)


class getalbum(dbrequestsingle):
    def __init__(self, songdbid, album):
        self.songdbid = songdbid
        self.album = album

    def __repr__(self):
        return "%r(%r)->%r" % (self.__class__.__name__, self.album, self.songdbid)


class getartist(dbrequestsingle):
    def __init__(self, songdbid, artist):
        self.songdbid = songdbid
        self.artist = artist

    def __repr__(self):
        return "%r(%r)->%r" % (self.__class__.__name__, self.artist, self.songdbid)


class getplaylist(dbrequestsingle):
    def __init__(self, songdbid, path):
        self.songdbid = songdbid
        self.path = path

    def __repr__(self):
        return "%r(%r)->%r" % (self.__class__.__name__, self.path, self.songdbid)


class getsongsinplaylist(dbrequestsingle):
    """ return all songs stored in playlist path """
    def __init__(self, songdbid, path, random=False):
        self.songdbid = songdbid
        self.path = path 
        self.random = random

    def __repr__(self):
        return "%r(%r,random=%r)->%r" % (self.__class__.__name__,
                                         self.path, self.random, self.songdbid)

#
# database requests which yield a list of songs
#

class getsongs(dbrequestsongs):

    def __init__(self, songdbid, artist=None, album=None, sort=False, filters=None, random=False):
        dbrequestsongs.__init__(self, songdbid, random, sort)
        self.songdbid = songdbid
        self.artist = artist
        self.album = album
        self.filters = filters

    def __repr__(self):
        return "%r(%r, %r, sort=%r, filters=%r, random=%r)->%r" % (self.__class__.__name__,
                  self.artist, self.album, self.sort,  self.filters, self.random, self.songdbid)


class getlastplayedsongs(dbrequestsongs):

    def __init__(self, songdbid, random=False, sort=False, filters=None):
        dbrequestsongs.__init__(self, songdbid, random, sort, filters)


class gettopplayedsongs(dbrequestsongs):
    pass


class getlastaddedsongs(dbrequestsongs):
    pass


class getsongsinplaylists(dbrequestsongs):
    """ return all songs stored in all playlists """
    pass


class getartists(dbrequestlist):
    def __init__(self, songdbid, sort=False, filters=None):
        self.songdbid = songdbid
        self.sort = sort
        self.filters = filters

    def __repr__(self):
        return "%r(%r, %r)->%r" % (self.__class__.__name__, self.sort, self.filters, self.songdbid)


class getalbums(dbrequestlist):
    def __init__(self, songdbid, artist=None, sort=False, filters=None):
        self.songdbid = songdbid
        self.artist = artist
        self.sort = sort
        self.filters = filters

    def __repr__(self):
        return "%r(%r, %r, %r)->%r" % (self.__class__.__name__, self.artist, self.sort, self.filters, self.songdbid)


class getgenres(dbrequestlist):
    pass


class getdecades(dbrequestlist):
    pass


class getratings(dbrequestlist):
    pass


class getplaylists(dbrequestlist):
    pass

#
# database request yielding the numbe of items of a certain kind
#

class getnumberofsongs(dbrequest):
    def __init__(self, songdbid, artist=None, album=None, filters=None):
        self.songdbid = songdbid
        self.artist = artist
        self.album = album
        self.filters = filters

    def __repr__(self):
        return ( "%r(%r, %r, %r))->%r" %
                 (self.__class__.__name__,
                  self.artist, self.album, self.filters,
                  self.songdbid))


class dbrequestnumber(dbrequest):
    def __init__(self, songdbid, filters=None):
        self.songdbid = songdbid
        self.filters = filters

    def __repr__(self):
        return ( "%r(%r))->%r" % (self.__class__.__name__, self.filters, self.songdbid))


class getnumberofalbums(dbrequestnumber):
    pass

class getnumberofartists(dbrequestnumber):
    pass

class getnumberofdecades(dbrequestnumber):
    pass

class getnumberofgenres(dbrequestnumber):
    pass

class getnumberofratings(dbrequestnumber):
    pass

# songdbmanager

class getsongdbmanagerstats(request):
    """ request statistical information about songdbs and the request cache

    Returns services.songdb.songdbmanagerstats instance."""
    pass

#
# other requests for playlist and player service
#

class requestnextsong(request):
    """ request a song from playlistid. Go back in playlist if previous is set """
    def __init__(self, playlistid, previous=0):
        self.playlistid = playlistid
        self.previous = previous

    def __repr__(self):
        return "%r->%r,%r" % (self.__class__.__name__, `self.playlistid`, `self.previous`)


class getplaybackinfo(request):
    """ request info about song currently playing on player playerid """
    def __init__(self, playerid):
        self.playerid = playerid

    def __repr__(self):
        return "%r->%r" % (self.__class__.__name__, `self.playerid`)


class requestinput:
    def __init__(self, title, prompt, handler):
        self.title = title
        self.prompt = prompt
        self.handler = handler

    def __repr__(self):
        return "%r(%r,%r,%r)" % (self.__class__.__name__,
                              self.title, self.prompt, `self.handler`)


class playlistgetcontents(request):
    pass
