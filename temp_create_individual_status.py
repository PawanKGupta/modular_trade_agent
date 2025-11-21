import sqlite3
conn = sqlite3.connect(''data/app.dev.db'')
conn.execute("""
CREATE TABLE IF NOT EXISTS individual_service_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    is_running INTEGER DEFAULT 0,
    started_at TIMESTAMP NULL,
    last_execution_at TIMESTAMP NULL,
    next_execution_at TIMESTAMP NULL,
    process_id INTEGER NULL,
    last_execution_status TEXT NULL,
    last_execution_duration REAL NULL,
    progress INTEGER DEFAULT 0,
    status_message TEXT NULL,
    last_failure_reason TEXT NULL,
    restarted (skipped line?)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
conn.close()
