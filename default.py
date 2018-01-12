# -*- coding: utf-8 -*-

# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with XBMC; see the file COPYING. If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html

from demjson import demjson
from PIL import Image
from stats import STATS
from collections import defaultdict
import bs4
import cStringIO
import datetime
import math
import os
import re
import socket
import sys
import urllib2
import util
import xbmc
import xbmcaddon
import xbmcgui


# Nacitanie informacii o doplnku
__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
__addonid__ = __addon__.getAddonInfo('id')
__cwd__ = __addon__.getAddonInfo('path').decode("utf-8")
__language__ = __addon__.getLocalizedString
PROFILE = xbmc.translatePath(__addon__.getAddonInfo('profile')).decode('utf-8')


def log(msg):
    xbmc.log(("### [%s] - %s" % (__addonname__.decode('utf-8'),
                                 msg.decode('utf-8'))).encode('utf-8'), level=xbmc.LOGDEBUG)

# Vseobecne nastavenia
_UserAgent_ = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3'
WEATHER_WINDOW = xbmcgui.Window(12600)
socket.setdefaulttimeout(10)

# Vypisovanie nazvov dnov v Slovencine
skdays = ['Nedeľa', 'Pondelok', 'Utorok', 'Streda', 'Štvrtok', 'Piatok', 'Sobota',
          'Nedeľa', 'Pondelok', 'Utorok', 'Streda', 'Štvrtok', 'Piatok', 'Sobota', 'Nedeľa']
den = datetime.datetime.now()
den = int(den.strftime("%w"))
log('den: %s' % den)

# Nastavenie hodnot o pocasi


def set_property(name, value):
    WEATHER_WINDOW.setProperty(name, value)


en2icon = defaultdict(str)
en2icon.update({
    'rain': 'dest',
    'clear': 'jasno',
    'clouds': 'oblacno',
    'thunderstorm': 'bourky',
    'mist': 'mlha',
    'fog': 'mlha'
})

WEATHER_CODES = {
    '1': '32',
    '2': '34',  # mala oblacnost
    '3': '26',
    '4': '40',  # dazd
    '5': '39',
    '6': '17',
    '7': '18',
    '8': '6',
    '9': '20',
    '10': '26',  # oblacno
    '11': '39',
    '12': '30',  # mala oblacnost
    '13': '42',
    '16': '26',  # zamracene
}

# Nacita udaje o pocasi zo servera


def degToCompass(num):
    """https://stackoverflow.com/questions/7490660/converting-wind-direction-in-angles-to-text-words"""
    val = int((num / 22.5) + .5)
    arr = ["N", "NNE", "NE", "ENE", "E", "ESE",  "SE",  "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return arr[(val % 16)]


def parse_data():
    # Stiahnutie udajov
    mesto = __addon__.getSetting('mesto')
    mestometeogram = __addon__.getSetting('mestometeogram')
    key = __addon__.getSetting('key')

    if not key:
        xbmcgui.Dialog().ok('Chyba', 'Zadajte v nastaveniach kľúč k OpenWeather API!')
        return True

    data = {'mesto': mesto, 'page': '1', 'id': 'meteo_predpoved_sk'}
    url = 'http://www.shmu.sk/sk/?#tab'
    page = util.post(url, data)
    soup = bs4.BeautifulSoup(page, "html5lib")
    print('mesto: %s, den: %s' % (mesto, den))
    WEATHER_WINDOW.clearProperties()
    cnt = 1
    for x in soup.select('.w600')[0].tbody.findAll('td', 'center'):
        if x.has_attr('style'):
            if 'white-space' in x['style']:
                print('Daily.%s.LongDay' % cnt, skdays[den + cnt - 1])
                set_property('Daily.%s.LongDay' % cnt, skdays[den + cnt - 1])
                set_property('Daily.%s.ShortDay' % cnt, skdays[den + cnt - 1])
                night, day = x.get_text(separator='|').split('|')
                set_property('Daily.%s.HighTemperature' % cnt, day)
                set_property('Daily.%s.LowTemperature' % cnt, night)
            elif 'background:#00660E' in x['style']:
                imgname = x.img['src'].split('/')[-1]
                set_property('Daily.%s.Outlook' % cnt, x.img['alt'])
                image_name = x.img['src'].split('/')[-1]
                set_property('Daily.%s.OutlookIcon' % cnt, WEATHER_CODES[
                             image_name.replace('.gif', '')] + '.png')
                cnt += 1

    url = 'http://api.openweathermap.org/data/2.5/find?q=%s&type=like&mode=json&APPID=%s&units=metric' \
        % (urllib2.quote(mesto), key)
    req = urllib2.urlopen(url)
    response = req.read()
    req.close()
    jsonresponse = demjson.decode(response)['list'][0]

    set_property('Current.Temperature', str(jsonresponse['main']['temp']))
    set_property('Current.Wind', str(jsonresponse['wind']['speed'] * 3.6))
    set_property('Current.WindDirection',
                 degToCompass(jsonresponse['wind']['deg']))
    set_property('Current.FeelsLike', feelslike(round(float(jsonresponse['main']['temp'])),
                                                int(round(float(jsonresponse['wind']['speed']) * 3.6) + 0.5)))
    set_property('Current.Humidity', str(jsonresponse['main']['humidity']))
    set_property('Current.DewPoint', dewpoint(round(float(jsonresponse['main']['temp'])),
                                              int(jsonresponse['main']['humidity'])))
    set_property('Current.Pressure', str(jsonresponse['main']['pressure']))
    set_property('Current.Condition', str(jsonresponse['weather'][0]['main']))
    iconfilename = en2icon[jsonresponse['weather'][0]['main'].lower()]
    if not iconfilename:
        iconfilename = 'none'
    set_property('Current.OutlookIcon', xbmc.translatePath(os.path.join(
        __cwd__, 'resources/lib/icons', '%s.png' % iconfilename)))
    meteogrampage = util.parse_html('http://www.shmu.sk/sk/?page=1&id=meteo_num_mgram')
    cityid = meteogrampage.select('select#nwp_mesto')[0].find(text=mestometeogram).parent['value']
    day, month, year, hour, text = re.split(
        '[. ]', meteogrampage.select('select[class=w150] option')[-1].text)
    meteogramdate = '%s%s%s-%s00' % (year, month, day, hour)
    query = 'http://www.shmu.sk/data/datanwp/v2/' +\
        'meteogram/al-meteogram_%s-%s-nwp-.png' \
        % (cityid, meteogramdate)
    req = urllib2.Request(query)
    response = urllib2.urlopen(req, timeout=10)
    meteogramimage = Image.open(cStringIO.StringIO(response.read()))
    headerimage = meteogramimage.crop(box=(0, 0, 600, 45))
    response.close()

    aladin_text = ['Teplota, oblačnosť, zrážky', 'Tlak, rýchlosť a smer vetra']

    set_property('Map.IsFetched', '')
    print('Stahujem meteogram..')
    for i in range(0, 2):
        outfilename = os.path.join(PROFILE, '%s_aladin%s.png' % (meteogramdate, i + 1))
        imgfile = open(outfilename, 'wb')
        out = Image.new("RGBA", (756, 756), None)
        currview = meteogramimage.crop(box=(0, 45 + 430 * i, 600, 430 * (i + 1) + 45))
        out.paste(headerimage, (75, 75))
        out.paste(currview, (75, 75 + 45))
        out.save(imgfile)
        imgfile.close()
        set_property('Map.%s.Area' % str(i + 1), outfilename)
        set_property('Map.%s.Layer' % str(i + 1), outfilename)
        set_property('Map.%s.Heading' % str(i + 1), aladin_text[i])
    set_property('Map.IsFetched', 'true')


def clear():  # Vynulovanie hodnot pred stiahnutim novych
    set_property('Current.Condition', 'N/A')
    set_property('Current.Temperature', '0')
    set_property('Current.Wind', '0')
    set_property('Current.WindDirection' , 'N/A')
    set_property('Current.Humidity', '0')
    set_property('Current.OutlookIcon', 'na.png')
    set_property('Current.FanartCode', 'na')
    for count in range(0, 4):
        set_property('Daily.%i.Title' % count, 'N/A')
        set_property('Daily.%i.HighTemperature' % count, '0')
        set_property('Daily.%i.LowTempTemperature' % count, '0')
        set_property('Daily.%i.Outlook' % count, 'N/A')
        set_property('Daily.%i.OutlookIcon' % count, 'na.png')
        set_property('Daily.%i.FanartCode' % count, 'na')


def feelslike(T=10, V=25):  # Pomocna funkce pro vypocet pocitove teploty
    """ The formula to calculate the equivalent temperature related to the wind chill is:
        T(REF) = 13.12 + 0.6215 * T - 11.37 * V**0.16 + 0.3965 * T * V**0.16
        Or:
        T(REF): is the equivalent temperature in degrees Celsius
        V: is the wind speed in km/h measured at 10m height
        T: is the temperature of the air in degrees Celsius
        source: http://zpag.tripod.com/Meteo/eolien.htm

        getFeelsLike( tCelsius, windspeed )
    """
    FeelsLike = T
    # Wind speeds of 4 mph or less, the wind chill temperature is the same as
    # the actual air temperature.
    if round((V + .0) / 1.609344) > 4:
        FeelsLike = (13.12 + (0.6215 * T) - (11.37 * V**0.16) + (0.3965 * T * V**0.16))
    return str(round(FeelsLike))


def dewpoint(Tc=0, RH=93, minRH=(0, 0.075)[0]):  # Pomocna funkce pro vypocet rosneho bodu
    """ Dewpoint from relative humidity and temperature
        If you know the relative humidity and the air temperature,
        and want to calculate the dewpoint, the formulas are as follows.

        getDewPoint( tCelsius, humidity )
    """
    # First, if your air temperature is in degrees Fahrenheit, then you must convert it to degrees Celsius by using the Fahrenheit to Celsius formula.
    # Tc = 5.0 / 9.0 * ( Tf - 32.0 )
    # The next step is to obtain the saturation vapor pressure(Es) using this
    # formula as before when air temperature is known.
    Es = 6.11 * 10.0**(7.5 * Tc / (237.7 + Tc))
    # The next step is to use the saturation vapor pressure and the relative humidity to compute the actual vapor pressure(E) of the air. This can be done with the following formula.
    # RH=relative humidity of air expressed as a percent. or except
    # minimum(.075) humidity to abort error with math.log.
    RH = RH or minRH  # 0.075
    E = (RH * Es) / 100
    # Note: math.log( ) means to take the natural log of the variable in the parentheses
    # Now you are ready to use the following formula to obtain the dewpoint temperature.
    try:
        DewPoint = (-430.22 + 237.7 * math.log(E)) / (-math.log(E) + 19.08)
    except ValueError:
        # math domain error, because RH = 0%
        # return "N/A"
        DewPoint = 0  # minRH
    # Note: Due to the rounding of decimal places, your answer may be slightly
    # different from the above answer, but it should be within two degrees.
    return str(int(DewPoint))


def settings():
    # Vyparsuj a zobraz mesta
    dialog = xbmcgui.Dialog()
    mestalist1 = [
        'BANSKÁ BYSTRICA',
        'BARDEJOV',
        'BRATISLAVA',
        'BREZNO',
        'DOLNÝ KUBÍN',
        'DUNAJSKÁ STREDA',
        'HURBANOVO',
        'KOMÁRNO',
        'KOŠICE',
        'KRÁĽ. CHLMEC',
        'LEVICE',
        'LIPTOVSKÝ MIKULÁŠ',
        'LUČENEC',
        'MEDZILABORCE',
        'MICHALOVCE',
        'NITRA',
        'PEZINOK',
        'PIEŠŤANY',
        'POPRAD',
        'PREŠOV',
        'PRIEVIDZA',
        'RIMAVSKÁ SOBOTA',
        'ROŽŇAVA',
        'SENICA',
        'SKALICA',
        'ŠAHY',
        'TRENČÍN',
        'TRNAVA',
        'VEĽKÝ KRTÍŠ',
        'ŽILINA',
    ]

    log("Mesta zoznam: %s" % mestalist1)
    mesto = dialog.select('Vyberte mesto', mestalist1)

    meteogrampage = util.parse_html('http://www.shmu.sk/sk/?page=1&id=meteo_num_mgram')
    mestalist2 = meteogrampage.select('select#nwp_mesto')[0].get_text(separator='|').split('|')
    mestometeogram = dialog.select('Vyberte mesto (meteogram)', mestalist2)

    # Uloz nastavenia
    __addon__.setSetting('mesto', mestalist1[mesto])
    __addon__.setSetting('mestometeogram', mestalist2[mestometeogram])

# Hlavny program


# Zobraz nastavenia
if sys.argv[1].startswith('mesto'):
    settings()

# Vycisti data
clear()

# Dopln aktualne data
parse_data()

# Vseobecne informacie
set_property('Location1',           __addon__.getSetting('mesto'))
set_property('Locations',           str(1))
set_property('WeatherProvider',     __addonname__)
set_property('WeatherProviderLogo', xbmc.translatePath(
    os.path.join(__cwd__, 'resources', 'banner.png')))
set_property('Forecast.IsFetched', 'true')
set_property('Daily.IsFetched', 'true')
set_property('Map.IsFetched', 'true')

# Statistiky
STATS(__addon__.getSetting('mesto'), "Location")
