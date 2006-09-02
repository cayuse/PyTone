# -*- coding: ISO-8859-1 -*-

# Copyright (C) 2002, 2003, 2004, 2005, 2006 J�rg Lehmann <joerg@luga.de>
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


import os.path, string, time
import config, dbitem, metadata
import events, hub, requests
import helper

# We import the _genrandomchoice function used in the songdb module.
# Maybe we should instead put it in a separate module
from services.songdb import _genrandomchoice

# helper function for usage in getinfo methods, which merges information about
# filters in third and forth columns of lines
def _mergefilters(lines, filters):
    # filter out filters which are to be shown
    filters = [filter for filter in filters if filter.name]
    if filters:
        for nr, filter in enumerate(filters[:4]):
            if len(lines) > nr:
                lines[nr][2:3] = [_("Filter:"), filter.name]
            else:
                lines.append(["", "", _("Filter:"), filter.name])
    return lines


class item(object):
    """ base class for various items presentend in the database and
    playlist windows (as opposed to those stored in the database
    itself (cf. module dbitem)"""

    def __init__(self, songdbid):
        """ each item has to be bound to a specific database
        identified by songdbid """
        self.songdbid = songdbid

    def getid(self):
        """ return unique id of item in context """
        raise NotImplementedError("has to be implemented by sub classes")

    def getname(self):
        """ short name used for item in lists """
        raise NotImplementedError("has to be implemented by sub classes")

    def getinfo(self):
        """ 4x4 array containing rows and columns used for display of item
        in iteminfowin"""
        return [["", "", "", ""]]

    def getinfolong(self):
        """ nx4 array containing rows and columns used for display of item
        in iteminfowin2"""
        return self.getinfo()

class diritem(item):

    """ item containing other items """

    def getname(self):
        return "%s/" % self.name

    def getid(self):
        return self.name

    def cmpitem(x, y):
        """ compare the two items x, y of diritem

        Note that can be implemented as a staticmethod, when no reference to the
        concrete instance is necessary. This may be useful, when cmpitem is passed to
        database requests, because then the caching of the result only works, when always
        the same cmpitem function is passed to the request. """
        # by default we just compare the names of the artists (case insensitively)
        return cmp(x.name.lower(), y.name.lower())
    cmpitem = staticmethod(cmpitem)

    def getcontents(self):
        """ return items contained in self """
        pass

    def getcontentsrecursive(self):
        """ return items contained in self including subdirs (in arbitrary order)"""
        result = []
        for aitem in self.getcontents():
            if isinstance(aitem, diritem):
                result.extend(aitem.getcontentsrecursive())
            else:
                result.append(aitem)

        return result

    def getcontentsrecursivesorted(self):
        """ return items contained in self including subdirs (sorted)"""
        result = []
        for aitem in self.getcontents():
            if isinstance(aitem, diritem):
                result.extend(aitem.getcontentsrecursivesorted())
            else:
                result.append(aitem)

        return result

    def getcontentsrecursiverandom(self):
        """ return random list of items contained in self including subdirs """
        # this should be implemented by subclasses
        return []

    def getheader(self, item):
        """ return header (used for title bar in filelistwin) of item in self.

        Note that item can be None!
        """
        pass

    def isartist(self):
        """ does self represent an artist? """
        return False

    def isalbum(self):
        """ does self represent an album? """
        return False

#
# filters
#

class filter:
    def __init__(self, name, indexname, indexid):
        self.name = name
        self.indexname = indexname
        self.indexid = indexid

    def __hash__(self):
        return hash("%s=%s" % (self.indexname, self.indexid))

    def SQLstring(self):
	return ""

    def SQLargs(self):
	return []


class hiddenfilter(filter):
    " a filter which does not show up in the UI "
    def __init__(self, indexname, indexid):
	filter.__init__(self, None, indexname, indexid)


class compilationfilter(hiddenfilter):
    def __init__(self, iscompilation):
	self.iscompilation = iscompilation
        hiddenfilter.__init__(self, "compilation", iscompilation)

    def SQLstring(self):
	return "%s songs.compilation" % (not self.iscompilation and "NOT" or "")
	# return "(songs.compilation = %s)" % (self.iscompilation and "1" or "0")


class artistfilter(hiddenfilter):
    def __init__(self, artist_id):
	self.artist_id = artist_id
        hiddenfilter.__init__(self, "artist_id", artist_id)

    def SQLstring(self):
	return "artists.id = ?"

    def SQLargs(self):
	return [self.artist_id]


class albumfilter(hiddenfilter):
    def __init__(self, album_id):
	self.album_id = album_id
        hiddenfilter.__init__(self, "album_id", album_id)

    def SQLstring(self):
	return "albums.id = ?"

    def SQLargs(self):
	return [self.album_id]


class decadefilter(filter):

    """ filters items of a given decade """

    def __init__(self, decade):
        name = "%s=%s" % (_("Decade"), decade and "%ds" % decade or _("Unknown"))
        filter.__init__(self, name, indexname="decade", indexid=decade)


class genrefilter(filter):

    """ filters only items of given genre """

    def __init__(self, genre):
        name = "%s=%s" % (_("Genre"), genre)
        filter.__init__(self, name, indexname="genre", indexid=genre)


class ratingfilter(filter):

    """ filters only items of given rating """

    def __init__(self, rating):
        if rating is not None:
            name = "%s=%s" % (_("Rating"), "*" * rating)
        else:
            name = "%s=%s" % (_("Rating"), _("Not rated"))
        filter.__init__(self, name, indexname="rating", indexid=rating)

class filters(tuple):

     def getname(self):
	 s = ", ".join([filter.name for filter in self if filter.name])
         if s:
             return " <%s>" % s
         else:
             return ""

     def filtered(self, filter):
         return filters(self + (filter,))

     def SQLstring(self):
	filterstring = " AND ".join(["(%s)" % filter.SQLstring() for filter in self])
	if filterstring:
	    filterstring = "WHERE (%s)" % filterstring
	return filterstring

     def SQLargs(self):
	 result = []
	 for filter in self:
	     result.extend(filter.SQLargs())
	 return result

#
# specialized classes
#

def _formatnumbertotal(number, total):
    """ return string for number and total number """
    if number and total:
        return "%d/%d" % (number, total)
    elif number:
        return "%d" % number
    else:
        return ""

class song(item):

    __slots__ = ["songdbid", "id", "song"]

    def __init__(self, songdbid, id):
        """ create song with given id together with its database."""
        self.songdbid = songdbid
        self.id = id
        self.song = None

    def __repr__(self):
        return "song(%s) in %s database" % (self.id, self.songdbid)

    __str__ = __repr__

    def __getattr__(self, attr):
        # Python tries to call __setstate__ upon unpickling -- prevent this
        if attr=="__setstate__":
            raise AttributeError
        if not self.song:
            import log
            log.debug("Fetching song metadata from database")
            self.song = hub.request(requests.getsong(self.songdbid, self.id))
            log.debug("Got song metadata from database")
        return getattr(self.song, attr)

    def _updatesong(self):
        """ notify database of song changes """
        hub.notify(events.updatesong(self.songdbid, self.song))

    def getid(self):
        return self.id

    def getname(self):
        return self.title

    def getinfo(self):
        l = [["", "", "", ""]]*4
        l[0] = [_("Title:"), self.title]
        if self.tracknumber:
            l[0] += [_("Nr:"), _formatnumbertotal(self.tracknumber, self.trackcount)]
        else:
            l[0] += ["", ""]
        l[1] = [_("Album:"),  self.album]
        if self.year:
            l[1] += [_("Year:"), str(self.year)]
        else:
            l[1] += ["", ""]
        l[2] = [_("Artist:"), self.artist,
              _("Time:"), helper.formattime(self.length)]
        # l[3] = [_("Genre:"), self.genre]

        if 0 and self.getplayingtime() is not None:
            seconds = int((time.time()-self.getplayingtime())/60)
            days, rest = divmod(seconds, 24*60)
            hours, minutes = divmod(rest, 60)
            if days>=10:
                played = "%dd" % days
            elif days>0:
                played = "%dd %dh" % (days, hours)
            elif hours>0:
                played = "%dh %dm" % (hours, minutes)
            else:
                played = "%dm" % minutes
            if self.rating:
                played = played + " (%s)" % ("*"*self.rating)
            l[3] += [_("Played:"),
                   _("#%d, %s ago") % (self.nrplayed, played)]

        else:
            if self.rating:
                l[3] += [_("Rating:"), "*"*self.rating]
            else:
                l[3] += ["", ""]
        return l

    def getinfolong(self):
        l = []
        directory, filename = os.path.split(self.song.url)
        l.append([_("Path:"), directory, "", ""])
        l.append([_("File name:"), filename, "", ""])
        if self.size:
            if self.size > 1024*1024:
                sizestring = "%.1f MB" % (self.size / 1024.0 / 1024)
            elif self.song.size > 1024:
                sizestring = "%.1f kB" % (self.size / 1024.0)
            else:
                sizestring = "%d B" % self.size
        else:
            sizestring = ""
        l.append([_("Size:"), sizestring, "", ""])
        typestring = self.type.upper()
        if self.song.bitrate is not None:
            typestring = "%s %dkbps" % (typestring, self.bitrate/1000)
            if self.is_vbr:
                typestring = typestring + "VBR"
            if self.samplerate:
                typestring = "%s (%.1f kHz)" % (typestring, self.samplerate/1000.)

        l.append([_("File type:"), typestring, "", ""])
        l.append([_("Title:"), self.title, "", ""])
        l.append([_("Album:"),  self.album, "", ""])
        l.append([_("Artist:"), self.artist, "", ""])
        if self.song.year:
            l.append([_("Year:"), str(self.year), "", ""])
        else:
            l.append([_("Year:"), "", "", ""])

        l.append([_("Track No:"), _formatnumbertotal(self.tracknumber, self.trackcount), 
                  "", ""])
        l.append([_("Disk No:"), _formatnumbertotal(self.disknumber, self.diskcount), 
                  "", ""])
        l.append([_("Tags:"), u" | ".join(self.tags), "", ""])
        l.append([_("Time:"), "%d:%02d" % divmod(self.length, 60), "", ""])
        replaygain = ""
        if self.replaygain_track_gain is not None and self.replaygain_track_peak is not None:
            replaygain = replaygain + "%s: %+f dB (peak: %f) " % (_("track"),
                                                                  self.replaygain_track_gain,
                                                                  self.replaygain_track_peak)
        if self.replaygain_album_gain is not None and self.replaygain_album_peak is not None:
            replaygain = replaygain + "%s: %+f dB (peak: %f)" % (_("album"),
                                                                 self.replaygain_album_gain,
                                                                 self.replaygain_album_peak)
        l.append([_("Replaygain:"), replaygain, "", ""])

        if self.rating:
            l.append([_("Rating:"), "*"*self.rating, "", ""])
        else:
            l.append([_("Rating:"), "-", "", ""])

        l.append([_("Times played:"), str(self.playcount), "", ""])

        # for played in self.lastplayed[-1:-6:-1]:
        #     last = int((time.time()-played)/60)
        #     days, rest = divmod(last, 24*60)
        #     hours, minutes = divmod(rest, 60)
        #     if days>0:
        #         lastplayed = "%dd %dh %dm" % (days, hours, minutes)
        #     elif hours>0:
        #         lastplayed = "%dh %dm" % (hours, minutes)
        #     else:
        #         lastplayed = "%dm" % minutes

        #     l.append([_("Played:"), "%s (%s)" % (time.ctime(played), _("%s ago") % lastplayed), "", ""])

        return l

    def format(self, formatstring, adddict={}, safe=False):
        """format song info using formatstring. Further song information
        in adddict is added. If safe is True, all values are cleaned
        of characters which are neither letters, digits, a blank or a colon.
        """

        d = {}
        d.update(self.song.__dict__)
        d.update(adddict)
        d["minutes"], d["seconds"] = divmod(d["length"], 60)
        d["length"] = "%d:%02d" % (d["minutes"], d["seconds"])

        if safe:
            allowedchars = string.letters + string.digits + " :"
            for key, value in d.items():
                try:
                    l = []
                    for c in value:
                        if c in allowedchars:
                            l.append(c)
                    d[key] = "".join(l)
                except TypeError:
                    pass

        return formatstring % d

    def play(self):
        self.song.play()
        self._updatesong()

    def unplay(self):
        """ forget last time song has been played (e.g., because playback was not complete) """
        self.song.unplay()
        self._updatesong()

    def rate(self, rating):
        if rating:
            self.song.rating = rating
        else:
            self.song.rating = None
        self.song.ratingsource = 0
        self._updatesong()

    def rescan(self):
        """rescan id3 information for song, keeping playing statistic, rating, etc."""
        hub.notify(events.rescansong(self.songdbid, self.song))

    def getplayingtime(self):
        """ return time at which this particular song instance has been played or the
        last playing time, if no such time has been specified at instance creation time """
        if self.playingtime is None and self.song.lastplayed:
            return self.song.lastplayed[-1]
        else:
            return self.playingtime

class artist(diritem):

    """ artist bound to specific songdb """

    def __init__(self, songdbid, id, name, filters):
        self.songdbid = songdbid
        self.id = id
        self.name = name
        self.filters = filters.filtered(artistfilter(id))

    def __repr__(self):
        return "artist(%s) in %s (filtered: %s)" % (self.name, self.songdbid, repr(self.filters))

    def getcontents(self):
        albums = hub.request(requests.getalbums(self.songdbid,
                                                sort=self.cmpitem, filters=self.filters))
        return albums + [songs(self.songdbid, self.name, self.filters)]

    def getcontentsrecursive(self):
        return hub.request(requests.getsongs(self.songdbid, filters=self.filters))

    def getcontentsrecursivesorted(self):
        albums = hub.request(requests.getalbums(self.songdbid,
                                                sort=self.cmpitem, filters=self.filters))
        result = []
        for aalbum in albums:
            result.extend(aalbum.getcontentsrecursivesorted())
        return result

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getsongs(self.songdbid, filters=self.filters, random=True))

    def getheader(self, item):
        return self.name + self.filters.getname()

    def getinfo(self):
        return _mergefilters([[_("Artist:"), self.name, "", ""]], self.filters)

    def isartist(self):
        return True

    def rate(self, rating):
        for song in self.getcontentsrecursive():
            if song.ratingsource is None or song.ratingsource == 2:
                if rating:
                    song.song.rating = rating
                else:
                    song.song.rating = None
                song.song.ratingsource = 2
                song._updatesong()


class album(diritem):

    """ album bound to specific songdb """

    def __init__(self, songdbid, id, artist, name, filters):
        self.songdbid = songdbid
        self.id = id
        self.artist = artist
        self.name = name
        self.filters = filters.filtered(albumfilter(id))

    def __repr__(self):
        return "album(%s) in %s" % (self.id, self.songdbid)

    def cmpitem(x, y):
        return ( x.disknumber and y.disknumber and cmp(x.disknumber, y.disknumber) or
                 x.tracknumber and y.tracknumber and cmp(x.tracknumber, y.tracknumber) or
                 cmp(x.name, y.name) or
                 cmp(x.path, y.path) )
    cmpitem = staticmethod(cmpitem)

    def getid(self):
        return self.id

    def getcontents(self):
        songs = hub.request(requests.getsongs(self.songdbid, sort=self.cmpitem, filters=self.filters))
        return songs

    def getcontentsrecursive(self):
        return hub.request(requests.getsongs(self.songdbid, filters=self.filters))

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getsongs(self.songdbid, filters=self.filters, random=True))

    def getheader(self, item):
        if item:
            s = "%s - %s" % (item.artist, item.album)
        else:
            s = self.name
        return s + self.filters.getname()

    def getinfo(self):
        l = [[_("Artist:"), self.artist is None and _("various") or self.artist, "", ""],
             [_("Album:"), self.name, "", ""]]
        return _mergefilters(l, self.filters)

    def isalbum(self):
        return True

    def rate(self, rating):
        for song in self.getcontentsrecursive():
            if song.ratingsource is None or song.ratingsource >= 1:
                if rating:
                    song.song.rating = rating
                else:
                    song.song.rating = None
                song.song.ratingsource = 1
                song._updatesong()


class playlist(diritem):

    """ songs in a playlist in the corresponding database """

    def __init__(self, songdbid, path, name, songs):
        self.songdbid = songdbid
        self.path = path
        self.name = name
        self.songs = songs

    def getid(self):
        return self.path

    def getcontents(self):
        return hub.request(requests.getsongsinplaylist(self.songdbid, self.path))

    def getcontentsrecursive(self):
        return hub.request(requests.getsongsinplaylist(self.songdbid, self.path))

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getsongsinplaylist(self.songdbid, self.path, random=True))

    def getheader(self, item):
        if item:
            return item.artist + " - " + item.album
        else:
            return self.name

    def getinfo(self):
        return [["%s:" % _("Playlist"), self.name, "", ""]]


class totaldiritem(diritem):

    """ diritem which contains the total database(s) as its contents """
    
    def getcontentsrecursive(self):
        return hub.request(requests.getsongs(self.songdbid, filters=self.filters))

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getsongs(self.songdbid, filters=self.filters, random=True))


class randomsonglist(totaldiritem):

    """ random list of songs out of  the corresponding database """

    def __init__(self, songdbid, maxnr, filters):
        self.songdbid = songdbid
        self.name = "[%s]" % _("Random song list")
        self.maxnr = maxnr
        self.filters = filters

    def getcontents(self):
        songs = []
        while len(songs)<self.maxnr:
            newsongs = hub.request(requests.getsongs(self.songdbid, filters=self.filters, random=True))
            if len(newsongs) > 0:
                songs.extend(newsongs)
            else:
                break
        return songs[:self.maxnr]

    def getheader(self, item):
        if item:
            return item.artist + " - " + item.album
        else:
            return _("Random song list")

    def getinfo(self):
        return _mergefilters([[_("Random song list"), "", "", ""]], self.filters)


class lastplayedsongs(diritem):

    """ songs last played out of the corresponding databases """

    def __init__(self, songdbid, filters):
        self.songdbid = songdbid
        self.filters = filters
        self.name = "[%s]" % _("Last played songs")

    def cmpitem(x, y):
        return cmp(y.getplayingtime(), x.getplayingtime())
    cmpitem = staticmethod(cmpitem)

    def getcontents(self):
        songs = hub.request(requests.getlastplayedsongs(self.songdbid, sort=self.cmpitem, filters=self.filters))
        return songs

    getcontentsrecursive = getcontentsrecursivesorted = getcontents

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getlastplayedsongs(self.songdbid, filters=self.filters, random=True))

    def getheader(self, item):
        if item:
            return item.artist + " - " + item.album
        else:
            return _("Last played songs")

    def getinfo(self):
        return _mergefilters([[_("Last played songs"), "", "", ""]], self.filters)


class topplayedsongs(diritem):

    """ songs most often played of the corresponding databases """

    def __init__(self, songdbid, filters):
        self.songdbid = songdbid
        self.filters = filters
        self.name = "[%s]" % _("Top played songs")

    def cmpitem(x, y):
        return cmp(y.nrplayed, x.nrplayed) or cmp(y.lastplayed, x.lastplayed)
    cmpitem = staticmethod(cmpitem)

    def getcontents(self):
        songs = hub.request(requests.gettopplayedsongs(self.songdbid, sort=self.cmpitem, filters=self.filters))
        return songs

    getcontentsrecursive = getcontentsrecursivesorted = getcontents

    def getcontentsrecursiverandom(self):
        return hub.request(requests.gettopplayedsongs(self.songdbid, filters=self.filters, random=True))

    def getheader(self, item):
        if item:
            return item.artist + " - " + item.album
        else:
            return _("Top played songs")

    def getinfo(self):
        return _mergefilters([[_("Top played songs"), "", "", ""]], self.filters)


class lastaddedsongs(diritem):

    """ songs last added to the corresponding database """

    def __init__(self, songdbid, filters):
        self.songdbid = songdbid
        self.filters = filters
        self.name = "[%s]" % _("Last added songs")

    def cmpitem(x, y):
        return cmp(y.added, x.added)
    cmpitem = staticmethod(cmpitem)

    def getcontents(self):
        return hub.request(requests.getlastaddedsongs(self.songdbid, sort=self.cmpitem, filters=self.filters))

    getcontentsrecursive = getcontentsrecursivesorted = getcontents

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getlastaddedsongs(self.songdbid, filters=self.filters, random=True))

    def getheader(self, item):
        if item:
            return item.artist + " - " + item.album
        else:
            return _("Last added songs")

    def getinfo(self):
        return _mergefilters([[_("Last added songs"), "", "", ""]], self.filters)


class albums(totaldiritem):

    """ all albums in the corresponding database """

    def __init__(self, songdbid, filters):
        self.songdbid = songdbid
        self.filters = filters
        self.name = _("Albums")
        self.nralbums = None

    def getname(self):
        if self.nralbums is None:
            self.nralbums = hub.request(requests.getnumberofalbums(self.songdbid, filters=self.filters))
        return "[%s (%d)]/" % (self.name, self.nralbums)

    def getcontents(self):
        albums = hub.request(requests.getalbums(self.songdbid, sort=self.cmpitem, filters=self.filters))
        self.nralbums = len(albums)
        return albums

    def getheader(self, item):
        return self.getname()[1:-2] + self.filters.getname()

    def getinfo(self):
        return _mergefilters([[self.name, "", "", ""]], self.filters)


class compilations(albums):
    def __init__(self, songdbid, filters):
	filters = filters.filtered(compilationfilter(True))
	albums.__init__(self, songdbid, filters)
	self.name = _("Compilations")


class genres(totaldiritem):

    """ all genres in the corresponding database """

    def __init__(self, songdbid, songdbids, filters):
        self.songdbid = songdbid
        self.songdbids = songdbids
        self.filters = filters
        self.name = _("Genres")
        self.nrgenres = None

    def cmpitem(x, y):
        return cmp(x.description, y.description)
    cmpitem = staticmethod(cmpitem)

    def getname(self):
        if self.nrgenres is None:
            self.nrgenres = hub.request(requests.getnumberofgenres(self.songdbid, filters=self.filters))
        return "[%s (%d)]/" % (_("Genres"), self.nrgenres)

    def getcontents(self):
        genres = hub.request(requests.getgenres(self.songdbid, sort=self.cmpitem, filters=self.filters))
        self.nrgenres = len(genres)
        return genres

    def getheader(self, item):
        if self.nrgenres is None:
            self.nrgenres = hub.request(requests.getnumberofgenres(self.songdbid, filters=self.filters))
        return "%s (%d)" % (_("Genres"), self.nrgenres) + self.filters.getname()

    def getinfo(self):
        return _mergefilters([[_("Genres"), "", "", ""]], self.filters)


class decades(totaldiritem):

    """ all decades in the corresponding database """

    def __init__(self, songdbid, songdbids, filters):
        self.songdbid = songdbid
        self.songdbids = songdbids
        self.filters = filters
        self.name = _("Decades")
        self.nrdecades = None

    def cmpitem(x, y):
        return cmp(x.description, y.description)
    cmpitem = staticmethod(cmpitem)

    def getname(self):
        if self.nrdecades is None:
            self.nrdecades = hub.request(requests.getnumberofdecades(self.songdbid, filters=self.filters))
        return "[%s (%d)]/" % (_("Decades"), self.nrdecades)

    def getcontents(self):
        decades = hub.request(requests.getdecades(self.songdbid, sort=self.cmpitem, filters=self.filters))
        self.nrdecades = len(decades)
        return decades

    def getheader(self, item):
        if self.nrdecades is None:
            self.nrdecades = hub.request(requests.getnumberofdecades(self.songdbid))
        return "%s (%d)" % (_("Decades"), self.nrdecades) + self.filters.getname()

    def getinfo(self):
        return _mergefilters([[_("Decades"), "", "", ""]], self.filters)


class ratings(totaldiritem):

    """ all ratings in the corresponding database """

    def __init__(self, songdbid, songdbids, filters):
        self.songdbid = songdbid
        self.songdbids = songdbids
        self.filters = filters
        self.name = _("Ratings")
        self.nrratings = None

    def getname(self):
        if self.nrratings is None:
            self.nrratings = hub.request(requests.getnumberofratings(self.songdbid, filters=self.filters))
        return "[%s (%d)]/" % (_("Ratings"), self.nrratings)

    def cmpitem(x, y):
        return cmp(x.description, y.description)
    cmpitem = staticmethod(cmpitem)

    def getcontents(self):
        ratings = hub.request(requests.getratings(self.songdbid, sort=self.cmpitem, filters=self.filters))
        self.nrratings = len(ratings)
        return ratings

    def getheader(self, item):
        if self.nrratings is None:
            nrratings = hub.request(requests.getnumberofratings(self.songdbid, filters=self.filters))
        return "%s (%d)" % (_("Ratings"), self.nrratings) + self.filters.getname()

    def getinfo(self):
        return _mergefilters([[_("Ratings"), "", "", ""]], self.filters)


class songs(diritem):

    """ all songs in the corresponding database """

    def __init__(self, songdbid, artist=None, filters=None):
        self.songdbid = songdbid
        self.name = _("Songs")
        self.artist = artist
        self.filters = filters
        self.nrsongs = None

    def getname(self):
        if self.nrsongs is None:
            self.nrsongs = hub.request(requests.getnumberofsongs(self.songdbid, filters=self.filters))
        return "[%s (%d)]/" % (self.name, self.nrsongs)

    def cmpitem(x, y):
        return ( cmp(x.title, y.title) or
                 cmp(x.album, y.album) or
                 cmp(x.path, y.path)
                 )
    cmpitem = staticmethod(cmpitem)

    def getcontents(self):
        songs = hub.request(requests.getsongs(self.songdbid, filters=self.filters, sort=self.cmpitem))
        self.nrsongs = len(songs)
        return songs

    getcontentsrecursivesorted = getcontentsrecursive = getcontents

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getsongs(self.songdbid, artist=self.artist, filters=self.filters, random=True))

    def getheader(self, item):
        if item:
            s = item.artist + " - " + item.album
        else:
            s = self.getname()[1:-2]
        if self.filters:
            return s + self.filters.getname()
        else:
            return s

    def getinfo(self):
        if self.artist is not None:
            l = [[_("Artist:"), self.artist, "", ""],
                    [_("Songs"), "", "", ""]]
        else:
            l = [[_("Songs"), "", "", ""]]
        return _mergefilters(l, self.filters)


class playlists(diritem):

    """ all playlists in the corresponding database """

    def __init__(self, songdbid):
        self.songdbid = songdbid
        self.name = _("Playlists")
        self.nrplaylists = None

    def getname(self):
        if self.nrplaylists is None:
            self.nrplaylists = len(self.getcontents())
        return "[%s (%d)]/" % (_("Playlists"), self.nrplaylists)

    def getcontents(self):
        playlists = hub.request(requests.getplaylists(self.songdbid, sort=self.cmpitem))
        self.nrplaylists = len(playlists)
        return playlists

    def getcontentsrecursive(self):
        return hub.request(requests.getsongsinplaylists(self.songdbid))

    def getcontentsrecursiverandom(self):
        return hub.request(requests.getsongsinplaylists(self.songdbid, random=True))

    def getheader(self, item):
        if self.nrplaylists is None:
            self.nrplaylists = len(self.getcontents())
        return "%s (%d)" % (_("Playlists"), self.nrplaylists)

    def getinfo(self):
        return [[_("Playlists"), "", "", ""]]


class filesystemdir(diritem):

    """ diritem corresponding to directory in filesystem """

    def __init__(self, songdbid, basedir, dir):
        self.songdbid = songdbid
        self.basedir = basedir
        self.dir = dir

        if self.dir==self.basedir:
            self.name = "[%s]" % _("Filesystem")
        else:
            self.name = self.dir[len(self.basedir):].split("/")[-1]

    def getcontents(self):
        items = []
        try:
            for name in os.listdir(self.dir):
                try:
                    path = os.path.join(self.dir, name)
                    extension = os.path.splitext(path)[1]
                    if os.path.isdir(path) and os.access(path, os.R_OK|os.X_OK):
                        newitem = filesystemdir(self.songdbid, self.basedir, path)
                        items.append(newitem)
                    elif extension in metadata.getextensions() and os.access(path, os.R_OK):
                        newsong = hub.request(requests.queryregistersong(self.songdbid, path))
                        items.append(newsong)
                except (IOError, OSError) : pass
        except OSError:
            return None
        items.sort(self.cmpitem)
        return items

    def getcontentsrecursiverandom(self):
        songs = self.getcontentsrecursive()
        return _genrandomchoice(songs)

    def getheader(self, item):
        if self.dir==self.basedir:
            return _("Filesystem")
        else:
            return self.name

    def getinfo(self):
        return [["%s:" % _("Filesystem"), self.dir, "", ""]]

    def isbasedir(self):
        """ return whether the filesystemdir is the basedir of a song database """
        return self.dir == self.basedir

_dbstats = None

class basedir(totaldiritem):

    """ base dir of database view"""

    def __init__(self, songdbids, filters=filters(())):
        # XXX: as a really dirty hack, we cache the result of getdatabasestats for
        # all databases because we cannot call this request safely later on
        # (we might be handling another request which calls the basedir constructor)
        global _dbstats
        if _dbstats is None:
            _dbstats = {}
            for songdbid in songdbids:
                _dbstats[songdbid] = hub.request(requests.getdatabasestats(songdbid))
        self.name =  _("Song Database")
        self.songdbids = songdbids
        if len(songdbids) == 1:
            self.songdbid = songdbids[0]
            self.type = _dbstats[self.songdbid].type
            self.basedir = _dbstats[self.songdbid].basedir
        else:
            self.songdbid = None
            self.type = "virtual"
            self.basedir = None
        self.filters = filters
        self.maxnr = 100
        self.nrartists = None
	self.nrsongs = None
        self._initvirtdirs()

    def _initvirtdirs(self):
        self.virtdirs = []
        self.virtdirs.append(compilations(self.songdbid, filters=self.filters))
        if self.type == "local" and not self.filters:
            self.virtdirs.append(filesystemdir(self.songdbid, self.basedir, self.basedir))
        self.virtdirs.append(songs(self.songdbid, filters=self.filters))
        self.virtdirs.append(albums(self.songdbid, filters=self.filters))
	return
        for filter in self.filters:
            if isinstance(filter, decadefilter):
                break
        else:
            self.virtdirs.append(decades(self.songdbid, self.songdbids, filters=self.filters))
        for filter in self.filters:
            if isinstance(filter, genrefilter):
                break
        else:
            self.virtdirs.append(genres(self.songdbid, self.songdbids, filters=self.filters))
        for filter in self.filters:
            if isinstance(filter, ratingfilter):
                break
        else:
            self.virtdirs.append(ratings(self.songdbid, self.songdbids, filters=self.filters))
        self.virtdirs.append(topplayedsongs(self.songdbid, filters=self.filters))
        self.virtdirs.append(lastplayedsongs(self.songdbid, filters=self.filters))
        self.virtdirs.append(lastaddedsongs(self.songdbid, filters=self.filters))
        self.virtdirs.append(randomsonglist(self.songdbid, self.maxnr, filters=self.filters))
        if not self.filters:
            self.virtdirs.append(playlists(self.songdbid))
        if len(self.songdbids) > 1:
            self.virtdirs.extend([basedir([songdbid], self.filters) for songdbid in self.songdbids])

    def getname(self):
        if self.nrsongs is None:
            self.nrsongs = hub.request(requests.getnumberofsongs(self.songdbid, filters=self.filters))
        if self.basedir:
            return  _("[Database: %s (%d)]") % (self.basedir, self.nrsongs)
        else:
            return _("%d databases (%d)") % (len(self.songdbids), self.nrsongs)

    def getcontents(self):
	# do not show artists which only appear in compilations
	filters = self.filters.filtered(compilationfilter(False))
        aartists = hub.request(requests.getartists(self.songdbid, sort=self.cmpitem,
                                                   filters=filters))
	self.nrartists = len(aartists)
	# reset cached value
	self.nrsongs = None
        if config.filelistwindow.virtualdirectoriesattop:
            return self.virtdirs + aartists
        else:
            return aartists + self.virtdirs

    def getcontentsrecursivesorted(self):
        # we cannot rely on the default implementation since we don't want
        # to have the albums and songs included trice
        artists = hub.request(requests.getartists(self.songdbid, sort=self.cmpitem,
                                                  filters=self.filters))
        result = []
        for aartist in artists:
            result.extend(aartist.getcontentsrecursivesorted())
        return result

    def getheader(self, item):
        if self.nrartists is not None:
	    nrartistsstring = _("%d artists") % self.nrartists
	else:
	    nrartistsstring = _("? artists") 
        if self.basedir:
            maxlen = 15
            dirname = self.basedir
            if len(dirname)>maxlen:
                dirname = "..."+dirname[-maxlen+3:]
            else:
                dirname = self.basedir
            s = _("Database (%s, %s)") % (dirname, nrartistsstring)
        else:
            s = _("%d databases (%s)") % (len(self.songdbids), nrartistsstring)
        return s + self.filters.getname()

    def getinfo(self):
         if self.basedir:
             description = _("[Database: %s (%%d)]") % (self.basedir)
         else:
             description = _("%d databases (%%d)") % (len(self.songdbids))
         return _mergefilters([[self.name, description, "", ""]], self.filters)


class index(basedir):

    def __init__(self, songdbids, name, description, filters):
        basedir.__init__(self, songdbids, filters)
        self.name = name
        self.description = description
        self.type = "index"

    def getname(self):
        if self.nrsongs is None:
            self.nrsongs = hub.request(requests.getnumberofsongs(self.songdbid, filters=self.filters))
        return "%s (%d)/" % (self.description, self.nrsongs)

    def getinfo(self):
        return _mergefilters([[self.name, self.description, "", ""]], self.filters[:-1])

