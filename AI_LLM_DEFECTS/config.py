PRIMARY_COMPONENTS = [
    "Electrical controls", "Evaporator", "Non-component", "Gas", "Input Devices",
    "Starter/VFD", "Condenser", "Compressor", "Valve", "Other", "Oil System", "Ambiguous"
]

SECONDARY_COMPONENTS = [
    "Electrical Controls - Wiring", "Electrical Controls - Boards", "Cond/Evap - Fan motor",
    "NC - Water Leak", "NC - Refrigerant Leak", "NC - Not Warranty",
    "Cond/Evap - Fan blades", "Gas - Valve", "Cond/Evap - coil leak",
    "Input devices - Transducer", "Starter/VFD - Boards", "Electrical Controls - Breakers",
    "Electrical Controls - Contactors", "NC - field install issue", "NC -no fault found",
    "Input devices - High pressure switch", "Valve - EXV/TXV", "Starter/VFD - wiring",
    "Input devices - Temp sensor", "Electronic Controls - wiring", "NC - concession",
    "NC - Cosmetic", "Compressor - Mechanical failure", "NC - Other (comments box)",
    "Non-Component - Other (comments box)", "Non-Component - Refrigerant Leak",
    "Starter/VFD - Program", "Other - note issues in comments", "Valve - Check",
    "NC - missing parts", "NC - no fault found", "NC - frame", "NC - sales order issue",
    "Non-Component - Cosmetic Damage", "Valve - economizer", "Electrical Controls - Transformer",
    "Oil system - oil line", "Compressor - Motor", "NC - configuration",
    "Input devices - Thermistor", "NC - Field Install Issues", "Valve - Stepper",
    "Electrical Controls - Program", "Electronic controls - program", "NC - Cosmetic Damage",
    "Valve - damper", "Input devices - Sensor", "Compressor - Heater",
    "Electrical controls - display", "Electrical Controls - Relays",
    "NC -  refrigerant undercharge", "NC -  Refrigerant leak", "NC - refrigerant overcharge",
    "NC - system contamination", "Electrical Controls - fuses", "NC - no fault found ",
    "NC - no fault found (noise/vibration)", "NC - not fault found", "NC - service call",
    "NC - no fault found  ", "Gas - Inducer", "Gas-burner", "Gas - leak",
    "NC-insulation", "NC - insulation", "Gas - Sensor", "Compressor - wiring",
    "Gas - HX", "Gas - exhaust", "Input devices -Flow Switch", "NC -refrigerant leak",
    "Non-Component - Water Leak", "NC-field install issue", "NC -  configuration",
    "Valve - Ball", "0", "NC - refrigerant undercharge", "Valve - charging/service",
    "NC - air leak", "NC - leak", "Valve - actuator", "NC -not warranty", "Ambiguous"
]

FAILURE_REASONS = [
    "Design", "Installation", "Manufacturing", "Applications/Systems",
    "Part Failure", "Network Controls", "Resettable alarms", "Other", "Ambiguous"
]

VALID_SECONDARY_BY_PRIMARY = {
    "Compressor": ["Compressor - Mechanical failure", "Compressor - Motor", "Compressor - Heater", "Compressor - wiring"],
    "Electrical controls": [
        "Electrical Controls - Wiring", "Electrical Controls - Boards", "Electrical Controls - Breakers",
        "Electrical Controls - Contactors", "Electrical Controls - Transformer", "Electrical Controls - Program",
        "Electrical controls - display", "Electrical Controls - Relays", "Electrical Controls - fuses",
        "Electronic Controls - wiring", "Electronic controls - program"
    ],
    "Starter/VFD": ["Starter/VFD - Boards", "Starter/VFD - wiring", "Starter/VFD - Program"],
    "Input Devices": [
        "Input devices - Transducer", "Input devices - High pressure switch", "Input devices - Temp sensor",
        "Input devices - Thermistor", "Input devices - Sensor", "Input devices -Flow Switch"
    ],
    "Valve": ["Valve - EXV/TXV", "Valve - Check", "Valve - economizer", "Valve - Stepper", "Valve - damper", "Valve - Ball", "Valve - charging/service", "Valve - actuator"],
    "Gas": ["Gas - Valve", "Gas - Inducer", "Gas-burner", "Gas - leak", "Gas - Sensor", "Gas - HX", "Gas - exhaust"],
    "Condenser": ["Cond/Evap - Fan motor", "Cond/Evap - Fan blades", "Cond/Evap - coil leak"],
    "Evaporator": ["Cond/Evap - Fan motor", "Cond/Evap - Fan blades", "Cond/Evap - coil leak"],
    "Oil System": ["Oil system - oil line"],
    "Non-component": [
        "NC - Water Leak", "NC - Refrigerant Leak", "NC - Not Warranty", "NC - field install issue",
        "NC -no fault found", "NC - concession", "NC - Cosmetic", "NC - Other (comments box)",
        "NC - missing parts", "NC - no fault found", "NC - frame", "NC - sales order issue",
        "NC - configuration", "NC - Field Install Issues", "NC - Cosmetic Damage", "NC - service call",
        "NC-insulation", "NC - insulation", "NC - refrigerant undercharge", "NC - air leak",
        "NC - leak", "NC -not warranty", "Non-Component - Other (comments box)",
        "Non-Component - Refrigerant Leak", "Non-Component - Cosmetic Damage", "Non-Component - Water Leak"
    ],
    "Other": ["Other - note issues in comments", "0"],
    "Ambiguous" : ["Ambiguous"]
}

HVAC_REASONING_GUIDE = """
CLASSIFICATION WORKFLOW

Step 1: Determine whether the issue can be identified.

If the issue itself cannot be determined:

Examples:

* bad component
* failed
* burned out
* shorted
* not communicating
* unit not working
* intermittent issue

and no affected system can be identified:

Primary Component = Ambiguous
Secondary Component = Ambiguous
Failure Reason = Ambiguous

Stop classification.

---

Step 2: Determine whether the issue is a Non-component issue.

Use Primary Component = Non-component when the issue is identifiable but does NOT involve a failed HVAC component.

Examples:

* water leak
* hood leak
* rain intrusion
* cabinet leak
* sealant issue
* cosmetic damage
* missing parts
* concession
* service call only
* not warranty
* sales order issue
* field install issue
* configuration issue
* no fault found
* insulation issue
* frame/panel issue

These are NOT Ambiguous.

If a Non-component condition is identified:
Primary Component = Non-component

QUESTION:

"Did a physical HVAC component fail?"

YES → HVAC Component Primary

NO → Non-component Primary
---
---

Step 3: Determine the HVAC system area.

Primary Component represents the system or equipment area.

Choose the system where the confirmed root issue occurred.

Priority:
Diagnosis > Root Cause > Corrective Action > Replaced Parts

---

GENERAL RULES

1. Classify the confirmed root issue.

2. Do not classify based only on replaced parts.

3. Do not classify based only on troubleshooting steps.

4. Ignore routine actions:

   * vacuumed
   * pressure tested
   * startup
   * checked operation
   * LOTO
   * recovered refrigerant
   * opened valves
   * contacted tech support

5. If no failed component is confirmed, do not automatically choose Part Failure.

---

NEGATIVE EVIDENCE

The following indicate a component is NOT the root cause:

* checked ok
* operating normally
* no corrosion found
* no moisture found
* no leaks found
* grounding checked ok
* wiring checked ok
* bonding checked ok

Use confirmed failures over inspected-good components.

---
CONFIGURATION / TUNING RULE

If the service text describes:

- PID tuning
- ramp rate adjustments
- parameter changes
- configuration changes
- programming changes
- commissioning adjustments
- control tuning

then a Primary Component IS identified.

Do NOT classify as Ambiguous.

Classify the affected system and use:

Failure Reason = Installation

unless the text explicitly indicates a design issue.
---
NON-COMPONENT CONDITIONS

Choose Non-component when the diagnosed issue is:

Administrative:
- concession
- not warranty
- sales order issue

Installation:
- field install issue
- setup issue
- commissioning issue
- programming setup issue

System Conditions:
- refrigerant overcharge
- refrigerant undercharge
- improper refrigerant charge
- non-condensables
- air in system
- incorrect refrigerant weight
- airflow issue without failed component

Physical Non-Component:
- water intrusion
- weather intrusion
- hood leak
- cabinet leak
- cosmetic issue
- missing parts
- insulation issue

--------------------------------------------------

COMPONENT MENTION RULE

The presence of a component does NOT automatically make that component the Primary Component.

Examples:

"Compressor failure alarm. Compressor running normally. System appears overcharged."

Primary = Non-component

NOT Compressor

--------------------------------------------------

SYSTEM CONDITION RULE

If the issue is caused by:

- refrigerant charge
- airflow condition
- operating condition
- commissioning condition
- setup condition

and no failed component is confirmed,

Primary = Non-component

--------------------------------------------------

ALARM OVERRIDE RULE

Alarm names are symptoms.

Examples:

- Compressor Failure Alarm
- High Pressure Alarm
- Low Pressure Alarm
- Sensor Alarm
- Communication Alarm

Do not classify from the alarm name.

Classify from the diagnosed cause of the alarm.

--------------------------------------------------

ROOT CAUSE OVERRIDE RULE

Diagnosis overrides:

1. Alarm descriptions
2. Components mentioned
3. Parts replaced
4. Corrective actions

Examples:

"High pressure trip caused by overcharge"

Primary = Non-component

NOT Compressor
NOT Condenser

--------------------------------------------------
NO COMPONENT FAILURE FOUND RULE

If alarms exist but troubleshooting confirms:

- component operating normally
- component rotation correct
- component passes testing
- no failed hardware found

then do NOT classify from the alarm.

Classify from the diagnosed root cause.

Examples:

"Compressor failure alarm. Compressor running normally."

→ Not Compressor Part Failure.

"High pressure trip caused by overcharge."

→ Non-component
→ NC - refrigerant overcharge
------------------
NON-COMPONENT PRIORITY

If a clear Non-component condition is identified,
choose Non-component even when HVAC components are referenced elsewhere in the note.
---

NON-COMPONENT SECONDARY SELECTION

Water/weather intrusion:
Secondary = NC - Water Leak

No fault found:
Secondary = NC - no fault found

Not warranty:
Secondary = NC - Not Warranty

Field install issue:
Secondary = NC - field install issue

Configuration/setup issue:
Secondary = NC - configuration

Concession:
Secondary = NC - concession

Service call only:
Secondary = NC - service call

Missing parts:
Secondary = NC - missing parts

Cosmetic damage:
Secondary = NC - Cosmetic Damage

Refrigerant leak with no confirmed component:
Secondary = NC - Refrigerant Leak

---

PRIMARY COMPONENT MAPS

STARTER/VFD

Keywords:
vfd, drive, inverter, starter

Program:
software, firmware, settings, parameters, configuration, nuisance alarms, intermittent alarms

Boards:
failed board, burnt electronics, igbt, power module

Wiring:
loose wire, damaged wire, shorted wire, open circuit

Important:
A VFD alarm does NOT automatically mean VFD failure.
Classify the cause of the alarm.

---

ELECTRICAL CONTROLS

Keywords:
contactor, relay, transformer, breaker, fuse, control board, display

Boards:
failed board

Wiring:
actual wiring defect only

Breakers:
failed breaker

Contactors:
welded, burnt, stuck

Transformer:
failed transformer

Fuses:
blown fuse

Program:
control programming issue

---

COMPRESSOR

Keywords:
compressor, grounded compressor, locked rotor, burnt windings

Mechanical failure:
default compressor bucket

Motor:
compressor motor

Wiring:
confirmed compressor wiring defect

Heater:
crankcase heater

Important:
Do not classify fan/blower issues as Compressor unless compressor is explicitly diagnosed.

---

CONDENSER

Keywords:
condenser fan, outdoor fan, exhaust fan, power exhaust, blower wheel

Fan motor:
fan motor, blower motor, exhaust motor

Fan blades:
fan blade, blower wheel

coil leak:
coil refrigerant leak

---

EVAPORATOR

Keywords:
evaporator, evap coil, indoor coil

Fan motor:
evaporator fan motor

Fan blades:
fan blade, blower wheel

coil leak:
evaporator refrigerant leak

---

INPUT DEVICES

Keywords:
sensor, thermistor, transducer, pressure switch, flow switch

Sensor:
generic sensor

Temp sensor:
temperature sensor

Thermistor:
thermistor

Transducer:
pressure transducer

High pressure switch:
high pressure switch

Flow Switch:
flow switch

---

VALVE

Keywords:
exv, txv, check valve, ball valve, economizer valve, stepper valve, actuator, damper

EXV/TXV:
expansion valves

Check:
check valve

Ball:
ball valve

economizer:
economizer valve

Stepper:
stepper valve

actuator:
actuator

damper:
damper

charging/service:
service valve

---

GAS

Keywords:
gas valve, burner, inducer, flame sensor, heat exchanger, exhaust

Valve:
gas valve

Inducer:
inducer motor

burner:
burner

Sensor:
flame sensor

HX:
heat exchanger

exhaust:
flue issue

leak:
gas leak

---

OIL SYSTEM

Keywords:
oil line, oil pressure, oil pump, oil return, oil separator

oil line:
default oil system bucket

---

FAILURE REASON SELECTION

Part Failure:
Physical component failure confirmed.

Installation:
Field installation, setup, commissioning, adjustment, alignment, mounting, field wiring, field configuration.

Manufacturing:
Factory defect, factory workmanship, factory assembly issue, factory sealing issue.

Applications/Systems:
Airflow issues, pressure issues, charge issues, operating conditions, system behavior.

Network Controls:
BAS, controls communication, controls integration, network issues.

Resettable alarms:
Alarm or trip present, but no hardware failure and no configuration issue confirmed.

Other:
Administrative issue, concession, unclear cause.


"""
