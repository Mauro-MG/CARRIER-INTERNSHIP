import pyodbc
import pandas.io.sql as psql
import numpy as np
from sqlalchemy import create_engine
import urllib
import pandas as pd
import json

### Connection ###

conn = pyodbc.connect(r"DRIVER={SQL Server};"             
               r"Server=Hvac-phdb-db.apps.carrier.com;"
               r"Database=CarrierAnalytics;"
               r"UID=cads;"
               r"PWD=zs823j1903;"                      
                      )
cursor = conn.cursor()

#Monthly Data
year_warranty=pd.read_sql_query("""Select ClaimNumber,Model,Serial,ReplPartNumCompress, ReplacementPartDescription, Plant,EquipmentState,ClaimDate,PaidDate,ManufactureDate,DateFailed,DateRepaired,StartupDate,ShipDate,ClaimType,TimeType,LaborAmountApproved,LaborHours,ServicePerformed,WarrantyType,WtyTypeDescription,GLTotal,GLStandardExt,TotalClaimAmountAppr,GLStandardTot,GLStandard1stYr,GLOptional,GLConcessions,GLMargin,GLProductTrouble,clmqty,qty,PRODUCT_WLC_STD,SalesCat,WarrCName,BusinessUnit,DefectCode,CustomerCompanyName,ReferenceNumber FROM CarrierAnalytics.dbo.[WarrantyGL2YearHistory] Where Plant In ('CMXB','Charlotte') """, conn)
year_warranty.PaidDate=pd.to_datetime(year_warranty.PaidDate)
year_warranty.DateFailed=pd.to_datetime(year_warranty.DateFailed)
print(year_warranty.DateFailed.min(),year_warranty.DateFailed.max())
print(year_warranty.PaidDate.min(),year_warranty.PaidDate.max())
## Drop Duplicates
old=year_warranty.drop_duplicates(['Serial','ClaimNumber','ServicePerformed','GLTotal','TotalClaimAmountAppr','GLStandardTot','GLStandard1stYr','GLOptional','GLProductTrouble'],keep='first')  #How to put this into SQL code???
old['Beyond1stYr']=old['GLStandardExt']

#Monthly Data
monthly_warranty=pd.read_sql_query("""Select ClaimNumber,Model,Serial,ReplPartNumCompress, ReplacementPartDescription, Plant,EquipmentState,ClaimDate,PaidDate,ManufactureDate,DateFailed,DateRepaired,StartupDate,ShipDate,ClaimType,TimeType,LaborAmountApproved,LaborHours,ServicePerformed,WarrantyType,WtyTypeDescription,GLTotal,GLStandardExt,TotalClaimAmountAppr,GLStandardTot,GLStandard1stYr,GLOptional,GLConcessions,GLMargin,GLProductTrouble,clmqty,qty,PRODUCT_WLC_STD,SalesCat,WarrCName,BusinessUnit,DefectCode,CustomerCompanyName,ReferenceNumber FROM CarrierAnalytics.dbo.[WarrantyGLNewMonthHistory] Where Plant In ('CMXB','Charlotte') """, conn)
monthly_warranty.PaidDate=pd.to_datetime(monthly_warranty.PaidDate)
monthly_warranty.DateFailed=pd.to_datetime(monthly_warranty.DateFailed)
print(monthly_warranty.DateFailed.min(),monthly_warranty.DateFailed.max())
print(monthly_warranty.PaidDate.min(),monthly_warranty.PaidDate.max())
## Drop Duplicates
monthly_warranty=monthly_warranty.drop_duplicates(['Serial','ClaimNumber','ServicePerformed','GLTotal','TotalClaimAmountAppr','GLStandardTot','GLStandard1stYr','GLOptional','GLProductTrouble'],keep='first')  #How to put this into SQL code???
monthly_warranty['Beyond1stYr']=monthly_warranty['GLStandardExt']

old = old[(old.PaidDate<monthly_warranty.PaidDate.min())]
hist_full = pd.concat([old,monthly_warranty])
hist_full = hist_full[list(monthly_warranty.columns)]
hist_full
duplicado_full=hist_full[hist_full['Serial'].duplicated(keep=False)].reset_index(drop=True)
duplicado_small = duplicado_full[(duplicado_full['GLStandard1stYr']!=0)&(duplicado_full['ClaimType']=='Standard')&(duplicado_full['WarrantyType']!='1S')&(duplicado_full['TimeType'].isin(['FFR','DOA',90]))]
duplicado_big = duplicado_full[(duplicado_full['GLStandard1stYr']==0)|(duplicado_full['ClaimType']!='Standard')|(duplicado_full['WarrantyType']=='1S')|(~duplicado_full['TimeType'].isin(['FFR','DOA',90]))]
no_duplicado=hist_full[~hist_full['Serial'].duplicated(keep=False)].reset_index(drop=True)
start=0
for plants in duplicado_small.Plant.unique():
    print(plants)
    start=start+1
    duplicado=duplicado_small[(duplicado_small.Plant==plants)]
    print('Len Duplo',len(duplicado),'\n\n\n')
    for i in range (duplicado['Serial'].nunique()):
        print(duplicado['Serial'].nunique())
        duplo=duplicado[duplicado['Serial']==duplicado['Serial'].unique()[i]]
        duplo=duplo.sort_values(['PaidDate'], ascending=True).reset_index(drop=True)
        duplo=duplo.sort_values(['Serial','DateFailed','clmqty'], ascending=True).reset_index(drop=True)
        #print(duplicado['Serial'].unique()[i])     
        X=[]
        a,b,c=0,0,0
        for j in range(len(duplo)):
            #print(j)
            if (duplo['clmqty'][j]==1):
                a=a+1
            if (duplo['clmqty'][j]==0):
                b=b+1
            if (duplo['clmqty'][j]==-1):
                c=c+1
            if j ==0:
                X.append('yes')
            else:
                dias=abs((duplo['DateFailed'][j-1]-duplo['DateFailed'][j]).days)
                if dias >= 30:
                    X.append('yes')
                else:
                    if duplo['clmqty'][j-1]!=duplo['clmqty'][j]:
                        if (duplo['clmqty'][j]==1)&(a<=1):
                            X.append('yes')
                        else:
                            if (duplo['clmqty'][j]==0)&(b<=1):
                                X.append('yes')
                            else:
                                if (duplo['clmqty'][j]==-1)&(c<=1):
                                    X.append('yes')
                                else:
                                    X.append('no')
                    else:
                        X.append('no')
        print(len(duplo),len(X))
        duplo['15.- Comm Count']=X
        if i >0:
            duplicated=pd.concat([duplicated, duplo])
        else:
            duplicated=duplo
    #X=pd.DataFrame(X)
    #X.columns=['15.- Comm Count']
    duplicado=duplicated#pd.concat([duplicated.reset_index(drop=True), pd.DataFrame(X).reset_index(drop=True)], axis=1)
    if start>1:
        duplicado_concat=pd.concat([duplicado_concat,duplicado])
    else:
        duplicado_concat=duplicado
no_duplicado.loc[no_duplicado['GLStandard1stYr']!=0, '15.- Comm Count']='yes'
duplicado_big['15.- Comm Count']='no'
df=pd.concat([duplicado_concat,duplicado_big, no_duplicado])

hist_full=df

##Does the 30 day rule applies for Residential Also. Well I don't Know???
hist_full.reset_index(drop=True, inplace=True)
hist_full['Quantity']=0
hist_full['Quantity w/ 1S']=0
hist_full.loc[(hist_full['ClaimType']=='Standard')&(hist_full['WarrantyType']!='1S')& (hist_full['TimeType'].isin(['FFR','DOA',90]))&(hist_full['15.- Comm Count']=='yes'), 'Quantity'] = hist_full['clmqty']
#hist_full.loc[(hist_full['ClaimType']=='Standard')& (hist_full['TimeType'].isin(['FFR','DOA',90]))&(hist_full['15.- Comm Count']=='yes'), 'Quantity w/ 1S'] = hist_full['clmqty']
print(len(hist_full),hist_full.PaidDate.min(),hist_full.PaidDate.max())

## Drop Duplicates
new_data=hist_full

new_data['duplo']=new_data[['Serial','ClaimNumber','ServicePerformed','GLTotal','TotalClaimAmountAppr','GLStandardTot','GLStandard1stYr','GLOptional','GLProductTrouble']].astype('str').agg(' '.join, axis=1)
#last['duplo']=last[['Serial','ClaimNumber','ServicePerformed','GLTotal','TotalClaimAmountAppr','GLStandardTot','GLStandard1stYr','GLOptional','GLProductTrouble']].astype('str').agg(' '.join, axis=1)

#new_data=new_data[~new_data['duplo'].isin(last.duplo.unique())]
print(len(new_data))
print('New Data Paid Dates ',new_data.PaidDate.min(),new_data.PaidDate.max())

# ============================================================
# GEMMA AI CLASSIFICATION - GROUPED BY SERIAL 
# ============================================================

import time
import pandas as pd
import best_gemma_classifier as bgc

from best_gema_config import (
    PRIMARY_COMPONENTS,
    SECONDARY_COMPONENTS,
    FAILURE_REASONS,
    map_secondary_group,
    normalize_secondary,
)

MODEL = "gemma4:12B"




SAMPLE_SIZE = 200
RANDOM_STATE = 42
GROUPING_MONTHS = 6
OUTPUT_XLSX = f"REPORT_serial_group_sample_{SAMPLE_SIZE}.xlsx"
OUTPUT_CSV = f"RESULTS_serial_group_sample_{SAMPLE_SIZE}.csv"
SERIAL_COL = "Serial"
SERVICE_COL = "ServicePerformed"
PART_COL = "ReplacementPartDescription"

GROUP_DATE_COL = "ClaimDate"   # use ClaimDate for failure grouping
FALLBACK_DATE_COL = "PaidDate"  # fallback if ClaimDate is missing


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_key(value):
    return (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
    )


def force_match(value, taxonomy_list):
    cleaned = normalize_key(value)

    for item in taxonomy_list:
        if cleaned == normalize_key(item):
            return item

    return value


def normalize_to_taxonomy(value, taxonomy_list):
    if pd.isna(value):
        return ""

    if taxonomy_list == SECONDARY_COMPONENTS:
        grouped = map_secondary_group(normalize_secondary(value))
        return force_match(grouped, SECONDARY_COMPONENTS)

    return force_match(value, taxonomy_list)

def build_serial_groups(df):
    df = df.copy()

    df[GROUP_DATE_COL] = pd.to_datetime(df[GROUP_DATE_COL], errors="coerce")
    df[FALLBACK_DATE_COL] = pd.to_datetime(df[FALLBACK_DATE_COL], errors="coerce")

    df["ai_group_date"] = df[GROUP_DATE_COL]
    df.loc[df["ai_group_date"].isna(), "ai_group_date"] = df[FALLBACK_DATE_COL]

    df[SERIAL_COL] = df[SERIAL_COL].astype(str).str.strip()

    df = df[
        df[SERIAL_COL].notna()
        & (df[SERIAL_COL].astype(str).str.strip() != "")
        & df[SERVICE_COL].notna()
        & (df[SERVICE_COL].astype(str).str.strip() != "")
    ].copy()

    df = df.sort_values(
        [SERIAL_COL, "ai_group_date", "ClaimNumber"],
        ascending=True
    ).reset_index(drop=True)

    group_ids = []
    gap_days_list = []

    current_group_id = 0
    previous_serial = None
    previous_date = None

    for _, row in df.iterrows():
        serial = row[SERIAL_COL]
        current_date = row["ai_group_date"]

        start_new_group = False
        gap_days = None

        if serial != previous_serial:
            start_new_group = True

        elif pd.isna(current_date) or pd.isna(previous_date):
            start_new_group = True

        else:
            gap_days = (current_date - previous_date).days

            # Chain-based 6-month grouping:
            # Start a new group only if the gap from the immediately previous
            # claim for the same serial is greater than 6 calendar months.
            max_allowed_date = previous_date + pd.DateOffset(months=GROUPING_MONTHS)

            if current_date > max_allowed_date:
                start_new_group = True

        if start_new_group:
            current_group_id += 1

        group_ids.append(current_group_id)
        gap_days_list.append(gap_days)

        previous_serial = serial
        previous_date = current_date

    df["AIGroupID"] = group_ids
    df["GapDaysFromPreviousClaimSameSerial"] = gap_days_list

    return df

def build_claim_text(row):
    claim = clean_text(row.get("ClaimNumber", ""))
    claim_date = clean_text(row.get("ClaimDate", ""))
    part = clean_text(row.get(PART_COL, ""))
    service = clean_text(row.get(SERVICE_COL, ""))

    return (
        f"ClaimNumber: {claim}\n"
        f"ClaimDate: {claim_date}\n"
        f"ReplacementPartDescription: {part}\n"
        f"ServicePerformed: {service}"
    )


def split_target_and_history(group, first_history_limit=5):
    group = group.copy()

    target_row = group.iloc[0]
    history_rows = group.iloc[1:]

    target_text = build_claim_text(target_row)

    first_history_texts = []
    remaining_history_texts = []

    for i, (_, hist_row) in enumerate(history_rows.iterrows(), start=1):
        hist_text = build_claim_text(hist_row)

        if i <= first_history_limit:
            first_history_texts.append(hist_text)
        else:
            remaining_history_texts.append(hist_text)

    first_history_text = "\n\n--- HISTORICAL CLAIM ONLY ---\n\n".join(first_history_texts)
    remaining_history_text = "\n\n--- HISTORICAL CLAIM ONLY ---\n\n".join(remaining_history_texts)

    return target_text, first_history_text, remaining_history_text

def is_weak_ai_result(result):
    primary = result.get("primary_component", "")
    secondary = result.get("secondary_component", "")
    failure = result.get("failure_reason", "")

    return (
        primary in ["Other", "Ambiguous", ""]
        or secondary in ["Other - note issues in comments", "Ambiguous", ""]
        or failure in ["Other", "Ambiguous", ""]
    )

def combine_group_texts(group, max_history_claims=5):
    group = group.copy()

    # First row is the target claim
    target_row = group.iloc[0]
    history_rows = group.iloc[1:]

    target_text = build_claim_text(target_row)

    history_texts = []
    for _, hist_row in history_rows.head(max_history_claims).iterrows():
        history_texts.append(build_claim_text(hist_row))

    historical_text = "\n\n--- HISTORICAL CLAIM ONLY ---\n\n".join(history_texts)

    return target_text, historical_text


def combine_parts(group):
    parts = (
        group[PART_COL]
        .dropna()
        .astype(str)
        .str.strip()
    )

    parts = [p for p in parts if p]

    if not parts:
        return "Not Provided"

    return " | ".join(sorted(set(parts)))


# ------------------------------------------------------------
# 1. Build grouped dataframe
# ------------------------------------------------------------

ai_row_level = build_serial_groups(new_data)

grouped_rows = []

for group_id, group in ai_row_level.groupby("AIGroupID"):
    serial = group[SERIAL_COL].iloc[0]

    target_text, first_history_text, remaining_history_text = split_target_and_history(
        group,
        first_history_limit=5
    )

    # IMPORTANT: target claim replacement part only
    target_replacement_part = clean_text(group.iloc[0].get(PART_COL, "")) or "Not Provided"

    grouped_rows.append({
        "AIGroupID": group_id,
        "Serial": serial,
        "Plant": " | ".join(sorted(set(group["Plant"].dropna().astype(str)))) if "Plant" in group.columns else "",
        "ClaimNumbers": " | ".join(group["ClaimNumber"].dropna().astype(str).unique()),
        "GroupClaimCount": len(group),
        "HistoricalClaimCount": max(len(group) - 1, 0),
        "GroupStartDate": group["ai_group_date"].min(),
        "GroupEndDate": group["ai_group_date"].max(),

        # Keep this only for review/debug
        "CombinedReplacementParts": combine_parts(group),

        # Use this for AI classification
        "TargetReplacementPart": target_replacement_part,

        "TargetClaimText": target_text,
        "FirstHistoricalClaimsText": first_history_text,
        "RemainingHistoricalClaimsText": remaining_history_text,

        "TotalClaimAmountAppr": group["TotalClaimAmountAppr"].sum() if "TotalClaimAmountAppr" in group.columns else None,
        "GLTotal": group["GLTotal"].sum() if "GLTotal" in group.columns else None,
    })

ai_grouped = pd.DataFrame(grouped_rows)

print(f"Total original rows available for AI: {len(ai_row_level)}")
print(f"Total serial/date groups available for AI: {len(ai_grouped)}")

# ------------------------------------------------------------
# 2. Take  group sample
# ------------------------------------------------------------

sample_groups = ai_grouped.sample(
    n=min(SAMPLE_SIZE, len(ai_grouped)),
    random_state=RANDOM_STATE
).copy()

print(f"Groups selected for Gemma sample: {len(sample_groups)}")

# ------------------------------------------------------------
# 3. Create prediction columns
# ------------------------------------------------------------

sample_groups["pred_primary_gemma"] = ""
sample_groups["pred_secondary_gemma"] = ""
sample_groups["pred_failure_gemma"] = ""
sample_groups["needs_review"] = False
sample_groups["review_reason"] = ""
sample_groups["classification_stage"] = ""

# ------------------------------------------------------------
# 4. Run Gemma classification
# ------------------------------------------------------------

start_time = time.perf_counter()

for counter, (idx, row) in enumerate(sample_groups.iterrows(), start=1):
    print(f"[{counter}/{len(sample_groups)}] Running Gemma for AIGroupID {row['AIGroupID']}")

    target_text = clean_text(row["TargetClaimText"])
    first_history_text = clean_text(row["FirstHistoricalClaimsText"])
    remaining_history_text = clean_text(row["RemainingHistoricalClaimsText"])

    # IMPORTANT: use target claim replacement part, not all historical parts
    replacement_part = clean_text(row.get("TargetReplacementPart", "")) or "Not Provided"

    if first_history_text:
        service_text = f"""
TARGET CLAIM TO CLASSIFY:
{target_text}

HISTORICAL CLAIMS FOR CONTEXT ONLY:
Use these only if they clarify the target claim.
Do not classify based on historical claims if they describe different repairs.
The target claim is always the first priority.

{first_history_text}
"""
        classification_stage = "target_plus_first_5_history"
    else:
        service_text = target_text
        classification_stage = "target_only"

    result = bgc.classify(
        text=service_text,
        replacement_part_description=replacement_part,
        model=MODEL,
    )

    if is_weak_ai_result(result) and remaining_history_text:
        retry_text = f"""
TARGET CLAIM TO CLASSIFY:
{target_text}

ADDITIONAL HISTORICAL CLAIMS FOR CONTEXT ONLY:
The first historical claims did not provide enough clarity.
Use these only if they clarify the target claim.
Do not classify based on historical claims if they describe different repairs.
The target claim is always the first priority.

{remaining_history_text}
"""

        result = bgc.classify(
            text=retry_text,
            replacement_part_description=replacement_part,
            model=MODEL,
        )

        classification_stage = "target_plus_remaining_history"

    pred_primary = result.get("primary_component", "")
    pred_secondary = result.get("secondary_component", "")
    pred_failure = result.get("failure_reason", "")

    sample_groups.at[idx, "pred_primary_gemma"] = pred_primary
    sample_groups.at[idx, "pred_secondary_gemma"] = pred_secondary
    sample_groups.at[idx, "pred_failure_gemma"] = pred_failure
    sample_groups.at[idx, "classification_stage"] = classification_stage

    review_reasons = []

    if result.get("needs_review", False):
        review_reason = result.get("review_reason", "")
        if review_reason:
            review_reasons.append(review_reason)
        else:
            review_reasons.append("Classifier marked needs_review")

    if pred_primary in ["Ambiguous", "Other"] or pred_secondary in ["Ambiguous", "Other - note issues in comments"] or pred_failure in ["Ambiguous", "Other"]:
        review_reasons.append("Weak prediction after classification attempts")

    if len(target_text) < 40:
        review_reasons.append("Very short target claim text")

    if review_reasons:
        sample_groups.at[idx, "needs_review"] = True
        sample_groups.at[idx, "review_reason"] = " | ".join(sorted(set(review_reasons)))

elapsed = (time.perf_counter() - start_time) / 60

# ------------------------------------------------------------
# 5. Merge predictions back to row-level data
# ------------------------------------------------------------

prediction_cols = [
    "AIGroupID",
    "pred_primary_gemma",
    "pred_secondary_gemma",
    "pred_failure_gemma",
    "needs_review",
    "review_reason",
    "classification_stage",
]

ai_row_level_sample = ai_row_level.merge(
    sample_groups[prediction_cols],
    on="AIGroupID",
    how="inner"
)

# ------------------------------------------------------------
# 6. Build summary
# ------------------------------------------------------------

summary = pd.DataFrame([
    {"Metric": "Original rows in new_data", "Value": len(new_data)},
    {"Metric": "Rows eligible for AI", "Value": len(ai_row_level)},
    {"Metric": "Serial/date groups available", "Value": len(ai_grouped)},
    {"Metric": "Groups classified in sample", "Value": len(sample_groups)},
    {"Metric": "Row-level records represented in sample", "Value": len(ai_row_level_sample)},
    {"Metric": "Needs review groups", "Value": int(sample_groups["needs_review"].sum())},
    {"Metric": "Needs review rate", "Value": sample_groups["needs_review"].mean()},
    {"Metric": "Runtime minutes", "Value": elapsed},
])

primary_dist = (
    sample_groups["pred_primary_gemma"]
    .value_counts()
    .reset_index()
)
primary_dist.columns = ["pred_primary_gemma", "Count"]

secondary_dist = (
    sample_groups["pred_secondary_gemma"]
    .value_counts()
    .reset_index()
)
secondary_dist.columns = ["pred_secondary_gemma", "Count"]

failure_dist = (
    sample_groups["pred_failure_gemma"]
    .value_counts()
    .reset_index()
)
failure_dist.columns = ["pred_failure_gemma", "Count"]

needs_review = sample_groups[sample_groups["needs_review"]].copy()

# ------------------------------------------------------------
# 7. Export
# ------------------------------------------------------------

with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
    summary.to_excel(writer, sheet_name="Summary", index=False)
    sample_groups.to_excel(writer, sheet_name="ClassifiedGroups", index=False)
    ai_row_level_sample.to_excel(writer, sheet_name="ClassifiedRows", index=False)
    needs_review.to_excel(writer, sheet_name="NeedsReview", index=False)
    primary_dist.to_excel(writer, sheet_name="PrimaryDistribution", index=False)
    secondary_dist.to_excel(writer, sheet_name="SecondaryDistribution", index=False)
    failure_dist.to_excel(writer, sheet_name="FailureDistribution", index=False)

ai_row_level_sample.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')

print(f"\nGemma AI classification completed.")
print(f"Runtime: {elapsed:.2f} minutes")
print(f"Excel created: {OUTPUT_XLSX}")