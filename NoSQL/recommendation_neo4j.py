#!/usr/bin/env python3
"""
Simple end-to-end recommendation flow:
SQL Server -> Neo4j -> Top doctors by patient_id
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import os
import sys
from typing import Any

import pyodbc
from neo4j import GraphDatabase


SQL_QUERIES = {
    "patients": """
        SELECT Patient_ID AS patient_id, Full_Name AS full_name, Gender AS gender, Date_Of_Birth AS date_of_birth
        FROM dbo.Patients
    """,
    "clinics": """
        SELECT Clinic_ID AS clinic_id, Clinic_Name AS clinic_name, City AS city, Address_Line AS address_line
        FROM dbo.Clinics
    """,
    "doctors": """
        SELECT
            d.Doctor_ID AS doctor_id,
            d.Full_Name AS full_name,
            d.Years_Experience AS years_experience,
            d.Consultation_Fee AS consultation_fee,
            CAST(d.Is_Available AS INT) AS is_available,
            d.Clinic_ID AS clinic_id,
            SUM(CASE
                    WHEN a.Appointment_Status = 'BOOKED' AND a.Appointment_Date >= SYSDATETIME()
                    THEN 1 ELSE 0
                END) AS upcoming_load
        FROM dbo.Doctors d
        LEFT JOIN dbo.Appointments a ON a.Doctor_ID = d.Doctor_ID
        GROUP BY
            d.Doctor_ID, d.Full_Name, d.Years_Experience,
            d.Consultation_Fee, d.Is_Available, d.Clinic_ID
    """,
    "specializations": """
        SELECT Specialization_ID AS specialization_id, Specialization_Name AS specialization_name
        FROM dbo.Specializations
    """,
    "symptoms": """
        SELECT Symptom_ID AS symptom_id, Symptom_Name AS symptom_name
        FROM dbo.Symptoms
    """,
    "doctor_specializations": """
        SELECT Doctor_ID AS doctor_id, Specialization_ID AS specialization_id
        FROM dbo.Doctor_Specializations
    """,
    "symptom_specialization": """
        SELECT Symptom_ID AS symptom_id, Specialization_ID AS specialization_id, Match_Weight AS weight
        FROM dbo.Symptom_Specialization
    """,
    "patient_symptoms_latest": """
        WITH ranked AS (
            SELECT
                Patient_ID AS patient_id,
                Symptom_ID AS symptom_id,
                Severity AS severity,
                Recorded_At AS recorded_at,
                ROW_NUMBER() OVER (
                    PARTITION BY Patient_ID, Symptom_ID
                    ORDER BY Recorded_At DESC, Patient_Symptom_ID DESC
                ) AS rn
            FROM dbo.Patient_Symptoms
        )
        SELECT patient_id, symptom_id, severity, recorded_at
        FROM ranked
        WHERE rn = 1
    """,
    "reviews": """
        SELECT Patient_ID AS patient_id, Doctor_ID AS doctor_id, Rating AS rating, Review_Date AS review_date
        FROM dbo.Reviews
    """,
}


RECOMMEND_QUERY = """
MATCH (p:Patient {patient_id: $patient_id})
OPTIONAL MATCH (p)-[:HAS_SYMPTOM]->(s0:Symptom)
WITH p, count(s0) AS symptom_count
WHERE symptom_count > 0

MATCH (p)-[hs:HAS_SYMPTOM]->(:Symptom)-[sg:SUGGESTS]->(:Specialization)<-[:SPECIALIZES_IN]-(d:Doctor)-[:AT_CLINIC]->(c:Clinic)
WHERE d.is_available = true

WITH d, c, sum(toFloat(hs.severity) * coalesce(toFloat(sg.weight), 1.0)) AS fit_score
OPTIONAL MATCH (:Patient)-[rt:RATED]->(d)
WITH d, c, fit_score, coalesce(avg(toFloat(rt.rating)), 3.5) AS avg_rating, count(rt) AS num_reviews

WITH d, c, fit_score, avg_rating, num_reviews, toFloat(coalesce(d.upcoming_load, 0)) AS upcoming_load
WITH d, c, fit_score, avg_rating, num_reviews, upcoming_load,
     (fit_score * 0.70 + avg_rating * 0.30 - upcoming_load * 0.05) AS final_score

RETURN
  d.doctor_id AS doctor_id,
  d.name AS doctor_name,
  c.name AS clinic_name,
  round(fit_score, 4) AS fit_score,
  round(avg_rating, 4) AS avg_rating,
  num_reviews,
  round(final_score, 4) AS final_score
ORDER BY final_score DESC, avg_rating DESC
LIMIT $top_k
"""


def build_sqlserver_connection_string() -> str:
    direct = os.getenv("SQLSERVER_CONNECTION_STRING")
    if direct:
        return direct

    server = os.getenv("SQLSERVER_SERVER", "mcruebs04.isad.isadroot.ex.ac.uk")
    database = os.getenv("SQLSERVER_DATABASE")
    uid = os.getenv("SQLSERVER_UID")
    pwd = os.getenv("SQLSERVER_PWD")
    driver = os.getenv("SQLSERVER_DRIVER", "{ODBC Driver 18 for SQL Server}")

    if not database or not uid or not pwd:
        raise ValueError("Set SQLSERVER_DATABASE, SQLSERVER_UID, SQLSERVER_PWD (or SQLSERVER_CONNECTION_STRING).")

    return (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={uid};PWD={pwd};"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )


def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise ValueError("Set NEO4J_PASSWORD.")
    return GraphDatabase.driver(uri, auth=(user, password))


def normalize_value(value: Any) -> Any:
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return value


def fetch_rows(cursor, query: str) -> list[dict[str, Any]]:
    cursor.execute(query)
    columns = [c[0] for c in cursor.description]
    output = []
    for row in cursor.fetchall():
        item = {}
        for key, value in zip(columns, row):
            item[key] = normalize_value(value)
        output.append(item)
    return output


def read_sql_data(conn) -> dict[str, list[dict[str, Any]]]:
    cursor = conn.cursor()
    data = {}
    for key, query in SQL_QUERIES.items():
        data[key] = fetch_rows(cursor, query)
    return data


def create_constraints(session) -> None:
    session.run("CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE")
    session.run("CREATE CONSTRAINT doctor_id IF NOT EXISTS FOR (d:Doctor) REQUIRE d.doctor_id IS UNIQUE")
    session.run("CREATE CONSTRAINT clinic_id IF NOT EXISTS FOR (c:Clinic) REQUIRE c.clinic_id IS UNIQUE")
    session.run("CREATE CONSTRAINT symptom_id IF NOT EXISTS FOR (s:Symptom) REQUIRE s.symptom_id IS UNIQUE")
    session.run(
        "CREATE CONSTRAINT specialization_id IF NOT EXISTS "
        "FOR (sp:Specialization) REQUIRE sp.specialization_id IS UNIQUE"
    )


def sync_data_to_neo4j(driver, data: dict[str, list[dict[str, Any]]], reset_graph: bool) -> None:
    db_name = os.getenv("NEO4J_DATABASE", "neo4j")
    with driver.session(database=db_name) as session:
        if reset_graph:
            session.run("MATCH (n) DETACH DELETE n")

        create_constraints(session)

        session.run(
            """
            UNWIND $rows AS row
            MERGE (p:Patient {patient_id: row.patient_id})
            SET p.name = row.full_name, p.gender = row.gender, p.date_of_birth = row.date_of_birth
            """,
            rows=data["patients"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (c:Clinic {clinic_id: row.clinic_id})
            SET c.name = row.clinic_name, c.city = row.city, c.address = row.address_line
            """,
            rows=data["clinics"],
        )

        doctor_rows = []
        for row in data["doctors"]:
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

        session.run(
            """
            UNWIND $rows AS row
            MERGE (sp:Specialization {specialization_id: row.specialization_id})
            SET sp.name = row.specialization_name
            """,
            rows=data["specializations"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (s:Symptom {symptom_id: row.symptom_id})
            SET s.name = row.symptom_name
            """,
            rows=data["symptoms"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (d:Doctor {doctor_id: row.doctor_id})
            MATCH (sp:Specialization {specialization_id: row.specialization_id})
            MERGE (d)-[:SPECIALIZES_IN]->(sp)
            """,
            rows=data["doctor_specializations"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (s:Symptom {symptom_id: row.symptom_id})
            MATCH (sp:Specialization {specialization_id: row.specialization_id})
            MERGE (s)-[r:SUGGESTS]->(sp)
            SET r.weight = row.weight
            """,
            rows=data["symptom_specialization"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (p:Patient {patient_id: row.patient_id})
            MATCH (s:Symptom {symptom_id: row.symptom_id})
            MERGE (p)-[r:HAS_SYMPTOM]->(s)
            SET r.severity = row.severity, r.recorded_at = datetime(row.recorded_at)
            """,
            rows=data["patient_symptoms_latest"],
        )

        session.run(
            """
            UNWIND $rows AS row
            MATCH (p:Patient {patient_id: row.patient_id})
            MATCH (d:Doctor {doctor_id: row.doctor_id})
            MERGE (p)-[r:RATED {review_date: datetime(row.review_date)}]->(d)
            SET r.rating = row.rating
            """,
            rows=data["reviews"],
        )


def recommend(driver, patient_id: int, top_k: int) -> list[dict[str, Any]]:
    db_name = os.getenv("NEO4J_DATABASE", "neo4j")
    with driver.session(database=db_name) as session:
        exists = session.run(
            "MATCH (p:Patient {patient_id: $patient_id}) RETURN p LIMIT 1",
            patient_id=patient_id,
        ).single()
        if not exists:
            raise ValueError(f"Patient {patient_id} not found in graph.")

        result = session.run(RECOMMEND_QUERY, patient_id=patient_id, top_k=top_k)
        return [dict(row) for row in result]


def print_recommendations(patient_id: int, rows: list[dict[str, Any]]) -> None:
    print(f"\nTop recommendations for patient_id={patient_id}\n")
    if not rows:
        print("No recommendation found.")
        return

    for i, row in enumerate(rows, start=1):
        print(
            f"{i}. #{row['doctor_id']} {row['doctor_name']} ({row['clinic_name']}) | "
            f"score={row['final_score']} | fit={row['fit_score']} | "
            f"rating={row['avg_rating']} ({row['num_reviews']} reviews)"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple SQL -> Neo4j doctor recommendation script.")
    parser.add_argument("patient_id", type=int, help="Patient ID")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    parser.add_argument("--reset-graph", action="store_true", help="Delete old Neo4j data before syncing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.top_k <= 0:
        raise ValueError("--top-k must be > 0")

    print("1) Read from SQL Server...")
    sql_conn = pyodbc.connect(build_sqlserver_connection_string())
    try:
        data = read_sql_data(sql_conn)
    finally:
        sql_conn.close()

    print("2) Sync to Neo4j...")
    driver = get_neo4j_driver()
    try:
        sync_data_to_neo4j(driver, data, reset_graph=args.reset_graph)
        print("3) Run recommendation...")
        rows = recommend(driver, args.patient_id, args.top_k)
    finally:
        driver.close()

    print_recommendations(args.patient_id, rows)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
