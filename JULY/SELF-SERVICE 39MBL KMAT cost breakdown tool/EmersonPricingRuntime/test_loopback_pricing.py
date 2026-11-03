"""Smoke-test the Emerson pricing helper without administrator rights.

The script starts the loopback-only helper as the current Windows user, sends
one hardcoded drive-selection request, prints the response, and stops it.
Only Python's standard library is required.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HELPER = ROOT / "WcfEmersonEXE-loopback.exe"

# Representative test inputs. Replace these later with values derived from the
# part-number rules: 5 HP, 1750 RPM motor, 1000 RPM fan, and a 12-18 in center.
TEST_REQUEST = """<Main>
  <Settings>
    <IgnoreNEMAStandards>True</IgnoreNEMAStandards>
    <Data>XML</Data>
    <Data><XMLPath>PATHPATHPATH</XMLPath></Data>
    <Culture>es-mx</Culture>
  </Settings>
  <InputString>
    <RequiredInputs>
      <Property><ID>ReqInp_DoNotExceedSpeed</ID><Value>9999</Value></Property>
      <Property><ID>ReqInp_DrivenDiameter</ID><Value>1.5</Value></Property>
      <Property><ID>ReqInp_DrivenSpeed</ID><Value>1000</Value></Property>
      <Property><ID>ReqInp_DriverDiameter</ID><Value>1.125</Value></Property>
      <Property><ID>ReqInp_DriverSpeed</ID><Value>1750</Value></Property>
      <Property><ID>ReqInp_Horsepower</ID><Value>5</Value></Property>
      <Property><ID>ReqInp_MinCenterDistance</ID><Value>12</Value></Property>
      <Property><ID>ReqInp_MaxCenterDistance</ID><Value>18</Value></Property>
      <Property><ID>ReqInp_ServiceFactor</ID><Value>1.2</Value></Property>
      <Property><ID>ReqInp_VariableSpeed</ID><Value>False</Value></Property>
      <Property><ID>ReqInp_DrivenDiameterIsMetric</ID><Value>False</Value></Property>
      <Property><ID>ReqInp_DrivenSpeedIsMidrange</ID><Value>True</Value></Property>
      <Property><ID>ReqInp_DriverDiameterIsMetric</ID><Value>False</Value></Property>
      <Property><ID>ReqInp_OptionsInvoked</ID><Value>True</Value></Property>
      <Property><ID>ReqInp_OrderDrive</ID><Value>False</Value></Property>
      <Property><ID>ReqInp_OutputMode</ID><Value>1</Value></Property>
      <Property><ID>ReqInp_InputPowerMode</ID><Value>1</Value></Property>
      <Property><ID>ReqInp_CenterDistanceMode</ID><Value>1</Value></Property>
      <Property><ID>SelectedMultID</ID><Value>0</Value></Property>
      <Property><ID>ReqInp_ProvideNetPrice</ID><Value>True</Value></Property>
      <Property><ID>ReqInp_ProvideInterchanges</ID><Value>False</Value></Property>
    </RequiredInputs>
    <OptionalInputs>
      <Property><ID>OptInp_MinNumGrooves</ID><Value>1</Value></Property>
      <Property><ID>OptInp_MaxSpeedVariation</ID><Value>3</Value></Property>
      <Property><ID>OptInp_MinSpeedVariation</ID><Value>2</Value></Property>
      <Property><ID>OptInp_MaxDriverPD</ID><Value>8</Value></Property>
      <Property><ID>OptInp_Allow3VXBelts</ID><Value>True</Value></Property>
      <Property><ID>OptInp_Allow4LBelts</ID><Value>False</Value></Property>
      <Property><ID>OptInp_Allow5LBelts</ID><Value>False</Value></Property>
      <Property><ID>OptInp_Allow5VBelts</ID><Value>True</Value></Property>
      <Property><ID>OptInp_Allow5VXBelts</ID><Value>True</Value></Property>
      <Property><ID>OptInp_Allow8VBelts</ID><Value>False</Value></Property>
      <Property><ID>OptInp_AllowABelts</ID><Value>True</Value></Property>
      <Property><ID>OptInp_AllowAXBelts</ID><Value>True</Value></Property>
      <Property><ID>OptInp_AllowBBelts</ID><Value>True</Value></Property>
      <Property><ID>OptInp_AllowBrowningBushedSheaves</ID><Value>True</Value></Property>
      <Property><ID>OptInp_AllowBXBelts</ID><Value>True</Value></Property>
      <Property><ID>OptInp_AllowCBelts</ID><Value>False</Value></Property>
      <Property><ID>OptInp_AllowCXBelts</ID><Value>False</Value></Property>
      <Property><ID>OptInp_AllowFinishedBoreSheaves</ID><Value>True</Value></Property>
      <Property><ID>OptInp_AllowQDBushedSheaves</ID><Value>True</Value></Property>
      <Property><ID>OptInp_LimitHubLoad</ID><Value>False</Value></Property>
      <Property><ID>OptInp_MaxBeltFPM</ID><Value>6500</Value></Property>
      <Property><ID>OptInp_MaxDrivenPD</ID><Value>15</Value></Property>
      <Property><ID>OptInp_MaxFaceWidth</ID><Value>8</Value></Property>
      <Property><ID>OptInp_MaxHubLoad</ID><Value>9999</Value></Property>
      <Property><ID>OptInp_MaxNumGrooves</ID><Value>16</Value></Property>
      <Property><ID>OptInp_MinBeltFPM</ID><Value>900</Value></Property>
      <Property><ID>OptInp_MinDrivenPD</ID><Value>1.5</Value></Property>
      <Property><ID>OptInp_MinDriverPD</ID><Value>1.5</Value></Property>
      <Property><ID>OptInp_ConformToNEMAStandard</ID><Value>True</Value></Property>
      <Property><ID>OptInp_NEMANumber</ID><Value>184</Value></Property>
      <Property><ID>OptInp_UseDesignatedPartsOnly</ID><Value>False</Value></Property>
      <Property><ID>SelectedDesgPartsListID</ID><Value>-1</Value></Property>
      <Property><ID>OptInp_UseMinSpeedInHorsepowerCalculation</ID><Value>False</Value></Property>
    </OptionalInputs>
  </InputString>
</Main>"""

# The vendor schema names each entry ``Input``. Keeping the readable payload
# above mechanically normalized makes accidental Property/Input drift obvious.
TEST_REQUEST = TEST_REQUEST.replace("<Property>", "<Input>").replace("</Property>", "</Input>")


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until_listening(process: subprocess.Popen[str], port: int, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise RuntimeError(
                f"Pricing helper exited with code {process.returncode}.\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Pricing helper did not listen on 127.0.0.1:{port}")


def main() -> int:
    if not HELPER.exists():
        print(f"Missing helper: {HELPER}", file=sys.stderr)
        return 2

    port = available_port()
    base_url = f"http://127.0.0.1:{port}/"
    endpoint = base_url + "SelectDrive"
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    print(f"Starting helper as current user on {base_url}")
    process = subprocess.Popen(
        [str(HELPER), str(ROOT), base_url],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creationflags,
    )

    try:
        wait_until_listening(process, port)
        request = urllib.request.Request(
            endpoint,
            data=TEST_REQUEST.encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
        print(f"POST {endpoint}")
        with urllib.request.urlopen(request, timeout=60) as response:
            result = response.read().decode("utf-8", errors="replace")
        print(f"HTTP request succeeded; response length: {len(result):,} characters")
        print(result)
        return 0 if result.startswith("GOOD:") else 1
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {details}", file=sys.stderr)
        if "PTS.VbeltDriveLibrary" in details:
            print(
                "\nDeployment dependency missing: copy PTS.VbeltDriveLibrary.dll "
                "and its dependent DLL/catalog files beside the helper, or into a "
                "runtime directory the helper can resolve.",
                file=sys.stderr,
            )
        return 1
    except Exception as exc:
        print(f"Test failed: {exc}", file=sys.stderr)
        return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
