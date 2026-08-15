"""Airflow DAG: prove the failure-alerting path actually fires.

`python -m src.alerting --test` proves the channels work. It does not prove that Airflow
calls them — that depends on `on_failure_callback` being wired into default_args and on the
worker being able to reach the alert sinks. This DAG closes that gap by failing on purpose.

Manual trigger only, and `retries: 0` so it fails immediately: on_failure_callback fires on
*final* failure, so a retrying task would delay the alert by the retry window.

    airflow dags trigger cfbd_alerting_selftest

Expect: the task fails, a line appears in data/alerts/failures.jsonl, and an email arrives
if SMTP is configured. A failure here means real pipeline failures would also go unheard.
"""
from datetime import datetime

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

from src.alerting import failure_callback


def fail_on_purpose(**context):
    raise RuntimeError(
        "Synthetic failure from cfbd_alerting_selftest. If you are reading this in an "
        "alert, the alerting path works."
    )


with DAG(
    dag_id="cfbd_alerting_selftest",
    description="Fails on purpose to verify failure alerting reaches you",
    default_args={
        "owner": "cfdb",
        "retries": 0,
        "on_failure_callback": failure_callback,
    },
    start_date=datetime(2026, 8, 15),
    schedule=None,
    catchup=False,
    tags=["cfdb", "diagnostic"],
) as dag:
    PythonOperator(task_id="fail_on_purpose", python_callable=fail_on_purpose)
