"""业务日唯一裁决口径。

裁决：跨中心的一切日历结论（方案切换、访视窗、偏离、锁库）只承认研究时区
Asia/Shanghai 的日历日，称为“采用日”(adopted day)。海外中心原始时刻里的当地
墙钟日仅作证据，保留在 at_raw/local_date/local_offset，不参与任何业务判断。
复检 72 小时是真实时长，按 UTC 即时刻差值计算（elapsed_hours），与采用日无关。
本模块是该口径的唯一来源，禁止其他模块自行做时区换算或本地日推断。
"""
from datetime import datetime, timezone, timedelta

STUDY_TZ_NAME = 'Asia/Shanghai'
STUDY_TZ = timezone(timedelta(hours=8))


def parse_instant(value):
    """解析带偏移的时刻并归一到 UTC；无偏移拒绝，避免隐式假定时区。"""
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        from app.errors import BusinessError
        raise BusinessError('BAD_TIME', '时间缺少有效偏移')


def local_offset_hours(value):
    """原始时刻自带的偏移（小时），仅用于证据展示。"""
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return dt.utcoffset().total_seconds() / 3600


def local_date(value):
    """原始偏移下的当地日历日（ISO 字符串）。仅证据，不参与业务结论。"""
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return dt.date().isoformat()


def adopted_date(value):
    """研究时区日历日——本工具唯一承认的业务日（ISO 字符串）。"""
    return parse_instant(value).astimezone(STUDY_TZ).date().isoformat()


def study_dt(value):
    """研究时区下的带时刻日期时间，用于与生效窗边界做同一口径比较。"""
    return parse_instant(value).astimezone(STUDY_TZ)


def visit_day(at_value, enrolled_value):
    """采用日之间的整数日差 = 访视日。入组基准同样取研究时区日历日。"""
    d0 = study_dt(enrolled_value).date()
    d1 = study_dt(at_value).date()
    return (d1 - d0).days


def elapsed_hours(later_value, earlier_value):
    """两个真实时刻之间的小时数（复检时限专用，不做任何日历取整）。"""
    return (parse_instant(later_value) - parse_instant(earlier_value)).total_seconds() / 3600


def time_basis(value):
    """一次性产出一条记录的完整时间证据，保证原始时刻与时区依据不丢失。"""
    return {
        'at_raw': str(value),
        'at_utc': parse_instant(value).isoformat(),
        'local_offset': f'{local_offset_hours(value):+g}',
        'local_date': local_date(value),
        'adopted_date': adopted_date(value),
    }
