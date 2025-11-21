import sqlite3
conn = sqlite3.connect('data/app.dev.db')
c = conn.cursor()
c.execute("INSERT INTO individual_service_status (user_id, task_name, is_running, started_at, last_execution_at, next_execution_at, process_id, schedule_enabled, last_execution_status, last_execution_duration, last_execution_details, created_at, updated_at) VALUES (3, 'sell_monitor', 1, datetime('now'), datetime('now'), datetime('now','+1 minute'), 77777, 1, 'running', 0.0, '{}', datetime('now'), datetime('now'))")
conn.commit()
conn.close()
