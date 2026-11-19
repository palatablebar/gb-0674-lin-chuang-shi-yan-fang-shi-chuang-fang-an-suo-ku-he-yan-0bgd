from app.calendar import parse_instant, study_dt, visit_day, time_basis, STUDY_TZ
from app.coerce import number
from app.errors import BusinessError
from app.reasons import reject
def choose_protocol(subject,at,context):
    # 生效窗边界均按研究时区墙钟时刻解释，与“采用日”同一口径；
    # 对整日边界而言等价于按研究时区日历日比较，绝不使用中心当地日。
    at_study=study_dt(at)
    matches=[a for a in context['assignments'].get(subject,[]) if study_dt(a['start'])<=at_study<study_dt(a['end'])]
    if len(matches)!=1:raise BusinessError('PROTOCOL_CONFLICT','受试者方案未定或生效窗重叠')
    chosen=matches[0]['version']
    if chosen not in context['plans']:raise BusinessError('UNKNOWN_PROTOCOL','方案不存在')
    return chosen

def normalize(row,context):
    at,enrolled=parse_instant(row['at']),parse_instant(row['enrolled']);revision=number(row['revision'])
    if row['subject'] not in context['subjects']:raise BusinessError('UNKNOWN_SUBJECT','受试者未入组')
    if enrolled!=parse_instant(context['subjects'][row['subject']]):raise BusinessError('ENROLLMENT_CONFLICT','入组基准不一致')
    if at<enrolled or revision<1 or revision%1:raise BusinessError('INVALID_RANGE','访视日期或版本越界')
    if row['kind'] not in {'PRIMARY','RETEST'}:raise BusinessError('BAD_KIND','记录类型无效')
    chosen=choose_protocol(row['subject'],row['at'],context)
    if row['protocol'] not in {'auto',chosen}:raise BusinessError('PROTOCOL_MISMATCH','记录方案与受试者有效版不符')
    if row['visit'] not in context['plans'][chosen]:raise BusinessError('UNKNOWN_VISIT','访视编号不存在')
    value=number(row['value']);factor=context['units'].get(row['unit'])
    if factor is None:raise BusinessError('BAD_UNIT','检验单位无法换算')
    if value<0:raise BusinessError('INVALID_RANGE','检验值小于零')
    return {**row,
            **time_basis(row['at']),
            'at':at.isoformat(),
            'enrolled':enrolled.isoformat(),
            'enrolled_adopted':enrolled.astimezone(STUDY_TZ).date().isoformat(),
            'visit_day':visit_day(row['at'],row['enrolled']),
            'revision':int(revision),
            'selected_protocol':chosen,
            'value_mg_dl':str(value*number(factor))}

def apply(state):
    good=[]
    for row in state['records']:
        try:good.append(normalize(row,state['context']))
        except BusinessError as e:reject(state,row,e.code,e.message)
    state['records']=good
    state['views']['protocol']={'title':'受试者方案','rows':[{'id':r['id'],'subject':r['subject'],'visit':r['visit'],'kind':r['kind'],'selected_protocol':r['selected_protocol'],'at_raw':r['at_raw'],'local_date':r['local_date'],'local_offset':r['local_offset'],'adopted_date':r['adopted_date']} for r in good],'metrics':{'有效记录':len(good),'方案版本':len(state['context']['plans'])}}
