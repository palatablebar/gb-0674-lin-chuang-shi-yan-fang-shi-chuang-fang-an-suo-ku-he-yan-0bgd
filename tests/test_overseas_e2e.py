"""海外跨午夜批的端到端：API 幂等、重跑稳定、页面可读、证据入档。"""
from fastapi.testclient import TestClient
from app import main
import io, json, zipfile


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', str(tmp_path / 'overseas.sqlite'))
    return TestClient(main.app)


def test_overseas_run_idempotent_and_rerun_stable(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    a = c.post('/api/runs', json={'dataset': 'overseas'}).json()
    b = c.post('/api/runs', json={'dataset': 'overseas'}).json()
    assert a['manifest']['run_id'] == b['manifest']['run_id']
    rid = a['manifest']['run_id']
    rerun = c.post(f'/api/runs/{rid}/rerun', json={})
    assert rerun.status_code == 200
    assert rerun.json()['manifest']['run_id'] == rid
    assert rerun.json()['manifest']['sha256'] == a['manifest']['sha256']


def test_overseas_pages_show_adopted_day_window_and_blocking_reason(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    rid = c.post('/api/runs', json={'dataset': 'overseas'}).json()['manifest']['run_id']
    for key in main.MODULES:
        html = c.get(f'/{key}?run_id={rid}').text
        assert '业务日裁决' in html                       # 裁决横幅
        assert 'Asia/Shanghai' in html
        assert '采用日（研究时区）' in html or key == 'intake'
    windows = c.get(f'/windows?run_id={rid}').text
    assert '2026-10-18' in windows                          # OS02-V2 采用日
    assert '延后（采用日已到/过窗末）' in windows           # 阻断原因中文化
    assert '中心当地日（仅证据）' in windows
    retest = c.get(f'/retest?run_id={rid}').text
    assert 'UTC真实时刻' in retest and '真实时差(小时)' in retest


def test_overseas_export_keeps_raw_time_evidence(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    rid = c.post('/api/runs', json={'dataset': 'overseas'}).json()['manifest']['run_id']
    z = zipfile.ZipFile(io.BytesIO(c.get(f'/api/export/{rid}').content))
    evidence = json.loads(z.read('evidence.json'))
    flat = json.dumps(evidence, ensure_ascii=False)
    assert '2026-10-17T20:00:00-05:00' in flat             # 原始时刻+偏移
    assert 'adopted_date' in flat and 'local_date' in flat
    manifest = json.loads(z.read('manifest.json'))
    assert manifest['timezone'] == 'Asia/Shanghai'
    assert 'calendar_basis' in manifest


def test_source_change_creates_distinct_run_and_conclusion(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    old = c.post('/api/runs', json={'dataset': 'overseas'}).json()
    from app.config import ROOT
    raw = (ROOT / 'sample_data' / 'overseas.csv').read_text()
    new = c.post('/api/runs', json={'csv_text': raw.replace('2026-10-17T20:00:00-05:00', '2026-10-17T10:00:00-05:00')}).json()
    assert new['manifest']['run_id'] != old['manifest']['run_id']
    # 两条批次都保留，互不覆盖；历史里各自可查
    ids = {r['id'] for r in c.get('/api/runs').json()}
    assert {old['manifest']['run_id'], new['manifest']['run_id']} <= ids
