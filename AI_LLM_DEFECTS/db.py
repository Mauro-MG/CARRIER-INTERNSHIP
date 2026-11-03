import os
import pandas as pd
import pyodbc
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pandas as pd
load_dotenv()


def get_connection():
    driver = "SQL Server"
    server = os.environ["DB_SERVER"]
    database = os.environ["DB_DATABASE"]
    username = os.environ["DB_USERNAME"]
    password = os.environ["DB_PASSWORD"]
    trust_cert = "yes"
    encrypt = "no"

    if not all([server, database, username, password]):
        raise ValueError("Missing SQL connection values in .env file.")

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust_cert};"
    )

    return pyodbc.connect(conn_str, timeout=30)


def test_sql_connection():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1
      

def load_claims(limit=50, claim_number=None, serial=None, date_from=None, date_to=None):

    conn = get_connection()

    query = f"""
    SELECT TOP ({int(limit)})
        ClaimNumber,
        Model,
        Serial,
        Plant,
        EquipmentState,
        ClaimDate,
        PaidDate,
        ManufactureDate,
        DateFailed,
        DateRepaired,
        StartupDate,
        ShipDate,
        ClaimType,
        TimeType,
        LaborAmountApproved,
        LaborHours,
        ServicePerformed,
        WarrantyType,
        WtyTypeDescription,
        GLTotal,
        TotalClaimAmountAppr,
        GLStandardTot,
        GLStandard1stYr,
        GLStandardExt,
        GLOptional,
        GLConcessions,
        GLMargin,
        GLProductTrouble,
        clmqty,
        qty,
        PRODUCT_WLC_STD,
        SalesCat,
        WarrCName,
        BusinessUnit,
        DefectCode
    FROM dbo.WarrantyGLNewMonthHistory
    WHERE ServicePerformed IS NOT NULL
      AND LTRIM(RTRIM(ServicePerformed)) <> ''
    """

    params = []

    if claim_number:
        query += " AND CAST(ClaimNumber AS VARCHAR(50)) LIKE ?"
        params.append(f"%{claim_number}%")

    if serial:
        query += " AND CAST(Serial AS VARCHAR(100)) LIKE ?"
        params.append(f"%{serial}%")

    if date_from:
        query += " AND DateFailed >= ?"
        params.append(date_from)

    if date_to:
        query += " AND DateFailed <= ?"
        params.append(date_to)

    query += " ORDER BY DateFailed DESC"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    date_cols = [
        "ClaimDate", "PaidDate", "ManufactureDate", "DateFailed",
        "DateRepaired", "StartupDate", "ShipDate"
    ]

    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].dt.strftime("%Y-%m-%d")
            df[col] = df[col].fillna("")

    df = df.fillna("")

    return df

def load_last_week_claims_with_serial_history():
    conn = get_connection()

    today = datetime.today()
    week_start = today - timedelta(days=7)

    query = """
    WITH LastWeekSerials AS (
        SELECT DISTINCT Serial
        FROM dbo.WarrantyGLNewMonthHistory
        WHERE PaidDate >= ?
          AND Serial IS NOT NULL
          AND LTRIM(RTRIM(Serial)) <> ''
          AND ServicePerformed IS NOT NULL
          AND LTRIM(RTRIM(ServicePerformed)) <> ''
    )

    SELECT
        h.ClaimNumber,
        h.Model,
        h.Serial,
        h.Plant,
        h.ClaimDate,
        h.PaidDate,
        h.DateFailed,
        h.ServicePerformed,
        h.ClaimType,
        h.TimeType,
        h.WarrantyType,
        h.GLTotal,
        h.TotalClaimAmountAppr,
        h.GLStandardTot,
        h.GLStandard1stYr,
        h.GLStandardExt,
        h.GLOptional,
        h.GLProductTrouble,
        h.clmqty,
        h.DefectCode,
        CASE 
            WHEN h.PaidDate >= ? THEN 1 
            ELSE 0 
        END AS IsLastWeekTarget
    FROM dbo.WarrantyGL2YearHistory h
    INNER JOIN LastWeekSerials s
        ON h.Serial = s.Serial

    UNION ALL

    SELECT
        h.ClaimNumber,
        h.Model,
        h.Serial,
        h.Plant,
        h.ClaimDate,
        h.PaidDate,
        h.DateFailed,
        h.ServicePerformed,
        h.ClaimType,
        h.TimeType,
        h.WarrantyType,
        h.GLTotal,
        h.TotalClaimAmountAppr,
        h.GLStandardTot,
        h.GLStandard1stYr,
        h.GLStandardExt,
        h.GLOptional,
        h.GLProductTrouble,
        h.clmqty,
        h.DefectCode,
        CASE 
            WHEN h.PaidDate >= ? THEN 1 
            ELSE 0 
        END AS IsLastWeekTarget
    FROM dbo.WarrantyGLNewMonthHistory h
    INNER JOIN LastWeekSerials s
        ON h.Serial = s.Serial

    WHERE h.ServicePerformed IS NOT NULL
      AND LTRIM(RTRIM(h.ServicePerformed)) <> ''

    ORDER BY Serial, DateFailed, PaidDate
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=[week_start, week_start, week_start]
    )

    conn.close()

    df = df.drop_duplicates(
        subset=[
            "Serial",
            "ClaimNumber",
            "ServicePerformed",
            "GLTotal",
            "TotalClaimAmountAppr",
            "GLStandardTot",
            "GLStandard1stYr",
            "GLOptional",
            "GLProductTrouble",
        ],
        keep="first"
    )

    date_cols = ["ClaimDate", "PaidDate", "DateFailed"]

    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].dt.strftime("%Y-%m-%d")
            df[col] = df[col].fillna("")

    df = df.fillna("")

    return df



