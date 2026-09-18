from pathlib import Path
from datetime import datetime, timezone, timedelta, date
from icalendar import Calendar
import json

from astrbot.core.utils.session_waiter import (
    session_waiter,
    SessionController,
)
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger

from .core.ics_parser import ics_generator, fetch_ics

SHANGHAI_TZ = timezone(timedelta(hours=8))
CONFIG_FILE = Path(__file__).parent / "config.json"

if not CONFIG_FILE.is_file():
    logger.error(
        "配置文件 %s 不存在",
        CONFIG_FILE,
    )
    raise ValueError("配置文件缺失，请确保 config.json 存在于插件目录下")
else:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
        BASE_URL = config.get("BASE_URL", "")


@register(
    "astrbot_plugin_nnu_schedule",
    "FreshAcrobat",
    "用于查询南师大课程表的 AstrBot 插件",
    "v0.1.0",
)
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_data_dir = StarTools.get_data_dir(self.name)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

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

            @session_waiter(timeout=60, record_history_chains=False)
            async def bind_waiter(
                controller: SessionController, event: AstrMessageEvent
            ):
                reference_address = event.message_str

                if BASE_URL not in reference_address:
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
                await bind_waiter(event)
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
                yield event.plain_result("明日课程\n" + "".join(message))
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
