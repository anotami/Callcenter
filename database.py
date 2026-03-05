"""
Proceso 4: Almacenamiento en SQL Server.
Guarda resultados de evaluacion y permite cruzar con datos de demanda.
"""

import pyodbc
import pandas as pd
from datetime import datetime
from config import SQL_SERVER, SQL_DATABASE, SQL_USERNAME, SQL_PASSWORD, SQL_DRIVER


def get_connection_string() -> str:
    return (
        f"DRIVER={{{SQL_DRIVER}}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USERNAME};"
        f"PWD={SQL_PASSWORD};"
        "TrustServerCertificate=yes;"
    )


def get_connection() -> pyodbc.Connection:
    conn = pyodbc.connect(get_connection_string())
    print(f"[DB] Conectado a {SQL_SERVER}/{SQL_DATABASE}")
    return conn


def create_tables(conn: pyodbc.Connection):
    """Crea las tablas necesarias si no existen."""
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='evaluaciones' AND xtype='U')
        CREATE TABLE evaluaciones (
            id INT IDENTITY(1,1) PRIMARY KEY,
            archivo_audio VARCHAR(500) NOT NULL,
            fecha_procesamiento DATETIME DEFAULT GETDATE(),
            fecha_llamada DATETIME NULL,
            duracion_segundos FLOAT NULL,
            num_hablantes INT NULL,
            transcripcion_completa NVARCHAR(MAX) NULL,
            puntaje_total INT NULL,
            resumen_general NVARCHAR(MAX) NULL,
            recomendaciones NVARCHAR(MAX) NULL,
            -- Campos de demanda
            grupo_plataforma VARCHAR(200) NULL,
            registro_evento VARCHAR(200) NULL,
            proveedor VARCHAR(200) NULL,
            motivo VARCHAR(200) NULL,
            sub_motivo VARCHAR(200) NULL,
            documento_asesor VARCHAR(50) NULL
        )
    """)

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='evaluacion_criterios' AND xtype='U')
        CREATE TABLE evaluacion_criterios (
            id INT IDENTITY(1,1) PRIMARY KEY,
            evaluacion_id INT NOT NULL,
            criterio_id INT NOT NULL,
            criterio_nombre VARCHAR(200) NOT NULL,
            calificacion VARCHAR(20) NOT NULL,
            justificacion NVARCHAR(MAX) NULL,
            FOREIGN KEY (evaluacion_id) REFERENCES evaluaciones(id)
        )
    """)

    conn.commit()
    print("[DB] Tablas creadas/verificadas")


def save_evaluation(
    conn: pyodbc.Connection,
    audio_file: str,
    dialogue: str,
    evaluation: dict,
    num_speakers: int = 2,
    duration: float = 0.0,
) -> int:
    """Guarda una evaluacion completa en la base de datos. Retorna el ID."""
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO evaluaciones
            (archivo_audio, transcripcion_completa, puntaje_total,
             resumen_general, recomendaciones, num_hablantes, duracion_segundos)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        audio_file,
        dialogue,
        evaluation.get("puntaje_total"),
        evaluation.get("resumen_general"),
        str(evaluation.get("recomendaciones", [])),
        num_speakers,
        duration,
    )

    cursor.execute("SELECT @@IDENTITY")
    eval_id = int(cursor.fetchone()[0])

    for item in evaluation.get("evaluacion", []):
        cursor.execute(
            """
            INSERT INTO evaluacion_criterios
                (evaluacion_id, criterio_id, criterio_nombre, calificacion, justificacion)
            VALUES (?, ?, ?, ?, ?)
            """,
            eval_id,
            item.get("criterio_id"),
            item.get("criterio"),
            item.get("calificacion"),
            item.get("justificacion"),
        )

    conn.commit()
    print(f"[DB] Evaluacion guardada con ID={eval_id}")
    return eval_id


def export_to_csv(conn: pyodbc.Connection, output_path: str):
    """Exporta todas las evaluaciones a CSV."""
    query = """
        SELECT
            e.id, e.archivo_audio, e.fecha_procesamiento,
            e.puntaje_total, e.resumen_general, e.num_hablantes,
            e.duracion_segundos, e.grupo_plataforma, e.proveedor,
            e.motivo, e.documento_asesor,
            c.criterio_nombre, c.calificacion, c.justificacion
        FROM evaluaciones e
        LEFT JOIN evaluacion_criterios c ON e.id = c.evaluacion_id
        ORDER BY e.id, c.criterio_id
    """
    df = pd.read_sql(query, conn)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[DB] Exportado a {output_path} ({len(df)} filas)")
