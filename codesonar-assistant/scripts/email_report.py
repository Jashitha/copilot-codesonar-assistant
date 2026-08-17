#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import mimetypes
import shutil
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote_plus

from dashboard import generate_dashboard, load_tracker
from env_bootstrap import ensure_env_file

SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = TASK_DIR / 'output'
EMAIL_DIR = OUTPUT_DIR / 'email'
ENV_FILE = ensure_env_file(TASK_DIR)


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env(name: str, env: dict[str, str], default: str = '') -> str:
    return os.environ.get(name) or env.get(name) or default


def _bool(name: str, env: dict[str, str], default: bool = False) -> bool:
    return _env(name, env, '1' if default else '0').strip().lower() in {'1', 'true', 'yes', 'on'}


def _split_recipients(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r'[;,\n]+', raw or '') if item.strip()]


def _list(name: str, env: dict[str, str]) -> list[str]:
    return _split_recipients(_env(name, env, ''))


def _json_map(name: str, env: dict[str, str]) -> dict[str, str]:
    raw = _env(name, env, '')
    if not raw.strip():
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be a JSON object.')
    return {str(key).strip(): str(val).strip() for key, val in value.items() if str(key).strip() and str(val).strip()}


def _slug(value: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_-]+', '_', value.strip())
    return value.strip('_') or 'owner'


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ''), quote=True)


def _format_analysis_stamp(value: str | None) -> str:
    raw = str(value or '').strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%d %b %Y, %H:%M'):
        try:
            return datetime.strptime(raw, fmt).strftime('%d %b %Y, %H:%M')
        except ValueError:
            continue
    return raw or datetime.now().strftime('%d %b %Y, %H:%M')


def _load_dashboard_data(task_dir: Path) -> dict:
    result = generate_dashboard(task_dir)
    if result.get('status') != 'ok':
        raise RuntimeError(result.get('message', 'Dashboard generation failed'))
    dashboard_path = task_dir / 'output' / 'dashboard' / 'dashboard_data.json'
    if not dashboard_path.exists():
        raise RuntimeError(f'Dashboard data not found at {dashboard_path}')
    return json.loads(dashboard_path.read_text(encoding='utf-8'))


def _current_metrics(data: dict) -> dict:
    summary = data.get('summary') or {}
    owner_validation = data.get('owner_validation') or {}
    return {
        'total_findings': int(summary.get('total_issues', 0) or 0),
        'hb_prio_1': int(summary.get('hb_prio_1', 0) or 0),
        'hb_prio_2': int(summary.get('hb_prio_2', 0) or 0),
        'new_findings': int(summary.get('new_issues', 0) or 0),
        'resolved_findings': int(summary.get('resolved_issues', 0) or 0),
        'pending_findings': int(summary.get('pending', 0) or 0),
        'completion_pct': float(summary.get('completion_pct', 0) or 0),
        'unassigned_findings': int(owner_validation.get('unassigned_total', 0) or 0),
    }


def _snapshot_metrics(snapshot_path: Path) -> dict:
    df = load_tracker(snapshot_path)
    return {
        'total_findings': len(df),
        'hb_prio_1': int((df['priority'] == 'HB_PRIO_1').sum()) if 'priority' in df.columns else 0,
        'hb_prio_2': int((df['priority'] == 'HB_PRIO_2').sum()) if 'priority' in df.columns else 0,
        'pending_findings': int((df['Status'].str.lower() == 'pending').sum()) if 'Status' in df.columns else 0,
        'resolved_findings': int((df['Status'].str.lower() == 'done').sum()) if 'Status' in df.columns else 0,
        'unassigned_findings': int((df['Owner'].astype(str).str.strip() == 'Unassigned').sum()) if 'Owner' in df.columns else 0,
    }


def _previous_snapshot(task_dir: Path) -> Path | None:
    snaps = [p for p in (task_dir / 'output').glob('Master_Tracker_*.xlsx') if p.name != 'Master_Tracker.xlsx']
    snaps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return snaps[1] if len(snaps) > 1 else None


def _trend_rows(current: dict, previous: dict | None) -> list[dict]:
    if not previous:
        return []

    def build(label: str, key: str, invert: bool = False) -> dict:
        cur = int(current.get(key, 0) or 0)
        prev = int(previous.get(key, 0) or 0)
        delta = cur - prev
        if delta == 0:
            arrow = '→'
        elif (delta > 0 and not invert) or (delta < 0 and invert):
            arrow = '↑'
        else:
            arrow = '↓'
        return {'label': label, 'current': cur, 'previous': prev, 'delta': delta, 'arrow': arrow}

    return [
        build('Total Findings', 'total_findings'),
        build('HB_PRIO_1', 'hb_prio_1'),
        build('Resolved', 'resolved_findings'),
        build('Pending', 'pending_findings', invert=True),
        build('Unassigned', 'unassigned_findings', invert=True),
    ]


def _risk_label(hb1: int, hb2: int, total: int) -> str:
    if hb1 > 0:
        return 'High' if hb1 >= 3 or total >= 20 else 'Medium'
    if hb2 > 0:
        return 'Medium' if total >= 10 else 'Low'
    return 'Low'


def _top_hotspots(data: dict, owner: str | None = None, limit: int = 5) -> list[dict]:
    if owner:
        files: dict[str, dict] = {}
        for finding in data.get('findings', []) or []:
            if finding.get('owner') != owner:
                continue
            file_name = str(finding.get('file', '')).strip()
            if not file_name:
                continue
            row = files.setdefault(file_name, {'file': file_name, 'findings': 0, 'hb_prio_1': 0, 'hb_prio_2': 0})
            row['findings'] += 1
            if finding.get('priority') == 'HB_PRIO_1':
                row['hb_prio_1'] += 1
            elif finding.get('priority') == 'HB_PRIO_2':
                row['hb_prio_2'] += 1
        values = list(files.values())
        values.sort(key=lambda row: (-row['hb_prio_1'], -row['hb_prio_2'], -row['findings'], row['file']))
    else:
        values = []
        for row in data.get('hotspots', []) or []:
            values.append({
                'file': row.get('file', ''),
                'findings': int(row.get('count', row.get('findings', 0)) or 0),
                'hb_prio_1': int(row.get('hb_prio_1', 0) or 0),
                'hb_prio_2': int(row.get('hb_prio_2', 0) or 0),
            })
    result = []
    for row in values[:limit]:
        hb1 = int(row.get('hb_prio_1', 0) or 0)
        hb2 = int(row.get('hb_prio_2', 0) or 0)
        findings = int(row.get('findings', 0) or 0)
        result.append({'file': row.get('file', ''), 'findings': findings, 'hb_prio_1': hb1, 'hb_prio_2': hb2, 'risk': _risk_label(hb1, hb2, findings)})
    return result


def _top_action_findings(data: dict, owner: str | None = None, limit: int = 5) -> list[dict]:
    findings = [row for row in (data.get('findings', []) or []) if str(row.get('status', '')).lower() != 'done']
    if owner:
        findings = [row for row in findings if row.get('owner') == owner]
    findings.sort(key=lambda row: (0 if row.get('priority') == 'HB_PRIO_1' else 1, str(row.get('class', '')), str(row.get('id', ''))))
    return findings[:limit]


def _owner_rows(data: dict, owner: str | None = None) -> list[dict]:
    rows = data.get('owners', []) or []
    if owner:
        return [row for row in rows if row.get('name') == owner or row.get('owner') == owner]
    return rows


def _dashboard_url(env: dict[str, str], owner: str | None = None, link_base: str = '.') -> str | None:
    url = _env('EMAIL_DASHBOARD_URL', env, '').strip()
    if not url:
        prefix = '' if link_base in {'', '.'} else link_base.rstrip('/') + '/'
        url = f'{prefix}dashboard/index.html'
    if owner:
        separator = '&' if '?' in url else '?'
        return f'{url}{separator}owner={quote_plus(owner)}'
    return url


def _quick_links(env: dict[str, str], owner: str | None = None, link_base: str = '.') -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    dashboard_url = _dashboard_url(env, owner, link_base=link_base)
    if dashboard_url:
        links.append(('Interactive Dashboard', dashboard_url))
        if owner:
            links.append(('Owner-wise Details', dashboard_url))
    tracker_url = _env('EMAIL_MASTER_TRACKER_URL', env, '').strip()
    if tracker_url:
        links.append(('Master Tracker', tracker_url))
    hb1_url = _env('EMAIL_HB_PRIO_1_URL', env, '').strip()
    if hb1_url:
        links.append(('HB_PRIO_1 Findings', hb1_url))
    return links


def _normalize_token(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', value.lower())


def _owner_email_map(env: dict[str, str]) -> dict[str, str]:
    raw = _env('OWNER_EMAILS_JSON', env, '').strip()
    if not raw:
        return {}
    try:
        return _json_map('OWNER_EMAILS_JSON', env)
    except Exception:
        owners = _configured_owner_names(env)
        entries = [item.strip() for item in raw.split(',') if item.strip()]
        if not entries:
            return {}
        mapping: dict[str, str] = {}
        remaining = entries[:] 

        for owner in owners:
            owner_key = _normalize_token(owner)
            match_index = None
            for index, email in enumerate(remaining):
                email_key = _normalize_token(email)
                local_part = _normalize_token(email.split('@', 1)[0])
                if owner_key and (owner_key in email_key or owner_key in local_part):
                    match_index = index
                    break
            if match_index is not None:
                mapping[owner] = remaining.pop(match_index)

        unmatched_owners = [owner for owner in owners if owner not in mapping]
        for owner, email in zip(unmatched_owners, remaining):
            mapping[owner] = email

        if len(mapping) < len(owners):
            for owner in owners:
                if owner not in mapping:
                    mapping[owner] = ''
        return {owner: email for owner, email in mapping.items() if email}


def _configured_owner_names(env: dict[str, str]) -> list[str]:
    return _list('CODESONAR_OWNERS', env)


def _recipient_config(env: dict[str, str]) -> tuple[list[str], list[str], list[str], list[str]]:
    owners = _configured_owner_names(env)
    owner_map = _owner_email_map(env)
    team_email = _env('CODESONAR_TEAM_EMAIL', env, '').strip()

    issues: list[str] = []
    if not owners:
        issues.append('CODESONAR_OWNERS is not configured.')
    missing = [owner for owner in owners if owner not in owner_map]
    if missing:
        issues.append('Missing OWNER_EMAILS_JSON mappings for: ' + ', '.join(missing))

    to_recipients = [owner_map[owner] for owner in owners if owner in owner_map]
    cc_recipients = [team_email] if team_email else []

    invalid = [recipient for recipient in to_recipients + cc_recipients if '@' not in recipient or recipient.startswith('@') or recipient.endswith('@')]
    if invalid:
        issues.append('Invalid recipient address(es): ' + ', '.join(sorted(set(invalid))))

    return to_recipients, cc_recipients, [], issues


def _write_report_files(name: str, html_body: str, text_body: str) -> tuple[Path, Path]:
    EMAIL_DIR.mkdir(parents=True, exist_ok=True)
    html_path = EMAIL_DIR / f'{name}.html'
    txt_path = EMAIL_DIR / f'{name}.txt'
    html_path.write_text(html_body, encoding='utf-8')
    txt_path.write_text(text_body, encoding='utf-8')
    return html_path, txt_path


def _append_log(scope: str, mode: str, status: str, recipients: list[str], error: str = '') -> None:
    EMAIL_DIR.mkdir(parents=True, exist_ok=True)
    log_path = EMAIL_DIR / 'email_history.log'
    payload = {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'scope': scope,
        'mode': mode,
        'status': status,
        'recipients': recipients,
        'error': error,
    }
    with log_path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + '\n')


def _email_backend(env: dict[str, str]) -> str:
    backend = _env('EMAIL_BACKEND', env, 'smtp').strip().lower()
    return backend or 'smtp'


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = ''.join(f'<th>{_esc(col)}</th>' for col in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>' for row in rows)
    return '<table>' + '<tr>' + head + '</tr>' + body + '</table>'


def _render_report(data: dict, env: dict[str, str], owner: str | None = None, link_base: str = '.') -> tuple[str, str, str]:
    current = _current_metrics(data)
    prev_path = _previous_snapshot(TASK_DIR)
    previous = _snapshot_metrics(prev_path) if prev_path else None
    trend_rows = _trend_rows(current, previous)
    meta = data.get('meta') or {}
    status_code = (data.get('release_readiness') or {}).get('level', 'amber')
    status_label = {'green': 'GREEN', 'amber': 'AMBER', 'red': 'RED'}.get(status_code, 'AMBER')
    project_name = meta.get('project_name') or TASK_DIR.name
    branch = meta.get('branch') or 'n/a'
    analysis_date = meta.get('analysis_date') or datetime.now().strftime('%d %b %Y')
    analysis_display = _format_analysis_stamp(meta.get('analysis_date'))

    if owner:
        owner_rows = _owner_rows(data, owner)
        if not owner_rows:
            raise ValueError(f"Owner '{owner}' not found in dashboard data.")
        owner_row = owner_rows[0]
        subject = f"Daily CodeSonar Report | {owner} | {analysis_display}"
        hotspots = _top_hotspots(data, owner=owner)
        action_findings = _top_action_findings(data, owner=owner)
        quick_links = _quick_links(env, owner, link_base=link_base)
        owner_caption = f'{owner} receives only assigned findings.'
        action_title = 'Highest-Priority Findings'
    else:
        subject = f"Daily CodeSonar Report | {project_name} | {analysis_display}"
        hotspots = _top_hotspots(data)
        action_findings = _top_action_findings(data)
        quick_links = _quick_links(env, None, link_base=link_base)
        owner_caption = 'Use the Interactive Dashboard for detailed drill-downs.'
        action_title = 'Action Required'

    cards = [
        ('Total Findings', current['total_findings']),
        ('HB_PRIO_1', current['hb_prio_1']),
        ('HB_PRIO_2', current['hb_prio_2']),
        ('New Findings', current['new_findings']),
        ('Resolved Findings', current['resolved_findings']),
        ('Pending Findings', current['pending_findings']),
        ('Completion %', f"{current['completion_pct']}%"),
    ]
    card_html = ''.join(f'<td class="card"><div class="label">{_esc(label)}</div><div class="value">{_esc(value)}</div></td>' for label, value in cards)

    owner_rows = _owner_rows(data, owner)
    owner_table_rows = []
    for row in owner_rows:
        owner_name = row.get('name') or row.get('owner') or 'Unassigned'
        dashboard_url = _dashboard_url(env, owner_name, link_base='../../')
        button = f'<a class="button" href="{_esc(dashboard_url)}">View Owner Findings</a>' if dashboard_url else '<span class="muted">Dashboard link not configured</span>'
        owner_table_rows.append([
            _esc(owner_name),
            _esc(row.get('total_assigned', row.get('assigned', 0))),
            _esc(row.get('hb_prio_1', 0)),
            _esc(row.get('hb_prio_2', 0)),
            _esc(row.get('pending', 0)),
            _esc(row.get('done', 0)),
            f"{_esc(row.get('completion_pct', row.get('completion', 0)))}%",
            button,
        ])

    action_lines = []
    if owner:
        action_lines.append(f'<li>{len(action_findings)} highest-priority finding(s) shown below.</li>')
        action_lines.append(f'<li>{len(hotspots)} top hotspot file(s) shown below.</li>')
    else:
        open_hb1 = len([row for row in data.get('findings', []) or [] if row.get('priority') == 'HB_PRIO_1' and str(row.get('status', '')).lower() != 'done'])
        unassigned_hb = len([row for row in data.get('findings', []) or [] if row.get('owner') == 'Unassigned' and row.get('priority') in {'HB_PRIO_1', 'HB_PRIO_2'}])
        worst_owners = sorted(owner_rows, key=lambda row: -int(row.get('pending', 0) or 0))[:3]
        action_lines.append(f'<li><strong>{open_hb1}</strong> open HB_PRIO_1 finding(s).</li>')
        action_lines.append(f'<li><strong>{unassigned_hb}</strong> unassigned high-priority finding(s).</li>')
        if worst_owners:
            action_lines.append('<li><strong>Highest pending workload:</strong> ' + ', '.join(f"{_esc(row.get('name') or row.get('owner'))} ({_esc(row.get('pending', 0))})" for row in worst_owners) + '</li>')

    hotspot_rows = [[_esc(row['file']), _esc(row['findings']), _esc(row['hb_prio_1']), _esc(row['hb_prio_2']), _esc(row['risk'])] for row in hotspots]
    trend_table = 'Trend data unavailable for this analysis.' if not trend_rows else _table(['Metric', 'Change', 'Current', 'Previous'], [[_esc(row['label']), f"{_esc(row['arrow'])} {_esc(abs(row['delta']))}", _esc(row['current']), _esc(row['previous'])] for row in trend_rows])
    action_table = _table(['Issue ID', 'Priority', 'Issue Class', 'File', 'Procedure', 'Status', 'Line', 'Finding'], [[_esc(row.get('id', row.get('issue_id', ''))), _esc(row.get('priority', '')), _esc(row.get('class', row.get('issue_class', ''))), _esc(row.get('file', '')), _esc(row.get('procedure', '')), _esc(row.get('status', '')), _esc(row.get('line_number', '')), _esc(row.get('finding', row.get('message', '')))] for row in action_findings[:5]])

    html_body = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
<title>{_esc(subject)}</title>
<style>
  body {{ margin:0; padding:0; background:#f4f6f8; font-family:Arial, Helvetica, sans-serif; color:#1f2937; }}
  .wrap {{ width:100%; padding:24px 0; background:#f4f6f8; }}
  .mail {{ width:100%; max-width:960px; margin:0 auto; background:#fff; border:1px solid #d1d5db; border-radius:16px; overflow:hidden; }}
  .hero {{ padding:24px 28px; background:linear-gradient(135deg,#0b57d0,#1a7f37); color:#fff; }}
  .hero h1 {{ margin:8px 0; font-size:24px; }}
  .pill {{ display:inline-block; padding:6px 12px; border-radius:999px; background:{'#16a34a' if status_code == 'green' else '#d97706' if status_code == 'amber' else '#dc2626'}; color:#fff; font-weight:700; font-size:12px; }}
  .section {{ padding:24px 28px; border-top:1px solid #e5e7eb; }}
  h2 {{ margin:0 0 12px; font-size:18px; }}
  .meta {{ margin:0; font-size:13px; opacity:.95; }}
  .cards {{ width:100%; border-collapse:separate; border-spacing:10px; }}
  .card {{ background:#f8fafc; border:1px solid #e5e7eb; border-radius:12px; padding:14px; width:14%; vertical-align:top; }}
  .label {{ font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#6b7280; }}
  .value {{ font-size:22px; font-weight:800; margin-top:6px; color:#111827; }}
  table {{ width:100%; border-collapse:collapse; }}
  th, td {{ border:1px solid #e5e7eb; padding:10px 12px; text-align:left; vertical-align:top; font-size:13px; }}
  th {{ background:#f9fafb; }}
  .button {{ display:inline-block; padding:8px 12px; background:#0b57d0; color:#fff; text-decoration:none; border-radius:8px; font-weight:700; }}
  .muted {{ color:#6b7280; }}
  ul {{ margin:0; padding-left:18px; }}
  .links a {{ display:inline-block; margin:0 10px 10px 0; }}
  .footer {{ padding:18px 28px 28px; font-size:12px; color:#6b7280; }}
  @media screen and (max-width:700px) {{ .section, .hero, .footer {{ padding-left:16px; padding-right:16px; }} .card {{ display:block; width:auto; }} }}
</style>
</head>
<body>
<div class=\"wrap\">
  <div class=\"mail\">
    <div class=\"hero\">
      <span class=\"pill\">{_esc(status_label)}</span>
      <h1>{_esc('Owner Summary: ' + owner) if owner else 'Daily Management Summary'}</h1>
      <p class=\"meta\">Project: <strong>{_esc(project_name)}</strong> | Branch: <strong>{_esc(branch)}</strong> | Analysis: <strong>{_esc(analysis_date)}</strong></p>
    </div>

    <div class=\"section\">
      <h2>Project Health Summary</h2>
      <table class=\"cards\" role=\"presentation\"><tr>{card_html}</tr></table>
      <div class=\"links\">{''.join(f'<a class=\"button\" href=\"{_esc(url)}\">{_esc(label)}</a>' for label, url in quick_links)}</div>
    </div>

    <div class=\"section\">
      <h2>Owner-wise Status</h2>
      <p class=\"muted\">{_esc(owner_caption)}</p>
      {_table(['Owner', 'Total Assigned', 'HB_PRIO_1', 'HB_PRIO_2', 'Pending', 'Done', 'Completion %', 'Findings'], owner_table_rows)}
    </div>

    <div class=\"section\">
      <h2>{_esc(action_title)}</h2>
      <ul>{''.join(action_lines)}</ul>
      {action_table if owner else ''}
    </div>

    <div class=\"section\">
      <h2>Top Hotspots</h2>
      {_table(['File', 'Findings', 'HB_PRIO_1', 'HB_PRIO_2', 'Risk'], hotspot_rows)}
    </div>

    <div class=\"section\">
      <h2>Trend Summary</h2>
      <p class=\"muted\">Trend comparison is based on the previous tracker snapshot when available.</p>
      {trend_table}
    </div>

    <div class=\"footer\">Generated by CodeSonar Assistant. Use the Interactive Dashboard for detailed drill-downs.</div>
  </div>
</div>
</body>
</html>
"""

    text_lines = [
        subject,
        '',
        f'Project: {project_name}',
        f'Branch: {branch}',
        f'Analysis: {analysis_date}',
        f'Overall Status: {status_label}',
        '',
        'Project Health Summary',
        f"Total Findings: {current['total_findings']}",
        f"HB_PRIO_1: {current['hb_prio_1']}",
        f"HB_PRIO_2: {current['hb_prio_2']}",
        f"New Findings: {current['new_findings']}",
        f"Resolved Findings: {current['resolved_findings']}",
        f"Pending Findings: {current['pending_findings']}",
        f"Completion %: {current['completion_pct']}%",
        '',
        'Owner-wise Status',
    ]
    for row in owner_rows:
        name = row.get('name') or row.get('owner') or 'Unassigned'
        text_lines.append(f"- {name}: total={int(row.get('total_assigned', row.get('assigned', 0)))} hb1={int(row.get('hb_prio_1', 0))} hb2={int(row.get('hb_prio_2', 0))} pending={int(row.get('pending', 0))} done={int(row.get('done', 0))} completion={row.get('completion_pct', row.get('completion', 0))}%")
    text_lines.extend(['', action_title])
    if owner:
        for row in action_findings[:5]:
            text_lines.append(f"- {row.get('id')} | {row.get('priority')} | {row.get('class')} | {row.get('file')} | {row.get('status')}")
    else:
        text_lines.append(f"- Open HB_PRIO_1 findings: {len([row for row in data.get('findings', []) or [] if row.get('priority') == 'HB_PRIO_1' and str(row.get('status', '')).lower() != 'done'])}")
        text_lines.append(f"- Unassigned high-priority findings: {len([row for row in data.get('findings', []) or [] if row.get('owner') == 'Unassigned' and row.get('priority') in {'HB_PRIO_1', 'HB_PRIO_2'}])}")
    text_lines.extend(['', 'Top Hotspots'])
    for row in hotspots:
        text_lines.append(f"- {row['file']}: {row['findings']} findings ({row['hb_prio_1']} HB_PRIO_1, {row['hb_prio_2']} HB_PRIO_2) - {row['risk']}")
    text_lines.extend(['', 'Trend Summary'])
    if trend_rows:
        for row in trend_rows:
            text_lines.append(f"- {row['label']}: {row['arrow']} {abs(row['delta'])} (current {row['current']}, previous {row['previous']})")
    else:
        text_lines.append('Trend data unavailable for this analysis.')

    return subject, html_body, '\n'.join(text_lines) + '\n'


def _mirror_dashboard_preview(task_dir: Path) -> None:
    source = task_dir / 'output' / 'dashboard' / 'index.html'
    if not source.exists():
        return
    target = task_dir / 'output' / 'email' / 'Interactive_Dashboard.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _run_report(task_dir: Path | None = None, preview: bool = False) -> dict:
    task_dir = Path(task_dir) if task_dir else TASK_DIR
    tracker_path = task_dir / 'output' / 'Master_Tracker.xlsx'
    mode = 'preview' if preview else 'send'
    if not tracker_path.exists():
        message = f'Master_Tracker.xlsx not found at {tracker_path}. Run Update Tracker first.'
        _append_log('management', mode, 'error', [], message)
        return {'answer': message, 'count': 0, 'rows': []}

    try:
        data = _load_dashboard_data(task_dir)
    except Exception as exc:
        message = str(exc)
        _append_log('management', mode, 'error', [], message)
        return {'answer': message, 'count': 0, 'rows': []}

    owner_validation = data.get('owner_validation') or {}
    if not owner_validation.get('reconciled', False) or owner_validation.get('warnings'):
        warnings = owner_validation.get('warnings', [])
        message = 'Owner validation failed; email report was not generated.'
        _append_log('management', mode, 'error', [], message)
        return {'answer': message, 'count': 0, 'rows': [{'warning': warning} for warning in warnings]}

    env = _load_env(ENV_FILE)
    config = _smtp_config(env)
    owner_map = _owner_email_map(env)

    subject, html_body, text_body = _render_report(data, env, owner=None)
    html_path, txt_path = _write_report_files('Daily_CodeSonar_Report', html_body, text_body)
    _mirror_dashboard_preview(task_dir)
    rows = [
        {'output': f'Generated management report: {html_path}'},
        {'output': f'Generated plain text fallback: {txt_path}'},
    ]

    if preview:
        _append_log('management', mode, 'generated', [], '')
        for owner_name in owner_map:
            owner_subject, owner_html, owner_text = _render_report(data, env, owner=owner_name, link_base='../../')
            owner_dir = EMAIL_DIR / 'owners' / _slug(owner_name)
            owner_dir.mkdir(parents=True, exist_ok=True)
            (owner_dir / 'Daily_CodeSonar_Report.html').write_text(owner_html, encoding='utf-8')
            (owner_dir / 'Daily_CodeSonar_Report.txt').write_text(owner_text, encoding='utf-8')
            _append_log(owner_name, mode, 'generated', [owner_map[owner_name]], '')
            rows.append({'output': f'Generated owner report preview: {owner_name} -> {owner_dir}'})
        return {'answer': f'Daily CodeSonar report preview generated: {html_path}', 'count': len(rows), 'rows': rows}

    issues = _validate_send_config(config)
    if issues:
        message = 'Email configuration is incomplete: ' + '; '.join(issues)
        _append_log('management', mode, 'error', list(config['to']), message)
        return {'answer': message, 'count': 0, 'rows': rows}

    try:
        _send_email(config, subject, html_body, text_body)
        _append_log('management', mode, 'sent', list(config['to']) + list(config['cc']) + list(config['bcc']), '')
        rows.append({'output': f"Sent management email to: {', '.join(config['to'])}"})
    except Exception as exc:
        message = f'Failed to send management email: {exc}'
        _append_log('management', mode, 'error', list(config['to']), message)
        return {'answer': message, 'count': 0, 'rows': rows}

    for owner_name, owner_email in owner_map.items():
        try:
            owner_subject, owner_html, owner_text = _render_report(data, env, owner=owner_name, link_base='../../')
            owner_dir = EMAIL_DIR / 'owners' / _slug(owner_name)
            owner_dir.mkdir(parents=True, exist_ok=True)
            (owner_dir / 'Daily_CodeSonar_Report.html').write_text(owner_html, encoding='utf-8')
            (owner_dir / 'Daily_CodeSonar_Report.txt').write_text(owner_text, encoding='utf-8')
            owner_config = dict(config)
            owner_config['to'] = [owner_email]
            owner_config['cc'] = []
            owner_config['bcc'] = []
            _send_email(owner_config, owner_subject, owner_html, owner_text)
            _append_log(owner_name, mode, 'sent', [owner_email], '')
            rows.append({'output': f'Sent owner email: {owner_name} -> {owner_email}'})
        except Exception as exc:
            _append_log(owner_name, mode, 'error', [owner_email], str(exc))
            rows.append({'error': f'Owner email failed for {owner_name}: {exc}'})

    return {'answer': f'Daily CodeSonar report sent successfully: {html_path}', 'count': len(rows), 'rows': rows}


def preview_daily_code_sonar_report(task_dir: Path | None = None) -> dict:
    return _run_report(task_dir=task_dir, preview=True)


def send_daily_code_sonar_report(task_dir: Path | None = None) -> dict:
    return _run_report(task_dir=task_dir, preview=False)


def daily_code_sonar_report(task_dir: Path | None = None) -> dict:
    result = preview_daily_code_sonar_report(task_dir)
    answer = result.get("answer", "")
    if answer.startswith("Daily CodeSonar report preview generated:"):
        result["answer"] = answer.replace("Daily CodeSonar report preview generated:", "Daily CodeSonar report generated:", 1)
    return result


def _smtp_config(env: dict[str, str]) -> dict[str, str | list[str] | bool]:
    backend = _env('EMAIL_BACKEND', env, 'smtp').strip().lower() or 'smtp'
    return {
        'backend': backend,
        'host': _env('SMTP_HOST', env, '').strip(),
        'port': _env('SMTP_PORT', env, '').strip(),
        'username': _env('SMTP_USERNAME', env, '').strip(),
        'password': _env('SMTP_PASSWORD', env, '').strip(),
        'use_tls': _bool('SMTP_USE_TLS', env, True),
        'from': _env('EMAIL_FROM', env, '').strip(),
        'to': _list('EMAIL_TO', env),
        'cc': _list('EMAIL_CC', env),
    }


def _validate_send_config(config: dict[str, str | list[str] | bool]) -> list[str]:
    issues: list[str] = []
    if config['backend'] != 'smtp':
        issues.append('EMAIL_BACKEND must be smtp.')
    if not config['host']:
        issues.append('SMTP_HOST is not configured.')
    if not config['port']:
        issues.append('SMTP_PORT is not configured.')
    if not config['from']:
        issues.append('EMAIL_FROM is not configured.')
    if not config['to']:
        issues.append('EMAIL_TO is not configured.')
    if not config['cc']:
        issues.append('EMAIL_CC is not configured.')
    if bool(config['username']) ^ bool(config['password']):
        issues.append('SMTP_USERNAME and SMTP_PASSWORD must both be set or both be empty.')
    return issues


def _attachment_candidates(task_dir: Path, html_path: Path, txt_path: Path) -> list[Path]:
    attachments = [html_path, txt_path]
    for candidate in [
        task_dir / 'output' / 'Master_Tracker.xlsx',
        task_dir / 'output' / 'Tracker_History.xlsx',
    ]:
        if candidate.exists():
            attachments.append(candidate)
    return attachments


def _attachment_bytes(path: Path) -> tuple[str, str, bytes]:
    mimetype, _ = mimetypes.guess_type(str(path))
    if mimetype:
        maintype, subtype = mimetype.split('/', 1)
    else:
        maintype, subtype = 'application', 'octet-stream'
    return maintype, subtype, path.read_bytes()


def _send_smtp_email(config: dict[str, str | list[str] | bool], subject: str, html_path: Path, txt_path: Path, attachments: list[Path]) -> dict:
    port = int(str(config['port']))
    recipients = list(dict.fromkeys([*(config['to'] or []), *(config['cc'] or [])]))
    if not recipients:
        raise RuntimeError('No SMTP recipients were configured.')

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = str(config['from'])
    message['To'] = ';'.join(str(item) for item in config['to'])
    if config['cc']:
        message['Cc'] = ';'.join(str(item) for item in config['cc'])

    text_body = txt_path.read_text(encoding='utf-8') if txt_path.exists() else 'Daily CodeSonar report is attached.'
    html_body = html_path.read_text(encoding='utf-8')
    message.set_content(text_body)
    message.add_alternative(html_body, subtype='html')

    for attachment in attachments:
        if not attachment.exists():
            continue
        maintype, subtype, data = _attachment_bytes(attachment)
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=attachment.name)

    if port == 465:
        smtp_client = smtplib.SMTP_SSL(str(config['host']), port, timeout=30)
    else:
        smtp_client = smtplib.SMTP(str(config['host']), port, timeout=30)

    with smtp_client as smtp:
        smtp.ehlo()
        if port != 465 and bool(config['use_tls']):
            smtp.starttls()
            smtp.ehlo()
        if config['username'] or config['password']:
            smtp.login(str(config['username']), str(config['password']))
        smtp.send_message(message, from_addr=str(config['from']), to_addrs=recipients)

    return {
        'recipient_count': len(recipients),
        'recipients': recipients,
    }


def _run_report(task_dir: Path | None = None, preview: bool = False, display: bool = False) -> dict:
    task_dir = Path(task_dir) if task_dir else TASK_DIR
    tracker_path = task_dir / 'output' / 'Master_Tracker.xlsx'
    mode = 'preview' if preview else ('display' if display else 'send')
    if not tracker_path.exists():
        message = f'Master_Tracker.xlsx not found at {tracker_path}. Run Update Tracker first.'
        _append_log('management', mode, 'error', [], message)
        return {'answer': message, 'count': 0, 'rows': []}

    try:
        data = _load_dashboard_data(task_dir)
    except Exception as exc:
        message = str(exc)
        _append_log('management', mode, 'error', [], message)
        return {'answer': message, 'count': 0, 'rows': []}

    owner_validation = data.get('owner_validation') or {}
    if not owner_validation.get('reconciled', False) or owner_validation.get('warnings'):
        warnings = owner_validation.get('warnings', [])
        message = 'Owner validation failed; email report was not generated.'
        _append_log('management', mode, 'error', [], message)
        return {'answer': message, 'count': 0, 'rows': [{'warning': warning} for warning in warnings]}

    env = _load_env(ENV_FILE)
    config = _smtp_config(env)

    try:
        subject, html_body, text_body = _render_report(data, env, owner=None)
    except Exception as exc:
        message = str(exc)
        _append_log('management', mode, 'error', list(config['to']) + list(config['cc']), message)
        return {'answer': message, 'count': 0, 'rows': []}

    html_path, txt_path = _write_report_files('Daily_CodeSonar_Report', html_body, text_body)
    _mirror_dashboard_preview(task_dir)
    rows = [
        {'output': f'Generated management report: {html_path}'},
        {'output': f'Generated plain text fallback: {txt_path}'},
        {'output': f"To recipients: {', '.join(config['to']) if config['to'] else '(none)'}"},
        {'output': f"CC: {', '.join(config['cc']) if config['cc'] else '(none)'}"},
    ]

    if preview or display or config.get('backend') == 'preview':
        _append_log('management', mode, 'generated', list(config['to']) + list(config['cc']), '')
        return {'answer': f'Daily CodeSonar report preview generated: {html_path}', 'count': len(rows), 'rows': rows}

    issues = _validate_send_config(config)
    if issues:
        message = 'SMTP configuration is incomplete: ' + '; '.join(issues)
        _append_log('management', mode, 'error', list(config['to']) + list(config['cc']), message)
        rows.extend({'warning': issue} for issue in issues)
        return {'answer': message, 'count': len(rows), 'rows': rows}

    try:
        send_result = _send_smtp_email(config, subject, html_path, txt_path, _attachment_candidates(task_dir, html_path, txt_path))
        sent_at = datetime.now().isoformat(timespec='seconds')
        _append_log('management', mode, 'sent', send_result['recipients'], '')
        rows.append({'output': f"Sent SMTP email to {send_result['recipient_count']} recipient(s) at {sent_at}"})
        rows.append({'output': f"To: {', '.join(config['to'])}"})
        rows.append({'output': f"CC: {', '.join(config['cc'])}"})
        return {
            'answer': f'Daily CodeSonar report sent successfully to {send_result["recipient_count"]} recipient(s) at {sent_at}.',
            'count': len(rows),
            'rows': rows,
        }
    except Exception as exc:
        message = f'Failed to send SMTP email: {exc}'
        _append_log('management', mode, 'error', list(config['to']) + list(config['cc']), message)
        rows.append({'error': message})
        return {'answer': message, 'count': len(rows), 'rows': rows}


def preview_daily_code_sonar_report(task_dir: Path | None = None) -> dict:
    return _run_report(task_dir=task_dir, preview=True)


def send_daily_code_sonar_report(task_dir: Path | None = None, display: bool = False) -> dict:
    return _run_report(task_dir=task_dir, preview=False, display=display)


def daily_code_sonar_report(task_dir: Path | None = None) -> dict:
    result = preview_daily_code_sonar_report(task_dir)
    answer = result.get('answer', '')
    if answer.startswith('Daily CodeSonar report preview generated:'):
        result['answer'] = answer.replace('Daily CodeSonar report preview generated:', 'Daily CodeSonar report generated:', 1)
    return result
