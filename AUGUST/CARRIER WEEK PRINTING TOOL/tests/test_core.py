from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from PIL import Image
from services.database_service import DatabaseService, QueryBackedDatabaseError
from services.excel_importer import ExcelImporter, ImportValidationError
from services.label_renderer import LabelRenderer
from services.student_search import matches_student_search

class CoreTests(unittest.TestCase):
    def setUp(self):
        test_temp = Path(__file__).resolve().parent / ".tmp"
        test_temp.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_temp)
        self.root = Path(self.temp.name)

    def tearDown(self): self.temp.cleanup()

    def write_response(self, name, rows):
        path = self.root / name
        pd.DataFrame(rows).to_excel(path, index=False)
        return path

    def test_sources_coexist_and_reimport_is_idempotent(self):
        importer, db = ExcelImporter(), DatabaseService(self.root / "database" / "students.xlsx")
        week = self.write_response("Carrier Week responses.xlsx", [{"ID": 1, "Nombre completo": "Juan Perez", "Carrera": "ITC", "Semestre": 6.0}])
        day = self.write_response("Carrier Day responses.xlsx", [{"ID": 1, "Nombre completo": "Luis Martinez", "Carrera": "IMA", "Semestre": 2}])
        self.assertEqual(db.upsert(importer.read(week).records)[:2], (1, 0))
        self.assertEqual(db.upsert(importer.read(week).records)[:2], (0, 1))
        self.assertEqual(db.upsert(importer.read(day).records)[:2], (1, 0))
        frame = db.load()
        self.assertEqual(set(frame.UniqueID), {"1 - Carrier Week", "1 - Carrier Day"})

    def test_update_preserves_print_history(self):
        importer, db = ExcelImporter(), DatabaseService(self.root / "students.xlsx")
        path = self.write_response("Carrier Week.xlsx", [{"ID": 12, "Nombre": "Juan Perez", "Carrera": "ITC", "Semestre": 6}])
        db.upsert(importer.read(path).records); db.mark_printed("12 - Carrier Week")
        self.write_response("Carrier Week.xlsx", [{"ID": 12, "Nombre": "Juan Carlos Perez", "Carrera": "ITC", "Semestre": 7}])
        db.upsert(importer.read(path).records)
        row = db.load().iloc[0]
        self.assertEqual((row["Nombre completo"], str(row.Semestre), row.Printed, row.PrintCount), ("Juan Carlos Perez", "7", "Yes", 1))

    def test_unknown_filename_rejected(self):
        with self.assertRaises(ImportValidationError): ExcelImporter.detect_source(Path("responses.xlsx"))

    def test_search_matches_partial_unique_id(self):
        student = {
            "UniqueID": "11 - Carrier Day",
            "Nombre completo": "Carolina Sánchez",
            "Carrera": "IDM",
        }
        self.assertTrue(matches_student_search(student, "11"))
        self.assertTrue(matches_student_search(student, "11 - carrier day"))
        self.assertTrue(matches_student_search(student, "carrier day"))
        self.assertTrue(matches_student_search(student, "sanchez"))
        self.assertFalse(matches_student_search(student, "carrier week"))

    def test_label_render_dimensions(self):
        assets = self.root / "assets"; assets.mkdir()
        Image.new("RGB", (799, 400), "white").save(assets / "label_template.png")
        cfg = {"label": {"width_px": 799, "height_px": 400, "name": {"x":399,"y":145,"max_width":700,"font_size":42}, "last_name": {"x":399,"y":195,"max_width":700,"font_size":38}, "career1": {"x":399,"y":245,"max_width":650,"font_size":30}, "career2": {"x":399,"y":275,"max_width":650,"font_size":26}, "semester": {"x":399,"y":310,"max_width":500,"font_size":28}, "folio": {"x":399,"y":365,"max_width":500,"font_size":20}}}
        image = LabelRenderer(assets / "label_template.png", assets / "fonts", cfg).render({"UniqueID":"12345 - Carrier Week","Nombre completo":"Nombre Muy Largo " * 8,"Carrera":"Programa Academico Extenso " * 4,"Semestre":"6"})
        self.assertEqual(image.size, (799, 400))
        self.assertTrue(any(channel_min < 255 for channel_min, _ in image.crop((100, 345, 700, 390)).getextrema()))

    def test_full_name_split_uses_second_space(self):
        self.assertEqual(
            LabelRenderer.split_full_name("Juan Carlos Pérez López"),
            ("Juan Carlos", "Pérez López"),
        )
        self.assertEqual(LabelRenderer.split_full_name("Ana García"), ("Ana", "García"))
        self.assertEqual(LabelRenderer.split_full_name("Madonna"), ("Madonna", ""))

    def test_legacy_nombre_database_is_migrated_on_load(self):
        path = self.root / "students.xlsx"
        pd.DataFrame([{
            "UniqueID": "8 - Carrier Day", "OriginalID": "8", "Nombre": "Ana García",
            "Carrera": "LDE", "Semestre": "4", "Source": "Carrier Day", "ImportedAt": "",
            "Printed": "No", "PrintedAt": "", "PrintCount": 0,
        }]).to_excel(path, index=False)
        frame = DatabaseService(path).load()
        self.assertEqual(frame.iloc[0]["Nombre completo"], "Ana García")

    def test_query_backed_sheets_keep_independent_incremental_ids(self):
        path = self.root / "students.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame([{"UniqueID": "1 - Carrier Day", "Id": 4, "Nombre completo": "Ana", "Carrera": "ITC", "Semestre": "5°"}]).to_excel(writer, index=False, sheet_name="Students - Carrier Day")
            pd.DataFrame([{"Id": 7, "Nombre completo": "Luis", "Carrera": "IIS", "Semestre": "7°"}]).to_excel(writer, index=False, sheet_name="Students - Carrier Week")
        frame = DatabaseService(path).load()
        self.assertEqual(set(frame["UniqueID"]), {"1 - Carrier Day", "1 - Carrier Week"})
        self.assertEqual(set(frame["Source"]), {"Carrier Day", "Carrier Week"})

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame([
                {"UniqueID": "1 - Carrier Day", "Id": 4, "Nombre completo": "Ana", "Carrera": "ITC", "Semestre": "5°"},
                {"Id": 20, "Nombre completo": "Marta", "Carrera": "IMA", "Semestre": "3°"},
            ]).to_excel(writer, index=False, sheet_name="Students - Carrier Day")
            pd.DataFrame([{"UniqueID": "1 - Carrier Week", "Id": 7, "Nombre completo": "Luis", "Carrera": "IIS", "Semestre": "7°"}]).to_excel(writer, index=False, sheet_name="Students - Carrier Week")
        refreshed = DatabaseService(path).load()
        self.assertEqual(set(refreshed["UniqueID"]), {"1 - Carrier Day", "2 - Carrier Day", "1 - Carrier Week"})
        self.assertTrue((refreshed["Printed"] == "No").all())

    def test_print_history_is_stored_without_rewriting_query_workbook(self):
        path = self.root / "students.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame([{"Id": 4, "Nombre completo": "Ana", "Carrera": "ITC", "Semestre": "5°"}]).to_excel(writer, index=False, sheet_name="Students - Carrier Day")
        before = path.read_bytes()
        db = DatabaseService(path)
        db.mark_printed("1 - Carrier Day")
        self.assertEqual(path.read_bytes(), before)
        row = db.load().iloc[0]
        self.assertEqual((row["Printed"], row["PrintCount"]), ("Yes", 1))

    def test_manual_import_cannot_overwrite_query_backed_sheets(self):
        path = self.root / "students.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame([{"Id": 4, "Nombre completo": "Ana", "Carrera": "ITC", "Semestre": "5°"}]).to_excel(writer, index=False, sheet_name="Students - Carrier Day")
        db = DatabaseService(path)
        with self.assertRaises(QueryBackedDatabaseError):
            db.upsert([{"UniqueID": "8 - Carrier Day", "OriginalID": "8", "Nombre completo": "Luis", "Carrera": "IIS", "Semestre": "7°", "Source": "Carrier Day"}])

    def test_new_carrier_day_row_generates_workbook_updates(self):
        raw = pd.DataFrame([
            {"UniqueID": "1 - Carrier Day", "Id": 4, "Nombre completo": "Ana", "Printed": "No", "PrintedAt": "", "PrintCount": 0},
            {"UniqueID": "", "Id": 15, "Nombre completo": "Carolina", "Printed": "", "PrintedAt": "", "PrintCount": ""},
        ])
        combined = pd.DataFrame([
            {"UniqueID": "1 - Carrier Day", "OriginalID": "4", "Source": "Carrier Day", "Printed": "No", "PrintedAt": "", "PrintCount": 0},
            {"UniqueID": "11 - Carrier Day", "OriginalID": "15", "Source": "Carrier Day", "Printed": "No", "PrintedAt": "", "PrintCount": 0},
        ])
        updates = DatabaseService(self.root / "students.xlsx")._query_sheet_updates(
            {"Students - Carrier Day": raw}, combined
        )
        self.assertEqual(
            updates,
            {"Students - Carrier Day": [(3, {"UniqueID": "11 - Carrier Day", "Printed": "No", "PrintCount": 0})]},
        )

    def test_print_history_generates_workbook_updates(self):
        raw = pd.DataFrame([{
            "UniqueID": "11 - Carrier Day", "Id": 15, "Printed": "No",
            "PrintedAt": "", "PrintCount": 0,
        }])
        combined = pd.DataFrame([{
            "UniqueID": "11 - Carrier Day", "OriginalID": "15", "Source": "Carrier Day",
            "Printed": "Yes", "PrintedAt": "2026-09-07 10:30:00", "PrintCount": 2,
        }])
        updates = DatabaseService(self.root / "students.xlsx")._query_sheet_updates(
            {"Students - Carrier Day": raw}, combined
        )
        self.assertEqual(updates["Students - Carrier Day"][0][1], {
            "Printed": "Yes", "PrintedAt": "2026-09-07 10:30:00", "PrintCount": 2,
        })

if __name__ == "__main__": unittest.main()
