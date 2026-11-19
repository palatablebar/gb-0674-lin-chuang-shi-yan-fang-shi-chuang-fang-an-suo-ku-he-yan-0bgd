from app.calendar import visit_day

def calculate(row,context):
    # 唯一业务日 = 研究时区采用日；中心当地日只展示、不入算。
    # 始终由真实时刻重算，不依赖上游缓存，防止 at 被改写后沿用旧访视日。
    day=visit_day(row['at'],row['enrolled'])
    start,end=context['plans'][row['selected_protocol']][row['visit']]
    code='IN_WINDOW' if start<=day<end else ('EARLY' if day<start else 'LATE')
    return {'id':row['id'],'subject':row['subject'],'visit':row['visit'],'kind':row['kind'],
            'day':day,'start_day':start,'end_day':end,'window':f'[{start},{end})',
            'selected_protocol':row['selected_protocol'],'code':code,'line':row['_line'],
            'at_raw':row.get('at_raw',row['at']),
            'local_date':row.get('local_date',''),'local_offset':row.get('local_offset',''),
            'adopted_date':row.get('adopted_date','')}

def apply(state):
    state['windows']=[calculate(r,state['context']) for r in state['records']]
    primary=[r for r in state['windows'] if r['kind']=='PRIMARY']
    state['views']['windows']={'title':'访视窗口','rows':state['windows'],'metrics':{'首次访视':len(primary),'窗内':sum(r['code']=='IN_WINDOW' for r in primary),'窗外':sum(r['code']!='IN_WINDOW' for r in primary)}}
