# -*- coding: ISO-8859-1 -*-

# Copyright (C) 2005, 2006 J�rg Lehmann <joerg@luga.de>
#
# Ogg Vorbis interface by Byron Ellacott <bje@apnic.net>.
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

import locale, os, struct, sys
import log

fallbacklocalecharset = "iso-8859-1"

# Try to determine "correct" character set for the reencoding of the
# unicode strings contained in Ogg Vorbis files
try:
    # works only in python > 2.3
    localecharset = locale.getpreferredencoding()
except:
    try:
        localecharset = locale.getdefaultlocale()[1]
    except:
        try:
            localecharset = sys.getdefaultencoding()
        except:
            localecharset = fallbacklocalecharset
if localecharset in [None, 'ANSI_X3.4-1968']:
    localecharset = fallbacklocalecharset

#
# metadata decoder class and simple decoder registry
#

class metadata:
    def __init__(self, path):
        """ parse metadata of file """
        self.title = ""
        self.album = ""
        self.artist = ""
        self.year = ""
        self.genre = ""
        self.tracknumber = None
	self.trackcount = None
	self.disknumber = None
	self.diskcount = None
        self.length = 0
	self.version = None
	self.layer = None
	self.is_vbr = None
	self.samplerate = None
	self.bitrate = None
	self.size = os.stat(path).st_size
        self.replaygain_track_gain = None
        self.replaygain_track_peak = None
        self.replaygain_album_gain = None
        self.replaygain_album_peak = None

# mapping: file type -> (metadata, decoder class, file extension)
_fileformats = {}

def registerfileformat(type, metadataclass, extension):
    _fileformats[type] = (metadataclass, extension)

def getmetadatadecoder(type):
    return _fileformats[type][0]

def getextensions():
    result = []
    for decoderclass, extension in _fileformats.values():
        result.append(extension)
    return result

def gettype(extension):
    for type, extensions in _fileformats.items():
        if extension.lower() in extensions:
            return type
    return None

#
# Ogg Vorbis metadata decoder
#

class vorbismetadata(metadata):
    def __init__(self, path):
        vf = ogg.vorbis.VorbisFile(path)
        id3get = vf.comment().as_dict().get
        self.title = id3get('TITLE', [""])[0]
        self.title = self.title.encode(localecharset, 'replace')
        self.album = id3get('ALBUM', [""])[0]
        self.album = self.album.encode(localecharset, 'replace')
        self.artist = id3get('ARTIST', [""])[0]
        self.artist = self.artist.encode(localecharset, 'replace')
        self.year = id3get('DATE', [""])[0]
        self.year = self.year.encode(localecharset, 'replace')
        self.genre  = id3get('GENRE', [""])[0]
        self.genre = self.genre.encode(localecharset, 'replace')
        self.tracknr = id3get('TRACKNUMBER', [""])[0]
        self.tracknr = self.tracknr.encode(localecharset, 'replace')
        self.length = vf.time_total(0)

	# example format according to vorbisgain documentation
	# REPLAYGAIN_TRACK_GAIN=-7.03 dB
	# REPLAYGAIN_TRACK_PEAK=1.21822226
	# REPLAYGAIN_ALBUM_GAIN=-6.37 dB
	# REPLAYGAIN_ALBUM_PEAK=1.21822226

try:
    import ogg.vorbis
    registerfileformat("ogg", vorbismetadata, ".ogg")
    log.info("Ogg Vorbis support enabled")
except ImportError:
    log.info("Ogg Vorbis support disabled, since ogg.vorbis module is not present")

def _splitnumbertotal(s):
    """ split string into number and total number """
    r = map(int, s.split("/"))
    number = r[0]
    if len(r) == 2:
	count = r[1]
    else:
	count = None
    return number, count

#
# ID3 metadata decoder (using mutagen module)
#

class mp3mutagenmetadata(metadata):
    framemapping = { "TIT2": "title",
                     "TALB": "album",
                     "TPE1": "artist",
                     "TDRC": "year"  }
    def __init__(self, path):
        metadata.__init__(self, path)
        mp3 = mutagen.mp3.MP3(path, ID3=ID3hack)

        # we definitely want the length of the MP3 file, even if no ID3 tag is present,
        # so extract this info before anything goes wrong
        self.length = mp3.info.length

	self.version = mp3.info.version
	self.layer = mp3.info.layer
	self.samplerate = mp3.info.sample_rate
	self.bitrate = mp3.info.bitrate

        for frame in mp3.tags.values():
            if frame.FrameID == "TCON":
                self.genre = " ".join(frame.genres)
            elif frame.FrameID == "RVA2":
                if frame.channel == 1:
                    if frame.desc == "album":
                        basename = "replaygain_album_"
                    else:
                        # for everything else, we assume it's track gain
                        basename = "replaygain_track_"
                    setattr(self, basename+"gain", frame.gain)
                    setattr(self, basename+"peak", frame.peak)
            elif frame.FrameID == "TLEN":
                try:
                    self.length = int(+frame/1000)
                except:
                    pass
	    elif frame.FrameID == "TRCK":
		self.tracknumber, self.trackcount = _splitnumbertotal(frame.text[0])
	    elif frame.FrameID == "TPOS":
		self.disknumber, self.diskcount = _splitnumbertotal(frame.text[0])
            else:
                name = self.framemapping.get(frame.FrameID, None)
                if name:
                    text = " ".join(map(unicode, frame.text))
                    setattr(self, name, text)

        # self.title = MP3Info._strip_zero(self.title)
        # self.album = MP3Info._strip_zero(self.album)
        # self.artist = MP3Info._strip_zero(self.artist)

#
# ID3 metadata decoder (using eyeD3 module)
#

class mp3eyeD3metadata(metadata):
    def __init__(self, path):
        metadata.__init__(self, path)
        mp3file = eyeD3.Mp3AudioFile(path)
        mp3info = mp3file.getTag()

        # we definitely want the length of the MP3 file, even if no ID3 tag is present,
        # so extract this info before anything goes wrong
        self.length = mp3file.getPlayTime()

	self.is_vbr, bitrate = mp3file.getBitRate()
	self.bitrate = bitrate * 1000
	self.samplerate = mp3file.getSampleFreq()

        if mp3info:
            self.title = mp3info.getTitle()
            self.title = self.title.encode(localecharset, 'replace')
            self.title = MP3Info._strip_zero(self.title)

            self.album = mp3info.getAlbum()
            self.album = self.album.encode(localecharset, 'replace')
            self.album = MP3Info._strip_zero(self.album)

            self.artist = mp3info.getArtist()
            self.artist = self.artist.encode(localecharset, 'replace')
            self.artist = MP3Info._strip_zero(self.artist)

            self.year = mp3info.getYear()
            if self.year:
                self.year = self.year.encode(localecharset, 'replace')

            try:
                self.genre = mp3info.getGenre()
                if self.genre:
                    self.genre = self.genre.getName()
            except eyeD3.tag.GenreException, e:
                self.genre = e.msg.split(':')[1].strip()

            self.tracknumber, self.trackcount = mp3info.getTrackNum()
	    self.disknumber, self.diskcount = mp3info.getDiscNum()

            # if the playtime is also in the ID3 tag information, we
            # try to read it from there
            if mp3info.frames["TLEN"]:
                length = None
                try:
                    length = int(int(mp3info.frames["TLEN"])/1000)
                except:
                    # time in seconds (?), possibly with bad decimal separator, e.g "186,333"
                    try:
                        length = int(float(mp3info.frames["TLEN"].replace(",", ".")))
                    except:
                        pass
                if length:
                    self.length = length

	    for rva2frame in mp3info.frames["RVA2"]:
		# since eyeD3 currently doesn't support RVA2 frames, we have to decode
		# them on our own following mutagen
		desc, rest = rva2frame.data.split("\x00", 1)
		channel = ord(rest[0])
		if channel == 1:
		    gain = struct.unpack('>h', rest[1:3])[0]/512.0
		    # http://bugs.xmms.org/attachment.cgi?id=113&action=view
		    rest = rest[3:]
		    peak = 0
		    bits = ord(rest[0])
		    bytes = min(4, (bits + 7) >> 3)
		    shift = ((8 - (bits & 7)) & 7) + (4 - bytes) * 8
		    for i in range(1, bytes+1):
			peak *= 256
			peak += ord(rest[i])
		    peak *= 2**shift
		    peak = (float(peak) / (2**31-1))
		    if desc == "album":
                        basename = "replaygain_album_"
		    else:
                        # for everything else, we assume it's track gain
                        basename = "replaygain_track_"
                    setattr(self, basename+"gain", gain)
                    setattr(self, basename+"peak", peak)

#
# ID3 metadata decoder (using MP3Info module)
#

class mp3MP3Infometadata(metadata):
    def __init__(self, path):
        mp3file = open(path, "rb")
        mp3info = MP3Info.MP3Info(mp3file)
        self.title = mp3info.title
        self.album = mp3info.album
        self.artist = mp3info.artist
        self.year = mp3info.year
        self.genre  = mp3info.genre
        self.tracknumber = _splitnumbertotal(mp3info.track)
	self.version = mp3info.mpeg.version
	self.layer = mp3info.mpeg.layer
	self.is_vbr = mp3info.mpeg.is_vbr
	self.bitrate = mp3info.mpeg.bitrate
	self.samplerate = mp3info.mpeg.samplerate
        try:
            try:
                self.length = int(mp3info.id3.tags["TLEN"])/1000
            except:
                # time in seconds (?), possibly with bad decimal separator, e.g "186,333"
                t = mp3info.id3.tags["TLEN"].replace(",", ".")
                self.length = int(float(t))
        except:
            self.length = mp3info.mpeg.length
        mp3file.close()

try:
    import mutagen.mp3
    import mutagen.id3
    import MP3Info
    
    # copied from quodlibet
    class ID3hack(mutagen.id3.ID3):
        "Override 'correct' behavior with desired behavior"
        def loaded_frame(self, tag):
            if len(type(tag).__name__) == 3: tag = type(tag).__base__(tag)
            if tag.HashKey in self and tag.FrameID[0] == "T":
                self[tag.HashKey].extend(tag[:])
            else: self[tag.HashKey] = tag

    registerfileformat("mp3", mp3mutagenmetadata, ".mp3")
    log.info("using mutagen module for id3 tag parsing")
except ImportError:
    try:
        import eyeD3
        import MP3Info # we also need this
        registerfileformat("mp3", mp3eyeD3metadata, ".mp3")
        log.info("using eyeD3 module for id3 tag parsing")
    except ImportError:
        try:
            import MP3Info
            registerfileformat("mp3", mp3MP3Infometadata, ".mp3")
            log.info("using integrated MP3Info module for id3 tag parsing")
        except ImportError:
            pass

#
# FLAC metadata decoder
#

class flacmetadata(metadata):
    def __init__(self, path):
        metadata.__init__(self, path)
        chain = flac.metadata.Chain()
        chain.read(path)
        it = flac.metadata.Iterator()
        it.init(chain)
        while 1:
            block = it.get_block()
            if block.type == flac.metadata.VORBIS_COMMENT:
                comment = flac.metadata.VorbisComment(block).comments
                id3get = lambda key, default: getattr(comment, key, default)
                self.title = id3get('TITLE', "")
                self.title = self.title.encode(localecharset, 'replace')
                self.album = id3get('ALBUM', "")
                self.album = self.album.encode(localecharset, 'replace')
                self.artist = id3get('ARTIST', "")
                self.artist = self.artist.encode(localecharset, 'replace')
                self.year = id3get('DATE', "")
                self.year = self.year.encode(localecharset, 'replace')
                self.genre  = id3get('GENRE', "")
                self.genre = self.genre.encode(localecharset, 'replace')
                self.tracknr = id3get('TRACKNUMBER', "")
                self.tracknr = self.tracknr.encode(localecharset, 'replace')
            elif block.type == flac.metadata.STREAMINFO:
                streaminfo = block.data.stream_info
                self.length = streaminfo.total_samples / streaminfo.sample_rate
            if not it.next():
                break

try:
    import flac.metadata
    registerfileformat("flac", flacmetadata, ".flac")
    log.info("flac support enabled (VERY EXPERIMENTAL)")
except ImportError:
    log.info("flac support disabled, since flac module is not present")
