from importlib import import_module
from pathlib import Path
from copy import deepcopy
import json, time, base64
from app.config import ROOT, MODULES, MAX_BYTES
from app.errors import BusinessError
from app.manifest import digest, make_manifest

def evaluate(payload=None, until=7, snapshot=None):
    payload=payload or {}
    dataset=payload.get('dataset','dirty')
    if dataset not in {'dirty','clean','legacy','overseas'}: raise BusinessError('BAD_DATASET','样例名称无效')
    if not isinstance(payload.get('overrides',{}),dict): raise BusinessError('BAD_CONTEXT','参数须为对象')
    raw=(base64.b64decode(snapshot['bytes_b64'],validate=True) if snapshot is not None else (str(payload['csv_text']).encode() if 'csv_text' in payload else (ROOT/'sample_data'/f'{dataset}.csv').read_bytes()))
    if len(raw)>MAX_BYTES: raise BusinessError('TOO_LARGE','文件超过2MB',413)
    context=deepcopy(snapshot['context']) if snapshot is not None else json.loads((ROOT/'sample_data/context.json').read_text())
    context.update(deepcopy(payload.get('overrides',{})))
    start=time.perf_counter()
    from app.calendar import STUDY_TZ_NAME
    state={'raw_bytes':raw,'context':context,'records':[],'quarantine':[], 'counts':{},'views':{},'source':dataset,
           'calendar_basis':{'adopted_timezone':STUDY_TZ_NAME,
                             'ruling':'业务日一律取研究时区日历日（采用日）；中心当地日仅留证，不入方案切换、访视窗、偏离与锁库',
                             'retest':'复检时限按UTC真实时差判断，与采用日无关',
                             'evidence':'原始时刻at_raw、当地偏移local_offset、当地日local_date、UTC时刻at_utc全程保留'}}
    for index,key in enumerate(MODULES,1):
        if index>until: break
        import_module(f'app.modules.{key}.rules').apply(state)
    state['input_snapshot']={'bytes_b64':base64.b64encode(raw).decode(),'context':deepcopy(context)}
    state.pop('raw_bytes',None)
    state['manifest']=make_manifest(digest(raw,context),dataset,time.perf_counter()-start)
    return state
