try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    from datetime import datetime

    def hello():
        print("Hello from example DAG")

    with DAG(
        dag_id="example_ingest",
        start_date=datetime(2026, 1, 1),
        schedule_interval="@daily",
        catchup=False,
    ) as dag:
        run = PythonOperator(task_id="hello", python_callable=hello)

except Exception:
    # Airflow not installed in this environment — keep file safe to import.
    dag = None
