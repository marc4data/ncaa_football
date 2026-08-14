"""Airflow DAG: fetch CFBD endpoint and load raw JSON to Postgres.

Usage:
- Trigger the DAG with `endpoint` in `dag_run.conf`, e.g. `{"endpoint": "teams"}`.
- The tasks assume `python` and the project are available on the worker's PATH.
"""
try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
    from datetime import datetime, timedelta

    default_args = {
        "owner": "cfdb",
        "depends_on_past": False,
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    }

    with DAG(
        dag_id="cfbd_ingest_to_postgres",
        default_args=default_args,
        start_date=datetime(2026, 1, 1),
        schedule_interval="@daily",
        catchup=False,
        max_active_runs=1,
    ) as dag:

        endpoint = "{{ dag_run.conf.get('endpoint', 'teams') }}"

        ingest_cmd = f"python -m src.ingest fetch {endpoint}"
        load_cmd = f"python -m src.load_raw_to_postgres {endpoint}"

        ingest = BashOperator(
            task_id="ingest_raw",
            bash_command=ingest_cmd,
            env={"PYTHONUNBUFFERED": "1"},
        )

        load = BashOperator(
            task_id="load_to_postgres",
            bash_command=load_cmd,
            env={"PYTHONUNBUFFERED": "1"},
        )

        ingest >> load

except Exception:
    # Graceful fallback when Airflow is not installed in this environment
    dag = None
