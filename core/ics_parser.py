from icalendar import Calendar, Event
import httpx

from datetime import datetime, timezone, timedelta

from astrbot.api import logger

SHANGHAI_TZ = timezone(timedelta(hours=8))


async def fetch_ics(calender_url: str):

    try:
        # 获取课表数据并修补格式
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(calender_url)
            resp.raise_for_status()
        return resp.text.replace("DTSTART:\r", "DTSTART:19700101T000000\r")
    except Exception as e:
        logger.error(f"获取 ics 文件出错: {e}")
    return None


def ics_generator(ics: str, url: str):
    """简化课表信息"""
    cal = Calendar.from_ical(ics)
    simplifed = Calendar()
    simplifed.add("prodid", "-//NNU Schedule Converter//")
    simplifed.add("version", "2.0")
    simplifed.add("x-nnu-url", url)
    dtstamp = datetime.now()
    simplifed.add("x-nnu-dtstamp", dtstamp)
    for component in cal.walk()[::-1]:
        if component.name == "VEVENT":
            dtend = component.get("DTEND").dt
            if dtend < dtstamp:
                continue
            dtstart = component.get("DTSTART").dt
            uid = component.get("UID")
            summary = component.get("SUMMARY")
            location = component.get("LOCATION")

            dtstart = dtstart.replace(tzinfo=SHANGHAI_TZ)
            dtend = dtend.replace(tzinfo=SHANGHAI_TZ)

            course_event = Event()
            course_event.add("uid", uid)
            course_event.add("dtstart", dtstart)
            course_event.add("dtend", dtend)
            course_event.add("summary", summary)
            course_event.add("location", location)

            simplifed.add_component(course_event)

    return simplifed.to_ical()
