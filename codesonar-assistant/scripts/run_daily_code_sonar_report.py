#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from email_report import preview_daily_code_sonar_report, send_daily_code_sonar_report
from env_bootstrap import ensure_env_file


SCRIPT_DIR = Path(__file__).resolve().parent
TASK_DIR = SCRIPT_DIR.parent
ENV_FILE = ensure_env_file(TASK_DIR)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Send the daily CodeSonar email report automatically')
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Generate the email artifacts without sending mail',
    )
    parser.add_argument(
        '--display',
        action='store_true',
        help='Open the Outlook draft instead of sending it',
    )
    parser.add_argument(
        '--task-dir',
        default=str(TASK_DIR),
        help='Workspace root that contains output/Master_Tracker.xlsx',
    )
    parser.add_argument(
        '--format',
        choices=['json', 'text'],
        default='json',
        help='Output format',
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    task_dir = Path(args.task_dir)

    if args.preview:
        result = preview_daily_code_sonar_report(task_dir)
    else:
        result = send_daily_code_sonar_report(task_dir, display=args.display)

    payload = {
        'source': str(task_dir / 'output' / 'Master_Tracker.xlsx'),
        'answer': result.get('answer', ''),
        'count': result.get('count', 0),
        'rows': result.get('rows', []),
    }

    if args.format == 'json':
        print(json.dumps(payload, indent=2))
    else:
        print(f"Source : {payload['source']}")
        print(payload['answer'])
        if payload['rows']:
            print(json.dumps(payload['rows'], indent=2))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())