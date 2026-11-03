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
    "NC - Water Leak",
    "NC - Refrigerant Leak",
    "NC - Not Warranty",
    "NC - field install issue",
    "NC - no fault found",
    "NC - concession",
    "NC - Cosmetic",
    "NC - Other (comments box)",
    "NC - missing parts",
    "NC - frame",
    "NC - sales order issue",
    "NC - configuration",
    "NC - Cosmetic Damage",
    "NC - refrigerant undercharge",
    "NC - refrigerant overcharge",
    "NC - system contamination",
    "NC - service call",
    "NC - air leak",
    "NC - insulation",
],
    "Other": ["Other - note issues in comments", "0"],
    "Ambiguous" : ["Ambiguous"]
}

HVAC_REASONING_GUIDE = """
==================================================
HVAC WARRANTY CLASSIFICATION GUIDE
==================================

CORE PRINCIPLE

Classify the diagnosed root issue.

Use:

Diagnosis > Root Cause > Failed Component > Corrective Action > Replaced Parts > Alarm Names

Do not classify solely from:

* alarm names
* replaced parts
* troubleshooting steps
* components that were checked and found good

==================================================
STEP 1 - AMBIGUOUS
==================

Use Ambiguous only when:

* the issue cannot be determined
  AND
* no HVAC system can be identified

Examples:

* bad component
* failed
* burned out
* shorted
* not communicating
* intermittent issue
* unit not working

with no additional information.

Return:

Primary Component = Ambiguous
Secondary Component = Ambiguous
Failure Reason = Ambiguous

Do NOT use Ambiguous when:

* a refrigerant condition is identified
* a configuration issue is identified
* a setup issue is identified
* a water leak is identified
* a failed component is identified
* a system is identified

==================================================
STEP 2 - NON-COMPONENT DECISION TEST
====================================

Ask:

"Did a physical HVAC component fail?"

YES:
Continue to HVAC component classification.

NO:
Primary Component = Non-component
==================================================
FIELD INSTALL PRIORITY RULE
==================================================

Use:

Primary = Non-component
Secondary = NC - field install issue

when the root cause involves:

- missing field-installed tubing
- missing field-installed wiring
- contractor installation issue
- startup installation issue
- incorrect phasing from installation
- incomplete ductwork
- missing field connections
- field communication setup
- BAS integration issue caused by installation

Even if:

- configuration changes were made
- programming changes were made
- controls were adjusted

The field installation issue takes priority over configuration.
==================================================
DIAGNOSIS OVERRIDE RULE
=======================

The confirmed diagnosis overrides:

* alarm names
* component mentions
* corrective actions
* replaced parts
* replacement part descriptions

Example:

Compressor failure alarm.
Compressor operating normally.
System overcharged.

Correct:

Primary = Non-component

Incorrect:

Primary = Compressor
------------------------------
WIRING OVERRIDE RULE

If the note states:

- loose wire
- disconnected wire
- damaged wire
- repaired wiring
- broken wire

Use:
Electrical Controls - Wiring

Do NOT use:
Input devices - Sensor

unless the sensor itself is confirmed failed.
==================================================
NEGATIVE EVIDENCE
=================

The following indicate a component is NOT the root cause:

* checked ok
* operating normally
* no corrosion found
* no moisture found
* no leaks found
* wiring checked ok
* grounding checked ok
* bonding checked ok
* rotation correct
* passes testing

Use confirmed failures over inspected-good components.

==================================================
REPLACEMENT PART RULE
=====================

Replacement Part Description is supporting evidence.

Priority:

Diagnosis

> Root Cause
> Service Performed
> Replacement Part

Use the Replacement Part Description when:

* the service note is vague
* the replacement part identifies the failed component

Do NOT override a diagnosed root cause with a replacement part.

Example:

Service:
System overcharged.

Replacement Part:
Pressure Sensor.

Correct:
Non-component

Incorrect:
Input Devices

==================================================
NON-COMPONENT
=============

Definition:

Choose Non-component when the root issue is not a failed HVAC component.

The issue is a:

* condition
* setup issue
* configuration issue
* commissioning issue
* refrigerant condition
* administrative issue
* no-fault-found result

Examples:

Refrigerant overcharge
→ Non-component

Refrigerant undercharge
→ Non-component

Incorrect refrigerant weight
→ Non-component

Non-condensables
→ Non-component

Air in system
→ Non-component

Configuration issue
→ Non-component

Commissioning issue
→ Non-component

Field install issue
→ Non-component

Water intrusion
→ Non-component

No fault found
→ Non-component

The presence of compressors, valves, sensors, motors, or alarms does NOT automatically make them the failed component.

CONFIGURATION AS NON-COMPONENT RULE

If the issue is corrected by changing:

- setpoints
- PID loops
- ramp rates
- BACnet address
- controller address
- configuration values
- setup parameters
- commissioning settings

and no failed hardware is confirmed:

Use:
Primary = Non-component
Secondary = NC - configuration

Do NOT use:
Electrical Controls - Program
Starter/VFD - Program

unless the hardware/software module itself is diagnosed as failed.

PROGRAM VS BOARD RULE

If corrected by:

- programming
- configuration
- parameter changes
- firmware update
- software adjustment

Use:
Electrical Controls - Program

Do NOT use:
Electrical Controls - Boards

unless a board is diagnosed as failed.
==================================================
NON-COMPONENT SECONDARY SELECTION
=================================

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

REFRIGERANT OVERCHARGE OVERRIDE

If the text says:

- removed refrigerant
- recovered refrigerant
- removed gas
- high subcooling
- excessive subcooling
- balanced refrigerant charge
- high head pressure corrected by removing refrigerant
- remove charge in increments

Use:
Primary = Non-component
Secondary = NC - refrigerant overcharge

Do NOT use:
NC - Water Leak
NC - Refrigerant Leak
Compressor
Condenser

Refrigerant undercharge:
NC - refrigerant undercharge

Non-condensables:
NC - system contamination

----------------------------------------------
==================================================
MANUFACTURING OVERCHARGE RULE
==================================================

Use:

Failure Reason = Manufacturing

when:

- refrigerant overcharge is identified
- refrigerant charge must be removed
- excessive subcooling exists on startup
- unit appears factory overcharged
- charge imbalance exists from initial installation

Examples:

Removed refrigerant to correct factory charge.
→ NC - refrigerant overcharge
→ Manufacturing

High subcooling corrected by removing refrigerant.
→ NC - refrigerant overcharge
→ Manufacturing

Manufacturing takes priority over Applications/Systems when the condition is attributed to factory charging.
------------------------------------------------

NO FAULT FOUND STRICT RULE

Use NC - no fault found only when the note explicitly says:

- no fault found
- no alarms present
- no issue found
- unable to duplicate
- unit operating normally
- all tests passed


==================================================
CONFIGURATION / TUNING RULE
===========================

If the service text describes:

* PID tuning
* ramp rate adjustments
* parameter changes
* configuration changes
* programming changes
* commissioning adjustments
* control tuning
* alarm setpoint changes
* controller setup

The issue is identifiable.

Do NOT classify as Ambiguous.

Use NC - configuration unless a failed hardware component is explicitly diagnosed.


==================================================
STARTER/VFD
===========

Keywords:

vfd
drive
inverter
starter

Program:

software
firmware
settings
parameters
configuration
PID loops
ramp rates

Boards:

failed board
IGBT
power module
electronics failure

Wiring:

loose wire
damaged wire
shorted wire
open circuit

A VFD alarm does NOT automatically indicate VFD failure.

==================================================
ELECTRICAL CONTROLS
===================

Examples:

Control board failed
→ Electrical Controls - Boards

Blown fuse
→ Electrical Controls - fuses

Failed transformer
→ Electrical Controls - Transformer

Failed breaker
→ Electrical Controls - Breakers

Burnt contactor
→ Electrical Controls - Contactors

Programming issue
→ Electrical Controls - Program

==================================================
COMPRESSOR
==========

Use Compressor only when the compressor itself is diagnosed as failed.

Examples:

* grounded compressor
* locked rotor
* compressor not pumping
* failed compressor motor
* burnt compressor windings

Do NOT use Compressor for:

* refrigerant overcharge
* refrigerant undercharge
* non-condensables
* condenser fan failures
* blower failures

==================================================
MOTOR RULE
==========

Fan and blower motors are not compressors.

Examples:

* blower motor
* fan motor
* condenser fan motor
* evaporator fan motor
* exhaust fan motor
* power exhaust motor

Use:

Cond/Evap - Fan motor

Do NOT use Compressor unless the compressor itself is diagnosed.
FAN MOTOR PRIORITY RULE

If the failed component is:

- blower motor
- evaporator fan motor
- condenser fan motor
- exhaust fan motor

Use:
Cond/Evap - Fan motor

Even if:

- VFD
- starter
- drive
- overload

are mentioned.

Use Starter/VFD only when the VFD itself is diagnosed as failed.
==================================================
CONDENSER
=========

Fan motor:
fan motor
blower motor
exhaust motor

Fan blades:
fan blade
blower wheel

Coil leak:
condenser coil refrigerant leak

==================================================
EVAPORATOR
==========

Fan motor:
evaporator fan motor

Fan blades:
blower wheel

Coil leak:
evaporator coil refrigerant leak

==================================================
INPUT DEVICES
=============

Pressure measurement devices:
→ Input devices - Transducer

Examples:

* pressure transducer
* suction pressure transducer
* discharge pressure transducer
* static pressure sensor
* static sensor

Generic sensing devices:
→ Input devices - Sensor

Examples:

* CO2 sensor
* occupancy sensor
* generic sensor

Temperature devices:
→ Input devices - Temp sensor

Examples:

* SAT sensor
* RAT sensor
* LAT sensor
* temperature sensor

High pressure switch:
→ Input devices - High pressure switch

Flow switch:
→ Input devices - Flow Switch
INPUT DEVICE OVERRIDE RULE

If the text or Replacement Part Description contains:

- transducer
- pressure transducer
- suction pressure transducer
- discharge pressure transducer
- static pressure sensor
- static sensor
- pressure signal

Use:
Primary = Input Devices
Secondary = Input devices - Transducer

Do NOT use:
Input devices - Sensor
==================================================
VALVE
=====

EXV/TXV:
Valve - EXV/TXV

Check valve:
Valve - Check

Ball valve:
Valve - Ball

Economizer valve:
Valve - economizer

Stepper valve:
Valve - Stepper

Actuator:
Valve - actuator

Damper:
Valve - damper

Service valve:
Valve - charging/service

==================================================
GAS
===

Gas valve:
Gas - Valve

Burner:
Gas-burner

Inducer:
Gas - Inducer

Flame sensor:
Gas - Sensor

Heat exchanger:
Gas - HX

Exhaust:
Gas - exhaust

Gas leak:
Gas - leak

==================================================
OIL SYSTEM
==========

Oil line:
Oil system - oil line

==================================================
FAILURE REASON SELECTION
========================

Part Failure

Use when a physical component failure is confirmed.

---

Installation

Use for:

* commissioning
* setup
* tuning
* alignment
* mounting
* parameter changes
* field wiring
* field configuration

---

MANUFACTURING PRIORITY RULE

Use Failure Reason = Manufacturing when the note says or implies:

- factory defect
- factory installed incorrectly
- factory workmanship
- assembly issue
- shipped without part
- shipped incorrectly
- factory wiring missing
- factory sealing issue
- manufacturing defect
- issue present from startup/new install

Manufacturing overrides:
- Part Failure
- Installation
- Applications/Systems
---

Applications/Systems

Use for:

* refrigerant charge issues
* airflow issues
* operating conditions
* pressure issues
* system behavior

---

Network Controls

Use for:

* BAS communication
* controls integration
* network communication

---

Resettable Alarms

Use when:

* alarm exists
* no hardware failure found
* no setup issue found
* no configuration issue found

---

Other

Administrative or unclear cause.

==================================================
FINAL VALIDATION
================

Before answering:

1. Is the issue truly Ambiguous?
2. If not, do not use Ambiguous.
3. Did a physical HVAC component fail?
4. If not, use Non-component.
5. Is the diagnosis stronger than the alarm?
6. Is the diagnosis stronger than the replacement part?
7. Is Manufacturing identified?
8. Are all labels exact taxonomy labels?
   ==================================================

"""
