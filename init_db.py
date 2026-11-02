"""
Emergency Attendance Dashboard — Database Initialization
=========================================================
VIT Vellore | Database Management Systems Course Project

Demonstrates:
  • Full 3NF normalized schema (15 tables)
  • AFTER INSERT triggers (auto-alerts, materialized-view refresh, audit trail)
  • Views with window-function-equivalent aggregations
  • Materialized view tables refreshed by triggers
  • B+ tree-style composite indexes
  • Transactions with savepoints
  • Realistic seed data (50 students, 2000+ attendance records)

Run:
    python init_db.py
"""

import sqlite3
import os
import random
import json
from datetime import date, timedelta, datetime

# ── password hashing ──────────────────────────────────────────────────────────
try:
    from werkzeug.security import generate_password_hash as _wz_hash
    def _hash(pw: str) -> str:
        return _wz_hash(pw, method="pbkdf2:sha256")
except Exception:
    import hashlib, hmac
    def _hash(pw: str) -> str:            # fallback — not for production!
        return "pbkdf2:sha256:" + hashlib.sha256(pw.encode()).hexdigest()

# ═════════════════════════════════════════════════════════════════════════════
# DDL HELPERS
# ═════════════════════════════════════════════════════════════════════════════

TABLES_DDL = """
-- ─── Core entity tables ───────────────────────────────────────────────────

-- 1. students
CREATE TABLE IF NOT EXISTS students (
    student_id      TEXT PRIMARY KEY,
    full_name       TEXT NOT NULL,
    email           TEXT UNIQUE NOT NULL,
    phone           TEXT,
    department      TEXT NOT NULL,
    semester        INTEGER NOT NULL,
    section         TEXT NOT NULL,
    hostel_block    TEXT,
    room_number     TEXT,
    parent_phone    TEXT,
    parent_email    TEXT,
    parent_consent  BOOLEAN DEFAULT 0,
    enrollment_date DATE DEFAULT (date('now')),
    status          TEXT DEFAULT 'ACTIVE'
                        CHECK (status IN ('ACTIVE','ON_LEAVE','WITHDRAWN','GRADUATED')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. departments  (lookup / 3NF normalisation)
CREATE TABLE IF NOT EXISTS departments (
    dept_code TEXT PRIMARY KEY,
    dept_name TEXT NOT NULL
);

-- 3. faculty
CREATE TABLE IF NOT EXISTS faculty (
    faculty_id  TEXT PRIMARY KEY,
    full_name   TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    department  TEXT NOT NULL,
    role        TEXT DEFAULT 'FACULTY'
                    CHECK (role IN ('FACULTY','ADVISOR','HOD','DEAN')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. warden
CREATE TABLE IF NOT EXISTS warden (
    warden_id   TEXT PRIMARY KEY,
    full_name   TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    phone       TEXT,
    hostel_block TEXT NOT NULL,
    shift       TEXT CHECK (shift IN ('MORNING','EVENING','NIGHT')),
    is_active   BOOLEAN DEFAULT 1,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. subjects
CREATE TABLE IF NOT EXISTS subjects (
    subject_code  TEXT PRIMARY KEY,
    subject_name  TEXT NOT NULL,
    department    TEXT NOT NULL,
    semester      INTEGER NOT NULL,
    credits       INTEGER DEFAULT 3,
    faculty_id    TEXT REFERENCES faculty(faculty_id),
    schedule_json TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. attendance  (main fact table)
CREATE TABLE IF NOT EXISTS attendance (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL REFERENCES students(student_id),
    subject_code TEXT NOT NULL REFERENCES subjects(subject_code),
    class_date   DATE NOT NULL,
    period       INTEGER NOT NULL,
    status       TEXT NOT NULL
                     CHECK (status IN ('PRESENT','ABSENT','LATE','EXCUSED','ON_DUTY')),
    marked_by    TEXT REFERENCES faculty(faculty_id),
    marked_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    device_info  TEXT,
    UNIQUE(student_id, subject_code, class_date, period)
);

-- 7. alerts
CREATE TABLE IF NOT EXISTS alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL REFERENCES students(student_id),
    alert_type       TEXT NOT NULL
                         CHECK (alert_type IN (
                             'CONSECUTIVE_ABSENCE','LOW_ATTENDANCE',
                             'EXAM_AVOIDANCE','WEEKEND_SYNDROME',
                             'SUBJECT_DROP','CROSS_SUBJECT','HOSTEL_ANOMALY')),
    severity         TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    message          TEXT NOT NULL,
    risk_score       REAL DEFAULT 0,
    status           TEXT DEFAULT 'ACTIVE'
                         CHECK (status IN ('ACTIVE','ACKNOWLEDGED','RESOLVED','FALSE_POSITIVE')),
    acknowledged_by  TEXT REFERENCES warden(warden_id),
    acknowledged_at  TIMESTAMP,
    resolved_at      TIMESTAMP,
    resolution_notes TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. absence_patterns  (detailed pattern records, separate from summary alerts)
CREATE TABLE IF NOT EXISTS absence_patterns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL REFERENCES students(student_id),
    pattern_type TEXT NOT NULL,
    severity     TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    risk_score   REAL NOT NULL,
    details_json TEXT,
    detected_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at  TIMESTAMP,
    resolution   TEXT CHECK (resolution IN ('RESOLVED','REFERRED','FALSE_POSITIVE','ONGOING'))
);

-- 9. welfare_visits  (warden follow-up on alerts)
CREATE TABLE IF NOT EXISTS welfare_visits (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id          INTEGER NOT NULL REFERENCES alerts(id),
    warden_id         TEXT NOT NULL REFERENCES warden(warden_id),
    visit_date        DATE NOT NULL,
    visit_time        TIME NOT NULL,
    student_found     BOOLEAN,
    student_condition TEXT CHECK (student_condition IN
                          ('HEALTHY','ILL','DISTRESSED','ABSENT','REFUSED')),
    notes             TEXT,
    follow_up_required BOOLEAN DEFAULT 0,
    follow_up_date    DATE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. hostel_logs  (gate access logs)
CREATE TABLE IF NOT EXISTS hostel_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL REFERENCES students(student_id),
    gate_id    TEXT NOT NULL,
    direction  TEXT CHECK (direction IN ('ENTRY','EXIT')),
    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    method     TEXT CHECK (method IN ('CARD','BIOMETRIC','MANUAL','MOBILE_APP'))
);

-- 11. lms_activity  (Learning Management System events)
CREATE TABLE IF NOT EXISTS lms_activity (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT NOT NULL REFERENCES students(student_id),
    activity_type    TEXT CHECK (activity_type IN (
                         'LOGIN','ASSIGNMENT_SUBMIT','QUIZ_ATTEMPT',
                         'FORUM_POST','VIDEO_WATCH','DOWNLOAD')),
    subject_code     TEXT REFERENCES subjects(subject_code),
    timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    duration_seconds INTEGER
);

-- 12. audit_log  (immutable audit trail)
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    TEXT NOT NULL,
    actor_role  TEXT NOT NULL,
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    old_values  TEXT,
    new_values  TEXT,
    ip_address  TEXT,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. mv_dept_attendance  (materialized view — refreshed by trigger)
CREATE TABLE IF NOT EXISTS mv_dept_attendance (
    department     TEXT NOT NULL,
    week           TEXT NOT NULL,
    attendance_pct REAL NOT NULL,
    total_classes  INTEGER NOT NULL,
    present_count  INTEGER NOT NULL,
    PRIMARY KEY (department, week)
);

-- 14. mv_risk_trend  (materialized view — alert severity trend by day)
CREATE TABLE IF NOT EXISTS mv_risk_trend (
    day            TEXT NOT NULL PRIMARY KEY,
    critical_count INTEGER DEFAULT 0,
    high_count     INTEGER DEFAULT 0,
    medium_count   INTEGER DEFAULT 0,
    low_count      INTEGER DEFAULT 0
);

-- 15. users  (authentication)
CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('FACULTY','WARDEN','ADMIN','STUDENT')),
    linked_id     TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ─── Triggers ────────────────────────────────────────────────────────────────

TRIGGERS_DDL = """
-- ── Trigger 1: Auto-alert on 3+ consecutive absences (within rolling 3 days)
DROP TRIGGER IF EXISTS auto_alert_on_streak;
CREATE TRIGGER auto_alert_on_streak
AFTER INSERT ON attendance
WHEN NEW.status = 'ABSENT'
BEGIN
    INSERT INTO alerts (student_id, alert_type, severity, message, risk_score, created_at)
    SELECT
        NEW.student_id,
        'CONSECUTIVE_ABSENCE',
        'CRITICAL',
        'Student has 3+ consecutive absences across subjects',
        85.0,
        datetime('now')
    WHERE (
        SELECT COUNT(*)
        FROM attendance a
        WHERE a.student_id = NEW.student_id
          AND a.status     = 'ABSENT'
          AND a.class_date >= date(NEW.class_date, '-3 days')
          AND a.class_date <= NEW.class_date
    ) >= 3
    AND NOT EXISTS (
        SELECT 1 FROM alerts al
        WHERE al.student_id  = NEW.student_id
          AND al.alert_type  = 'CONSECUTIVE_ABSENCE'
          AND al.status      = 'ACTIVE'
          AND al.created_at >= datetime('now', '-24 hours')
    );
END;

-- ── Trigger 2: Refresh mv_dept_attendance after every attendance insert
DROP TRIGGER IF EXISTS refresh_mv_dept_attendance;
CREATE TRIGGER refresh_mv_dept_attendance
AFTER INSERT ON attendance
BEGIN
    INSERT OR REPLACE INTO mv_dept_attendance
        (department, week, attendance_pct, total_classes, present_count)
    SELECT
        s.department,
        strftime('%Y-%W', NEW.class_date) AS week,
        ROUND(
            100.0 * SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
                  / COUNT(*),
            1
        ),
        COUNT(*),
        SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
    FROM students s
    JOIN attendance a ON s.student_id = a.student_id
    WHERE strftime('%Y-%W', a.class_date) = strftime('%Y-%W', NEW.class_date)
      AND s.department = (
              SELECT department FROM students WHERE student_id = NEW.student_id
          )
    GROUP BY s.department;
END;

-- ── Trigger 3: Audit trail when a warden acknowledges an alert
DROP TRIGGER IF EXISTS audit_alert_ack;
CREATE TRIGGER audit_alert_ack
AFTER UPDATE ON alerts
WHEN NEW.acknowledged_at IS NOT NULL AND OLD.acknowledged_at IS NULL
BEGIN
    INSERT INTO audit_log
        (actor_id, actor_role, action, entity_type, entity_id, old_values, new_values)
    VALUES (
        NEW.acknowledged_by,
        'WARDEN',
        'ACKNOWLEDGE_ALERT',
        'alerts',
        CAST(NEW.id AS TEXT),
        json_object('status', OLD.status),
        json_object('status', NEW.status, 'acknowledged_at', NEW.acknowledged_at)
    );
END;

-- ── Trigger 4: Auto-alert when subject attendance drops below 75%
DROP TRIGGER IF EXISTS auto_alert_low_attendance;
CREATE TRIGGER auto_alert_low_attendance
AFTER INSERT ON attendance
WHEN NEW.status = 'ABSENT'
BEGIN
    INSERT INTO alerts (student_id, alert_type, severity, message, risk_score, created_at)
    SELECT
        NEW.student_id,
        'LOW_ATTENDANCE',
        'HIGH',
        'Attendance has dropped below 75% in ' || NEW.subject_code,
        70.0,
        datetime('now')
    WHERE (
        SELECT ROUND(
            100.0 * SUM(CASE WHEN status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
                  / COUNT(*),
            1
        )
        FROM attendance
        WHERE student_id   = NEW.student_id
          AND subject_code = NEW.subject_code
    ) < 75.0
    AND NOT EXISTS (
        SELECT 1 FROM alerts al
        WHERE al.student_id = NEW.student_id
          AND al.alert_type = 'LOW_ATTENDANCE'
          AND al.status     = 'ACTIVE'
          AND al.created_at >= datetime('now', '-24 hours')
    );
END;
"""

# ─── Views ───────────────────────────────────────────────────────────────────

VIEWS_DDL = """
-- ── View 1: Per-student risk assessment (30-day rolling window)
--    Demonstrates aggregation, correlated sub-queries, CASE expressions
DROP VIEW IF EXISTS student_risk;
CREATE VIEW student_risk AS
SELECT
    s.student_id,
    s.full_name,
    s.department,
    s.semester,
    s.hostel_block,
    s.room_number,
    s.section,
    COUNT(CASE WHEN a.status = 'ABSENT' THEN 1 END)                          AS total_absences,
    COUNT(a.id)                                                               AS total_classes,
    ROUND(
        100.0 * COUNT(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 END)
              / MAX(COUNT(a.id), 1),
        1
    )                                                                         AS attendance_pct,
    (SELECT COUNT(*) FROM alerts al
     WHERE al.student_id = s.student_id AND al.status = 'ACTIVE')            AS active_alerts,
    CASE
        WHEN (SELECT COUNT(*) FROM alerts al
              WHERE al.student_id = s.student_id
                AND al.severity   = 'CRITICAL'
                AND al.status     = 'ACTIVE') > 0         THEN 'CRITICAL'
        WHEN ROUND(
                 100.0 * COUNT(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 END)
                       / MAX(COUNT(a.id), 1), 1
             ) < 75                                        THEN 'HIGH'
        WHEN ROUND(
                 100.0 * COUNT(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 END)
                       / MAX(COUNT(a.id), 1), 1
             ) < 85                                        THEN 'MEDIUM'
        ELSE 'LOW'
    END                                                                       AS risk_level,
    ROUND(
        (100 - ROUND(
                   100.0 * COUNT(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 END)
                         / MAX(COUNT(a.id), 1),
                   1
               )
        ) * 0.4
        + (SELECT COUNT(*) FROM alerts al
           WHERE al.student_id = s.student_id AND al.status = 'ACTIVE') * 10.0,
        1
    )                                                                         AS risk_score
FROM students s
LEFT JOIN attendance a
       ON s.student_id = a.student_id
      AND a.class_date >= date('now', '-30 days')
WHERE s.status = 'ACTIVE'
GROUP BY s.student_id;

-- ── View 2: Alert details enriched with student and warden info
DROP VIEW IF EXISTS alert_details;
CREATE VIEW alert_details AS
SELECT
    al.id,
    al.student_id,
    s.full_name        AS student_name,
    s.department,
    s.semester,
    s.hostel_block,
    s.room_number,
    al.alert_type,
    al.severity,
    al.message,
    al.risk_score,
    al.status,
    al.acknowledged_by,
    w.full_name        AS warden_name,
    al.acknowledged_at,
    al.resolved_at,
    al.created_at,
    ROUND((julianday('now') - julianday(al.created_at)) * 24, 1) AS hours_open
FROM alerts al
JOIN  students s ON al.student_id      = s.student_id
LEFT JOIN warden w ON al.acknowledged_by = w.warden_id;

-- ── View 3: Weekly attendance summary per student per subject
DROP VIEW IF EXISTS weekly_attendance;
CREATE VIEW weekly_attendance AS
SELECT
    a.student_id,
    s.full_name,
    a.subject_code,
    subj.subject_name,
    strftime('%Y-%W', a.class_date)                                           AS week,
    COUNT(*)                                                                  AS total_classes,
    SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END) AS attended,
    ROUND(
        100.0 * SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
              / COUNT(*),
        1
    )                                                                         AS pct
FROM attendance a
JOIN students s    ON a.student_id   = s.student_id
JOIN subjects subj ON a.subject_code = subj.subject_code
GROUP BY a.student_id, a.subject_code, week;
"""

# ─── Indexes ─────────────────────────────────────────────────────────────────

INDEXES_DDL = """
-- B+ tree composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_attendance_student_date
    ON attendance(student_id, class_date DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_subject_date
    ON attendance(subject_code, class_date DESC);

CREATE INDEX IF NOT EXISTS idx_attendance_status
    ON attendance(status);

CREATE INDEX IF NOT EXISTS idx_alerts_student_active
    ON alerts(student_id, status);

CREATE INDEX IF NOT EXISTS idx_alerts_severity
    ON alerts(severity, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_hostel_student_time
    ON hostel_logs(student_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_lms_student_time
    ON lms_activity(student_id, timestamp DESC);
"""

# ═════════════════════════════════════════════════════════════════════════════
# SEED DATA
# ═════════════════════════════════════════════════════════════════════════════

def _recreate_triggers(cur: sqlite3.Cursor) -> None:
    """
    Re-create the four triggers using individual execute() calls so that
    no implicit COMMIT is issued (unlike executescript).
    Each CREATE TRIGGER block is a single atomic DDL statement in SQLite.
    """
    trigger_blocks = [
        # Trigger 1 — consecutive absence auto-alert
        """
        CREATE TRIGGER IF NOT EXISTS auto_alert_on_streak
        AFTER INSERT ON attendance
        WHEN NEW.status = 'ABSENT'
        BEGIN
            INSERT INTO alerts (student_id, alert_type, severity, message, risk_score, created_at)
            SELECT
                NEW.student_id, 'CONSECUTIVE_ABSENCE', 'CRITICAL',
                'Student has 3+ consecutive absences across subjects', 85.0, datetime('now')
            WHERE (
                SELECT COUNT(*) FROM attendance a
                WHERE a.student_id = NEW.student_id AND a.status = 'ABSENT'
                  AND a.class_date >= date(NEW.class_date, '-3 days')
                  AND a.class_date <= NEW.class_date
            ) >= 3
            AND NOT EXISTS (
                SELECT 1 FROM alerts al
                WHERE al.student_id = NEW.student_id
                  AND al.alert_type = 'CONSECUTIVE_ABSENCE'
                  AND al.status = 'ACTIVE'
                  AND al.created_at >= datetime('now', '-24 hours')
            );
        END
        """,
        # Trigger 2 — refresh mv_dept_attendance
        """
        CREATE TRIGGER IF NOT EXISTS refresh_mv_dept_attendance
        AFTER INSERT ON attendance
        BEGIN
            INSERT OR REPLACE INTO mv_dept_attendance
                (department, week, attendance_pct, total_classes, present_count)
            SELECT
                s.department,
                strftime('%Y-%W', NEW.class_date) AS week,
                ROUND(
                    100.0 * SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
                          / COUNT(*), 1
                ),
                COUNT(*),
                SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
            FROM students s
            JOIN attendance a ON s.student_id = a.student_id
            WHERE strftime('%Y-%W', a.class_date) = strftime('%Y-%W', NEW.class_date)
              AND s.department = (
                  SELECT department FROM students WHERE student_id = NEW.student_id
              )
            GROUP BY s.department;
        END
        """,
        # Trigger 3 — audit trail on alert acknowledgment
        """
        CREATE TRIGGER IF NOT EXISTS audit_alert_ack
        AFTER UPDATE ON alerts
        WHEN NEW.acknowledged_at IS NOT NULL AND OLD.acknowledged_at IS NULL
        BEGIN
            INSERT INTO audit_log
                (actor_id, actor_role, action, entity_type, entity_id, old_values, new_values)
            VALUES (
                NEW.acknowledged_by, 'WARDEN', 'ACKNOWLEDGE_ALERT', 'alerts',
                CAST(NEW.id AS TEXT),
                json_object('status', OLD.status),
                json_object('status', NEW.status, 'acknowledged_at', NEW.acknowledged_at)
            );
        END
        """,
        # Trigger 4 — low attendance auto-alert
        """
        CREATE TRIGGER IF NOT EXISTS auto_alert_low_attendance
        AFTER INSERT ON attendance
        WHEN NEW.status = 'ABSENT'
        BEGIN
            INSERT INTO alerts (student_id, alert_type, severity, message, risk_score, created_at)
            SELECT
                NEW.student_id, 'LOW_ATTENDANCE', 'HIGH',
                'Attendance has dropped below 75% in ' || NEW.subject_code, 70.0, datetime('now')
            WHERE (
                SELECT ROUND(
                    100.0 * SUM(CASE WHEN status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
                          / COUNT(*), 1
                )
                FROM attendance
                WHERE student_id = NEW.student_id AND subject_code = NEW.subject_code
            ) < 75.0
            AND NOT EXISTS (
                SELECT 1 FROM alerts al
                WHERE al.student_id = NEW.student_id
                  AND al.alert_type = 'LOW_ATTENDANCE'
                  AND al.status = 'ACTIVE'
                  AND al.created_at >= datetime('now', '-24 hours')
            );
        END
        """,
    ]
    cur.execute("DROP TRIGGER IF EXISTS auto_alert_on_streak")
    cur.execute("DROP TRIGGER IF EXISTS refresh_mv_dept_attendance")
    cur.execute("DROP TRIGGER IF EXISTS audit_alert_ack")
    cur.execute("DROP TRIGGER IF EXISTS auto_alert_low_attendance")
    for block in trigger_blocks:
        cur.execute(block.strip())


def _seed_data(conn: sqlite3.Connection) -> dict:
    """
    Insert realistic demo data.  Returns row-count dict for reporting.
    Uses a fixed random seed for determinism.
    Uses explicit SAVEPOINTs to demonstrate transaction savepoint semantics.
    """
    rng = random.Random(42)
    cur = conn.cursor()
    counts: dict = {}

    # ── Departments ──────────────────────────────────────────────────────────
    cur.execute("SAVEPOINT sp_departments")
    depts = [
        ("CSE",  "Computer Science & Engineering"),
        ("ECE",  "Electronics & Communication Engineering"),
        ("MECH", "Mechanical Engineering"),
        ("IT",   "Information Technology"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO departments (dept_code, dept_name) VALUES (?,?)", depts
    )
    cur.execute("RELEASE SAVEPOINT sp_departments")
    counts["departments"] = len(depts)

    # ── Faculty ──────────────────────────────────────────────────────────────
    cur.execute("SAVEPOINT sp_faculty")
    faculty_rows = [
        # CSE
        ("FAC_CSE1", "Dr. Rajesh Kumar",    "rajesh.kumar@vit.ac.in",    "CSE",  "HOD"),
        ("FAC_CSE2", "Prof. Anitha Rajan",  "anitha.rajan@vit.ac.in",    "CSE",  "FACULTY"),
        ("FAC_CSE3", "Prof. Karthik Nair",  "karthik.nair@vit.ac.in",    "CSE",  "FACULTY"),
        # ECE
        ("FAC_ECE1", "Dr. Sunita Sharma",   "sunita.sharma@vit.ac.in",   "ECE",  "HOD"),
        ("FAC_ECE2", "Prof. Vivek Menon",   "vivek.menon@vit.ac.in",     "ECE",  "FACULTY"),
        ("FAC_ECE3", "Prof. Deepa Pillai",  "deepa.pillai@vit.ac.in",    "ECE",  "FACULTY"),
        # MECH
        ("FAC_MCH1", "Dr. Arun Prasad",     "arun.prasad@vit.ac.in",     "MECH", "HOD"),
        ("FAC_MCH2", "Prof. Latha Gopal",   "latha.gopal@vit.ac.in",     "MECH", "FACULTY"),
        ("FAC_MCH3", "Prof. Suresh Babu",   "suresh.babu@vit.ac.in",     "MECH", "FACULTY"),
        # IT
        ("FAC_IT1",  "Dr. Meera Nandakumar","meera.nandakumar@vit.ac.in","IT",   "HOD"),
        ("FAC_IT2",  "Prof. Ganesh Iyer",   "ganesh.iyer@vit.ac.in",     "IT",   "FACULTY"),
        ("FAC_IT3",  "Prof. Preethi Das",   "preethi.das@vit.ac.in",     "IT",   "FACULTY"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO faculty (faculty_id, full_name, email, department, role) "
        "VALUES (?,?,?,?,?)",
        faculty_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_faculty")
    counts["faculty"] = len(faculty_rows)

    # ── Wardens ──────────────────────────────────────────────────────────────
    cur.execute("SAVEPOINT sp_warden")
    warden_rows = [
        ("WRD_A", "Mr. Balu Krishnan",    "balu.krishnan@vit.ac.in", "9876543210", "A", "EVENING"),
        ("WRD_B", "Ms. Kavitha Selvam",   "kavitha.selvam@vit.ac.in","9876543211", "B", "NIGHT"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO warden (warden_id, full_name, email, phone, hostel_block, shift) "
        "VALUES (?,?,?,?,?,?)",
        warden_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_warden")
    counts["warden"] = len(warden_rows)

    # ── Subjects ─────────────────────────────────────────────────────────────
    cur.execute("SAVEPOINT sp_subjects")
    subjects_rows = [
        # CSE — semester 3
        ("CSE2001", "Data Structures & Algorithms", "CSE",  3, 4, "FAC_CSE2",
         json.dumps({"days": ["Mon","Wed","Fri"], "time": "09:00"})),
        ("CSE2002", "Operating Systems",            "CSE",  3, 3, "FAC_CSE3",
         json.dumps({"days": ["Tue","Thu"],       "time": "11:00"})),
        ("CSE2003", "Database Management Systems",  "CSE",  3, 4, "FAC_CSE1",
         json.dumps({"days": ["Mon","Wed"],       "time": "14:00"})),
        # ECE — semester 3
        ("ECE2001", "Digital Electronics",          "ECE",  3, 4, "FAC_ECE2",
         json.dumps({"days": ["Mon","Wed","Fri"], "time": "08:00"})),
        ("ECE2002", "Signals & Systems",            "ECE",  3, 3, "FAC_ECE3",
         json.dumps({"days": ["Tue","Thu"],       "time": "10:00"})),
        ("ECE2003", "Electromagnetic Theory",       "ECE",  3, 3, "FAC_ECE1",
         json.dumps({"days": ["Mon","Fri"],       "time": "13:00"})),
        # MECH — semester 3
        ("MCH2001", "Engineering Thermodynamics",   "MECH", 3, 4, "FAC_MCH2",
         json.dumps({"days": ["Mon","Wed","Fri"], "time": "09:00"})),
        ("MCH2002", "Fluid Mechanics",              "MECH", 3, 3, "FAC_MCH3",
         json.dumps({"days": ["Tue","Thu"],       "time": "11:00"})),
        ("MCH2003", "Theory of Machines",           "MECH", 3, 3, "FAC_MCH1",
         json.dumps({"days": ["Tue","Thu"],       "time": "14:00"})),
        # IT — semester 3
        ("IT2001",  "Computer Networks",            "IT",   3, 4, "FAC_IT2",
         json.dumps({"days": ["Mon","Wed","Fri"], "time": "08:00"})),
        ("IT2002",  "Web Technologies",             "IT",   3, 3, "FAC_IT3",
         json.dumps({"days": ["Tue","Thu"],       "time": "10:00"})),
        ("IT2003",  "Software Engineering",         "IT",   3, 3, "FAC_IT1",
         json.dumps({"days": ["Mon","Fri"],       "time": "14:00"})),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO subjects "
        "(subject_code, subject_name, department, semester, credits, faculty_id, schedule_json) "
        "VALUES (?,?,?,?,?,?,?)",
        subjects_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_subjects")
    counts["subjects"] = len(subjects_rows)

    # ── Students ─────────────────────────────────────────────────────────────
    # Department meta: (dept_code, prefix, section_pool)
    dept_meta = [
        ("CSE",  "21BCE", ["A","B","C"], "A"),
        ("ECE",  "21BEC", ["A","B"],     "B"),
        ("MECH", "21BME", ["A","B"],     "A"),
        ("IT",   "21BIT", ["A","B"],     "B"),
    ]
    # Subject map: dept → [subject_codes]
    dept_subjects = {
        "CSE":  ["CSE2001","CSE2002","CSE2003"],
        "ECE":  ["ECE2001","ECE2002","ECE2003"],
        "MECH": ["MCH2001","MCH2002","MCH2003"],
        "IT":   ["IT2001","IT2002","IT2003"],
    }
    # Faculty map for marking attendance: dept → faculty_id
    dept_faculty = {
        "CSE":  ["FAC_CSE1","FAC_CSE2","FAC_CSE3"],
        "ECE":  ["FAC_ECE1","FAC_ECE2","FAC_ECE3"],
        "MECH": ["FAC_MCH1","FAC_MCH2","FAC_MCH3"],
        "IT":   ["FAC_IT1","FAC_IT2","FAC_IT3"],
    }

    first_names = [
        "Aarav","Arjun","Vignesh","Siddharth","Rohan","Vikram","Karthik","Nikhil",
        "Aditya","Ravi","Priya","Ananya","Divya","Meghna","Sneha","Aishwarya",
        "Pooja","Lakshmi","Nithya","Kavya","Mohammed","Farhan","Rahul","Suresh",
        "Ganesh","Harish","Balaji","Prashanth","Deepak","Manoj",
    ]
    last_names = [
        "Kumar","Sharma","Patel","Nair","Reddy","Singh","Pillai","Iyer","Das","Menon",
        "Verma","Joshi","Rao","Krishnan","Selvam","Gopal","Prasad","Babu","Naik","Rajan",
    ]

    students_rows = []
    counter_per_dept = {d[0]: 1234 for d in dept_meta}

    # ── Special students (indices 0 and 1) ───────────────────────────────────
    # Index 0 → 21BCE1234  (CRITICAL — crisis student)
    # Index 1 → 21BCE1235  (HIGH — exam-anxiety student)
    special = [
        ("21BCE1234", "Arjun Sharma",   "arjun.sharma@vit.ac.in",   "9876500001",
         "CSE", 3, "A", "A", "A-101", "9811111111", "parent.sharma@gmail.com", 1),
        ("21BCE1235", "Priya Nair",     "priya.nair@vit.ac.in",     "9876500002",
         "CSE", 3, "A", "A", "A-102", "9822222222", "parent.nair@gmail.com",   1),
    ]
    for sp in special:
        students_rows.append(sp)
    counter_per_dept["CSE"] = 1236   # next CSE counter

    # ── Regular students ──────────────────────────────────────────────────────
    target = 50 - len(special)   # 48 more students
    per_dept = target // len(dept_meta)  # 12 each

    for dept_code, prefix, sections, hostel in dept_meta:
        for i in range(per_dept):
            sid = f"{prefix}{counter_per_dept[dept_code]}"
            counter_per_dept[dept_code] += 1
            fname = rng.choice(first_names)
            lname = rng.choice(last_names)
            name  = f"{fname} {lname}"
            email = f"{fname.lower()}.{lname.lower()}{rng.randint(1,99)}@vit.ac.in"
            phone = f"98765{rng.randint(10000,99999)}"
            sect  = rng.choice(sections)
            room  = f"{hostel}-{rng.randint(100,250)}"
            pp    = f"97{rng.randint(10000000,99999999)}"
            pe    = f"parent{rng.randint(1,999)}@gmail.com"
            students_rows.append((
                sid, name, email, phone, dept_code, 3, sect,
                hostel, room, pp, pe, 1,
            ))

    cur.execute("SAVEPOINT sp_students")
    cur.executemany(
        "INSERT OR IGNORE INTO students "
        "(student_id, full_name, email, phone, department, semester, section, "
        " hostel_block, room_number, parent_phone, parent_email, parent_consent) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        students_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_students")
    counts["students"] = len(students_rows)

    # ── Attendance records ────────────────────────────────────────────────────
    # Strategy:
    #   • Last 60 weekdays (Mon–Sat) treated as class days
    #   • Each student × each dept-subject × each class_day → 1 record
    #   • Base 80% PRESENT probability; 5% LATE; 3% EXCUSED; 2% ON_DUTY; rest ABSENT
    #   • Crisis student  (21BCE1234): last 5 days → ABSENT in ALL subjects
    #   • Exam-anxiety    (21BCE1235): last 2 weeks Monday absences (simulates exam avoidance)
    #   • 6 random students: <75% per subject to trigger LOW_ATTENDANCE alert

    today = date.today()
    class_days: list[date] = []
    d = today - timedelta(days=1)
    while len(class_days) < 60:
        if d.weekday() < 6:   # Mon=0 … Sat=5  (exclude Sunday only)
            class_days.append(d)
        d -= timedelta(days=1)
    class_days.reverse()  # chronological order

    # Pick 6 "low-attendance" students from the regular pool (not the two special ones)
    regular_ids = [r[0] for r in students_rows[2:]]
    low_att_ids = set(rng.sample(regular_ids, 6))

    # Pre-compute faculty for each subject (positional alignment with subjects_rows)
    subj_faculty = {
        r[0]: r[5] for r in subjects_rows  # subject_code → faculty_id
    }

    attendance_rows = []
    # Weekday name → period
    period_map = {"Mon":1,"Tue":2,"Wed":3,"Thu":4,"Fri":5,"Sat":6}
    week_short  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

    for stu in students_rows:
        sid   = stu[0]
        dept  = stu[4]
        subjs = dept_subjects[dept]
        facs  = dept_faculty[dept]

        for subj, fac in zip(subjs, facs):
            for cd in class_days:
                day_name = week_short[cd.weekday()]
                period   = period_map.get(day_name, 1)

                # ── Determine status ──────────────────────────────────────
                if sid == "21BCE1234" and cd >= today - timedelta(days=5):
                    status = "ABSENT"
                elif sid == "21BCE1235":
                    # Drop attendance last 2 weeks
                    if cd >= today - timedelta(days=14) and rng.random() < 0.80:
                        status = "ABSENT"
                    else:
                        r = rng.random()
                        status = ("PRESENT" if r < 0.82 else
                                  "LATE"    if r < 0.88 else
                                  "EXCUSED" if r < 0.91 else
                                  "ON_DUTY" if r < 0.93 else "ABSENT")
                elif sid in low_att_ids:
                    r = rng.random()
                    status = ("ABSENT"  if r < 0.35 else
                              "PRESENT" if r < 0.90 else
                              "LATE"    if r < 0.95 else "EXCUSED")
                else:
                    r = rng.random()
                    status = ("PRESENT" if r < 0.80 else
                              "LATE"    if r < 0.85 else
                              "EXCUSED" if r < 0.88 else
                              "ON_DUTY" if r < 0.90 else "ABSENT")

                attendance_rows.append((
                    sid, subj, cd.isoformat(), period, status, fac,
                    f"DEVICE_{rng.randint(1000,9999)}",
                ))

    # Disable triggers during bulk load to avoid O(n²) trigger overhead;
    # we will manually populate alerts and materialized views afterwards.
    # NOTE: executescript() issues an implicit COMMIT, so we drop triggers
    # using individual execute() calls to preserve the open savepoint.
    cur.execute("DROP TRIGGER IF EXISTS auto_alert_on_streak")
    cur.execute("DROP TRIGGER IF EXISTS refresh_mv_dept_attendance")
    cur.execute("DROP TRIGGER IF EXISTS auto_alert_low_attendance")
    cur.execute("SAVEPOINT sp_attendance_start")

    BATCH = 500
    for i in range(0, len(attendance_rows), BATCH):
        batch = attendance_rows[i : i + BATCH]
        cur.executemany(
            "INSERT OR IGNORE INTO attendance "
            "(student_id, subject_code, class_date, period, status, marked_by, device_info) "
            "VALUES (?,?,?,?,?,?,?)",
            batch,
        )
    cur.execute("RELEASE SAVEPOINT sp_attendance_start")
    counts["attendance"] = len(attendance_rows)

    # ── Re-create triggers after bulk seed ───────────────────────────────────
    # Use individual execute() calls to avoid executescript's implicit COMMIT.
    # SQLite CREATE TRIGGER is a single statement (even if multi-line), so
    # we split on the sentinel "END;" and execute each block individually.
    _recreate_triggers(cur)

    # ── Pre-populate mv_dept_attendance ──────────────────────────────────────
    cur.execute("SAVEPOINT sp_mv_dept")
    cur.execute("DELETE FROM mv_dept_attendance")
    cur.execute("""
        INSERT OR REPLACE INTO mv_dept_attendance (department, week, attendance_pct, total_classes, present_count)
        SELECT
            s.department,
            strftime('%Y-%W', a.class_date) AS week,
            ROUND(
                100.0 * SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
                      / COUNT(*),
                1
            ),
            COUNT(*),
            SUM(CASE WHEN a.status IN ('PRESENT','LATE','ON_DUTY') THEN 1 ELSE 0 END)
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        GROUP BY s.department, strftime('%Y-%W', a.class_date)
    """)
    cur.execute("RELEASE SAVEPOINT sp_mv_dept")

    # ── Pre-populate mv_risk_trend ────────────────────────────────────────────
    # We'll seed synthetic alert records first, then compute trend from them
    # (see alerts seeding below)

    # ── Alerts (manual seed — pre-existing alerts before trigger era) ────────
    cur.execute("SAVEPOINT sp_alerts")
    alert_rows = [
        # Crisis student — CRITICAL consecutive absences (already flagged)
        ("21BCE1234", "CONSECUTIVE_ABSENCE", "CRITICAL",
         "Student has 3+ consecutive absences across subjects", 85.0,
         "ACTIVE", None, None, None, None,
         (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")),
        ("21BCE1234", "LOW_ATTENDANCE", "HIGH",
         "Attendance has dropped below 75% in CSE2001", 70.0,
         "ACTIVE", None, None, None, None,
         (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")),
        # Exam-anxiety student
        ("21BCE1235", "LOW_ATTENDANCE", "HIGH",
         "Attendance has dropped below 75% in CSE2002", 70.0,
         "ACTIVE", None, None, None, None,
         (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")),
        ("21BCE1235", "EXAM_AVOIDANCE", "HIGH",
         "Student shows pattern of absence before/after exam dates", 75.0,
         "ACTIVE", None, None, None, None,
         (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")),
    ]
    # Generate alerts for low-attendance students
    for low_sid in low_att_ids:
        # Find their department's first subject
        dept = next(r[4] for r in students_rows if r[0] == low_sid)
        subj = dept_subjects[dept][0]
        alert_rows.append((
            low_sid, "LOW_ATTENDANCE", "HIGH",
            f"Attendance has dropped below 75% in {subj}", 68.0,
            "ACTIVE", None, None, None, None,
            (datetime.now() - timedelta(hours=rng.randint(1,48))).strftime("%Y-%m-%d %H:%M:%S"),
        ))
    # Add a few historical resolved alerts for audit/trend
    historical = [
        ("21BCE1234", "LOW_ATTENDANCE",      "MEDIUM",
         "Attendance dipped below 80% in CSE2003", 55.0,
         "RESOLVED", "WRD_A",
         (datetime.now()-timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
         (datetime.now()-timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"),
         "Student was hospitalised; situation resolved",
         (datetime.now()-timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")),
        ("21BCE1235", "CONSECUTIVE_ABSENCE", "HIGH",
         "3 consecutive absences detected",            72.0,
         "ACKNOWLEDGED", "WRD_B",
         (datetime.now()-timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),
         None, None,
         (datetime.now()-timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")),
    ]
    # Insert current alerts (11 cols minus id)
    cur.executemany(
        "INSERT OR IGNORE INTO alerts "
        "(student_id, alert_type, severity, message, risk_score, status, "
        " acknowledged_by, acknowledged_at, resolved_at, resolution_notes, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        alert_rows,
    )
    # Insert historical alerts
    cur.executemany(
        "INSERT OR IGNORE INTO alerts "
        "(student_id, alert_type, severity, message, risk_score, status, "
        " acknowledged_by, acknowledged_at, resolved_at, resolution_notes, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        historical,
    )
    cur.execute("RELEASE SAVEPOINT sp_alerts")
    counts["alerts"] = len(alert_rows) + len(historical)

    # ── mv_risk_trend (last 14 days from seeded alerts) ───────────────────────
    cur.execute("SAVEPOINT sp_mv_risk")
    cur.execute("DELETE FROM mv_risk_trend")
    cur.execute("""
        INSERT OR REPLACE INTO mv_risk_trend (day, critical_count, high_count, medium_count, low_count)
        SELECT
            date(created_at)                                             AS day,
            SUM(CASE WHEN severity='CRITICAL' THEN 1 ELSE 0 END)        AS critical_count,
            SUM(CASE WHEN severity='HIGH'     THEN 1 ELSE 0 END)        AS high_count,
            SUM(CASE WHEN severity='MEDIUM'   THEN 1 ELSE 0 END)        AS medium_count,
            SUM(CASE WHEN severity='LOW'      THEN 1 ELSE 0 END)        AS low_count
        FROM alerts
        GROUP BY date(created_at)
    """)
    cur.execute("RELEASE SAVEPOINT sp_mv_risk")

    # ── Absence patterns ──────────────────────────────────────────────────────
    cur.execute("SAVEPOINT sp_patterns")
    pattern_rows = [
        ("21BCE1234", "CONSECUTIVE_ABSENCE", "CRITICAL", 85.0,
         json.dumps({"streak_days": 5, "subjects_affected": 3}), "ONGOING"),
        ("21BCE1234", "LOW_ATTENDANCE",      "HIGH",     70.0,
         json.dumps({"subject": "CSE2001", "current_pct": 62.0}), "ONGOING"),
        ("21BCE1235", "EXAM_AVOIDANCE",      "HIGH",     75.0,
         json.dumps({"exam_weeks": ["2026-W41","2026-W42"], "absence_pct": 80.0}), "ONGOING"),
        ("21BCE1235", "LOW_ATTENDANCE",      "HIGH",     70.0,
         json.dumps({"subject": "CSE2002", "current_pct": 55.0}), "ONGOING"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO absence_patterns "
        "(student_id, pattern_type, severity, risk_score, details_json, resolution) "
        "VALUES (?,?,?,?,?,?)",
        pattern_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_patterns")
    counts["absence_patterns"] = len(pattern_rows)

    # ── Welfare visits ────────────────────────────────────────────────────────
    cur.execute("SAVEPOINT sp_welfare")
    # Get alert IDs
    crisis_alert_id = cur.execute(
        "SELECT id FROM alerts WHERE student_id='21BCE1234' AND alert_type='CONSECUTIVE_ABSENCE' LIMIT 1"
    ).fetchone()
    visit_rows = []
    if crisis_alert_id:
        visit_rows.append((
            crisis_alert_id[0], "WRD_A",
            (today - timedelta(days=1)).isoformat(), "19:30",
            1, "DISTRESSED",
            "Student found in room, appears stressed about exams. Counselling recommended.",
            1, (today + timedelta(days=1)).isoformat(),
        ))
    cur.executemany(
        "INSERT OR IGNORE INTO welfare_visits "
        "(alert_id, warden_id, visit_date, visit_time, student_found, student_condition, "
        " notes, follow_up_required, follow_up_date) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        visit_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_welfare")
    counts["welfare_visits"] = len(visit_rows)

    # ── Hostel logs (5 entries per student, last 7 days) ─────────────────────
    cur.execute("SAVEPOINT sp_hostel")
    hostel_rows = []
    gates   = ["GATE_A1","GATE_A2","GATE_B1","GATE_B2"]
    methods = ["CARD","BIOMETRIC","MOBILE_APP"]
    for stu in students_rows:
        sid   = stu[0]
        block = stu[7] or "A"
        gate_pool = [g for g in gates if g.startswith(f"GATE_{block}")]
        for offset in range(7):
            day = today - timedelta(days=offset)
            # EXIT in morning
            ts_exit  = datetime(day.year, day.month, day.day,
                                rng.randint(7,9), rng.randint(0,59))
            # ENTRY in evening
            ts_entry = datetime(day.year, day.month, day.day,
                                rng.randint(17,22), rng.randint(0,59))
            gate = rng.choice(gate_pool) if gate_pool else "GATE_A1"
            method = rng.choice(methods)
            hostel_rows.append((sid, gate, "EXIT",  ts_exit.strftime("%Y-%m-%d %H:%M:%S"),  method))
            hostel_rows.append((sid, gate, "ENTRY", ts_entry.strftime("%Y-%m-%d %H:%M:%S"), method))
    cur.executemany(
        "INSERT OR IGNORE INTO hostel_logs (student_id, gate_id, direction, timestamp, method) "
        "VALUES (?,?,?,?,?)",
        hostel_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_hostel")
    counts["hostel_logs"] = len(hostel_rows)

    # ── LMS activity (3–5 records per student, last 14 days) ─────────────────
    cur.execute("SAVEPOINT sp_lms")
    lms_rows = []
    act_types = ["LOGIN","ASSIGNMENT_SUBMIT","QUIZ_ATTEMPT","FORUM_POST","VIDEO_WATCH","DOWNLOAD"]
    for stu in students_rows:
        sid   = stu[0]
        dept  = stu[4]
        subjs = dept_subjects[dept]
        n     = rng.randint(3, 5)
        for _ in range(n):
            offset = rng.randint(0, 13)
            ts = datetime.now() - timedelta(days=offset,
                                            hours=rng.randint(0,23),
                                            minutes=rng.randint(0,59))
            act  = rng.choice(act_types)
            subj = rng.choice(subjs)
            dur  = rng.randint(30, 3600)
            lms_rows.append((sid, act, subj, ts.strftime("%Y-%m-%d %H:%M:%S"), dur))
    cur.executemany(
        "INSERT OR IGNORE INTO lms_activity (student_id, activity_type, subject_code, timestamp, duration_seconds) "
        "VALUES (?,?,?,?,?)",
        lms_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_lms")
    counts["lms_activity"] = len(lms_rows)

    # ── Users (auth) ──────────────────────────────────────────────────────────
    cur.execute("SAVEPOINT sp_users")
    pw = _hash("demo123")
    user_rows = [
        ("USR_ADMIN",    "admin",        pw, "ADMIN",   None),
        ("USR_WRD_A",    "warden_a",     pw, "WARDEN",  "WRD_A"),
        ("USR_WRD_B",    "warden_b",     pw, "WARDEN",  "WRD_B"),
        ("USR_FAC_CSE1", "faculty_cse1", pw, "FACULTY", "FAC_CSE1"),
        ("USR_FAC_ECE1", "faculty_ece1", pw, "FACULTY", "FAC_ECE1"),
        ("USR_FAC_MCH1", "faculty_mech1",pw, "FACULTY", "FAC_MCH1"),
        ("USR_FAC_IT1",  "faculty_it1",  pw, "FACULTY", "FAC_IT1"),
        ("USR_STU_1234", "21BCE1234",    pw, "STUDENT", "21BCE1234"),
        ("USR_STU_1235", "21BCE1235",    pw, "STUDENT", "21BCE1235"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO users (user_id, username, password_hash, role, linked_id) "
        "VALUES (?,?,?,?,?)",
        user_rows,
    )
    cur.execute("RELEASE SAVEPOINT sp_users")
    counts["users"] = len(user_rows)

    # ── Final audit_log bootstrap entry ──────────────────────────────────────
    cur.execute("SAVEPOINT sp_audit")
    cur.execute(
        "INSERT OR IGNORE INTO audit_log "
        "(actor_id, actor_role, action, entity_type, entity_id, new_values) "
        "VALUES (?,?,?,?,?,?)",
        ("USR_ADMIN","ADMIN","DB_INIT","system","1",
         json.dumps({"info": "Database initialized by init_db.py"})),
    )
    cur.execute("RELEASE SAVEPOINT sp_audit")
    counts["audit_log"] = 1

    counts["mv_dept_attendance"] = cur.execute(
        "SELECT COUNT(*) FROM mv_dept_attendance"
    ).fetchone()[0]
    counts["mv_risk_trend"] = cur.execute(
        "SELECT COUNT(*) FROM mv_risk_trend"
    ).fetchone()[0]

    return counts


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

def init_database(db_path: str = "attendance.db") -> None:
    """
    Idempotent database initializer.

    Execution order
    ───────────────
    1. Open SQLite connection, enable WAL journal mode
    2. Enable foreign-key enforcement
    3. CREATE TABLE … IF NOT EXISTS  (TABLES_DDL)
    4. CREATE TRIGGER … (TRIGGERS_DDL)
    5. CREATE VIEW …    (VIEWS_DDL)
    6. CREATE INDEX …   (INDEXES_DDL)
    7. Seed data inside a savepoint-aware transaction
    8. Commit & close
    """
    print(f"[init_db] Opening database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # ── 1. WAL mode for concurrent read performance ────────────────────
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        # ── 2. Foreign-key enforcement ─────────────────────────────────────
        conn.execute("PRAGMA foreign_keys=ON")

        # ── 3–6. Schema DDL (tables → triggers → views → indexes) ─────────
        print("[init_db] Creating tables …")
        conn.executescript(TABLES_DDL)

        print("[init_db] Creating triggers …")
        _recreate_triggers(conn.cursor())

        print("[init_db] Creating views …")
        conn.executescript(VIEWS_DDL)

        print("[init_db] Creating indexes …")
        conn.executescript(INDEXES_DDL)

        # ── 7. Seed data inside an explicit transaction ────────────────────
        print("[init_db] Seeding data …")
        conn.execute("BEGIN")
        counts = _seed_data(conn)
        conn.execute("COMMIT")

        # ── 8. Report ───────────────────────────────────────────────────────
        total_rows = sum(counts.values())
        print(f"\n\033[1;30;42m ✓ DATABASE INITIALIZED SUCCESSFULLY \033[0m\n")
        print(f"\033[1;96m{'Table Name':<25} {'Records Added':>15}\033[0m")
        print("\033[90m" + "─" * 42 + "\033[0m")
        for tbl, cnt in sorted(counts.items()):
            print(f"  \033[1m{tbl:<23}\033[0m \033[1;92m{cnt:>13,} records\033[0m")
        print("\033[90m" + "─" * 42 + "\033[0m")
        print(f"  \033[1;97m{'TOTAL RECORDS ADDED':<23}\033[0m \033[1;30;43m {total_rows:>10,} records \033[0m\n")

    except Exception as exc:
        conn.execute("ROLLBACK")
        print(f"[init_db] ✗ Error: {exc}")
        raise
    finally:
        conn.close()
        print("\n[init_db] Connection closed.")


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    db_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "attendance.db"
    )
    if os.path.exists(db_path):
        os.remove(db_path)
        print("Removed existing database.")
    init_database(db_path)

    print("\nDemo accounts (password: demo123):")
    print("  admin        → Admin dashboard")
    print("  warden_a     → Warden dashboard  (Hostel A)")
    print("  warden_b     → Warden dashboard  (Hostel B)")
    print("  faculty_cse1 → Faculty attendance marking (CSE)")
    print("  21BCE1234    → Student portal  ⚠ CRITICAL risk")
    print("  21BCE1235    → Student portal  ⚠ HIGH risk (exam anxiety)")
