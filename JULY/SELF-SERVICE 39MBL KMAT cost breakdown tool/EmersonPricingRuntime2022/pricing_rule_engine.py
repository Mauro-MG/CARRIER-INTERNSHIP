"""Python migration of the Lau fan-sled Excel pricing rules.

Reads the source .xlsm without opening Excel or changing the workbook. The
RULEBEGIN/RULEEND tables remain the source of truth. `$DRIVEDLL` is delegated
to the local loopback-only Emerson helper, which runs as the current user.

Usage:
    py -3 pricing_rule_engine.py 39MBHHGTB10674MHDK
    py -3 pricing_rule_engine.py PART --no-drive --trace
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
BASE34 = "0123456789ABCDEFGHJKLMNPQRSTVWXYZ-"
RUNTIME = Path(__file__).resolve().parent
DEFAULT_WORKBOOK = RUNTIME.parent / "laufansledprice20251013 RELEASED.xlsm"


def col_number(address: str) -> int:
    letters = re.match(r"[A-Z]+", address).group(0)  # type: ignore[union-attr]
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value


def address(row: int, column: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row}"


def excel_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class Hit:
    name: str = ""
    category: str = ""
    description: str = ""
    price: float = 0.0
    value: str = ""
    why: str = ""
    base: bool = False


@dataclass
class RuleBlock:
    name: str
    start_row: int
    end_row: int
    start_column: int
    end_column: int


@dataclass
class DriveSolution:
    driver_sheave: str = ""
    driver_bushing: str = ""
    driven_sheave: str = ""
    driven_bushing: str = ""
    belt: str = ""
    belt_qty: int = 0
    cost: float = 0.0
    extra_belt_cost: float = 0.0
    actual_center_distance: str = ""
    actual_service_factor: str = ""
    actual_driven_speed: str = ""


@dataclass
class PricingResult:
    part_number: str
    ok: bool
    total_price: float
    price_hits: list[Hit]
    variables: dict[str, str]
    errors: list[str]
    warnings: list[str]
    reconciliation: dict[str, Any]
    drive_solutions: list[DriveSolution] = field(default_factory=list)
    selected_drive: DriveSolution | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "part_number": self.part_number,
            "ok": self.ok,
            "total_price": round(self.total_price, 6),
            "price_hits": [asdict(hit) for hit in self.price_hits],
            "variables": self.variables,
            "errors": self.errors,
            "warnings": self.warnings,
            "reconciliation": self.reconciliation,
            "drive_solutions": [asdict(item) for item in self.drive_solutions],
            "selected_drive": asdict(self.selected_drive) if self.selected_drive else None,
        }


class WorkbookData:
    """Fast cached-value reader for the workbook's Open XML files."""

    def __init__(self, path: Path):
        self.path = path
        self.shared: list[str] = []
        self.sheet_paths: dict[str, str] = {}
        self._sheet_cache: dict[str, dict[tuple[int, int], Any]] = {}
        self.comments: dict[str, str] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        with zipfile.ZipFile(self.path) as archive:
            with archive.open("xl/sharedStrings.xml") as stream:
                for _, element in ET.iterparse(stream, events=("end",)):
                    if element.tag == NS + "si":
                        self.shared.append("".join(element.itertext()))
                        element.clear()

            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            rel_map = {
                item.attrib["Id"]: item.attrib["Target"]
                for item in relationships.findall(PKG_REL_NS + "Relationship")
            }
            sheets = workbook.find(NS + "sheets")
            if sheets is None:
                raise ValueError("Workbook has no sheets")
            for item in sheets:
                target = rel_map[item.attrib[REL_NS + "id"]].replace("\\", "/")
                if target.startswith("/"):
                    target = target.lstrip("/")
                elif not target.startswith("xl/"):
                    target = "xl/" + target.lstrip("/")
                self.sheet_paths[item.attrib["name"]] = target

            if "xl/comments1.xml" in archive.namelist():
                root = ET.fromstring(archive.read("xl/comments1.xml"))
                comment_list = root.find(NS + "commentList")
                if comment_list is not None:
                    for comment in comment_list:
                        self.comments[comment.attrib["ref"]] = "".join(comment.itertext()).strip()

    def sheet(self, name: str) -> dict[tuple[int, int], Any]:
        if name in self._sheet_cache:
            return self._sheet_cache[name]
        target = self.sheet_paths[name]
        cells: dict[tuple[int, int], Any] = {}
        with zipfile.ZipFile(self.path) as archive, archive.open(target) as stream:
            for _, element in ET.iterparse(stream, events=("end",)):
                if element.tag != NS + "c":
                    continue
                ref = element.attrib["r"]
                row = int(re.search(r"\d+", ref).group(0))  # type: ignore[union-attr]
                column = col_number(ref)
                value_element = element.find(NS + "v")
                value: Any = None if value_element is None else value_element.text
                cell_type = element.attrib.get("t")
                if cell_type == "s" and value is not None:
                    value = self.shared[int(value)]
                elif cell_type == "inlineStr":
                    value = "".join(element.itertext())
                elif cell_type == "b" and value is not None:
                    value = value == "1"
                elif value is not None and cell_type not in ("str", "e"):
                    try:
                        value = float(value)
                        if value.is_integer():
                            value = int(value)
                    except ValueError:
                        pass
                cells[(row, column)] = value
                element.clear()
        self._sheet_cache[name] = cells
        return cells

    def lookup_table(self, sheet: str, key_col: int, value_cols: tuple[int, ...]) -> dict[str, tuple[Any, ...]]:
        cells = self.sheet(sheet)
        rows = sorted({row for row, _ in cells})
        result: dict[str, tuple[Any, ...]] = {}
        for row in rows:
            key = excel_text(cells.get((row, key_col)))
            if key:
                result[key] = tuple(cells.get((row, column)) for column in value_cols)
        return result


class LoopbackSolver:
    def __init__(self, runtime: Path):
        self.runtime = runtime
        self.process: subprocess.Popen[str] | None = None
        self.port = 0

    def __enter__(self) -> "LoopbackSolver":
        helper = self.runtime / "WcfEmersonEXE-loopback.exe"
        if not helper.exists():
            raise FileNotFoundError(helper)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = int(sock.getsockname()[1])
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.process = subprocess.Popen(
            [str(helper), str(self.runtime), f"http://127.0.0.1:{self.port}/"],
            cwd=self.runtime,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=flags,
        )
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(f"Solver exited early.\n{stdout}\n{stderr}")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return self
            except OSError:
                time.sleep(0.1)
        raise TimeoutError("Solver did not start listening")

    def __exit__(self, *_: Any) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        if self.process:
            if self.process.stdout:
                self.process.stdout.close()
            if self.process.stderr:
                self.process.stderr.close()

    def post(self, xml: str) -> str:
        endpoint = f"http://127.0.0.1:{self.port}/SelectDrive"
        request = urllib.request.Request(
            endpoint,
            data=xml.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Solver HTTP {exc.code}: {details}") from exc


class PricingEngine:
    def __init__(self, workbook: Path, runtime: Path = RUNTIME, trace: bool = False):
        self.book = WorkbookData(workbook)
        self.rules = self.book.sheet("Rules")
        self.runtime = runtime
        self.trace_enabled = trace
        self.blocks = self._find_rule_blocks()
        self.motor_frames = self.book.lookup_table("Motor Frame ", 4, (5, 6))
        self.emerson_costs = {
            key: number(values[0])
            for key, values in self.book.lookup_table("emersoncosts", 4, (5,)).items()
        }
        self.hits: list[Hit] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.trace: list[str] = []
        self.drive_solutions: list[DriveSolution] = []
        self.selected_drive: DriveSolution | None = None
        self.solver: LoopbackSolver | None = None

    def _find_rule_blocks(self) -> list[RuleBlock]:
        beginnings = sorted(
            (row, col, value)
            for (row, col), value in self.rules.items()
            if isinstance(value, str) and value.startswith("RULEBEGIN.")
        )
        endings = sorted(
            (row, col) for (row, col), value in self.rules.items() if value == "RULEEND"
        )
        blocks: list[RuleBlock] = []
        for start_row, start_col, name in beginnings:
            possible = [(row, col) for row, col in endings if row > start_row]
            if not possible:
                raise ValueError(f"No RULEEND after {address(start_row, start_col)}")
            end_row, _ = min(possible)
            header_columns = [
                col for (row, col), value in self.rules.items()
                if row == start_row and value not in (None, "")
            ]
            end_column = max(header_columns)
            blocks.append(RuleBlock(name, start_row, end_row, start_col, end_column))
        return blocks

    def find_hit(self, name: str) -> Hit | None:
        return next((hit for hit in self.hits if hit.name == name), None)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def log(self, message: str) -> None:
        if self.trace_enabled:
            self.trace.append(message)

    def restriction_allows(self, hit: Hit, restriction: str) -> bool:
        rule = restriction.strip()
        mapping = {
            '== "BELTPOSTFIVESIX"': hit.value == "BELTPOSTFIVESIX",
            '== "BELTPREFIVESIX"': hit.value == "BELTPREFIVESIX",
            '== "DDPF"': hit.value == "DDPF",
            '!= "DDPF"': hit.value != "DDPF",
            '=="9"': hit.value == "9",
            '!="9"': hit.value != "9",
        }
        if rule == 'not matches("TBL")':
            return hit.value not in "TBL"
        if rule == 'in ("BELTPREFIVESIX","BELTPOSTFIVESIX")':
            return hit.value in ("BELTPREFIVESIX", "BELTPOSTFIVESIX")
        if rule in mapping:
            return mapping[rule]
        self.error(f"Unsupported header restriction {rule!r}")
        return True  # Matches the VBA fallback after recording an error.

    def substitute(self, value: str) -> str:
        while "*" in value:
            match = re.search(r"\*([^#]+)#", value)
            if not match:
                self.error(f"Malformed substitution {value!r}")
                break
            hit = self.find_hit(match.group(1))
            replacement = hit.value if hit else ""
            if hit is None:
                self.error(f"Unknown substitution {match.group(1)}")
            value = value.replace(match.group(0), replacement)
        return value

    @staticmethod
    def decode_base34(value: str) -> int:
        result = 0
        for char in value:
            result = result * 34 + BASE34.index(char)
        return result

    @staticmethod
    def encode_base34(value: int) -> str:
        output = ""
        while True:
            value, remainder = divmod(value, 34)
            output = BASE34[remainder] + output
            if value < 1:
                return output

    def process_hit(self, hit: Hit) -> None:
        hit.value = self.substitute(hit.value)
        if hit.category == "$MOTOR":
            fan_qty = self.find_hit("FANQUANTITY")
            if fan_qty is None:
                self.error("Did not find FANQUANTITY in motor calculation")
            else:
                hit.price *= number(fan_qty.value)
        if hit.category == "CONVERTTOMOTORBASECODE":
            original = hit.value
            decoded = self.decode_base34(hit.value)
            if decoded > 578:
                decoded = abs(decoded - 1155)
            hit.category = "MOTORBASECODE"
            hit.name = "MOTORBASECODE"
            hit.value = self.encode_base34(decoded).rjust(2, "0")
            hit.description = f"{hit.description} {original} {hit.value}".strip()
        if hit.category.startswith("REMOVE."):
            target = hit.category[7:]
            for index, old in enumerate(self.hits):
                if old.category == target:
                    self.hits.pop(index)
                    break
        if "ERROR" in hit.category.upper():
            self.error(f"Error rule fired [{hit.category}] {hit.description} ({hit.why})")

    def _header_groups(self, block: RuleBlock) -> tuple[list[tuple[int, str, bool]], list[tuple[int, int, int]]] | None:
        matchers: list[tuple[int, str, bool]] = []
        groups: list[list[int]] = []
        current = [-1, -1, -1]
        for col in range(block.start_column + 1, block.end_column + 1):
            header = excel_text(self.rules.get((block.start_row, col)))
            if not header:
                continue
            if header.startswith("HIT."):
                if header == "HIT.CATEGORY":
                    if current[0] >= 0:
                        groups.append(current)
                        current = [-1, -1, -1]
                    current[0] = col
                elif header == "HIT.VALUE":
                    current[1] = col
                elif header == "HIT.DESCRIPTION":
                    current[2] = col
                else:
                    self.error(f"Unknown header {header} at {address(block.start_row, col)}")
                    return None
            else:
                hit = self.find_hit(header)
                if hit is None:
                    self.error(f"Unknown rule input {header} at {address(block.start_row, col)}")
                    return None
                restriction = self.book.comments.get(address(block.start_row, col), "")
                if restriction and not self.restriction_allows(hit, restriction):
                    return None
                matchers.append((col, hit.value, header.startswith("P")))
        if current[0] >= 0:
            groups.append(current)
        valid_groups = [tuple(item) for item in groups if all(col >= 0 for col in item)]
        if len(valid_groups) != len(groups):
            self.error(f"Incomplete HIT group in {block.name} row {block.start_row}")
            return None
        return matchers, valid_groups

    def run_rule(self, block: RuleBlock) -> None:
        setup = self._header_groups(block)
        if setup is None:
            return
        matchers, groups = setup
        for row in range(block.start_row + 1, block.end_row):
            matched = bool(matchers)
            for col, expected, is_position in matchers:
                possible = excel_text(self.rules.get((row, col)))
                if not possible:
                    continue  # Blank rule column is a wildcard in the VBA tables.
                if possible.startswith("^"):
                    if expected in possible:
                        matched = False
                        break
                elif expected not in possible or (not is_position and possible != expected):
                    matched = False
                    break
            if not matched:
                continue
            for category_col, value_col, description_col in groups:
                category = excel_text(self.rules.get((row, category_col)))
                if not category:
                    continue
                raw_value = self.rules.get((row, value_col))
                description = excel_text(self.rules.get((row, description_col)))
                if category.startswith("$"):
                    hit = Hit(
                        name="PRICEHIT", category=category, description=description,
                        price=number(raw_value), why=address(row, block.start_column + 1),
                    )
                    if hit.price == 0:
                        self.error(f"Zero price added for {category} at {hit.why}")
                        return
                else:
                    hit = Hit(
                        name=category, category=category, description=description,
                        value=excel_text(raw_value), why=address(row, block.start_column + 1),
                    )
                self.process_hit(hit)
                if any(old.category == hit.category for old in self.hits):
                    self.error(f"Duplicate category {hit.category} at {hit.why}")
                self.hits.append(hit)
                self.log(f"{block.name} {hit.category or hit.name}={hit.price or hit.value} {hit.why}")

    def drive_input_xml(self, use_nema: bool, extra_face_width: bool) -> str:
        def get(name: str) -> str:
            hit = self.find_hit(name)
            if hit is None:
                self.error(f"Unknown {name} in drive calculation")
                return ""
            return hit.value

        motor_frame = get("MOTORFRAME")
        frame_values = self.motor_frames.get(motor_frame)
        if not frame_values:
            self.error(f"MOTORFRAME {motor_frame!r} not found in Motor Frame sheet")
            max_driver_pd = driver_diameter = ""
        else:
            max_driver_pd, driver_diameter = map(excel_text, frame_values)
        rpm_map = {"1200": "1160", "1800": "1750", "3600": "3450", "1500": "1450", "3000": "2900"}
        driver_rpm = rpm_map.get(get("MOTORRPM"), "")
        if not driver_rpm:
            self.error("Unknown MOTORRPM in drive calculation")
        pitch = get("DRIVEPITCH")
        variable = "False" if pitch == "CONSTANT" else "True"
        min_tolerance, max_tolerance = (("2", "3") if pitch == "CONSTANT" else ("5", "5"))
        multiple = get("DRIVEMULTIPLEBELT")
        min_grooves = "2" if multiple == "YES" else "1"
        max_width = "19" if extra_face_width else get("DRIVENMAXWIDTH")
        nema_number = motor_frame.split("T", 1)[0] if use_nema else "0"

        required = {
            "ReqInp_DoNotExceedSpeed": "9999", "ReqInp_DrivenDiameter": get("FANSHAFT"),
            "ReqInp_DrivenSpeed": get("WHEELRPM"), "ReqInp_DriverDiameter": driver_diameter,
            "ReqInp_DriverSpeed": driver_rpm, "ReqInp_Horsepower": get("MOTORHP"),
            "ReqInp_MinCenterDistance": get("CENTERLINELOW"), "ReqInp_MaxCenterDistance": get("CENTERLINEHIGH"),
            "ReqInp_ServiceFactor": get("DRIVESERVICEFACTOR"), "ReqInp_VariableSpeed": variable,
            "ReqInp_DrivenDiameterIsMetric": "False", "ReqInp_DrivenSpeedIsMidrange": "True",
            "ReqInp_DriverDiameterIsMetric": "False", "ReqInp_OptionsInvoked": "True",
            "ReqInp_OrderDrive": "False", "ReqInp_OutputMode": "1", "ReqInp_InputPowerMode": "1",
            "ReqInp_CenterDistanceMode": "1", "SelectedMultID": "0", "ReqInp_ProvideNetPrice": "True",
            "ReqInp_ProvideInterchanges": "False",
        }
        optional = {
            "OptInp_MinNumGrooves": min_grooves, "OptInp_MaxSpeedVariation": max_tolerance,
            "OptInp_MinSpeedVariation": min_tolerance, "OptInp_MaxDriverPD": max_driver_pd,
            "OptInp_Allow3VXBelts": "True", "OptInp_Allow4LBelts": "False",
            "OptInp_Allow5LBelts": "False", "OptInp_Allow5VBelts": "True",
            "OptInp_Allow5VXBelts": "True", "OptInp_Allow8VBelts": "False",
            "OptInp_AllowABelts": "True", "OptInp_AllowAXBelts": "True", "OptInp_AllowBBelts": "True",
            "OptInp_AllowBrowningBushedSheaves": "True", "OptInp_AllowBXBelts": "True",
            "OptInp_AllowCBelts": "False", "OptInp_AllowCXBelts": "False",
            "OptInp_AllowFinishedBoreSheaves": "True", "OptInp_AllowQDBushedSheaves": "True",
            "OptInp_LimitHubLoad": "False", "OptInp_MaxBeltFPM": "6500",
            "OptInp_MaxDrivenPD": get("DRIVENMAXPD"), "OptInp_MaxFaceWidth": max_width,
            "OptInp_MaxHubLoad": "9999", "OptInp_MaxNumGrooves": "16", "OptInp_MinBeltFPM": "900",
            "OptInp_MinDrivenPD": "1.5", "OptInp_MinDriverPD": "1.5",
            "OptInp_ConformToNEMAStandard": "True" if use_nema else "False",
            "OptInp_NEMANumber": nema_number, "OptInp_UseDesignatedPartsOnly": "False",
            "SelectedDesgPartsListID": "-1", "OptInp_UseMinSpeedInHorsepowerCalculation": "False",
        }
        main = ET.Element("Main")
        settings = ET.SubElement(main, "Settings")
        ET.SubElement(settings, "IgnoreNEMAStandards").text = "True"
        ET.SubElement(settings, "Data").text = "XML"
        data = ET.SubElement(settings, "Data")
        ET.SubElement(data, "XMLPath").text = str(self.runtime)
        ET.SubElement(settings, "Culture").text = "es-mx"
        input_string = ET.SubElement(main, "InputString")
        for section_name, values in (("RequiredInputs", required), ("OptionalInputs", optional)):
            section = ET.SubElement(input_string, section_name)
            for key, value in values.items():
                item = ET.SubElement(section, "Input")
                ET.SubElement(item, "ID").text = key
                ET.SubElement(item, "Value").text = value
        return ET.tostring(main, encoding="unicode")

    def parse_solutions(self, response: str) -> list[DriveSolution]:
        if not response.startswith("GOOD:"):
            return []
        root = ET.fromstring(response[5:])
        output: list[DriveSolution] = []
        solutions_node = root.find("Solutions")
        if solutions_node is None:
            return output
        for solution_node in solutions_node.findall("Solution"):
            props = {
                item.findtext("Name", ""): item.findtext("Value", "")
                for item in solution_node.findall("Property")
            }
            belt = props.get("Belt", "")
            qty = int(number(props.get("BeltQty")))
            output.append(DriveSolution(
                driver_sheave=props.get("DriverSheave", ""), driver_bushing=props.get("DriverBushing", ""),
                driven_sheave=props.get("DrivenSheave", ""), driven_bushing=props.get("DrivenBushing", ""),
                belt=belt, belt_qty=qty, cost=number(props.get("Cost")),
                extra_belt_cost=self.emerson_costs.get("l" + belt, 0.0) * qty,
                actual_center_distance=props.get("ActualCenterDistance", ""),
                actual_service_factor=props.get("ActualServiceFactor", ""),
                actual_driven_speed=props.get("ActualDrivenShaftSpeed", ""),
            ))
        return output

    def run_drive(self, hit: Hit) -> None:
        if self.solver is None:
            hit.category = "ERRORDRIVEDLL"
            hit.price = 0
            self.error("Drive solver is disabled")
            return
        response = ""
        solutions: list[DriveSolution] = []
        for use_nema, extra_width in ((True, False), (False, True)):
            request_xml = self.drive_input_xml(use_nema, extra_width)
            response = self.solver.post(request_xml)
            solutions = self.parse_solutions(response)
            if any(item.cost > 0 for item in solutions):
                break
        self.drive_solutions = solutions
        if not solutions:
            hit.category = "ERRORDRIVEDLL"
            hit.price = 0
            self.error("Drive selection failed: " + response[:500])
            return
        valid = sorted((item for item in solutions if item.cost > 0), key=lambda item: item.cost)
        lowest = valid[0]
        selected = next((item for item in valid if item.cost > lowest.cost), None)
        if selected is None:
            selected = lowest
            self.warnings.append("Only one distinct drive cost; used lowest solution instead of VBA sentinel 999999 bug")
        self.selected_drive = selected
        extra_belts = self.find_hit("EXTRABELTS")
        extra_cost = 0.0
        if extra_belts is None:
            self.error("Unknown EXTRABELTS in drive calculation")
        elif extra_belts.value == "YES":
            extra_cost = selected.extra_belt_cost
            if extra_cost < 1:
                self.error(f"Extra belt cost lookup failed for l{selected.belt}")
        elif extra_belts.value != "NO":
            self.error(f"EXTRABELTS is not YES/NO: {extra_belts.value}")
        hit.category = "$DRIVEDLL"
        hit.description = f"Second distinct drive solution {selected.cost:.2f}; extra belt {extra_cost:.2f}"
        hit.price = (selected.cost + extra_cost) * hit.price

    def calculate(self, part_number: str, include_drive: bool = True) -> PricingResult:
        self.hits = [
            Hit(name=f"P{index}", value=char, why="Part number decode", base=True)
            for index, char in enumerate(part_number.strip().upper(), 1)
        ]
        self.errors = []
        self.warnings = []
        self.trace = []
        self.drive_solutions = []
        self.selected_drive = None

        solver_context: Any = LoopbackSolver(self.runtime) if include_drive else _NullContext()
        with solver_context as solver:
            self.solver = solver
            for block in self.blocks:
                before = len(self.hits)
                self.run_rule(block)
                for hit in self.hits[before:]:
                    if hit.category == "$DRIVEDLL":
                        # run_rule processes ordinary special hits immediately; drive needs solver context.
                        self.run_drive(hit)
        price_hits = [hit for hit in self.hits if not hit.base and abs(hit.price) > 0]
        variables: dict[str, str] = {}
        for hit in self.hits:
            if not hit.base and abs(hit.price) < 1e-9 and hit.name:
                variables.setdefault(hit.name, hit.value)
        total = 0.0
        for hit in price_hits:
            if hit.category.startswith("$MOTOR"):
                factor_name = "MOTORFACTOR"
            elif hit.category.startswith("$DRIVE"):
                factor_name = "DRIVEFACTOR"
            else:
                factor_name = "SLEDFACTOR"
            factor = number(variables.get(factor_name))
            if factor == 0:
                self.error(f"Missing or zero {factor_name}")
            total += hit.price * factor

        # Explicit three-bucket check requested for migration validation.
        # Sled includes base, springs, and all option categories.
        bucket_prefixes = {
            "sled": ("$BASE", "$SPRINGS", "$OPTIONS"),
            "motor": ("$MOTOR",),
            "drive": ("$DRIVE",),
        }
        bucket_factors = {
            "sled": number(variables.get("SLEDFACTOR")),
            "motor": number(variables.get("MOTORFACTOR")),
            "drive": number(variables.get("DRIVEFACTOR")),
        }
        raw_sums = {
            bucket: sum(
                hit.price
                for hit in price_hits
                if hit.category.startswith(prefixes)
            )
            for bucket, prefixes in bucket_prefixes.items()
        }
        adjusted_sums = {
            bucket: raw_sums[bucket] * bucket_factors[bucket]
            for bucket in bucket_prefixes
        }
        three_bucket_total = sum(adjusted_sums.values())
        unclassified = []
        for hit in price_hits:
            if any(hit.category.startswith(prefixes) for prefixes in bucket_prefixes.values()):
                continue
            # This is how the legacy total treats every non-motor/non-drive hit.
            adjusted = hit.price * bucket_factors["sled"]
            unclassified.append({
                "category": hit.category,
                "price": hit.price,
                "factor_used_by_total_price": bucket_factors["sled"],
                "adjusted_price": adjusted,
                "why": hit.why,
            })
        difference = total - three_bucket_total
        price_tolerance = 0.01
        reconciliation = {
            "bucket_prefixes": {key: list(value) for key, value in bucket_prefixes.items()},
            "raw_sums": raw_sums,
            "factors": bucket_factors,
            "adjusted_sums": adjusted_sums,
            "three_bucket_total": three_bucket_total,
            "total_price": total,
            "difference_total_minus_three_buckets": difference,
            "price_tolerance": price_tolerance,
            "matches_total_price": abs(difference) <= price_tolerance,
            "unclassified_price_hits": unclassified,
            "unclassified_adjusted_total": sum(item["adjusted_price"] for item in unclassified),
        }
        return PricingResult(
            part_number=part_number.strip().upper(), ok=not self.errors, total_price=total,
            price_hits=price_hits, variables=variables, errors=self.errors,
            warnings=self.warnings, reconciliation=reconciliation,
            drive_solutions=self.drive_solutions,
            selected_drive=self.selected_drive,
        )


class _NullContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: Any) -> None:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part_number")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--runtime", type=Path, default=RUNTIME)
    parser.add_argument("--no-drive", action="store_true", help="Evaluate rules but do not call Emerson")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    engine = PricingEngine(args.workbook.resolve(), args.runtime.resolve(), args.trace)
    result = engine.calculate(args.part_number, include_drive=not args.no_drive)
    payload = result.public_dict()
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    print(rendered)
    if args.trace:
        print("\nTRACE", file=sys.stderr)
        print("\n".join(engine.trace), file=sys.stderr)
    if args.json_out:
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
