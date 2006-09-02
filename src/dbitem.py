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

import os.path, re, string, sys, time
import log, metadata
import encoding

tracknrandtitlere = re.compile("^\[?(\d+)\]? ?[- ] ?(.*)\.(mp3|ogg)$")

# name used for unknown artist or album
UNKNOWN = u"Unknown"
# artist name for compilations
VARIOUS = u"___VARIOUS___"


# factory function for songs

def songfromfile(relpath, basedir, tracknrandtitlere, capitalize, stripleadingarticle, removeaccents):
    relpath = os.path.normpath(relpath)

    path = os.path.normpath(os.path.join(basedir, relpath))

    if not os.access(path, os.R_OK):
        raise IOError("cannot read song")

    url = u"file://" + encoding.decode_path(relpath)

    # determine type of file from its extension
    type = metadata.gettype(os.path.splitext(relpath)[1])
    if type is None:
        raise RuntimeError("Fileformat of song '%s' not supported" % (relpath))

    # song metadata
    title = u""
    album = u""
    artist = u""
    album_artist = u""
    year = None
    genre = u""
    comment = u""
    lyrics = u""
    tracknumber = None
    trackcount = None
    disknumber = None
    diskcount = None
    compilation = False
    length = 0
    bitrate = None
    samplerate = None
    is_vbr = None
    size = None
    replaygain_track_gain = None
    replaygain_track_peak = None
    replaygain_album_gain = None
    replaygain_album_peak = None

    # statistical information
    playcount = 0
    date_lastplayed = None
    date_changed = date_added = time.time()
    rating = None
    tags = []

    # guesses for title and tracknumber using the filename
    match = re.match(tracknrandtitlere, os.path.basename(path))
    if match:
        fntracknumber = int(match.group(1))
        fntitle = match.group(2)
    else:
        fntracknumber = None
        fntitle = os.path.basename(path)
        if fntitle.lower().endswith(".mp3") or fntitle.lower().endswith(".ogg"):
            fntitle = fntitle[:-4]

    first, second = os.path.split(os.path.dirname(relpath))
    if first and second and not os.path.split(first)[0]:
        fnartist = first
        fnalbum = second
    else:
        fnartist = fnalbum = ""

    # now convert this to unicode strings using the standard filesystem encoding
    fntitle = encoding.decode_path(fntitle)
    fnartist = encoding.decode_path(fnartist)
    fnalbum = encoding.decode_path(fnalbum)

    fntitle = fntitle.replace("_", " ")
    fnalbum = fnalbum.replace("_", " ")
    fnartist = fnartist.replace("_", " ")

    try:
        metadatadecoder = metadata.getmetadatadecoder(type)
    except:
        raise RuntimeError("Support for %s songs not enabled" % type)

    try:
        log.debug("reading metadata for %r" % path)
        md = metadatadecoder(path)
        title = md.title
        album = md.album
        artist = md.artist
        year = md.year
        genre = md.genre
        comment = md.comment
        lyrics = md.lyrics
        tracknumber = md.tracknumber
        trackcount = md.trackcount
        disknumber = md.disknumber
        diskcount = md.diskcount
        compilation = md.compilation
        length = md.length
        bitrate = md.bitrate
        samplerate = md.samplerate
        is_vbr = md.is_vbr
        size = md.size
        replaygain_track_gain = md.replaygain_track_gain
        replaygain_track_peak = md.replaygain_track_peak
        replaygain_album_gain = md.replaygain_album_gain
        replaygain_album_peak = md.replaygain_album_peak
        log.debug("metadata for %r read successfully" % path)
    except:
        log.warning("could not read metadata for %r" % path)
        log.debug_traceback()

    # do some further treatment of the song info

    # use title from filename, if it is a longer version of
    # the id3 tag title
    # XXX: unicode problem with startswith
    if not title: #  or fntitle.startswith(title): 
        title = fntitle

    # also try to use tracknumber from filename, if not present as id3 tag
    if not tracknumber or tracknumber == 0:
        tracknumber = fntracknumber

    # we don't want empty album names
    if not album:
        if fnalbum:
            album = fnalbum
        else:
            album = UNKNOWN

    # nor empty artist names
    if not artist:
        if fnartist:
            artist = fnartist
        else:
            artist = UNKNOWN

    # nor empty genres
    if not genre:
        genre = UNKNOWN

    if not year or year == "0":
        year = None
    else:
        try:
            year = int(year)
        except:
            year = None

    artist = artist.strip()
    album = album.strip()
    title = title.strip()

    if capitalize:
        # normalize artist, album and title
        artist = string.capwords(artist)
        album = string.capwords(album)
        title = string.capwords(title)

    if stripleadingarticle:
        # strip leading "The " in artist names, often used inconsistently
        if artist.startswith("The ") and len(artist)>4:
            artist = artist[4:]

    #if removeaccents:
    #    translationtable = string.maketrans('����������������������������������������',
    #                                        'AAAAEEEEIIIIOOOOUUUUaaaaeeeeiiiioooouuuu')
    #    artist = string.translate(artist, translationtable)
    #    album = string.translate(album, translationtable)
    #    title = string.translate(title, translationtable)

    if "Compilations" in path:
        compilation = True

    if compilation: 
	album_artist = VARIOUS
    else:
	album_artist = artist

    tags = []
    if genre:
        tags.append("G:%s" % genre)
    if year:
        tags.append("D:%d" % (10*(year//10)))


    return song(url, type, title, album, artist, album_artist, year, comment, lyrics, tags,
                tracknumber, trackcount, disknumber, diskcount, compilation, length, bitrate,
                samplerate, is_vbr, size, replaygain_track_gain, replaygain_track_peak,
                replaygain_album_gain, replaygain_album_peak,
                date_added, date_changed, date_lastplayed, playcount, rating)


class song:

    def __init__(self, url, type, title, album, artist, album_artist, year, comment, lyrics, tags,
                 tracknumber, trackcount, disknumber, diskcount, compilation, length, bitrate,
                 samplerate, is_vbr, size, replaygain_track_gain, replaygain_track_peak,
                 replaygain_album_gain, replaygain_album_peak,
                 date_added, date_changed, date_lastplayed, playcount, rating):
        self.url = url
        self.type = type
        self.title = title
        self.album = album
	self.album_artist = album_artist
        self.artist = artist
        self.year = year
        self.comment = comment
        self.lyrics = lyrics
        self.tags = tags
        self.tracknumber = tracknumber
        self.trackcount = trackcount
        self.disknumber = disknumber
        self.diskcount = diskcount
        self.compilation = compilation
        self.length = length

        # encoding information
        self.bitrate = bitrate
        self.samplerate = samplerate
        self.is_vbr = is_vbr
        self.size = size

        # replaygain
        self.replaygain_track_gain = replaygain_track_gain
        self.replaygain_track_peak = replaygain_track_peak
        self.replaygain_album_gain = replaygain_album_gain
        self.replaygain_album_peak = replaygain_album_peak

        # statistical information
        self.date_added = date_added
        self.date_changed = date_changed
        self.date_lastplayed = date_lastplayed
        self.playcount = playcount
        self.rating = rating

    def __cmp__(self, other):
        try:
            return cmp(self.id, other.id)
        except:
            return 1

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return "song(%s)" % (self.url)

    def update_id3(self, othersong):
        """ merge id3 information from othersong """
        self.title = othersong.title
        self.album = othersong.album
        self.artist = othersong.artist
        self.year = othersong.year
        self.comment = othersong.comment
        self.tags = othersong.tags
        self.tracknumber = othersong.tracknumber
        self.trackcount = othersong.trackcount
        self.disknumber = othersong.disknumber
        self.diskcount = othersong.diskcount
        self.length = othersong.length
        self.size = othersong.size
        self.replaygain_track_gain = othersong.replaygain_track_gain
        self.replaygain_track_peak = othersong.replaygain_track_peak
        self.replaygain_album_gain = othersong.replaygain_album_gain
        self.replaygain_album_peak = othersong.replaygain_album_peak
        self.date_changed = time.time()

    def play(self):
        self.playcount += 1
        self.date_lastplayed = time.time()

    def replaygain(self, profiles):
       # the following code is adapted from quodlibet
       """Return the recommended Replay Gain scale factor.

       profiles is a list of Replay Gain profile names ('album',
       'track') to try before giving up. The special profile name
       'none' will cause no scaling to occur.
       """
       for profile in profiles:
           if profile is "none":
               return 1.0
           try:
               db = getattr(self, "replaygain_%s_gain" % profile)
               peak = getattr(self, "replaygain_%s_peak" % profile)
           except AttributeError:
               continue
           else:
               if db is not None and peak is not None:
                   scale = 10.**(db / 20)
                   if scale * peak > 1:
                       scale = 1.0 / peak # don't clip
                   return min(15, scale)
       else:
           return 1.0


class playlist:

    # XXX just for the code

    def __init__(self, path):
        self.path = self.id = os.path.normpath(path)
        self.name = os.path.basename(path)
        if self.name.endswith(".m3u"):
            self.name = self.name[:-4]
        self.songs = []

        file = open(self.path, "r")

        for line in file.xreadlines():
            # XXX: interpret extended m3u format (especially for streams)
            # see: http://forums.winamp.com/showthread.php?s=dbec47f3a05d10a3a77959f17926d39c&threadid=65772
            if not line.startswith("#") and not chr(0) in line:
                path = line.strip()
                if not path.startswith("/"):
                    path = os.path.join(self.path, path)
                if os.path.isfile(path):
                    self.songs.append(path)
        file.close()
