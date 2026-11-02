"""
dashboard.py — Streamlit UI for the Attendance System.
Designed with Apple Human Interface Guidelines:
  • Centered 1120px container with 16px grid alignment
  • Flat Apple Light Mode palette (#F5F5F7 canvas, #FFFFFF elevated cards)
  • Centered Apple Segmented Control switcher navigation
  • Interactive 3D WebGL (Three.js) visualizations for each database subsystem
  • Zero descriptive fluff / subtext — pure focus on database operations & visualizers
  • Architecture: Database logic in db.py, 3D WebGL in viz3d.py
"""

import os
import streamlit as st
import pandas as pd
import db
import init_db

# Safe import of 3D WebGL engine
try:
    import viz3d
    HAS_VIZ3D = True
except Exception:
    HAS_VIZ3D = False

# Auto-initialize database on cloud platforms if attendance.db does not exist yet
if not os.path.exists(db.DB_PATH):
    with st.spinner("Setting up database for first-time launch..."):
        init_db.init_database(db.DB_PATH)

# -----------------------------------------------------------------------------
# Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Student Attendance & Welfare Management",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -----------------------------------------------------------------------------
# Apple Design System CSS (HIG Compliant · 16px Spatial Grid · No Subtext)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", sans-serif;
        color: #1D1D1F;
        letter-spacing: -0.011em;
    }

    .stApp {
        background-color: #F5F5F7;
    }

    /* Centered 1120px Container */
    .main .block-container {
        max-width: 1120px !important;
        padding-top: 28px !important;
        padding-bottom: 60px !important;
        padding-left: 24px !important;
        padding-right: 24px !important;
        margin: 0 auto !important;
    }

    /* Apple Minimal Hero */
    .apple-header {
        text-align: center;
        margin-bottom: 24px;
    }
    .apple-eyebrow {
        display: inline-block;
        font-size: 11.5px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #0071E3;
        background: #EBF4FF;
        padding: 4px 12px;
        border-radius: 9999px;
        margin-bottom: 8px;
    }
    .apple-title {
        font-size: 30px;
        font-weight: 700;
        letter-spacing: -0.024em;
        color: #1D1D1F;
        margin: 0;
    }

    /* Apple Metric Cards */
    div[data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid #E5E5EA !important;
        border-radius: 16px !important;
        padding: 16px 20px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03), 0 4px 12px rgba(0,0,0,0.02) !important;
        transition: transform 0.2s cubic-bezier(0.2, 0.8, 0.4, 1), box-shadow 0.2s ease !important;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.06) !important;
    }
    div[data-testid="stMetric"] label {
        color: #86868B !important;
        font-size: 12.5px !important;
        font-weight: 500 !important;
        text-transform: none !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #1D1D1F !important;
        font-size: 26px !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    /* Apple Segmented Control / Pill Bar Switcher */
    .stTabs [data-baseweb="tab-list"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        background: #E5E5EA !important;
        padding: 4px !important;
        border-radius: 9999px !important;
        border: 1px solid rgba(0,0,0,0.04) !important;
        margin: 0 auto 24px auto !important;
        max-width: 960px !important;
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.06) !important;
        gap: 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        border: none !important;
        border-radius: 9999px !important;
        background: transparent !important;
        color: #6E6E73 !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        padding: 7px 18px !important;
        transition: all 0.2s cubic-bezier(0.2, 0.8, 0.4, 1) !important;
        white-space: nowrap !important;
    }
    .stTabs [aria-selected="true"] {
        background: #FFFFFF !important;
        color: #1D1D1F !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08), 0 0 1px rgba(0, 0, 0, 0.04) !important;
    }
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Apple Elevated Card Box */
    .apple-card {
        background: #FFFFFF;
        border: 1px solid #E5E5EA;
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02), 0 4px 12px rgba(0,0,0,0.02);
    }
    .apple-card-title {
        font-size: 16.5px;
        font-weight: 600;
        letter-spacing: -0.016em;
        color: #1D1D1F;
        margin: 0;
    }

    /* 3D Visualizer Card Container */
    .viz-card {
        background: #FFFFFF;
        border: 1px solid #E5E5EA;
        border-radius: 16px;
        padding: 8px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02), 0 4px 12px rgba(0,0,0,0.02);
        overflow: hidden;
    }

    /* Apple System Buttons */
    .stButton > button {
        background-color: #0071E3 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 8px 18px !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        box-shadow: 0 1px 2px rgba(0, 113, 227, 0.15) !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        background-color: #0077ED !important;
        box-shadow: 0 4px 12px rgba(0, 113, 227, 0.25) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button:active {
        transform: translateY(0px) !important;
        background-color: #0062C4 !important;
    }

    /* Apple Inputs & Selectboxes */
    div[data-baseweb="select"] > div,
    input[type="text"],
    input[type="number"],
    div[data-baseweb="input"] > div {
        border-radius: 10px !important;
        border: 1px solid #D2D2D7 !important;
        background-color: #FFFFFF !important;
        font-size: 13.5px !important;
        color: #1D1D1F !important;
    }
    div[data-baseweb="select"] > div:focus-within,
    input:focus {
        border-color: #0071E3 !important;
        box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15) !important;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #E5E5EA !important;
        border-radius: 14px !important;
        background-color: #FFFFFF !important;
    }

    div[data-testid="stExpander"] {
        border: 1px solid #E5E5EA !important;
        border-radius: 14px !important;
        background: #FFFFFF !important;
        margin-top: 14px !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Top Hero & Summary Stats
# -----------------------------------------------------------------------------
st.markdown("""
<div class="apple-header">
    <span class="apple-eyebrow">Database Systems Project · VIT Vellore</span>
    <h1 class="apple-title">Student Welfare & Attendance Platform</h1>
</div>
""", unsafe_allow_html=True)

total_students, total_records, total_alerts, avg_att = db.get_summary_stats()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Enrolled Students", total_students)
c2.metric("Attendance Records", f"{total_records:,}")
c3.metric("Active Alerts", total_alerts)
c4.metric("Cohort Attendance", f"{avg_att}%")

st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Apple Segmented Control / Pill Bar Switcher
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Live Attendance & Alerts",
    "Query Performance",
    "Rollback & History",
    "Department Analytics",
    "Database Schema"
])

# =============================================================================
# TAB 1 — Live Attendance & Alerts
# =============================================================================
with tab1:
    # 3D WebGL Reactor
    if HAS_VIZ3D:
        st.markdown('<div class="viz-card">', unsafe_allow_html=True)
        viz3d.render_trigger_3d()
        st.markdown('</div>', unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1.4], gap="medium")

    with col_left:
        st.markdown('<div class="apple-card"><h3 class="apple-card-title">Mark Attendance</h3></div>', unsafe_allow_html=True)

        students = db.get_all_students()
        subjects = db.get_all_subjects()

        student_list = [f"{s[0]} — {s[1]}" for s in students]
        subject_list = [f"{s[0]} ({s[1]})" for s in subjects]

        chosen_student = st.selectbox("Student", student_list)
        chosen_subject = st.selectbox("Course Code", subject_list)
        chosen_status  = st.selectbox("Status", ["PRESENT", "ABSENT", "LATE"], index=1)

        if st.button("Record Attendance", use_container_width=True):
            sid  = chosen_student.split(" — ")[0]
            subj = chosen_subject.split(" ")[0]
            try:
                period, absences, triggered = db.record_attendance(sid, subj, chosen_status)
                st.success(f"Recorded: Period {period} marked {chosen_status}.")
                st.info(f"Student {sid} has {absences} absence(s) in rolling 3-day window.")
                new_row = db.run_raw_query(f"SELECT id, student_id, subject_code, class_date, period, status, marked_by FROM attendance WHERE student_id='{sid}' ORDER BY id DESC LIMIT 1")
                st.markdown("✨ **Highlighted Record Added to Database:**")
                st.dataframe(new_row, use_container_width=True, hide_index=True)
                if triggered:
                    st.warning("Trigger Fired: Critical welfare alert created autonomously.")
            except Exception as e:
                st.error(f"Error: {e}")

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        if st.button("⚡ Run Consecutive Streak Trigger Demo", use_container_width=True):
            conn = db.get_conn()
            max_id = conn.execute("SELECT COALESCE(MAX(id),0) FROM attendance").fetchone()[0]
            max_alert_id = conn.execute("SELECT COALESCE(MAX(id),0) FROM alerts").fetchone()[0]
            conn.close()

            log = db.run_trigger_demo()
            for line in log:
                if "Trigger fired" in line:
                    st.success(f"🔔 {line}")
                else:
                    st.write(f"• {line}")

            new_records = db.run_raw_query(f"SELECT id, student_id, subject_code, class_date, period, status, marked_by FROM attendance WHERE id > {max_id}")
            if not new_records.empty:
                st.markdown("➕ **Highlighted Records Added to `attendance`:**")
                st.dataframe(new_records, use_container_width=True, hide_index=True)

            new_alert = db.run_raw_query(f"SELECT id, student_id, alert_type, severity, message, risk_score FROM alerts WHERE id > {max_alert_id}")
            if not new_alert.empty:
                st.markdown("🚨 **Highlighted Record Autonomously Added to `alerts`:**")
                st.dataframe(new_alert, use_container_width=True, hide_index=True)

    with col_right:
        st.markdown('<div class="apple-card"><h3 class="apple-card-title">Active Alerts</h3></div>', unsafe_allow_html=True)

        alerts_df = db.get_active_alerts()
        st.dataframe(alerts_df, use_container_width=True, hide_index=True)

        ack_col, res_col = st.columns(2, gap="small")
        with ack_col:
            if len(alerts_df) > 0:
                alert_id = st.number_input("Alert ID", min_value=1, step=1, value=int(alerts_df["id"].iloc[0]))
                if st.button("Acknowledge Alert", use_container_width=True):
                    db.acknowledge_alert(alert_id)
                    st.success(f"Alert #{alert_id} acknowledged.")
                    st.rerun()

        with res_col:
            resolve_sid = st.selectbox("Student", [s[0] for s in students], key="resolve_student")
            if st.button("Resolve All Alerts", use_container_width=True):
                count = db.resolve_all_alerts(resolve_sid)
                st.success(f"Resolved {count} alert(s) for {resolve_sid}")
                st.rerun()

        with st.expander("Trigger DDL (auto_alert_on_streak)"):
            st.code("""
CREATE TRIGGER auto_alert_on_streak
AFTER INSERT ON attendance
WHEN NEW.status = 'ABSENT'
BEGIN
    INSERT INTO alerts (student_id, alert_type, severity, message, risk_score)
    SELECT NEW.student_id, 'CONSECUTIVE_ABSENCE', 'CRITICAL',
           'Student has 3+ consecutive absences', 85.0
    WHERE (
        SELECT COUNT(*) FROM attendance
        WHERE student_id = NEW.student_id
          AND status = 'ABSENT'
          AND class_date >= date(NEW.class_date, '-3 days')
    ) >= 3
    AND NOT EXISTS (
        SELECT 1 FROM alerts
        WHERE student_id = NEW.student_id
          AND alert_type = 'CONSECUTIVE_ABSENCE'
          AND status = 'ACTIVE'
          AND created_at >= datetime('now', '-24 hours')
    );
END;
            """, language="sql")


# =============================================================================
# TAB 2 — Query Performance & Optimizer
# =============================================================================
with tab2:
    # 3D WebGL B+ Tree Hierarchy
    if HAS_VIZ3D:
        st.markdown('<div class="viz-card">', unsafe_allow_html=True)
        viz3d.render_btree_3d()
        st.markdown('</div>', unsafe_allow_html=True)

    c_input, _ = st.columns([1, 2])
    with c_input:
        student_id = st.text_input("Benchmark Student ID", value="21BCE1234")

    q_indexed = f"SELECT * FROM attendance WHERE student_id = '{student_id}' AND class_date >= date('now','-30 days') ORDER BY class_date DESC"
    q_scan    = f"SELECT * FROM attendance WHERE +student_id = '{student_id}' AND class_date >= date('now','-30 days')"

    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        st.markdown("**B+ Tree Index Scan**")
        plan = db.get_query_plan(q_indexed)
        st.dataframe(plan[["detail"]], use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("**Sequential Table Scan**")
        plan2 = db.get_query_plan(q_scan)
        st.dataframe(plan2[["detail"]], use_container_width=True, hide_index=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    if st.button("▶ Run 50-Iteration Benchmark"):
        with st.spinner("Executing benchmark..."):
            avg_indexed, avg_scan = db.benchmark_query(student_id)
            speedup = avg_scan / avg_indexed if avg_indexed > 0 else 1
            m1, m2, m3 = st.columns(3)
            m1.metric("B+ Tree Index", f"{avg_indexed:.2f} µs")
            m2.metric("Sequential Scan", f"{avg_scan:.2f} µs")
            m3.metric("Speedup", f"{speedup:.1f}x Faster")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    if st.button("🔨 Drop Index → Evaluate Plan → Recreate"):
        before, dropped, after = db.drop_and_recreate_index(student_id)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Initial (Indexed)**")
            st.code(before)
        with c2:
            st.markdown("**Index Dropped (Degraded)**")
            st.code(dropped)
        with c3:
            st.markdown("**Recreated (Restored)**")
            st.code(after)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    st.markdown("##### System Indexes")
    st.dataframe(db.get_all_indexes(), use_container_width=True, hide_index=True)


# =============================================================================
# TAB 3 — Rollback & Savepoints (ACID)
# =============================================================================
with tab3:
    # 3D WebGL Transaction Frame Stack
    if HAS_VIZ3D:
        st.markdown('<div class="viz-card">', unsafe_allow_html=True)
        viz3d.render_savepoint_3d()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("##### Recent Records (21BCE1234)")
    st.dataframe(db.get_recent_records_for_student("21BCE1234"), use_container_width=True, hide_index=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1.3], gap="medium")

    with col1:
        if st.button("Run Savepoint Rollback Demo", use_container_width=True):
            log = db.run_savepoint_demo()
            st.session_state["tx_log"] = log
            st.success("Transaction cycle complete.")

    with col2:
        if "tx_log" in st.session_state:
            st.markdown("**Transaction Execution Log:**")
            for line in st.session_state["tx_log"]:
                st.write(f"• {line}")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="apple-card"><h3 class="apple-card-title">Atomic Batch Insertion</h3></div>', unsafe_allow_html=True)

    all_students = db.get_all_students()
    all_subjects = db.get_all_subjects()

    b1, b2, b3, b4, b5 = st.columns(5)
    batch_sid    = b1.selectbox("Student", [s[0] for s in all_students], key="batch_sid")
    batch_subj   = b2.selectbox("Course", [s[0] for s in all_subjects], key="batch_subj")
    batch_date   = b3.date_input("Start Date", key="batch_date")
    batch_days   = b4.number_input("Days", min_value=1, max_value=10, value=3, step=1)
    batch_status = b5.selectbox("Status", ["PRESENT", "ABSENT", "LATE"], key="batch_status")

    if st.button("Insert Batch Records"):
        try:
            conn = db.get_conn()
            max_id = conn.execute("SELECT COALESCE(MAX(id),0) FROM attendance").fetchone()[0]
            conn.close()
            inserted, log = db.insert_batch_records(batch_sid, batch_subj, batch_date, int(batch_days), batch_status)
            st.success(f"Committed {inserted} attendance record(s).")
            batch_df = db.run_raw_query(f"SELECT id, student_id, subject_code, class_date, period, status FROM attendance WHERE id > {max_id}")
            if not batch_df.empty:
                st.markdown("💾 **Highlighted Batch Records Added to Database:**")
                st.dataframe(batch_df, use_container_width=True, hide_index=True)
            with st.expander("Executed SQL Statements"):
                for line in log:
                    st.code(line, language="sql")
        except Exception as e:
            st.error(f"Transaction Aborted: {e}")

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    st.markdown("##### Audit Trail")
    try:
        st.dataframe(db.get_audit_log(), use_container_width=True, hide_index=True)
    except Exception:
        st.info("No audit log entries.")


# =============================================================================
# TAB 4 — Department Analytics & Views
# =============================================================================
with tab4:
    # 3D WebGL Multi-Dimensional Cube
    if HAS_VIZ3D:
        st.markdown('<div class="viz-card">', unsafe_allow_html=True)
        viz3d.render_materialized_cube_3d()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("##### At-Risk Student Cohort (student_risk View)")
    st.dataframe(db.get_risk_report(), use_container_width=True, hide_index=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2, gap="medium")

    with col_l:
        st.markdown("**Departmental Attendance (mv_dept_attendance)**")
        dept_df = db.get_dept_avg_attendance()
        st.bar_chart(dept_df.set_index("department")["avg_att"], color="#0071E3")

    with col_r:
        st.markdown("**Cohort Risk Tier Distribution**")
        risk_dist = db.get_risk_distribution()
        st.bar_chart(risk_dist.set_index("risk_level")["count"], color="#34C759")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("##### Subject-Level Breakdown")
    subjects = db.get_all_subjects()
    chosen_subj = st.selectbox("Course Code", [f"{s[0]} — {s[1]}" for s in subjects], key="subj_breakdown")
    subj_code = chosen_subj.split(" — ")[0]
    st.dataframe(db.get_subject_breakdown(subj_code), use_container_width=True, hide_index=True)

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    col_btn1, col_btn2 = st.columns(2, gap="medium")

    with col_btn1:
        if st.button("🔄 Trigger Materialized View Refresh", use_container_width=True):
            before, after = db.refresh_materialized_views()
            st.success("Refreshed via trigger.")
            st.write("Before:", before)
            st.write("After:", after)

    with col_btn2:
        if st.button("📤 Export Risk Report (CSV)", use_container_width=True):
            export_df = db.run_raw_query("SELECT * FROM student_risk")
            csv = export_df.to_csv(index=False)
            st.text_area("CSV Export", csv, height=160)


# =============================================================================
# TAB 5 — Database Schema Explorer
# =============================================================================
with tab5:
    # 3D WebGL Relational Topology Graph
    if HAS_VIZ3D:
        st.markdown('<div class="viz-card">', unsafe_allow_html=True)
        viz3d.render_schema_graph_3d()
        st.markdown('</div>', unsafe_allow_html=True)

    tables = db.get_all_tables()
    chosen_table = st.selectbox("Relational Table", tables, index=tables.index("attendance") if "attendance" in tables else 0)

    cols, fks, row_count = db.get_table_info(chosen_table)
    st.markdown(f"**Table:** `{chosen_table}` &nbsp;|&nbsp; **Rows:** `{row_count:,}`")

    left, right = st.columns([2, 1], gap="medium")
    with left:
        st.markdown("**Column Schema**")
        st.dataframe(cols[["cid", "name", "type", "notnull", "pk"]], use_container_width=True, hide_index=True)
    with right:
        st.markdown("**Foreign Key Constraints**")
        if len(fks) > 0:
            st.dataframe(fks[["table", "from", "to"]], use_container_width=True, hide_index=True)
        else:
            st.info("No foreign keys.")

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    col_b1, col_b2, col_b3 = st.columns(3, gap="small")

    with col_b1:
        if st.button("Analyze Table Statistics", use_container_width=True):
            rows, col_c, idx_c = db.analyze_table(chosen_table)
            st.metric("Total Rows", rows)
            st.metric("Total Columns", col_c)
            st.metric("Index Coverage", idx_c)

    with col_b2:
        if st.button("Test Foreign Key Constraint", use_container_width=True):
            blocked, message = db.test_fk_constraint()
            if blocked:
                st.error(f"Rejected: {message}")
            else:
                st.warning(message)

    with col_b3:
        if st.button("View Database Triggers", use_container_width=True):
            for name, sql in db.get_all_triggers():
                with st.expander(f"Trigger: {name}"):
                    st.code(sql, language="sql")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("##### SQL Console")

    p1, p2, p3 = st.columns(3)
    if p1.button("Critical Risk Students", use_container_width=True):
        st.session_state["console_sql"] = "SELECT student_id, full_name, attendance_pct, risk_level FROM student_risk WHERE risk_level = 'CRITICAL';"
    if p2.button("Trigger Definitions", use_container_width=True):
        st.session_state["console_sql"] = "SELECT name, sql FROM sqlite_master WHERE type = 'trigger';"
    if p3.button("Index Catalog", use_container_width=True):
        st.session_state["console_sql"] = "SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL ORDER BY tbl_name;"

    default_sql = st.session_state.get("console_sql", "SELECT student_id, full_name, department FROM students LIMIT 5;")
    sql_input = st.text_area("SQL Statement", value=default_sql, height=90)

    if st.button("Execute SQL"):
        try:
            result = db.run_raw_query(sql_input)
            st.dataframe(result, use_container_width=True)
        except Exception as e:
            st.error(f"SQL Error: {e}")

# -----------------------------------------------------------------------------
# Footer
# -----------------------------------------------------------------------------
st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; color: #86868B; font-size: 13px; border-top: 1px solid #E5E5EA; padding-top: 20px;">
    VIT Vellore · Database Systems (BACSE202) Project · SQLite 3 WAL Storage Engine
</div>
""", unsafe_allow_html=True)
