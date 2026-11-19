from app.calendar import elapsed_hours
from collections import defaultdict

def adjudicate(rows,context):
    by_id={r['id']:r for r in rows};children=defaultdict(list);issues=[];selected=[]
    limit=context['retest_hours']
    for row in rows:
        if row['kind']!='RETEST':continue
        parent=by_id.get(row['parent'])
        if parent is None or parent['kind']!='PRIMARY' or any(parent[k]!=row[k] for k in ('subject','visit')):
            issues.append({'id':row['id'],'code':'RETEST_REFERENCE','parent':row['parent'],'basis':'UTC真实时刻','elapsed_hours':''});continue
        # 复检时限按真实时差（UTC 即时刻差）判断，不采用研究时区日历日取整。
        hours=elapsed_hours(row['at'],parent['at'])
        if not 0<hours<=limit or row['revision']<=parent['revision']:
            issues.append({'id':row['id'],'code':'RETEST_WINDOW','parent':row['parent'],'basis':'UTC真实时刻','elapsed_hours':round(hours,2),'limit_hours':limit});continue
        children[parent['id']].append(row)
    for row in rows:
        if row['kind']!='PRIMARY':continue
        candidates=children[row['id']]
        if candidates:
            max_revision=max(r['revision'] for r in candidates);winners=[r for r in candidates if r['revision']==max_revision]
            if len(winners)>1:issues.append({'id':row['id'],'code':'RETEST_VERSION_CONFLICT','parent':row['id'],'basis':'UTC真实时刻','elapsed_hours':''});winner=row
            else:winner=winners[0]
        else:winner=row
        selected.append({'id':winner['id'],'subject':row['subject'],'visit':row['visit'],'primary_id':row['id'],'value_mg_dl':winner['value_mg_dl'],'revision':winner['revision'],'code':'RETEST_SELECTED' if winner is not row else 'PRIMARY_SELECTED'})
    return selected,issues

def apply(state):
    selected,issues=adjudicate(state['records'],state['context']);state.update(selected_results=selected,retest_issues=issues)
    state['retest_basis']={'rule':'真实时差判断（UTC即时刻差），不看采用日','retest_hours':state['context']['retest_hours']}
    # 视图列对齐：所有行带相同键，确保“真实时差/时限口径”列在页面稳定出现
    rows=[{**{'basis':'','elapsed_hours':'','limit_hours':''},**r} for r in selected]+issues
    state['views']['retest']={'title':'复检裁决','rows':rows,'metrics':{'有效结果':len(selected),'采用复检':sum(r['code']=='RETEST_SELECTED' for r in selected),'复检问题':len(issues)}}
