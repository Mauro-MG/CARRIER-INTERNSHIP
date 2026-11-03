import pandas as pd
import pyodbc
### Connection ###
conn = pyodbc.connect(r"DRIVER={SQL Server};"             
               r"Server=Hvac-phdb-db.apps.carrier.com;"
               r"Database =CarrierAnalytics;"
               r"UID=cads;"
               r"PWD=zs823j1903;"                      
                      )
cursor = conn.cursor()

# Monthly Data
monthly_warranty=pd.read_sql_query("""Select ClaimNumber,Model,Serial,ReplPartNumCompress, ReplacementPartDescription, Plant,EquipmentState,ClaimDate,PaidDate,ManufactureDate,DateFailed,DateRepaired,StartupDate,ShipDate,ClaimType,TimeType,LaborAmountApproved,LaborHours,ServicePerformed,WarrantyType,WtyTypeDescription,GLTotal,TotalClaimAmountAppr,GLStandardTot,GLStandard1stYr,GLStandardExt,GLOptional,GLConcessions,GLMargin,GLProductTrouble,clmqty,qty,PRODUCT_WLC_STD,SalesCat,WarrCName,BusinessUnit,DefectCode FROM CarrierAnalytics.dbo.[WarrantyGLNewMonthHistory]""", conn)
monthly_warranty.PaidDate=pd.to_datetime(monthly_warranty.PaidDate)
monthly_warranty.DateFailed=pd.to_datetime(monthly_warranty.DateFailed)
print(monthly_warranty.DateFailed.min(),monthly_warranty.DateFailed.max())
print(monthly_warranty.PaidDate.min(),monthly_warranty.PaidDate.max())
## Drop Duplicates
monthly_warranty=monthly_warranty.drop_duplicates(['Serial','ClaimNumber','ServicePerformed','GLTotal','TotalClaimAmountAppr','GLStandardTot','GLStandard1stYr','GLStandardExt','GLOptional','GLProductTrouble'],keep='first')  
monthly_warranty['Beyond1stYr']=monthly_warranty['GLStandardExt']

monthly_warranty.PaidDate.min()
monthly_warranty[monthly_warranty.Serial=='4323P29839'].ServicePerformed.unique()
monthly_warranty.Plant.unique()
monthly_warranty.ServicePerformed.unique()

PRIMARY_COMPONENTS = [
    "Electrical controls",
    "Evaporator",
    "Non-component",
    "Gas",
    "Input Devices",
    "Starter/VFD",
    "Condenser",
    "Compressor",
    "Valve",
    "Other",
    "Oil System",
]

SECONDARY_COMPONENTS = [
    "Electrical Controls - Wiring",
    "Electrical Controls - Boards",
    "Cond/Evap - Fan motor",
    "NC - Water Leak",
    "NC - Refrigerant Leak",
    "NC - Not Warranty",
    "Cond/Evap - Fan blades",
    "Gas - Valve",
    "Cond/Evap - coil leak",
    "Input devices - Transducer",
    "Starter/VFD - Boards",
    "Electrical Controls - Breakers",
    "Electrical Controls - Contactors",
    "NC - field install issue",
    "NC -no fault found",
    "Input devices - High pressure switch",
    "Valve - EXV/TXV",
    "Starter/VFD - wiring",
    "Input devices - Temp sensor",
    "Electronic Controls - wiring",
    "NC - concession",
    "NC - Cosmetic",
    "Compressor - Mechanical failure",
    "NC - Other (comments box)",
    "Non-Component - Other (comments box)",
    "Non-Component - Refrigerant Leak",
    "Starter/VFD - Program",
    "Other - note issues in comments",
    "Valve - Check",
    "NC - missing parts",
    "NC - no fault found",
    "NC - frame",
    "NC - sales order issue",
    "Non-Component - Cosmetic Damage",
    "Valve - economizer",
    "Electrical Controls - Transformer",
    "Oil system - oil line",
    "Compressor - Motor",
    "NC - configuration",
    "Input devices - Thermistor",
    "NC - Field Install Issues",
    "Valve - Stepper",
    "Electrical Controls - Program",
    "Electronic controls - program",
    "NC - Cosmetic Damage",
    "Valve - damper",
    "Input devices - Sensor",
    "Compressor - Heater",
    "Electrical controls - display",
    "Electrical Controls - Relays",
    "NC -  refrigerant undercharge",
    "NC -  Refrigerant leak",
    "NC - refrigerant overcharge",
    "NC - system contamination",
    "Electrical Controls - fuses",
    "NC - no fault found ",
    "NC - no fault found (noise/vibration)",
    "NC - not fault found",
    "NC - service call",
    "NC - no fault found  ",
    "Gas - Inducer",
    "Gas-burner",
    "Gas - leak",
    "NC-insulation",
    "NC - insulation",
    "Gas - Sensor",
    "Compressor - wiring",
    "Gas - HX",
    "Gas - exhaust",
    "Input devices -Flow Switch",
    "NC -refrigerant leak",
    "Non-Component - Water Leak",
    "NC-field install issue",
    "NC -  configuration",
    "Valve - Ball",
    "0",
    "NC - refrigerant undercharge",
    "Valve - charging/service",
    "NC - air leak",
    "NC - leak",
    "Valve - actuator",
    "NC -not warranty"
]

FAILURE_REASONS = [
    "Design",
    "Installation",
    "Manufacturing",
    "Applications/Systems",
    "Part Failure",
    "Network Controls",
    "Resettable alarms",
    "Other",
]

import requests
import json
import time

OLLAMA_URL = "http://localhost:11434/api/generate"

def classify(text: str, model="llama3"):

    prompt = f"""
    You are a strict HVAC warranty classification engine.

    CRITICAL RULES:
    1. Use ONLY categories explicitly supported by the text.
    2. The SECONDARY_COMPONENT must directly match the failed PRIMARY_COMPONENT.
    3. If compressors failed, NEVER select electrical board categories.
    4. Contactors and breakers are secondary unless they are the root failure.
    5. Prioritize the ROOT CAUSE component, not collateral damage.
    6. Confidence must be between 0 and 1.
    7. evidence_phrases must contain exact quotes from the text.
    8. Return ONLY valid JSON.

    PRIMARY_COMPONENT OPTIONS:
    {PRIMARY_COMPONENTS}

    SECONDARY_COMPONENT OPTIONS:
    {SECONDARY_COMPONENTS}

    FAILURE_REASON OPTIONS:
    {FAILURE_REASONS}

    TEXT:
    {text}
    
    RETURN FORMAT:
    {{
        "primary_component": "",
        "secondary_component": "",
        "failure_reason": "",
        "confidence": 0.0,
        "evidence_phrases": []
    }}
    """

    for attempt in range(3):

        try:

            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0
                    }
                },
                timeout=180
            )

            response.raise_for_status()

            data = response.json()

            raw = data.get("response", "").strip()

            return json.loads(raw)

        except Exception as e:

            print(f"ERROR attempt {attempt + 1}: {e}")

            time.sleep(5)

    return {
        "error": "Failed after retries"
    }


# ---------------- TEST ----------------
sample_text = monthly_warranty.ServicePerformed.unique()[3]
sample_text = 'While on a PM, found the unit was not cooling. Found two welded and burnt contactors and the breaker was tripped. Checked all electrical wiring and found that the compressors for both circuits were shorted internally to ground. Reclaimed the gas and removed the compressors. Installed new compressors, pressure tested with nitrogen, vacuumed unit under 500 microns. Charged unit back up and checked operation of the unit. All good, Had found the compressor shorted to ground. Compressor was covered under standard warranty. contactors and filter drier claim under optional contract. Replaced shorted contactors and restricted filter drier, and burnt contactors. Tested operation, all good.'
print(json.dumps(classify(sample_text), indent=2))