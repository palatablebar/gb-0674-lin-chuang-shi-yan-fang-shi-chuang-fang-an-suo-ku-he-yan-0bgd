"""业务日裁决：研究时区采用日为唯一日历口径，复检按真实时差。"""
from app.engine import evaluate
from app.calendar import adopted_date, visit_day, elapsed_hours, time_basis
from app.modules.windows.rules import calculate
from app.modules.protocol.rules import choose_protocol
from app.coerce import instant

import pytest


@pytest.fixture
def overseas():
    return evaluate({'dataset': 'overseas'})


def test_single_calendar_module_is_source():
    # 同一真实时刻的两种写法，采用日必须完全一致（TRAP：UTC日历归一）
    assert adopted_date('2026-10-07T16:00:00Z') == adopted_date('2026-10-08T00:00:00+08:00') == '2026-10-08'
    assert visit_day('2026-10-08T00:00:00+08:00', '2026-10-01T00:00:00+08:00') == 7


def test_negative_offset_midnight_shift_uses_adopted_day(overseas):
    # OS02-V2：中心当地日 10-17（窗内），研究时区采用日 10-18（恰在半开窗外）→ 必须判 LATE
    row = next(w for w in overseas['windows'] if w['id'] == 'OS02-V2')
    assert row['local_date'] == '2026-10-17' and row['adopted_date'] == '2026-10-18'
    assert row['day'] == 17 and row['code'] == 'LATE'
    # 若错用当地日，访视日=16 会落进 [12,17)，证明两套日历会给出相反结论
    assert row['local_date'] != row['adopted_date']


def test_positive_offset_naive_local_day_would_be_early(overseas):
    # OS03-V1：当地日 10-05（当地日差4，窗外提前），采用日 10-06（日差5，窗内）→ 采用日口径 IN_WINDOW
    row = next(w for w in overseas['windows'] if w['id'] == 'OS03-V1')
    assert row['local_date'] == '2026-10-05' and row['adopted_date'] == '2026-10-06'
    assert row['day'] == 5 and row['code'] == 'IN_WINDOW'


def test_protocol_switch_uses_adopted_instant_not_local_day(overseas):
    # 00001 于研究时区 10-10 00:00 切 v2。OS01-V1 当地 10-10 23:30(+09)，同一研究日，必须选 v2
    rec = next(r for r in overseas['records'] if r['id'] == 'OS01-V1')
    assert rec['selected_protocol'] == 'v2'
    # 边界：研究时区 10-09 23:59 仍是 v1，10-10 00:00 起为 v2
    assert choose_protocol('00001', '2026-10-09T23:59:59+08:00', overseas['context']) == 'v1'
    assert choose_protocol('00001', '2026-10-10T00:00:00+08:00', overseas['context']) == 'v2'


def test_deviation_and_locking_share_adopted_day(overseas):
    # 偏离与锁库读的是同一批 windows（采用日口径），当地日不产生第二条结论
    dev = {(d['subject'], d['visit']): d['code'] for d in overseas['deviations']}
    assert dev[('00002', 'V2')] == 'WINDOW_LATE'
    assert overseas['balance']['status'] == '待处理'
    assert overseas['balance']['blocked'] == len(overseas['deviations']) + len(overseas['retest_issues'])


def test_retest_judged_by_true_elapsed_time_even_when_local_days_gap_three(overseas):
    # OS03-V1-Z：当地日相差3天，但真实时差 70.5h ≤ 72 → 复检有效并被采用
    sel = next(r for r in overseas['selected_results'] if r['primary_id'] == 'OS03-V1')
    assert sel['id'] == 'OS03-V1-Z' and sel['code'] == 'RETEST_SELECTED'
    assert elapsed_hours('2026-10-08T23:30:00Z', '2026-10-05T20:00:00-05:00') == 70.5


def test_retest_beyond_true_hours_blocked_despite_any_calendar(overseas):
    # OS04-R1 83h、OS05-R1 93h 均超 72h 真实时差 → 阻断，采用日/当地日都不能解救
    blocked = {i['id']: i for i in overseas['retest_issues']}
    assert blocked['OS04-R1']['code'] == 'RETEST_WINDOW' and blocked['OS04-R1']['elapsed_hours'] == 83.0
    assert blocked['OS05-R1']['code'] == 'RETEST_WINDOW' and blocked['OS05-R1']['elapsed_hours'] == 93.0
    assert blocked['OS04-R1']['basis'] == 'UTC真实时刻'


def test_raw_instant_and_timezone_basis_never_lost(overseas):
    rec = next(r for r in overseas['records'] if r['id'] == 'OS02-V2')
    assert rec['at_raw'] == '2026-10-17T20:00:00-05:00'
    assert rec['local_offset'] == '-5' and rec['local_date'] == '2026-10-17'
    assert rec['adopted_date'] == '2026-10-18'
    assert rec['at_utc'] == instant('2026-10-17T20:00:00-05:00').isoformat()
    # 证据四件套齐备且可复核
    assert set(time_basis('2026-10-17T20:00:00-05:00')) == {'at_raw', 'at_utc', 'local_offset', 'local_date', 'adopted_date'}


def test_naive_local_vs_adopted_opposite_verdicts_document_split():
    # 显式对账：同一记录在两套日历下结论相反，证明混用会让同一访视一边窗内一边窗外
    from datetime import datetime
    ctx = evaluate({'dataset': 'overseas'})['context']
    at_raw, enr_raw = '2026-10-17T20:00:00-05:00', '2026-10-01T00:00:00+08:00'
    base = {'id': 'X', 'subject': '00002', 'visit': 'V2', 'kind': 'PRIMARY', '_line': 1,
            'at': at_raw, 'enrolled': enr_raw, 'selected_protocol': 'v1'}
    out = calculate(base, ctx)
    assert out['code'] == 'LATE'  # 采用日口径（正式结论）
    # 朴素“中心当地日”口径（被禁止，仅留作对照）：取记录自带偏移的墙钟日
    naive_day = (datetime.fromisoformat(at_raw).date() - datetime.fromisoformat(enr_raw).date()).days
    assert naive_day == 16  # 当地日差16，本会判 [12,17) 窗内，与正式结论相反


def test_rerun_same_input_keeps_official_conclusion(tmp_path):
    from app import store
    from app.config import ROOT
    p = str(tmp_path / 'det.sqlite')
    first = store.save(p, evaluate({'dataset': 'overseas'}))
    rid = first['manifest']['run_id']
    # 同批不可变快照重跑：批号、正式结论完全不变
    again = store.save(p, evaluate({'dataset': 'overseas'}, snapshot=first['input_snapshot']))
    assert again['manifest']['run_id'] == rid
    assert again['manifest']['sha256'] == first['manifest']['sha256']
    assert [(w['id'], w['code']) for w in again['windows']] == [(w['id'], w['code']) for w in first['windows']]


def test_source_update_invalidates_old_conclusion_with_new_run_id():
    from app.config import ROOT
    old = evaluate({'dataset': 'overseas'})
    raw = (ROOT / 'sample_data' / 'overseas.csv').read_text()
    # 源数据更新（改一个时刻）→ 摘要变化 → 新批号，旧批结论不再代表新源
    updated = raw.replace('2026-10-17T20:00:00-05:00', '2026-10-17T10:00:00-05:00')
    new = evaluate({'csv_text': updated})
    assert new['manifest']['run_id'] != old['manifest']['run_id']
    changed = next(w for w in new['windows'] if w['id'] == 'OS02-V2')
    assert changed['code'] == 'IN_WINDOW'  # 10-18 00:00 前移到 10-17 18:00 → 采用日17、日差16、窗内


def test_manifest_declares_calendar_basis(overseas):
    assert overseas['manifest']['timezone'] == 'Asia/Shanghai'
    assert overseas['calendar_basis']['adopted_timezone'] == 'Asia/Shanghai'
    assert 'UTC' in overseas['calendar_basis']['retest']
