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
==================================================
CLASSIFICATION WORKFLOW
==================================================

STEP 1 - CAN THE ISSUE BE IDENTIFIED?

If the issue itself cannot be determined from the service text:

Examples:
- bad component
- failed
- burned out
- shorted
- not communicating
- intermittent issue
- unit not working

and no affected system can be identified:

Primary Component = Ambiguous
Secondary Component = Ambiguous
Failure Reason = Ambiguous

STOP.

--------------------------------------------------

STEP 2 - DETERMINE ROOT CAUSE

Identify the diagnosed cause of the issue.

Do NOT classify from:

- alarm names
- troubleshooting steps
- parts replaced
- routine service actions

Use:

Diagnosis > Root Cause > Failed Component > Corrective Action > Replaced Parts

--------------------------------------------------

STEP 3 - NON-COMPONENT DECISION TEST

Ask:

"Did a physical HVAC component fail?"

YES:
Continue to HVAC Component classification.

NO:
Primary Component = Non-component

--------------------------------------------------

DIAGNOSIS OVERRIDE RULE

The confirmed diagnosis overrides:

- alarm names
- component mentions
- corrective actions
- replaced parts

Examples:

"Compressor failure alarm. Compressor operating normally. System overcharged."

Primary = Non-component

NOT Compressor

--------------------------------------------------

NEGATIVE EVIDENCE

The following indicate a component is NOT the root cause:

- checked ok
- operating normally
- no corrosion found
- no moisture found
- no leaks found
- wiring checked ok
- grounding checked ok
- bonding checked ok
- rotation correct
- passes testing

Use confirmed failures over inspected-good components.

--------------------------------------------------

IGNORE PROCEDURE-ONLY ACTIONS

Do not classify from:

- vacuumed
- pressure tested
- startup
- checked operation
- recovered refrigerant
- opened valves
- LOTO
- contacted tech support

==================================================
NON-COMPONENT CLASSIFICATION
==================================================

Choose Non-component when the issue is a condition, process issue, installation issue, administrative issue, or system state rather than a failed HVAC component.

--------------------------------------------------

NON-COMPONENT CONDITIONS

Administrative:

- concession
- not warranty
- sales order issue
- service call only

Installation / Setup:

- field install issue
- commissioning issue
- setup issue
- configuration issue
- programming setup issue

Refrigeration System Conditions:

- refrigerant overcharge
- refrigerant undercharge
- improper refrigerant charge
- incorrect refrigerant weight
- non-condensables
- air in system
- evacuation issue
- startup charge issue

Physical Non-Component Issues:

- water intrusion
- weather intrusion
- hood leak
- cabinet leak
- sealant issue
- cosmetic issue
- missing parts
- frame issue
- insulation issue

No Failure Found:

- no fault found
- operating normally
- unable to duplicate issue

--------------------------------------------------

ALARM RULE

Alarm names are symptoms.

Examples:

- Compressor Failure Alarm
- High Pressure Alarm
- Low Pressure Alarm
- Sensor Alarm
- Communication Alarm

Do NOT classify from the alarm.

Classify from the diagnosed cause.

--------------------------------------------------

NO COMPONENT FAILURE FOUND RULE

If alarms exist but testing confirms:

- component operating normally
- correct rotation
- no failed hardware
- component passes testing

then do NOT classify from the alarm.

Classify from the diagnosed root cause.

==================================================
NON-COMPONENT SECONDARY SELECTION
==================================================

Water/weather intrusion:
NC - Water Leak

No fault found:
NC - no fault found

Not warranty:
NC - Not Warranty

Field install issue:
NC - field install issue

Configuration/setup issue:
NC - configuration

Concession:
NC - concession

Service call only:
NC - service call

Missing parts:
NC - missing parts

Cosmetic damage:
NC - Cosmetic Damage

Refrigerant leak without identified component:
NC - Refrigerant Leak

Refrigerant overcharge:
NC - refrigerant overcharge

Refrigerant undercharge:
NC - refrigerant undercharge

==================================================
CONFIGURATION / TUNING RULE
==================================================

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

Classify the affected system.

Failure Reason = Installation

unless the text explicitly indicates a design issue.

==================================================
PRIMARY COMPONENT MAPS
==================================================

STARTER/VFD

Keywords:
vfd, drive, inverter, starter

Program:
software, firmware, settings, parameters, configuration, tuning, PID loops, ramp rates, nuisance alarms

Boards:
failed board, burnt electronics, igbt, power module

Wiring:
loose wire, damaged wire, shorted wire, open circuit

Important:
A VFD alarm does NOT automatically indicate VFD failure.
Classify the cause of the alarm.

--------------------------------------------------

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

--------------------------------------------------

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
Do NOT classify fan/blower issues as Compressor unless compressor is explicitly diagnosed.

--------------------------------------------------

CONDENSER

Keywords:
condenser fan, outdoor fan, exhaust fan, power exhaust, blower wheel

Fan motor:
fan motor, blower motor, exhaust motor

Fan blades:
fan blade, blower wheel

coil leak:
coil refrigerant leak

--------------------------------------------------

EVAPORATOR

Keywords:
evaporator, evap coil, indoor coil

Fan motor:
evaporator fan motor

Fan blades:
fan blade, blower wheel

coil leak:
evaporator refrigerant leak

--------------------------------------------------

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

--------------------------------------------------

VALVE

Keywords:
exv, txv, check valve, ball valve, economizer valve, stepper valve, actuator, damper

EXV/TXV:
expansion valves

Check:
check valve

Ball:
ball valve

Economizer:
economizer valve

Stepper:
stepper valve

Actuator:
actuator

Damper:
damper

Charging/service:
service valve

--------------------------------------------------

GAS

Keywords:
gas valve, burner, inducer, flame sensor, heat exchanger, ignition, exhaust

Valve:
gas valve

Inducer:
inducer motor

Burner:
burner

Sensor:
flame sensor

HX:
heat exchanger

Exhaust:
flue issue

Leak:
gas leak

--------------------------------------------------

OIL SYSTEM

Keywords:
oil line, oil pressure, oil pump, oil return, oil separator

Oil line:
default oil system bucket

==================================================
FAILURE REASON SELECTION
==================================================

Part Failure:
Physical component failure confirmed.

Installation:
Field installation, commissioning, setup, tuning, adjustment, alignment, mounting, field wiring, field configuration.

Manufacturing:
Factory defect, factory workmanship, factory assembly issue, factory sealing issue.

Applications/Systems:
Airflow issues, pressure issues, refrigerant charge issues, operating conditions, system behavior.

Network Controls:
BAS, communication, controls integration, network issues.

Resettable alarms:
Alarm or trip present but no hardware failure and no configuration issue confirmed.

Other:
Administrative issue, concession, unclear cause.

"""
