"""The Lich Am integration."""
from __future__ import annotations

import logging
import datetime
import math
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import Platform

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lich Am from a config entry."""
    
    coordinator = LichAmDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

class LichAmDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Lich Am data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Chạy thuật toán trong thread pool để không chặn loop chính
            return await self.hass.async_add_executor_job(self.calculate_solar2lunar)
        except Exception as err:
            raise UpdateFailed(f"Error calculating lunar date: {err}")

    def calculate_solar2lunar(self):
        """Logic tính toán Lịch Âm (Đã kiểm tra OK)."""
        today = datetime.date.today()
        dd, mm, yy = today.day, today.month, today.year

        # 1. Tính hôm nay
        ngay_am, thang_am, nam_am, is_leap_month = S2L(dd, mm, yy)
        
        can = ['Canh', 'Tân', 'Nhâm', 'Quý', 'Giáp', 'Ất', 'Bính', 'Đinh', 'Mậu', 'Kỷ']
        chi = ['Thân', 'Dậu', 'Tuất', 'Hợi', 'Tý', 'Sửu', 'Dần', 'Mão', 'Thìn', 'Tỵ', 'Ngọ', 'Mùi']
        nam_can_chi = f"{can[nam_am % 10]} {chi[nam_am % 12]}"

        # 2. Logic đếm ngược
        counter_text = ""
        if ngay_am == 1:
            counter_text = ". Hôm nay là Mùng 1"
        elif ngay_am == 15:
            counter_text = ". Hôm nay là Rằm"
        elif ngay_am < 14:
            days_left = 15 - ngay_am
            counter_text = f", còn {days_left} ngày nữa là Rằm"
        elif ngay_am == 14:
            counter_text = ", ngày mai là Rằm"
        else:
            try:
                next_month = thang_am + 1
                next_year = nam_am
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                solar_date_list_next_month = L2S(1, next_month, next_year, 0, 7)
                if solar_date_list_next_month != [0, 0, 0]:
                    next_new_moon_date = datetime.date(solar_date_list_next_month[2], solar_date_list_next_month[1], solar_date_list_next_month[0])
                    days_left = (next_new_moon_date - today).days
                    if days_left == 1:
                        counter_text = ", ngày mai là Mùng 1"
                    elif days_left > 1:
                        counter_text = f", còn {days_left} ngày nữa là Mùng 1"
            except: pass

        thang_text_list = ["Giêng", "Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy", "Tám", "Chín", "Mười", "Mười một", "Chạp"]
        thang_am_text = f"tháng {thang_text_list[thang_am - 1]}"
        if is_leap_month: thang_am_text += " nhuận"

        friendly_today_text = f"Ngày {ngay_am}, {thang_am_text} năm {nam_can_chi}{counter_text}"

        # 3. Tính ngày mai
        tmr = today + datetime.timedelta(days=1)
        ngay_am_sau, thang_am_sau, nam_am_sau, is_leap_next = S2L(tmr.day, tmr.month, tmr.year)
        nam_sau_can_chi = f"{can[nam_am_sau % 10]} {chi[nam_am_sau % 12]}"
        thang_sau_text = f"tháng {thang_text_list[thang_am_sau - 1]}"
        if is_leap_next: thang_sau_text += " nhuận"
        
        lunar_text_next = f"Ngày {ngay_am_sau}, {thang_sau_text} năm {nam_sau_can_chi}"

        return {
            "lunar_date": f"{ngay_am}/{thang_am}",
            "lunar_text_today": friendly_today_text,
            "lunar_date_next": f"{ngay_am_sau}/{thang_am_sau}",
            "lunar_text_next": lunar_text_next,
        }

# --- CÁC HÀM THUẬT TOÁN (S2L, L2S, jdFromDate...) ---
# Bạn hãy copy-paste nguyên văn phần thuật toán từ file sensor.py cũ vào cuối file này
# Để code gọn, tôi không paste lại toàn bộ thuật toán ở đây, 
# nhưng BẮT BUỘC phải có các hàm: jdFromDate, jdToDate, NewMoon, SunLongitude, 
# getSunLongitude, getNewMoonDay, getLunarMonth11, getLeapMonthOffset, S2L, L2S
# (Lấy từ file test_lich_am.py mà bạn vừa chạy thành công)

def jdFromDate(dd, mm, yy):
    a = int((14 - mm) / 12.)
    y = yy + 4800 - a
    m = mm + 12*a - 3
    jd = dd + int((153*m + 2) / 5.) + 365*y + int(y/4.) - int(y/100.) + int(y/400.) - 32045
    if (jd < 2299161):
        jd = dd + int((153*m + 2)/5.) + 365*y + int(y/4.) - 32083
    return jd

def jdToDate(jd):
    if (jd > 2299160):
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
    T = k / 1236.85
    T2 = T * T
    T3 = T2 * T
    dr = math.pi / 180.
    Jd1 = 2415020.75933 + 29.53058868*k + 0.0001178*T2 - 0.000000155*T3
    Jd1 = Jd1 + 0.00033*math.sin((166.56 + 132.87*T - 0.009173*T2)*dr)
    M = 359.2242 + 29.10535608*k - 0.0000333*T2 - 0.00000347*T3
    Mpr = 306.0253 + 385.81691806*k + 0.0107306*T2 + 0.00001236*T3
    F = 21.2964 + 390.67050646*k - 0.0016528*T2 - 0.00000239*T3
    C1 = (0.1734 - 0.000393*T)*math.sin(M*dr) + 0.0021*math.sin(2*dr*M)
    C1 = C1 - 0.4068*math.sin(Mpr*dr) + 0.0161*math.sin(dr*2*Mpr)
    C1 = C1 - 0.0004*math.sin(dr*3*Mpr)
    C1 = C1 + 0.0104*math.sin(dr*2*F) - 0.0051*math.sin(dr*(M + Mpr))
    C1 = C1 - 0.0074*math.sin(dr*(M - Mpr)) + 0.0004*math.sin(dr*(2*F + M))
    C1 = C1 - 0.0004*math.sin(dr*(2*F - M)) - 0.0006*math.sin(dr*(2*F + Mpr))
    C1 = C1 + 0.0010*math.sin(dr*(2*F - Mpr)) + 0.0005*math.sin(dr*(2*Mpr + M))
    if (T < -11):
        deltat= 0.001 + 0.000839*T + 0.0002261*T2 - 0.00000845*T3 - 0.000000081*T*T3
    else:
        deltat= -0.000278 + 0.000265*T + 0.000262*T2
    JdNew = Jd1 + C1 - deltat
    return JdNew

def SunLongitude(jdn):
    T = (jdn - 2451545.0 ) / 36525.
    T2 = T * T
    dr = math.pi / 180.
    M = 357.52910 + 35999.05030*T - 0.0001559*T2 - 0.00000048*T*T2
    L0 = 280.46645 + 36000.76983*T + 0.0003032*T2
    DL = (1.914600 - 0.004817*T - 0.000014*T2) * math.sin(dr*M)
    DL += (0.019993 - 0.000101*T) *math.sin(dr*2*M) + 0.000290*math.sin(dr*3*M)
    L = L0 + DL
    L = L * dr
    L = L - math.pi*2*(int(L / (math.pi*2)))
    return L

def getSunLongitude(dayNumber, timeZone):
    return int(SunLongitude(dayNumber - 0.5 - timeZone/24.) / math.pi*6)

def getNewMoonDay(k, timeZone):
    return int(NewMoon(k) + 0.5 + timeZone / 24.)

def getLunarMonth11(yy, timeZone):
    off = jdFromDate(31, 12, yy) - 2415021.
    k = int(off / 29.530588853)
    nm = getNewMoonDay(k, timeZone)
    sunLong = getSunLongitude(nm, timeZone)
    if (sunLong >= 9):
        nm = getNewMoonDay(k - 1, timeZone)
    return nm

def getLeapMonthOffset(a11, timeZone):
    k = int((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    last = 0
    i = 1
    arc = getSunLongitude(getNewMoonDay(k + i, timeZone), timeZone)
    while True:
        last = arc
        i += 1
        arc = getSunLongitude(getNewMoonDay(k + i, timeZone), timeZone)
        if  not (arc != last and i < 14):
            break
    return i - 1

def S2L(dd, mm, yy, timeZone = 7):
    dayNumber = jdFromDate(dd, mm, yy)
    k = int((dayNumber - 2415021.076998695) / 29.530588853)
    monthStart = getNewMoonDay(k + 1, timeZone)
    if (monthStart > dayNumber):
        monthStart = getNewMoonDay(k, timeZone)
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
        leapMonthDiff = getLeapMonthOffset(a11, timeZone)
        if (diff >= leapMonthDiff):
            lunarMonth = diff + 10
            if (diff == leapMonthDiff):
                lunarLeap = 1
    if (lunarMonth > 12):
        lunarMonth = lunarMonth - 12
    if (lunarMonth >= 11 and diff < 4):
        lunarYear -= 1
    return [ lunarDay, lunarMonth, lunarYear, lunarLeap ]

def L2S(lunarD, lunarM, lunarY, lunarLeap, tZ = 7):
    if (lunarM < 11):
        a11 = getLunarMonth11(lunarY - 1, tZ)
        b11 = getLunarMonth11(lunarY, tZ)
    else:
        a11 = getLunarMonth11(lunarY, tZ)
        b11 = getLunarMonth11(lunarY + 1, tZ)
    k = int(0.5 + (a11 - 2415021.076998695) / 29.530588853)
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