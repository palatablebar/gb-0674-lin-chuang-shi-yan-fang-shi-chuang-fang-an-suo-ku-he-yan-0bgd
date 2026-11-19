from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.config import ROOT, META
from app.engine import evaluate
from app import store

templates=Jinja2Templates(directory=str(ROOT/'app/templates'))

CODE_LABELS={
 'IN_WINDOW':'窗内','EARLY':'提前（采用日早于窗始）','LATE':'延后（采用日已到/过窗末）',
 'WINDOW_EARLY':'窗外-提前','WINDOW_LATE':'窗外-延后',
 'MISSING_PRIMARY':'缺首次访视','DUPLICATE_PRIMARY':'首次访视重复',
 'RETEST_REFERENCE':'复检引用无效','RETEST_WINDOW':'复检超真实时差或版本未升','RETEST_VERSION_CONFLICT':'同版本复检冲突',
 'RETEST_SELECTED':'采用复检值','PRIMARY_SELECTED':'采用首次值',
 'COLUMN_COUNT':'列数错误','MISSING_ID':'编号缺失','DUPLICATE_CONFLICT':'重复编号冲突',
 'MISSING_VALUE':'数值缺失','BAD_NUMBER':'数值格式错误','BAD_TIME':'时间格式错误',
 'BAD_UNIT':'单位不受支持','INVALID_RANGE':'范围错误','PROTOCOL_CONFLICT':'方案生效窗冲突',
 'UNKNOWN_PROTOCOL':'方案不存在','UNKNOWN_SUBJECT':'受试者未入组','ENROLLMENT_CONFLICT':'入组基准不一致',
 'BAD_KIND':'记录类型无效','PROTOCOL_MISMATCH':'申报方案与有效版不符','UNKNOWN_VISIT':'访视编号不存在',
}
templates.env.filters['code_label']=lambda code:CODE_LABELS.get(code,code)

def render(request:Request,key):
    from app.main import DB_PATH
    run_id=request.query_params.get('run_id')
    if run_id:
        state=store.get(DB_PATH,run_id)
    else:
        state=store.save(DB_PATH,evaluate({'dataset':request.query_params.get('dataset','dirty')}))
    return templates.TemplateResponse(request=request,name=f'{key}.html',context={'meta':META,'key':key,'state':state,'view':state['views'][key]})
