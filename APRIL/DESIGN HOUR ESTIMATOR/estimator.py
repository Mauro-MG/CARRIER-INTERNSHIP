import pandas as pd


class DesignHourEstimatorData: 
    def __init__(self, excel_path):
        self.excel_path = excel_path
        self.parts_df = None
        self.sets_df = None
        self.hours_df = None

    def load_data(self):
        self.parts_df = pd.read_excel(self.excel_path, sheet_name="parts")
        self.sets_df = pd.read_excel(self.excel_path, sheet_name="sets")
        self.hours_df = pd.read_excel(self.excel_path, sheet_name="hours")

        self.parts_df.columns = self.parts_df.columns.str.strip()
        self.sets_df.columns = self.sets_df.columns.str.strip()
        self.hours_df.columns = self.hours_df.columns.str.strip()

        # Clean parts sheet text columns
        for col in ["Sheet", "Product Family", "UNIT CHASSIS", "Part Name"]:
            if col in self.parts_df.columns:
                self.parts_df[col] = self.parts_df[col].fillna("").astype(str).str.strip()
                if col == "Sheet":
                    self.parts_df[col] = self.parts_df[col].apply(self.clean_qbom_string)

        # Clean parts quantity columns
        for col in ["Low", "Medium", "Complex"]:
            if col in self.parts_df.columns:
                self.parts_df[col] = pd.to_numeric(self.parts_df[col], errors="coerce").fillna(0)
                self.parts_df[col] = self.parts_df[col].clip(lower=0, upper=99).astype(int)

        # Clean sets sheet
        for col in ["Part Name", "SET"]:
            if col in self.sets_df.columns:
                self.sets_df[col] = self.sets_df[col].fillna("").astype(str).str.strip()
                if col == "SET":
                    self.sets_df[col] = self.sets_df[col].apply(self.clean_set)

        # Clean hours sheet text columns
        for col in ["SET", "ProductFamily", "Complexity", "Team"]:
            if col in self.hours_df.columns:
                self.hours_df[col] = self.hours_df[col].fillna("").astype(str).str.strip()
                if col == "SET":
                    self.hours_df[col] = self.hours_df[col].apply(self.clean_set)

        # Clean hour numeric columns
        for col in ["Modeling Hrs", "Detailing Hrs", "BOM Hrs", "QC Hrs"]:
            if col in self.hours_df.columns:
                self.hours_df[col] = pd.to_numeric(self.hours_df[col], errors="coerce").fillna(0)

    def get_filtered_parts(self, qbom, product_family):
        qbom = self.clean_qbom_string(qbom).lower()
        product_family = str(product_family).strip().lower()

        filtered = self.parts_df[
            (self.parts_df["Sheet"].str.lower() == qbom) &
            (self.parts_df["Product Family"].str.lower() == product_family) 
        ][["Part Name", "Low", "Medium", "Complex"]].copy()

        filtered["Part Name"] = filtered["Part Name"].str.strip()
        filtered = filtered[filtered["Part Name"] != ""]
        filtered = filtered.drop_duplicates(subset=["Part Name", "Low", "Medium", "Complex"])

        return filtered

    def get_parts_with_sets(self, qbom, product_family):
        filtered_parts = self.get_filtered_parts(qbom, product_family)

        sets_lookup = self.sets_df[["Part Name", "SET"]].copy()
        sets_lookup["Part Name"] = sets_lookup["Part Name"].str.strip()

        merged = filtered_parts.merge(sets_lookup, on="Part Name", how="left")
        merged["SET"] = merged["SET"].fillna("").astype(str).str.strip()

        return merged

    def get_complexity_hours(self, set_value, product_family, team):
        set_value = self.clean_set(set_value).lower()
        product_family = str(product_family).strip().lower()
        team = str(team).strip().lower()

        filtered = self.hours_df[
            (self.hours_df["SET"].str.lower() == set_value) &
            (self.hours_df["ProductFamily"].str.lower() == product_family) &
            (self.hours_df["Team"].str.lower() == team)
        ].copy()

        result = {
            "Low": {"Modeling Hrs": 0, "Detailing Hrs": 0, "BOM Hrs": 0, "QC Hrs": 0},
            "Medium": {"Modeling Hrs": 0, "Detailing Hrs": 0, "BOM Hrs": 0, "QC Hrs": 0},
            "Complex": {"Modeling Hrs": 0, "Detailing Hrs": 0, "BOM Hrs": 0, "QC Hrs": 0}
        }

        for complexity in ["Low", "Medium", "Complex"]:
            row = filtered[filtered["Complexity"].str.lower() == complexity.lower()]
            if not row.empty:
                row = row.iloc[0]
                result[complexity] = {
                    "Modeling Hrs": float(row.get("Modeling Hrs", 0)),
                    "Detailing Hrs": float(row.get("Detailing Hrs", 0)),
                    "BOM Hrs": float(row.get("BOM Hrs", 0)),
                    "QC Hrs": float(row.get("QC Hrs", 0))
                }

        return result

    def calculate_part_hours(self, set_value, product_family, team, low_qty, med_qty, complex_qty):
        low_qty = max(0, min(99, int(low_qty or 0)))
        med_qty = max(0, min(99, int(med_qty or 0)))
        complex_qty = max(0, min(99, int(complex_qty or 0)))

        hours = self.get_complexity_hours(set_value, product_family, team)

        modeling_hrs = (
            low_qty * hours["Low"]["Modeling Hrs"] +
            med_qty * hours["Medium"]["Modeling Hrs"] +
            complex_qty * hours["Complex"]["Modeling Hrs"]
        )

        detailing_hrs = (
            low_qty * hours["Low"]["Detailing Hrs"] +
            med_qty * hours["Medium"]["Detailing Hrs"] +
            complex_qty * hours["Complex"]["Detailing Hrs"]
        )

        bom_hrs = (
            low_qty * hours["Low"]["BOM Hrs"] +
            med_qty * hours["Medium"]["BOM Hrs"] +
            complex_qty * hours["Complex"]["BOM Hrs"]
        )

        qc_hrs = (
            low_qty * hours["Low"]["QC Hrs"] +
            med_qty * hours["Medium"]["QC Hrs"] +
            complex_qty * hours["Complex"]["QC Hrs"]
        )

        total_design_hrs = modeling_hrs + detailing_hrs + bom_hrs
        total_hrs = total_design_hrs + qc_hrs

        return {
            "Modeling Hrs": modeling_hrs,
            "Detailing Hrs": detailing_hrs,
            "BOM Hrs": bom_hrs,
            "QC Hrs": qc_hrs,
            "TotalDesignHrs": total_design_hrs,
            "Total Hrs": total_hrs
        }

    def clean_set(self, set_value):
        set_value = str(set_value).strip()
        if not set_value:
            return ""
        if " " in set_value:
            return set_value
        if len(set_value) <= 3:
            return set_value
        return set_value[:3] + " " + set_value[3:]

    def clean_qbom_string(self, value):
        value = str(value).strip()
        if not value:
            return ""

        if value.lower().startswith("q"):
            value = value[1:]

        value = value.replace("_", " ")
        return value.strip()