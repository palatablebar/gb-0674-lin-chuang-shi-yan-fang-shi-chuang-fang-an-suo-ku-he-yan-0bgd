from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import unicodedata, re
from app.config import SENTINELS
from app.errors import BusinessError

def number(value, unit=''):
    text = unicodedata.normalize('NFKC', str(value)).strip()
    if text.upper() in SENTINELS or text in SENTINELS:
        raise BusinessError('MISSING_VALUE', '数值缺失')
    if unit and text.endswith(unit):
        text = text[:-len(unit)].strip()
    if ',' in text:
        if not re.fullmatch(r'[+-]?\d{1,3}(,\d{3})+(\.\d+)?', text):
            raise BusinessError('BAD_NUMBER', '千分位格式错误')
        text = text.replace(',', '')
    try:
        val = Decimal(text)
        if not val.is_finite(): raise InvalidOperation
        return val
    except InvalidOperation:
        raise BusinessError('BAD_NUMBER', '数值格式错误')

def money(value):
    return format(Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), 'f')

def instant(value):
    # 时刻解析统一收口到 app.calendar，避免出现第二套时区口径。
    from app.calendar import parse_instant
    return parse_instant(value)

def decstr(value):
    return format(value, 'f') if isinstance(value, Decimal) else value
