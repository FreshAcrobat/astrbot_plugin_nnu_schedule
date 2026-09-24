import httpx
from astrbot.api import logger
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
from astrbot.core.astr_agent_context import AstrAgentContext
from pydantic import Field
from pydantic.dataclasses import dataclass

from .config import (
    BEIDA,
    BUILDING_URL,
    DIANJIAO,
    GUANGLE,
    XINXI,
    XUEHAI,
    XUEMING,
    XUESI,
    XUEXING,
    XUEZHENG,
)


@dataclass
class NNUClassroomTool(FunctionTool[AstrAgentContext]):
    name: str = "get_nnu_classroom_status"  # 工具名称
    description: str = (
        "根据教学楼名称，返回具体教室的空闲/占用情况，也可以用来查看课表"  # 工具描述
    )
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "building_name": {
                    "type": "string",
                    "description": "教学楼的名称，可选：学行楼/学正楼/学明楼/学思楼/学海楼/广乐楼/电教楼/北大楼/信息楼",
                },
            },
            "required": ["building_name"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> ToolExecResult:
        building_name = kwargs.get("building_name", "")
        building_url = match_building(building_name)
        if not building_url:
            return "输入的教学楼名称有误"
        classinfo = await fetch_classroom(building_url)
        if not classinfo:
            return "获取教学楼信息出错了"
        if not classinfo.get("msg") == "Success":
            return "获取教学楼信息出错了"

        lines = [f"教学楼: {building_name}"]
        course_time = (
            "课程节数时间说明: \n"
            "1节: 8:00-8:40 \n"
            "2节: 8:45-9:25 \n"
            "3节: 9:40-10:20 \n"
            "4节: 10:35-11:15 \n"
            "5节: 11:20-12:00 \n"
            "6节: 13:30-14:10 \n"
            "7节: 14:15-14:55 \n"
            "8节: 15:10-15:50 \n"
            "9节: 15:55-16:35 \n"
            "10节: 18:30-19:10 \n"
            "11节: 19:20-20:00 \n"
            "12节: 20:10-20:50 \n"
        )
        lines.append(course_time)

        for room in classinfo.get("data", []):
            occupied_lessons = []
            seen = set()

            for lesson in room.get("lessonList", []):
                if lesson.get("status") == 0:
                    continue

                key = (
                    lesson.get("activityName"),
                    lesson.get("lessonName"),
                    lesson.get("startTime"),
                    lesson.get("endTime"),
                )

                if key in seen:
                    continue
                seen.add(key)

                occupied_lessons.append(
                    {
                        "activityName": lesson.get("activityName"),
                        "lessonName": lesson.get("lessonName"),
                        "startTime": lesson.get("startTime"),
                        "endTime": lesson.get("endTime"),
                    }
                )

            room_name = room.get("roomName")
            lines.append(f"教室 {room_name}: ")

            if not occupied_lessons:
                lines.append("  - 无占用")
            else:
                for lesson in occupied_lessons:
                    activity = lesson["activityName"] or "未知活动"
                    lessonName = lesson["lessonName"] or "未知"
                    start = lesson["startTime"] or "?"
                    end = lesson["endTime"] or "?"
                    lines.append(f"  - {activity} {lessonName} {start}-{end}")
            lines.append("")

        return "\n".join(lines)


async def fetch_classroom(target_building_url: str):
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(f"{BUILDING_URL}{target_building_url}")
            resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"获取教学楼信息出错: {e}")
    return None


def match_building(name: str):
    match name:
        case "学行楼":
            return XUEXING
        case "学正楼":
            return XUEZHENG
        case "学明楼":
            return XUEMING
        case "学思楼":
            return XUESI
        case "学海楼":
            return XUEHAI
        case "广乐楼":
            return GUANGLE
        case "电教楼":
            return DIANJIAO
        case "北大楼":
            return BEIDA
        case "信息楼":
            return XINXI
        case _:
            return None
