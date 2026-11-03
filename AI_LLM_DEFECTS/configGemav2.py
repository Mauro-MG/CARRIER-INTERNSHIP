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
==================================================

CORE PRINCIPLE

Classify the diagnosed root issue.

Use:

Diagnosis
>
Root Cause
>
Failed Component
>
Corrective Action
>
Replacement Part
>
Alarm Names

Do NOT classify from:

- alarm names alone
- replaced parts alone
- troubleshooting steps
- components that were checked and found good

CLASSIFICATION ORDER (MANDATORY)

1. Determine Primary Component.
2. Determine Secondary Component.
3. Determine Failure Reason.

Failure Reason must NEVER be used to determine
Primary Component or Secondary Component.
Example:
A unit may have a Manufacturing issue affecting:
- Compressor
- Electrical Controls
- Gas
- Condenser
- Evaporator
- Input Devices
- Starter/VFD
- Valve
- Non-component

Therefore Manufacturing is evaluated ONLY AFTER
Primary and Secondary have been selected.
==================================================
PRIMARY COMPONENT HIERARCHY
==================================================

Choose the PRIMARY COMPONENT before selecting the secondary.
PRIMARY LOCK RULE
Once Primary Component is selected,
Failure Reason cannot change it.
Examples:

Water leak affecting multiple units
→ Primary = Non-component
→ Secondary = NC - Water Leak
→ Reason = Design

Board issue caused by recurring design flaw
→ Primary = Electrical Controls
→ Secondary = Electrical Controls - Boards
→ Reason = Design

Communication issue caused by network architecture
→ Primary = Non-component
→ Secondary = NC - field install issue
→ Reason = Network Controls
Use the diagnosed root cause.

Priority order:

1. Non-component
2. Input Devices
3. Electrical Controls
4. Starter/VFD
5. Compressor
6. Condenser
7. Evaporator
8. Gas
9. Valve

--------------------------------------------------

NON-COMPONENT

Use when:

- overcharge
- undercharge
- configuration
- field install issue
- no fault found
- startup issue
- commissioning issue
- missing component
- water intrusion
- administrative issue

--------------------------------------------------

INPUT DEVICES

Use when:

The sensor, thermistor, transducer, switch or sensing device itself failed.

--------------------------------------------------

ELECTRICAL CONTROLS

Use when:

The failure is:

- board
- contactor
- relay
- fuse
- transformer
- breaker
- wiring

--------------------------------------------------

STARTER/VFD

Use only when:

The VFD itself failed.

Do NOT use Starter/VFD when:

- motor failed
- fan failed
- compressor failed

even if the VFD is mentioned.

--------------------------------------------------

EVAPORATOR

Use when:

The failed component is:

- blower motor
- evaporator fan motor
- indoor fan motor
- blower wheel

unless the VFD itself is diagnosed as failed.

CONDENSER VS EVAPORATOR

When the service note references:

- condenser fan motor
- condenser fan blade
- outdoor fan
- rooftop condenser fan
- microchannel coil
- condenser coil

Primary = Condenser

Do NOT automatically classify fan motor or coil leak as Evaporator.
==================================================
STEP 1 - AMBIGUOUS
==================================================

Use Ambiguous only when:

- the issue cannot be determined
AND
- no HVAC system can be identified

Examples:

- failed component
- burned out
- intermittent issue
- not working
- bad part

with no additional information.

Return:

Primary Component = Ambiguous
Secondary Component = Ambiguous
Failure Reason = Ambiguous

Do NOT use Ambiguous when:

- a failed component is identified
- a refrigerant condition is identified
- a configuration issue is identified
- a setup issue is identified
- a water leak is identified
- a system is identifiable

==================================================
STEP 2 - NON-COMPONENT DECISION TEST
==================================================

Ask:

"Did a physical HVAC component fail?"

YES:
Continue to HVAC component classification.

NO:
Primary Component = Non-component
==================================================
NON-COMPONENT OVERRIDE PRIORITY
==================================================

If the real issue is a condition, setup problem, field issue, missing installation item, configuration issue, startup issue, water/weather issue, refrigerant condition, or administrative/warranty issue:

Primary Component = Non-component

This overrides hardware categories even if the note mentions:

- electrical controls
- sensors
- motors
- evaporator
- gas
- compressor
- VFD
- boards
- valves

Do not classify a hardware component unless the hardware itself is diagnosed as failed.

Examples:

Component mentioned but checked good
→ Non-component

Alarm mentions component but diagnosis is setup/charge/configuration
→ Non-component

Hardware adjusted or inspected, but no failed hardware confirmed
→ Non-component
==================================================
INPUT DEVICE FAILURE PROTECTION
==================================================

If a sensor, transducer, thermistor, switch, or flow switch itself is explicitly failed, bad, defective, replaced due to bad reading, or not reading properly:

Primary Component = Input Devices

Do NOT classify as Non-component unless the issue is missing/not installed, field wiring, configuration, or no fault found.
==================================================
DIAGNOSIS OVERRIDE RULE
==================================================

The confirmed diagnosis overrides:

- alarm names
- component mentions
- corrective actions
- replaced parts
- replacement part descriptions

Example:

Compressor failure alarm.
Compressor operating normally.
System overcharged.

Correct:

Primary = Non-component

Incorrect:

Primary = Compressor

==================================================
NEGATIVE EVIDENCE
==================================================

The following indicate a component is NOT the root cause:

- checked ok
- operating normally
- no leaks found
- passes testing
- rotation correct
- wiring checked ok
- sensor tested good
- resistance tested good

Use confirmed failures over inspected-good components.

==================================================
REPLACEMENT PART RULE
==================================================

Replacement Part Description is supporting evidence only.

Priority:

Diagnosis
>
Root Cause
>
Service Performed
>
Replacement Part

Use the Replacement Part Description when:

- service text is vague
- replacement part identifies the failed component

Do NOT override a diagnosed root cause with a replacement part.

Example:

Service:
System overcharged.

Replacement:
Pressure Transducer.

Correct:
Non-component

Incorrect:
Input Devices

==================================================
WIRING OVERRIDE RULE
==================================================

If the note states:

- loose wire
- disconnected wire
- broken wire
- damaged wire
- repaired wiring
- open connection
- bad connection

Use:

Electrical Controls - Wiring

Do NOT use:

Input Devices

unless the sensor itself is confirmed failed.

If:

- sensor tested good
- thermistor tested good
- resistance tested good

and the repair was wiring related:

Use:

Electrical Controls - Wiring

==================================================
MISSING COMPONENT RULE
==================================================

If a component is:

- missing
- not installed
- never installed

Use:

Primary = Non-component
Secondary = NC - field install issue

Do NOT classify as the component itself.

Examples:

- missing sensor
- sensor not installed
- missing tubing
- missing field wiring
- missing actuator

==================================================
FIELD INSTALL PRIORITY RULE
==================================================

Use:

Primary = Non-component
Secondary = NC - field install issue

Use Secondary = NC - field install issue when the issue is caused by:

- crossed wiring
- incorrect phasing
- missing tubing
- missing sensors
- missing duct static tube
- contractor work incomplete
- controls contractor issue
- startup setup error
- installation error


Even if:

- configuration changes were made
- programming changes were made
- controls were adjusted

Field install issue takes priority over configuration.

FIELD INSTALL EXAMPLES

The following are typically field install issues:

- missing sensor
- missing tubing
- missing wiring
- not installed
- never installed
- contractor wiring issue
- startup wiring issue
- phasing issue at startup
- BAS not configured during startup



==================================================
NON-COMPONENT
==================================================

Choose Non-component when the root issue is:

- a condition
- a setup issue
- a commissioning issue
- a configuration issue
- a refrigerant condition
- an administrative issue
- a no-fault-found result

Examples:

- refrigerant overcharge
- refrigerant undercharge
- non-condensables
- air in system
- configuration issue
- commissioning issue
- field install issue
- no fault found
- water intrusion

The presence of compressors, valves, sensors, motors, or alarms does NOT automatically make them the failed component.

==================================================
CONFIGURATION AS NON-COMPONENT RULE
==================================================

If corrected by changing:

- PID loops
- ramp rates
- controller settings
- BACnet address
- controller address
- configuration values
- commissioning settings
- setup parameters

and no failed hardware is confirmed:

Use:

Primary = Non-component
Secondary = NC - configuration

Do NOT use:

Electrical Controls - Program
Starter/VFD - Program

unless the hardware itself is diagnosed as failed.

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

Refrigerant undercharge:
NC - refrigerant undercharge

Non-condensables:
NC - system contamination

==================================================
SALES ORDER OVERRIDE
==================================================

If the note states:

- shipped without part
- incorrect shipment
- missing from shipment
- ordered incorrectly
- sales order error

Use:

Primary = Non-component
Secondary = NC - sales order issue

Do NOT use:

NC - missing parts

==================================================
REFRIGERANT OVERCHARGE OVERRIDE
==================================================

If the text says:

- removed refrigerant
- recovered refrigerant
- removed charge
- excessive subcooling
- high subcooling
- balanced refrigerant charge
- overcharged
- remove refrigerant in increments
- high head pressure corrected by removing refrigerant

Use:

Primary = Non-component
Secondary = NC - refrigerant overcharge

Do NOT use:

- NC - Water Leak
- NC - Refrigerant Leak
- Compressor
- Condenser

==================================================
NO FAULT FOUND RULE
==================================================

Use NC - no fault found only when the note explicitly states:

- no fault found
- unable to duplicate
- unit operating normally
- all tests passed
- no issue found

==================================================
INPUT DEVICE OVERRIDE RULE
==================================================

If the text states:

- pressure transducer
- suction transducer
- discharge transducer
- static pressure sensor
- pressure signal issue

Use:

Primary = Input Devices
Secondary = Input devices - Transducer

Do NOT use:

Input devices - Sensor

==================================================
FAN MOTOR PRIORITY RULE
==================================================

If the failed component is:

- blower motor
- evaporator fan motor
- condenser fan motor
- exhaust fan motor

Use:

Cond/Evap - Fan motor

Even if:

- VFD
- drive
- starter
- overload

are mentioned.

Use Starter/VFD only when the VFD itself is diagnosed as failed.
==================================================
ELECTRICAL CONTROLS MAP
==================================================

Use Electrical Controls when the diagnosed failure involves:

Contactor
→ Electrical Controls - Contactors

Breaker
→ Electrical Controls - Breakers

Fuse
→ Electrical Controls - Fuses

Transformer
→ Electrical Controls - Transformer

Control board
→ Electrical Controls - Boards

Display
→ Electrical Controls - Display

Relay
→ Electrical Controls - Relays

Wiring failure
→ Electrical Controls - Wiring

Programming issue
→ Electrical Controls - Program

Important:

If a sensor tests good but wiring is repaired:

Use:
Electrical Controls - Wiring

NOT:
Input Devices
==================================================
STARTER/VFD MAP
==================================================

Use Starter/VFD when the diagnosed failure involves:

VFD board
→ Starter/VFD - Boards

VFD wiring
→ Starter/VFD - wiring

VFD software
→ Starter/VFD - Program

VFD parameters
→ Starter/VFD - Program

VFD settings
→ Starter/VFD - Program

Important:

A VFD alarm does NOT automatically mean the VFD failed.

Use the diagnosed cause.

If the VFD, drive, starter, VFD board, VFD wiring, or VFD parameters are the diagnosed issue:

Primary Component = Starter/VFD

Do NOT classify as Electrical controls.
==================================================
GAS MAP
==================================================

Gas valve
→ Gas - Valve
GAS VALVES

Gas valves belong to the Gas primary component.

Do NOT classify gas valves under Valve primary.

Gas valve:
Primary = Gas
Secondary = Gas - Valve

Burner
→ Gas-burner

Heat exchanger
→ Gas - HX

Inducer
→ Gas - Inducer

Flue or exhaust issue
→ Gas - exhaust

Gas leak
→ Gas - leak
GAS SENSOR RULE

The following remain Gas components:

- rollout switch
- flame rollout switch
- flame sensor
- gas sensor
- ignition sensor
- high temperature limit in heating circuit

These are Gas components even though they are electrical devices.

Primary = Gas

==================================================
FAN MOTOR MAP
==================================================

Blower motor
Evaporator fan motor
Condenser fan motor
Exhaust fan motor

→ Cond/Evap - Fan motor

Fan blade
Blower wheel

→ Cond/Evap - Fan blades

Coil refrigerant leak

→ Cond/Evap - coil leak

Fan motors take priority over VFDs unless the VFD itself is diagnosed as failed.
==================================================
INPUT DEVICE MAP
==================================================

Pressure transducer
→ Input devices - Transducer

Temperature sensor
→ Input devices - Temp sensor

Thermistor
→ Input devices - Thermistor

High pressure switch
→ Input devices - High pressure switch

Flow switch
→ Input devices - Flow Switch

Generic sensor
→ Input devices - Sensor
==================================================
FAILURE REASON HIERARCHY
==================================================

MANUFACTURING

Use when:

- factory defect
- factory assembly issue
- factory workmanship issue
- factory wiring missing
- factory overcharge
- factory sealing issue
- issue present from startup
- shipped incorrectly
- shipped without part



--------------------------------------------------

INSTALLATION

Use when:

- commissioning
- startup
- field install issue
- setup
- tuning
- field wiring
- field configuration
- adjustment

--------------------------------------------------

==================================================
NETWORK CONTROLS DATASET RULE
==================================================

Use Failure Reason = Network Controls whenever the issue involves:

- BACnet
- Modbus
- CCN
- communication loss
- communication setup
- controller addressing
- translator
- UPC Open
- BAS integration
- network mapping
- points not visible
- controller not communicating

Even if a board was replaced.

Network communication issues take priority over hardware classification.

--------------------------------------------------

PART FAILURE

Use when:

- physical component failure is confirmed

--------------------------------------------------

APPLICATIONS/SYSTEMS

Use when:

- airflow issue
- pressure issue
- operating condition
- system behavior

--------------------------------------------------

RESETTABLE ALARMS

Use when:

- alarm exists
- no hardware failure found
- no setup issue found
- no configuration issue found

--------------------------------------------------
==================================================
DESIGN RULE
==================================================

Use Design when the service text indicates a product
engineering correction, product redesign, service bulletin,
mandatory rework, known issue, recurring issue, field
modification, engineering update, or product improvement.

Examples:

- service bulletin
- mandatory rework
- engineering update
- field modification
- redesign
- known issue
- recurring issue
- 8D corrective action
- install updated kit
- install grounding kit
- product improvement campaign

If the repair is being performed to correct a known product
design issue:

Failure Reason = Design

even if components are functioning correctly.

Do NOT classify as Installation simply because hardware
was installed during the correction.
-------------------------------------
OTHER

Administrative or unclear cause.

==================================================
MANUFACTURING OVERCHARGE RULE
==================================================

If:

- refrigerant overcharge is identified
AND
- charge must be removed
AND
- condition appears factory related

Use:

Failure Reason = Manufacturing

Examples:

Factory overcharged.
Removed refrigerant.
→ Manufacturing

High subcooling corrected by removing refrigerant.
→ Manufacturing

Manufacturing takes priority over Applications/Systems for factory charging issues.

==================================================
FINAL CHECK
==================================================

Classify:

1. Root Cause
2. Responsible Party
3. Exact Taxonomy Label

Diagnosis overrides:

- alarms
- replacement parts
- corrective actions

Remember:

The taxonomy is primarily a warranty responsibility classification system, not simply a hardware identification system.
"""
