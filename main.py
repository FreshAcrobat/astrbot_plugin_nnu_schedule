from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools
from astrbot.core.utils.session_waiter import (
    SessionController,
    SessionFilter,
    session_waiter,
)
from icalendar import Calendar

from .core.config import ICS_URL
from .core.ics_parser import fetch_ics, ics_generator
from .core.room_parser import NNUClassroomTool

SHANGHAI_TZ = timezone(timedelta(hours=8))


class CustomFilter(SessionFilter):
    def filter(self, event: AstrMessageEvent) -> str:
        return event.get_sender_id()


class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_data_dir = StarTools.get_data_dir(self.name)
        self.context = context
        self.context.add_llm_tools(NNUClassroomTool())

    @filter.command_group("sch")
    def sch():
        pass

    @sch.command("b")
    async def command_bind(self, event: AstrMessageEvent):
        """绑定课表"""
        try:
            sender_id = event.get_sender_id()
            yield event.plain_result(
                "请在60秒内，在本会话内直接发送你的课表外部引用链接。"
            )
            session_filter = CustomFilter()

            @session_waiter(timeout=60, record_history_chains=False)
            async def bind_waiter(
                controller: SessionController, event: AstrMessageEvent
            ):
                reference_address = event.message_str
                # 过滤 Napcat 神秘上报事件
                if reference_address == "":
                    return

                if ICS_URL not in reference_address:
                    await event.send(
                        event.plain_result("未输入正确的链接，已取消绑定。")
                    )
                    controller.stop()
                    return

                raw_data = await fetch_ics(reference_address)
                if not raw_data:
                    await event.send(event.plain_result("无法获取课程表数据。"))
                    controller.stop()
                    return

                try:
                    ics_content = ics_generator(raw_data, reference_address)
                    if not ics_content:
                        await event.send(
                            event.plain_result("日历文件解析失败，无法生成 ics 文件。")
                        )
                        controller.stop()
                        return

                    with open(self.plugin_data_dir / f"{sender_id}.ics", "wb") as f:
                        f.write(ics_content)

                except Exception as e:
                    logger.error(f"处理引用链接失败: {e}")
                    await event.send(event.plain_result("处理引用链接失败。"))
                    controller.stop()
                    return

                await event.send(event.plain_result("绑定课表成功"))
                controller.stop()

            try:
                await bind_waiter(event, session_filter=session_filter)
            except TimeoutError:
                yield event.plain_result("已超时，取消绑定。")
            except Exception as e:
                logger.error(f"绑定课表时出错：{e}")
                yield event.plain_result("发生错误，请联系管理员.")
            finally:
                event.stop_event()
        except Exception as e:
            logger.error(f"处理绑定课表出错: {e}")

    @filter.command("今日课表")
    async def command_today_schedule(self, event: AstrMessageEvent):
        """查看今日课表"""
        try:
            sender_id = event.get_sender_id()
            now = datetime.now(SHANGHAI_TZ)
            schedule_date = now.date()
            if not Path(self.plugin_data_dir / f"{sender_id}.ics").is_file():
                yield event.plain_result("你还没有绑定课表哦，先绑定课表吧。")
                return

            try:
                message = await self.get_schedule(event, schedule_date)
                if not message:
                    yield event.plain_result("你今天没有课哦~")
                    return
                yield event.plain_result(
                    "今日课程:\n" + "".join(message) + f"日期: {schedule_date}"
                )
            except Exception as e:
                logger.exception(f"查看今日课表信息出错: {e}")
                yield event.plain_result("查看今日课表信息出错。")

        except Exception as e:
            logger.error(f"{e}")

    @filter.command("明日课表")
    async def command_tomorrow_schedule(self, event: AstrMessageEvent):
        """查看明日课表"""
        try:
            sender_id = event.get_sender_id()
            now = datetime.now(SHANGHAI_TZ) + timedelta(days=1)
            schedule_date = now.date()
            if not Path(self.plugin_data_dir / f"{sender_id}.ics").is_file():
                yield event.plain_result("你还没有绑定课表哦，先绑定课表吧。")
                return

            try:
                message = await self.get_schedule(event, schedule_date)
                if not message:
                    yield event.plain_result("你明天没有课哦~")
                    return
                yield event.plain_result(
                    "明日课程\n" + "".join(message) + f"日期: {schedule_date}"
                )
            except Exception as e:
                logger.exception(f"查看明日课表信息出错: {e}")
                yield event.plain_result("查看明日课表信息出错。")

        except Exception as e:
            logger.error(f"{e}")

    async def get_schedule(self, event: AstrMessageEvent, target_date: date):
        sender_id = event.get_sender_id()
        with open(
            self.plugin_data_dir / f"{sender_id}.ics", "r", encoding="utf-8"
        ) as ics_file:
            sch_cal = Calendar.from_ical(ics_file.read())
            notifications = []
            for component in sch_cal.walk():
                if component.name == "VEVENT":
                    dtstart = component.get("DTSTART").dt
                    coures_date = dtstart.date()
                    if coures_date > target_date:
                        break
                    if not coures_date == target_date:
                        continue
                    dtend = component.get("DTEND").dt
                    summary = component.get("SUMMARY")
                    location = component.get("LOCATION")
                    tstart = format(dtstart, "%H:%M")
                    tend = format(dtend, "%H:%M")

                    notifications.append(f"{summary}-{location}\n{tstart}-{tend}\n")
            return notifications

    async def terminate(self):
        """插件被卸载/停用"""
        logger.info("课表插件已卸载。")
