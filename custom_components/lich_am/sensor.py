# encoding: utf-8
'''
=== Lunar calendar on Home Assistant by exlab ===
============ Date 11/03/2019 ====================
=== Mod by thangnd85
--------
#1 Copy sensor.py to {your_config folder}\custom_components\lich_am\
#2 Setup in configuration.yaml 
sensor:
  - platform: lich_am
    delimiter: "-"#Optional, default = "/"
	type: number or text
--------        
'''
import datetime
import logging
import math
from datetime import timedelta
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_DELIMITER = 'delimiter' 
SCAN_INTERVAL = datetime.timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DELIMITER, default= '/'): cv.string,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    delimiter = config.get(CONF_DELIMITER)
    add_devices([lunar_calendar(delimiter),lunar_calendar_text(delimiter),lunar_calendar_nextday(delimiter),lunar_calendar_nextdate(delimiter)])

class lunar_calendar(Entity):
    def __init__(self, delimiter):
        self._name = 'Ngày âm'
        self._state = None
        self._delimiter = delimiter
        self._description = 'Âm lịch @ Hồ Ngọc Đức'
        self.update()
    @property
    def name(self):
        return self._name
    @property
    def state(self):
        return self._state
    @property
    def icon(self):
        """Return the icon of the sensor"""
        return 'mdi:calendar'
    @property
    def device_state_attributes(self):
        return {'Thông tin': self._description}
    @Throttle(SCAN_INTERVAL)
    def update(self):
        self._state = solar2lunar(self._delimiter)[0]
class lunar_calendar_text(Entity):
    def __init__(self, delimiter):
        self._name = 'Hôm nay'
        self._state = None
        self._delimiter = delimiter
        self._description = 'Âm lịch @ Hồ Ngọc Đức'
        self.update()
    @property
    def name(self):
        return self._name
    @property
    def state(self):
        return self._state
    @property
    def icon(self):
        """Return the icon of the sensor"""
        return 'mdi:calendar'
    @property
    def device_state_attributes(self):
        return {'Thông tin': self._description}
    @Throttle(SCAN_INTERVAL)
    def update(self):
        self._state = solar2lunar(self._delimiter)[1]
class lunar_calendar_nextdate(Entity):

    def __init__(self, delimiter):
        self._name = 'Âm lịch ngày mai'
        self._state = None
        self._delimiter = delimiter
        self._description = 'Âm lịch @ Hồ Ngọc Đức'
        self.update()
    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state
		
    @property
    def icon(self):
        """Return the icon of the sensor"""
        return 'mdi:calendar'
		
    @property
    def device_state_attributes(self):
        return {'Thông tin': self._description}

    @Throttle(SCAN_INTERVAL)
    def update(self):
        self._state = solar2lunar(self._delimiter)[2]
class lunar_calendar_nextday(Entity):

    def __init__(self, delimiter):
        self._name = 'Ngày mai'
        self._state = None
        self._delimiter = delimiter
        self._description = 'Âm lịch @ Hồ Ngọc Đức'
        self.update()

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state
		
    @property
    def icon(self):
        """Return the icon of the sensor"""
        return 'mdi:calendar'
		
    @property
    def device_state_attributes(self):
        return {'Thông tin': self._description}

    @Throttle(SCAN_INTERVAL)
    def update(self):
        self._state = solar2lunar(self._delimiter)[3]
def today():
    a = 'Hôm nay'
    #print ('âm lịch hôm nay')
    ngay = datetime.date.today()
    yy,mm, dd = ngay.year, ngay.month, ngay.day 
    amlich = [a,yy,mm,dd]
    return amlich,ngay
def tomorrow():
    #print ('Âm lịch ngày mai')
    a = 'Ngày mai'
    ngay = datetime.date.today() + timedelta(1)
    yy,mm, dd = ngay.year, ngay.month, ngay.day 
    amlich = [a,yy,mm,dd]
    return amlich,ngay
def solar2lunar(_delimiter):
        today = datetime.date.today()
        yy =  today.year
        mm = today.month
        dd = today.day
        tmr = today + datetime.timedelta(1)
        yy_tmr = tmr.year
        mm_tmr = tmr.month
        dd_tmr = tmr.day
        lunar_date = S2L(dd, mm, yy)
        lunar_date_tmr = S2L(dd_tmr, mm_tmr, yy_tmr)
        ngay_am,thang_am,nam_am,nam_nhuan = lunar_date
        ngay_am_sau,thang_am_sau,nam_am_sau,nam_nhuan = lunar_date_tmr
        mung = 'mùng ' if ngay_am < 11 else ''
        special = 'rằm ' if ngay_am == 15 else ''
        ngay_am_text = ' '.join([mung,special,str(ngay_am)])
        mung_sau = 'mùng ' if ngay_am_sau < 11 else ''
        special_sau = 'rằm ' if ngay_am_sau == 15 else ''
        ngay_am_text_sau = ' '.join([mung_sau,special_sau,str(ngay_am_sau)])
        counter = ''
        if ngay_am < 14:
            days_left = 15 - ngay_am
            counter =' '.join([', còn',str(days_left),' ngày nữa thì đến rằm'])
        elif ngay_am == 14:
            counter ='ngày mai rằm nhé'
        else:
            if thang_am < 12:
                nam_a = nam_am
                thang_sau = thang_am + 1
            else:
                thang_sau = 1
                nam_a = nam_am + 1
                nd,td,nmd = L2S(28,12,yy,nam_nhuan)
                daa = '-'.join([str(nd),str(td),str(nmd)])
                a2dnew = datetime.datetime.strptime(daa, '%d-%m-%Y').date()
                ngaytet, thangtet, namtet= a2dnew.day, a2dnew.month, a2dnew.year
                nammoi = S2L(ngaytet,thangtet,namtet)
                nam_nhuan = nammoi[3]
            nd,td,nmd  = L2S(1,thang_sau,nam_a,nam_nhuan)
            daa = '-'.join([str(nd),str(td),str(nmd)])
            a2dnew = datetime.datetime.strptime(daa, '%d-%m-%Y').date()
            ngay_mai = tomorrow()[1]
            delta = a2dnew - ngay_mai
            days_left = delta.days
            counter =' '.join([', còn',str(days_left),'ngày nữa thì đến mùng 1'])
        list_thang = ["tháng Giêng","tháng Hai","tháng Ba","tháng Tư","tháng Năm","tháng Sáu","tháng Bảy","tháng Tám","tháng Chín","tháng Mười","tháng Mười một","tháng Chạp"]
        thang_nay_text = list_thang[thang_am-1]
        thang_sau_text = list_thang[thang_am_sau-1]
        can = ['Canh ', 'Tân ', 'Nhâm ', 'Quý ', 'Giáp ', 'Ất ', 'Bính ', 'Đinh ','Mậu ','Kỷ ']
        chi = ['Thân', 'Dậu', 'Tuất', 'Hợi','Tí','Sửu','Dần', 'Mão', 'Thìn', 'Tị', 'Ngọ', "Mùi"]
        vitri_can = nam_am % 10
        vitri_chi = nam_am % 12
        vitri_can_sau = nam_am_sau % 10
        vitri_chi_sau = nam_am_sau % 12
        lunar_text = ' '.join(['Ngày',ngay_am_text,thang_nay_text,'năm',can[vitri_can],chi[vitri_chi]])
        lunar_date = ngay_am
        lunar_text_sau = ' '.join(['Ngày',ngay_am_text_sau,thang_sau_text,'năm',can[vitri_can_sau],chi[vitri_chi_sau],str(nam_am_sau),counter])
        lunar_date_sau = ngay_am_sau
        return lunar_date, lunar_text, lunar_date_sau, lunar_text_sau #Hiện chữ
#        return lunar_text #Hiện ngày

''' Thuật toán tính âm lịch
(c) 2006 Ho Ngoc Duc.
Astronomical algorithms
from the book "Astronomical Algorithms" by Jean Meeus, 1998
link: https://www.informatik.uni-leipzig.de/~duc/amlich/calrules.html
'''
def jdFromDate(dd, mm, yy):
  '''def jdFromDate(dd, mm, yy): Compute the (integral) Julian day number of day dd/mm/yyyy, i.e., the number of days between 1/1/4713 BC (Julian calendar) and dd/mm/yyyy.'''
  a = int((14 - mm) / 12.)
  y = yy + 4800 - a
  m = mm + 12*a - 3
  jd = dd + int((153*m + 2) / 5.) \
        + 365*y + int(y/4.) - int(y/100.) \
        + int(y/400.) - 32045
  if (jd < 2299161):
    jd = dd + int((153*m + 2)/5.) \
          + 365*y + int(y/4.) - 32083
  return jd

def jdToDate(jd):
  '''def jdToDate(jd): Convert a Julian day number to day/month/year. jd is an integer.'''
  if (jd > 2299160):
    ## After 5/10/1582, Gregorian calendar
    a = jd + 32044
    b = int((4*a + 3) / 146097.)
    c = a - int((b*146097) / 4.)
  else:
    b = 0
    c = jd + 32082
  d = int((4*c + 3) / 1461.)
  e = c - int((1461*d) / 4.)
  m = int((5*e + 2) / 153.)
  day = e - int((153*m + 2) / 5.) + 1
  month = m + 3 - 12*int(m / 10.)
  year = b*100 + d - 4800 + int(m / 10.)
  return [day, month, year]

def NewMoon(k):
  '''def NewMoon(k): Compute the time of the k-th new moon after the new moon of 1/1/1900 13:52 UCT (measured as the number of days since 1/1/4713 BC noon UCT, e.g., 2451545.125 is 1/1/2000 15:00 UTC. Returns a floating number, e.g., 2415079.9758617813 for k=2 or 2414961.935157746 for k=-2.'''
  ## Time in Julian centuries from 1900 January 0.5
  T = k / 1236.85
  T2 = T * T
  T3 = T2 * T
  dr = math.pi / 180.
  Jd1 = 2415020.75933 + 29.53058868*k \
          + 0.0001178*T2 - 0.000000155*T3
  Jd1 = Jd1 + 0.00033*math.sin( \
            (166.56 + 132.87*T - 0.009173*T2)*dr)
  ## Mean new moon
  M = 359.2242 + 29.10535608*k \
      - 0.0000333*T2 - 0.00000347*T3
  ## Sun's mean anomaly
  Mpr = 306.0253 + 385.81691806*k \
          + 0.0107306*T2 + 0.00001236*T3
  ## Moon's mean anomaly
  F = 21.2964 + 390.67050646*k - 0.0016528*T2 \
        - 0.00000239*T3
  ## Moon's argument of latitude
  C1 = (0.1734 - 0.000393*T)*math.sin(M*dr) \
        + 0.0021*math.sin(2*dr*M)
  C1 = C1 - 0.4068*math.sin(Mpr*dr) \
        + 0.0161*math.sin(dr*2*Mpr)
  C1 = C1 - 0.0004*math.sin(dr*3*Mpr)
  C1 = C1 + 0.0104*math.sin(dr*2*F) \
        - 0.0051*math.sin(dr*(M + Mpr))
  C1 = C1 - 0.0074*math.sin(dr*(M - Mpr)) \
        + 0.0004*math.sin(dr*(2*F + M))
  C1 = C1 - 0.0004*math.sin(dr*(2*F - M)) \
        - 0.0006*math.sin(dr*(2*F + Mpr))
  C1 = C1 + 0.0010*math.sin(dr*(2*F - Mpr)) \
        + 0.0005*math.sin(dr*(2*Mpr + M))
  if (T < -11):
    deltat= 0.001 + 0.000839*T + 0.0002261*T2 \
                - 0.00000845*T3 - 0.000000081*T*T3
  else:
    deltat= -0.000278 + 0.000265*T + 0.000262*T2
  JdNew = Jd1 + C1 - deltat
  return JdNew

def SunLongitude(jdn):
  '''def SunLongitude(jdn): Compute the longitude of the sun at any time. Parameter: floating number jdn, the number of days since 1/1/4713 BC noon.'''
  T = (jdn - 2451545.0 ) / 36525.
  ## Time in Julian centuries
  ## from 2000-01-01 12:00:00 GMT
  T2 = T * T
  dr = math.pi / 180.  ## degree to radian
  M = 357.52910 + 35999.05030*T \
      - 0.0001559*T2 - 0.00000048*T*T2
  ## mean anomaly, degree
  L0 = 280.46645 + 36000.76983*T + 0.0003032*T2
  ## mean longitude, degree
  DL = (1.914600 - 0.004817*T - 0.000014*T2) \
          * math.sin(dr*M)
  DL += (0.019993 - 0.000101*T) *math.sin(dr*2*M) \
            + 0.000290*math.sin(dr*3*M)
  L = L0 + DL  ## true longitude, degree
  L = L * dr
  L = L - math.pi*2*(int(L / (math.pi*2)))
  #### Normalize to (0, 2*math.pi)
  return L

def getSunLongitude(dayNumber, timeZone):
  '''def getSunLongitude(dayNumber, timeZone):  Compute sun position at midnight of the day with the given Julian day number. The time zone if the time difference between local time and UTC: 7.0 for UTC+7:00. The function returns a number between 0 and 11.  From the day after March equinox and the 1st major term after March equinox, 0 is returned. After that, return 1, 2, 3 ...'''
  return int( \
    SunLongitude(dayNumber - 0.5 - timeZone/24.) \
    / math.pi*6)

def getNewMoonDay(k, timeZone):
  '''def getNewMoonDay(k, timeZone): Compute the day of the k-th new moon in the given time zone. The time zone if the time difference between local time and UTC: 7.0 for UTC+7:00.'''
  return int(NewMoon(k) + 0.5 + timeZone / 24.)

def getLunarMonth11(yy, timeZone):
  '''def getLunarMonth11(yy, timeZone):  Find the day that starts the luner month 11of the given year for the given time zone.'''
  # off = jdFromDate(31, 12, yy) \
  #            - 2415021.076998695
  off = jdFromDate(31, 12, yy) - 2415021.
  k = int(off / 29.530588853)
  nm = getNewMoonDay(k, timeZone)
  sunLong = getSunLongitude(nm, timeZone)
  #### sun longitude at local midnight
  if (sunLong >= 9):
    nm = getNewMoonDay(k - 1, timeZone)
  return nm

def getLeapMonthOffset(a11, timeZone):
  '''def getLeapMonthOffset(a11, timeZone): Find the index of the leap month after the month starting on the day a11.'''
  k = int((a11 - 2415021.076998695) \
              / 29.530588853 + 0.5)
  last = 0
  i = 1  ## start with month following lunar month 11
  arc = getSunLongitude( \
                getNewMoonDay(k + i, timeZone), timeZone)
  while True:
    last = arc
    i += 1
    arc = getSunLongitude( \
                      getNewMoonDay(k + i, timeZone), \
                      timeZone)
    if  not (arc != last and i < 14):
      break
  return i - 1

def S2L(dd, mm, yy, timeZone = 7):
  '''def S2L(dd, mm, yy, timeZone = 7): Convert solar date dd/mm/yyyy to the corresponding lunar date.'''
  dayNumber = jdFromDate(dd, mm, yy)
  k = int((dayNumber - 2415021.076998695) \
                / 29.530588853)
  monthStart = getNewMoonDay(k + 1, timeZone)
  if (monthStart > dayNumber):
    monthStart = getNewMoonDay(k, timeZone)
  # alert(dayNumber + " -> " + monthStart)
  a11 = getLunarMonth11(yy, timeZone)
  b11 = a11
  if (a11 >= monthStart):
    lunarYear = yy
    a11 = getLunarMonth11(yy - 1, timeZone)
  else:
    lunarYear = yy + 1
    b11 = getLunarMonth11(yy + 1, timeZone)
  lunarDay = dayNumber - monthStart + 1
  diff = int((monthStart - a11) / 29.)
  lunarLeap = 0
  lunarMonth = diff + 11
  if (b11 - a11 > 365):
    leapMonthDiff = \
        getLeapMonthOffset(a11, timeZone)
    if (diff >= leapMonthDiff):
      lunarMonth = diff + 10
      if (diff == leapMonthDiff):
        lunarLeap = 1
  if (lunarMonth > 12):
    lunarMonth = lunarMonth - 12
  if (lunarMonth >= 11 and diff < 4):
    lunarYear -= 1
  return \
      [ lunarDay, lunarMonth, lunarYear, lunarLeap ]
def L2S(lunarD, lunarM, lunarY, lunarLeap, tZ = 7):
  '''def L2S(lunarD, lunarM, lunarY, lunarLeap, tZ = 7): Convert a lunar date to the corresponding solar date.'''
  if (lunarM < 11):
    a11 = getLunarMonth11(lunarY - 1, tZ)
    b11 = getLunarMonth11(lunarY, tZ)
  else:
    a11 = getLunarMonth11(lunarY, tZ)
    b11 = getLunarMonth11(lunarY + 1, tZ)
  k = int(0.5 + \
              (a11 - 2415021.076998695) / 29.530588853)
  off = lunarM - 11
  if (off < 0):
    off += 12
  if (b11 - a11 > 365):
    leapOff = getLeapMonthOffset(a11, tZ)
    leapM = leapOff - 2
    if (leapM < 0):
      leapM += 12
    if (lunarLeap != 0 and lunarM != leapM):
      return [0, 0, 0]
    elif (lunarLeap != 0 or off >= leapOff):
      off += 1
  monthStart = getNewMoonDay(k + off, tZ)
  return jdToDate(monthStart + lunarD - 1)

''' end function calendar '''    
''' end function calendar '''




