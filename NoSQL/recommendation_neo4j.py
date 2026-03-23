#!/usr/bin/env python3
"""
Doctor Recommendation System (Polyglot Persistence demo)

End-to-end flow:
1) Read relational data from SQL Server
2) Sync entities/relations into Neo4j
3) Run recommendation query for a given patient_id

Usage:
  python NoSQL/recommendation_neo4j.py 1
  python NoSQL/recommendation_neo4j.py 2 --top-k 3 --reset-graph

Required packages:
  pip install pyodbc neo4j
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import os
import sys
from typing import Any

try:
    import pyodbc
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit("Missing dependency: pyodbc. Install via `pip install pyodbc`.") from exc

try:
    from neo4j import GraphDatabase
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit("Missing dependency: neo4j. Install via `pip install neo4j`.") from exc


def build_sqlserver_connection_string() -> str:
    """Build SQL Server connection string from env vars."""
    direct = os.getenv("SQLSERVER_CONNECTION_STRING")
    if direct:
        return direct

    server = os.getenv("SQLSERVER_SERVER", "mcruebs04.isad.isadroot.ex.ac.uk")
    database = os.getenv("SQLSERVER_DATABASE", "")
    uid = os.getenv("SQLSERVER_UID", "")
    pwd = os.getenv("SQLSERVER_PWD", "")
    driver = os.getenv("SQLSERVER_DRIVER", "{ODBC Driver 18 for SQL Server}")
    trust_cert = os.getenv("SQLSERVER_TRUST_CERT", "yes")
    encrypt = os.getenv("SQLSERVER_ENCRYPT", "yes")

    if not database:
        raise ValueError(
            "SQLSERVER_DATABASE is not set. "
            "Set env vars or provide SQLSERVER_CONNECTION_STRING."
        )

    if uid and pwd:
        auth_part = f"UID={uid};PWD={pwd};"
    else:
        trusted = os.getenv("SQLSERVER_TRUSTED_CONNECTION", "yes")
        auth_part = f"Trusted_Connection={trusted};"

    return (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"{auth_part}"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
    )


def get_sql_connection() -> pyodbc.Connection:
    conn_str = build_sqlserver_connection_string()
    return pyodbc.connect(conn_str)


def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise ValueError("NEO4J_PASSWORD is not set.")
    return GraphDatabase.driver(uri, auth=(user, password))


def rows_to_dicts(cursor: pyodbc.Cursor, query: str) -> list[dict[str, Any]]:
    cursor.execute(query)
    cols = [desc[0] for desc in cursor.description]
    records = []
    for row in cursor.fetchall():
        record: dict[str, Any] = {}
        for key, value in zip(cols, row):
            if isinstance(value, decimal.Decimal):
                record[key] = float(value)
            elif isinstance(value, (dt.datetime, dt.date)):
                record[key] = value.isoformat()
            else:
                record[key] = value
        records.append(record)
    return records


def extract_relational_data(conn: pyodbc.Connection) -> dict[str, list[dict[str, Any]]]:
    """Read all SQL data needed for recommendation graph."""
    cursor = conn.cursor()

    datasets: dict[str, list[dict[str, Any]]] = {
        "patients": rows_to_dicts(
            cursor,
            """
            SELECT
                p.Patient_ID AS patient_id,
                p.Full_Name AS full_name,
                p.Gender AS gender,
                p.Date_Of_Birth AS date_of_birth
            FROM dbo.Patients p;
            """,
        ),
        "clinics": rows_to_dicts(
            cursor,
            """
            SELECT
                c.Clinic_ID AS clinic_id,
                c.Clinic_Name AS clinic_name,
                c.City AS city,
                c.Address_Line AS address_line
            FROM dbo.Clinics c;
            """,
        ),
        "doctors": rows_to_dicts(
            cursor,
            """
            SELECT
                d.Doctor_ID AS doctor_id,
                d.Full_Name AS full_name,
                d.Years_Experience AS years_experience,
                d.Consultation_Fee AS consultation_fee,
                CAST(d.Is_Available AS INT) AS is_available,
                d.Clinic_ID AS clinic_id,
                SUM(CASE
                        WHEN a.Appointment_Status = 'BOOKED'
                         AND a.Appointment_Date >= SYSDATETIME()
                        THEN 1 ELSE 0
                    END) AS upcoming_load
            FROM dbo.Doctors d
            LEFT JOIN dbo.Appointments a
              ON a.Doctor_ID = d.Doctor_ID
            GROUP BY
                d.Doctor_ID, d.Full_Name, d.Years_Experience,
                d.Consultation_Fee, d.Is_Available, d.Clinic_ID;
            """,
        ),
        "specializations": rows_to_dicts(
            cursor,
            """
            SELECT
                s.Specialization_ID AS specialization_id,
                s.Specialization_Name AS specialization_name
            FROM dbo.Specializations s;
            """,
        ),
        "symptoms": rows_to_dicts(
            cursor,
            """
            SELECT
                s.Symptom_ID AS symptom_id,
                s.Symptom_Name AS symptom_name
            FROM dbo.Symptoms s;
            """,
        ),
        "doctor_specializations": rows_to_dicts(
            cursor,
            """
            SELECT
                ds.Doctor_ID AS doctor_id,
                ds.Specialization_ID AS specialization_id
            FROM dbo.Doctor_Specializations ds;
            """,
        ),
        "symptom_specialization": rows_to_dicts(
            cursor,
            """
            SELECT
                ss.Symptom_ID AS symptom_id,
                ss.Specialization_ID AS specialization_id,
                ss.Match_Weight AS weight
            FROM dbo.Symptom_Specialization ss;
            """,
        ),
        "patient_symptoms_latest": rows_to_dicts(
            cursor,
            """
            WITH ranked AS (
                SELECT
                    ps.Patient_ID AS patient_id,
                    ps.Symptom_ID AS symptom_id,
                    ps.Severity AS severity,
                    ps.Recorded_At AS recorded_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY ps.Patient_ID, ps.Symptom_ID
                        ORDER BY ps.Recorded_At DESC, ps.Patient_Symptom_ID DESC
                    ) AS rn
                FROM dbo.Patient_Symptoms ps
            )
            SELECT
                patient_id,
                symptom_id,
                severity,
                recorded_at
            FROM ranked
            WHERE rn = 1;
            """,
        ),
        "reviews": rows_to_dicts(
            cursor,
            """
            SELECT
                r.Patient_ID AS patient_id,
                r.Doctor_ID AS doctor_id,
                r.Rating AS rating,
                r.Review_Date AS review_date
            FROM dbo.Reviews r;
            """,
        ),
    }

    return datasets


def create_constraints(session) -> None:
    session.run(
        "CREATE CONSTRAINT patient_id IF NOT EXISTS "
        "FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT doctor_id IF NOT EXISTS "
        "FOR (d:Doctor) REQUIRE d.doctor_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT clinic_id IF NOT EXISTS "
        "FOR (c:Clinic) REQUIRE c.clinic_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT symptom_id IF NOT EXISTS "
        "FOR (s:Symptom) REQUIRE s.symptom_id IS UNIQUE"
    )
    session.run(
        "CREATE CONSTRAINT specialization_id IF NOT EXISTS "
        "FOR (sp:Specialization) REQUIRE sp.specialization_id IS UNIQUE"
    )


def sync_to_neo4j(driver, datasets: dict[str, list[dict[str, Any]]], reset_graph: bool) -> None:
    db_name = os.getenv("NEO4J_DATABASE", "neo4j")

    with driver.session(database=db_name) as session:
        if reset_graph:
            session.run("MATCH (n) DETACH DELETE n")

        create_constraints(session)

        if datasets["patients"]:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (p:Patient {patient_id: row.patient_id})
                SET p.name = row.full_name,
                    p.gender = row.gender,
                    p.date_of_birth = row.date_of_birth
                """,
                rows=datasets["patients"],
            )

        if datasets["clinics"]:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (c:Clinic {clinic_id: row.clinic_id})
                SET c.name = row.clinic_name,
                    c.city = row.city,
                    c.address = row.address_line
                """,
                rows=datasets["clinics"],
            )

        if datasets["doctors"]:
            doctor_rows = []
            for row in datasets["doctors"]:
                row = dict(row)
                row["is_available"] = bool(row["is_available"])
                row["upcoming_load"] = int(row["upcoming_load"] or 0)
                doctor_rows.append(row)

            session.run(
                """
                UNWIND $rows AS row
                MERGE (d:Doctor {doctor_id: row.doctor_id})
                SET d.name = row.full_name,
                    d.years_experience = row.years_experience,
                    d.consultation_fee = row.consultation_fee,
                    d.is_available = row.is_available,
                    d.upcoming_load = row.upcoming_load
                WITH d, row
                MATCH (c:Clinic {clinic_id: row.clinic_id})
                MERGE (d)-[:AT_CLINIC]->(c)
                """,
                rows=doctor_rows,
            )

        if datasets["specializations"]:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (sp:Specialization {specialization_id: row.specialization_id})
                SET sp.name = row.specialization_name
                """,
                rows=datasets["specializations"],
            )

        if datasets["symptoms"]:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (s:Symptom {symptom_id: row.symptom_id})
                SET s.name = row.symptom_name
                """,
                rows=datasets["symptoms"],
            )

        if datasets["doctor_specializations"]:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (d:Doctor {doctor_id: row.doctor_id})
                MATCH (sp:Specialization {specialization_id: row.specialization_id})
                MERGE (d)-[:SPECIALIZES_IN]->(sp)
                """,
                rows=datasets["doctor_specializations"],
            )

        if datasets["symptom_specialization"]:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (s:Symptom {symptom_id: row.symptom_id})
                MATCH (sp:Specialization {specialization_id: row.specialization_id})
                MERGE (s)-[r:SUGGESTS]->(sp)
                SET r.weight = row.weight
                """,
                rows=datasets["symptom_specialization"],
            )

        if datasets["patient_symptoms_latest"]:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Patient {patient_id: row.patient_id})
                MATCH (s:Symptom {symptom_id: row.symptom_id})
                MERGE (p)-[r:HAS_SYMPTOM]->(s)
                SET r.severity = row.severity,
                    r.recorded_at = datetime(row.recorded_at)
                """,
                rows=datasets["patient_symptoms_latest"],
            )

        if datasets["reviews"]:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Patient {patient_id: row.patient_id})
                MATCH (d:Doctor {doctor_id: row.doctor_id})
                MERGE (p)-[r:RATED {review_date: datetime(row.review_date)}]->(d)
                SET r.rating = row.rating
                """,
                rows=datasets["reviews"],
            )


def recommend_doctors(driver, patient_id: int, top_k: int) -> list[dict[str, Any]]:
    db_name = os.getenv("NEO4J_DATABASE", "neo4j")
    query = """
    MATCH (p:Patient {patient_id: $patient_id})
    OPTIONAL MATCH (p)-[:HAS_SYMPTOM]->(s0:Symptom)
    WITH p, count(s0) AS symptom_count
    WHERE symptom_count > 0

    MATCH (p)-[hs:HAS_SYMPTOM]->(s:Symptom)-[sg:SUGGESTS]->(sp:Specialization)<-[:SPECIALIZES_IN]-(d:Doctor)-[:AT_CLINIC]->(c:Clinic)
    WHERE d.is_available = true

    WITH d, c, sum(toFloat(hs.severity) * coalesce(toFloat(sg.weight), 1.0)) AS fit_score
    OPTIONAL MATCH (:Patient)-[rt:RATED]->(d)
    WITH d, c, fit_score, coalesce(avg(toFloat(rt.rating)), 3.5) AS avg_rating, count(rt) AS num_reviews

    WITH d, c, fit_score, avg_rating, num_reviews,
         toFloat(d.years_experience) AS years_experience,
         toFloat(coalesce(d.upcoming_load, 0)) AS upcoming_load,
         toFloat(d.consultation_fee) AS consultation_fee

    WITH d, c, fit_score, avg_rating, num_reviews, years_experience, upcoming_load, consultation_fee,
         (
           fit_score * 0.60 +
           avg_rating * 0.30 +
           CASE
             WHEN years_experience > 20 THEN 2.0
             ELSE years_experience / 10.0
           END -
           upcoming_load * 0.10 -
           consultation_fee / 500.0
         ) AS final_score

    RETURN
      d.doctor_id AS doctor_id,
      d.name AS doctor_name,
      c.name AS clinic_name,
      fit_score,
      avg_rating,
      num_reviews,
      years_experience,
      consultation_fee,
      upcoming_load,
      round(final_score, 4) AS final_score
    ORDER BY final_score DESC, avg_rating DESC
    LIMIT $top_k
    """

    with driver.session(database=db_name) as session:
        patient_exists = session.run(
            "MATCH (p:Patient {patient_id: $patient_id}) RETURN p LIMIT 1",
            patient_id=patient_id,
        ).single()
        if not patient_exists:
            raise ValueError(f"Patient {patient_id} does not exist in Neo4j graph.")

        results = session.run(query, patient_id=patient_id, top_k=top_k)
        return [dict(row) for row in results]


def print_recommendations(patient_id: int, rows: list[dict[str, Any]]) -> None:
    print(f"\nTop doctor recommendations for patient_id={patient_id}\n")
    if not rows:
        print("No recommendations found. Check patient symptoms and doctor mappings.")
        return

    for idx, row in enumerate(rows, start=1):
        print(
            f"{idx}. Doctor #{row['doctor_id']} - {row['doctor_name']} ({row['clinic_name']}) | "
            f"Score={row['final_score']} | Fit={round(row['fit_score'], 2)} | "
            f"Rating={round(row['avg_rating'], 2)} ({row['num_reviews']} reviews) | "
            f"Experience={int(row['years_experience'])}y | Fee={row['consultation_fee']} | "
            f"Upcoming load={int(row['upcoming_load'])}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run end-to-end Doctor Recommendation flow (SQL Server -> Neo4j)."
    )
    parser.add_argument("patient_id", type=int, help="Patient ID to recommend doctors for.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of recommendations (default: 5).")
    parser.add_argument(
        "--reset-graph",
        action="store_true",
        help="Delete all existing Neo4j nodes/relationships before syncing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.top_k <= 0:
        raise ValueError("--top-k must be > 0")

    print("Connecting SQL Server...")
    sql_conn = get_sql_connection()
    try:
        print("Extracting relational data...")
        datasets = extract_relational_data(sql_conn)
    finally:
        sql_conn.close()

    print("Connecting Neo4j...")
    driver = get_neo4j_driver()
    try:
        print("Syncing graph data...")
        sync_to_neo4j(driver, datasets, reset_graph=args.reset_graph)

        print("Running recommendation query...")
        recommendations = recommend_doctors(driver, args.patient_id, args.top_k)
    finally:
        driver.close()

    print_recommendations(args.patient_id, recommendations)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
