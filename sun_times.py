"""Lokale astronomische Sonnenzeiten nach NOAA-Näherung."""
from datetime import datetime, time, timezone
from math import acos, cos, degrees, pi, radians, sin, tan
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Berlin')


def _minutes(day, latitude, longitude):
    n = day.timetuple().tm_yday
    gamma = 2 * pi / 365 * (n - 1)
    equation = 229.18 * (0.000075 + 0.001868 * cos(gamma) - 0.032077 * sin(gamma)
                         - 0.014615 * cos(2 * gamma) - 0.040849 * sin(2 * gamma))
    declination = (0.006918 - 0.399912 * cos(gamma) + 0.070257 * sin(gamma)
                   - 0.006758 * cos(2 * gamma) + 0.000907 * sin(2 * gamma)
                   - 0.002697 * cos(3 * gamma) + 0.00148 * sin(3 * gamma))
    zenith = radians(90.833)
    latitude_radians = radians(latitude)
    cosine = cos(zenith) / (cos(latitude_radians) * cos(declination)) - tan(latitude_radians) * tan(declination)
    if cosine > 1:
        return None, None, 'polar_night'
    if cosine < -1:
        return None, None, 'midnight_sun'
    hour_angle = degrees(acos(cosine))
    noon = 720 - 4 * longitude - equation
    return noon - 4 * hour_angle, noon + 4 * hour_angle, None


def sun_times(day, latitude, longitude):
    sunrise_minutes, sunset_minutes, polar_state = _minutes(day, latitude, longitude)
    result = dict(sunrise=None, sunset=None, daylight_seconds=None,
                  polar_state=polar_state, latitude=latitude, longitude=longitude,
                  source='Lokale astronomische Berechnung')
    if polar_state:
        return result
    midnight = datetime.combine(day, time.min, timezone.utc)
    sunrise = midnight.timestamp() + sunrise_minutes * 60
    sunset = midnight.timestamp() + sunset_minutes * 60
    # Unix-Zeit bleibt eindeutig; die Anzeige übernimmt Europe/Berlin einschließlich DST.
    result.update(sunrise=sunrise, sunset=sunset,
                  daylight_seconds=round(sunset - sunrise))
    return result
