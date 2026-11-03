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
    "Ambiguous",
]

SECONDARY_COMPONENTS = [
    "Starter/Vfd-Control",
    "Starter/Vfd-Wiring",

    "Electrical Controls-Board/Software",
    "Electrical Controls-Power",
    "Electrical Controls-Wiring",
    "Electrical Controls-Transformer",

    "Input Devices-Sensor",
    "Input Devices-High Pressure Switch",

    "Cond/Evap-Fan Motor",
    "Cond/Evap-Fan Blade",
    "Cond/Evap-Coil Leak",

    "Compressor-Mechanical Failure",
    "Compressor-Motor",
    "Compressor-Heater",
    "Compressor-Wiring",

    "Gas-Hx",
    "Gas-Valve",
    "Gas-Sensor",
    "Gas-Inducer",
    "Gas-Leak",
    "Gas-Burner",
    "Gas-Exhaust",

    "Valve-Exv/Txv",
    "Valve-Actuator",
    "Valve-Damper",
    "Valve-Ball",
    "Valve-Check",
    "Valve-Stepper",
    "Valve-Charging/Service",
    "Valve-Economizer",

    "Nc-Leak",
    "Nc-Configuration",
    "Nc-No Fault Found",
    "Nc-Service Call",
    "Nc-System Contamination",
    "Nc-Other",

    "Oil System-Oil Line",

    "Other - note issues in comments",
    "Ambiguous",
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
    "Ambiguous",
]


VALID_SECONDARY_BY_PRIMARY = {
    "Starter/VFD": [
        "Starter/Vfd-Control",
        "Starter/Vfd-Wiring",
    ],
    "Electrical controls": [
        "Electrical Controls-Board/Software",
        "Electrical Controls-Power",
        "Electrical Controls-Wiring",
        "Electrical Controls-Transformer",
    ],
    "Input Devices": [
        "Input Devices-Sensor",
        "Input Devices-High Pressure Switch",
    ],
    "Condenser": [
        "Cond/Evap-Fan Motor",
        "Cond/Evap-Fan Blade",
        "Cond/Evap-Coil Leak",
    ],
    "Evaporator": [
        "Cond/Evap-Fan Motor",
        "Cond/Evap-Fan Blade",
        "Cond/Evap-Coil Leak",
    ],
    "Compressor": [
        "Compressor-Mechanical Failure",
        "Compressor-Motor",
        "Compressor-Heater",
        "Compressor-Wiring",
    ],
    "Gas": [
        "Gas-Hx",
        "Gas-Valve",
        "Gas-Sensor",
        "Gas-Inducer",
        "Gas-Leak",
        "Gas-Burner",
        "Gas-Exhaust",
    ],
    "Valve": [
        "Valve-Exv/Txv",
        "Valve-Actuator",
        "Valve-Damper",
        "Valve-Ball",
        "Valve-Check",
        "Valve-Stepper",
        "Valve-Charging/Service",
        "Valve-Economizer",
    ],
    "Non-component": [
        "Nc-Leak",
        "Nc-Configuration",
        "Nc-No Fault Found",
        "Nc-Service Call",
        "Nc-System Contamination",
        "Nc-Other",
    ],
    "Oil System": [
        "Oil System-Oil Line",
    ],
    "Other": [
        "Other - note issues in comments",
    ],
    "Ambiguous": [
        "Ambiguous",
    ],
}


SECONDARY_GROUP_MAPPING = {
    # Starter/VFD
    "Starter/Vfd-Board": "Starter/Vfd-Control",
    "Starter/Vfd-Boards": "Starter/Vfd-Control",
    "Starter/Vfd-Program": "Starter/Vfd-Control",
    "Starter/Vfd-Control": "Starter/Vfd-Control",
    "Starter/Vfd-Wiring": "Starter/Vfd-Wiring",

    # Electrical controls
    "Electrical Controls-Board": "Electrical Controls-Board/Software",
    "Electrical Controls-Boards": "Electrical Controls-Board/Software",
    "Electrical Controls-Software": "Electrical Controls-Board/Software",
    "Electrical Controls-Program": "Electrical Controls-Board/Software",
    "Electrical Controls-Parameter": "Electrical Controls-Board/Software",
    "Electrical Controls-Board/Software": "Electrical Controls-Board/Software",

    "Electrical Controls-Relay": "Electrical Controls-Power",
    "Electrical Controls-Relays": "Electrical Controls-Power",
    "Electrical Controls-Breaker": "Electrical Controls-Power",
    "Electrical Controls-Breakers": "Electrical Controls-Power",
    "Electrical Controls-Fuse": "Electrical Controls-Power",
    "Electrical Controls-Fuses": "Electrical Controls-Power",
    "Electrical Controls-Contactor": "Electrical Controls-Power",
    "Electrical Controls-Contactors": "Electrical Controls-Power",
    "Electrical Controls-Power": "Electrical Controls-Power",

    "Electrical Controls-Wiring": "Electrical Controls-Wiring",
    "Electrical Controls-Transformer": "Electrical Controls-Transformer",

    # Electronic controls old labels
    "Electronic Controls-Wiring": "Electrical Controls-Wiring",
    "Electronic Controls-Program": "Electrical Controls-Board/Software",

    # Input devices
    "Input Devices-Temp Sensor": "Input Devices-Sensor",
    "Input Devices-Thermistor": "Input Devices-Sensor",
    "Input Devices-Sensor": "Input Devices-Sensor",
    "Input Devices-Transducer": "Input Devices-Sensor",
    "Input Devices-Flow Switch": "Input Devices-Sensor",
    "Input Devices-High Pressure Switch": "Input Devices-High Pressure Switch",

    # Cond/Evap
    "Cond/Evap-Fan Motor": "Cond/Evap-Fan Motor",
    "Cond/Evap-Fan Motors": "Cond/Evap-Fan Motor",
    "Cond/Evap-Fan Blade": "Cond/Evap-Fan Blade",
    "Cond/Evap-Fan Blades": "Cond/Evap-Fan Blade",
    "Cond/Evap-Coil Leak": "Cond/Evap-Coil Leak",

    # Compressor
    "Compressor-Mechanical": "Compressor-Mechanical Failure",
    "Compressor-Mechanical Failure": "Compressor-Mechanical Failure",
    "Compressor-Motor": "Compressor-Motor",
    "Compressor-Heater": "Compressor-Heater",
    "Compressor-Wiring": "Compressor-Wiring",

    # Gas
    "Gas-Hx": "Gas-Hx",
    "Gas-HX": "Gas-Hx",
    "Gas-Valve": "Gas-Valve",
    "Gas-Sensor": "Gas-Sensor",
    "Gas-Inducer": "Gas-Inducer",
    "Gas-Leak": "Gas-Leak",
    "Gas-Burner": "Gas-Burner",
    "Gas-Exhaust": "Gas-Exhaust",

    # Valve
    "Valve-Exv/Txv": "Valve-Exv/Txv",
    "Valve-EXV/TXV": "Valve-Exv/Txv",
    "Valve-Actuator": "Valve-Actuator",
    "Valve-Damper": "Valve-Damper",
    "Valve-Ball": "Valve-Ball",
    "Valve-Check": "Valve-Check",
    "Valve-Stepper": "Valve-Stepper",
    "Valve-Charging/Service": "Valve-Charging/Service",
    "Valve-Economizer": "Valve-Economizer",

    # Non-component other
    "Nc-Concession": "Nc-Other",
    "Nc-No Warranty": "Nc-Other",
    "Nc-Not Warranty": "Nc-Other",
    "Nc-Missing Part": "Nc-Other",
    "Nc-Missing Parts": "Nc-Other",
    "Nc-Cosmetic": "Nc-Other",
    "Nc-Cosmetic Damage": "Nc-Other",
    "Nc-Frame": "Nc-Other",
    "Nc-Insulation": "Nc-Other",
    "Nc-Other": "Nc-Other",
    "Nc-Other (Comments Box)": "Nc-Other",
    "Other - note issues in comments": "Other - note issues in comments",

    # Non-component leaks / refrigerant conditions
    "Nc-Air Leak": "Nc-Leak",
    "Nc-Water Leak": "Nc-Leak",
    "Nc-Refrigerant Leak": "Nc-Leak",
    "Nc-Refrigerant Overcharge": "Nc-Leak",
    "Nc-Refrigerant Undercharge": "Nc-Leak",
    "Nc-Unknown Leak": "Nc-Leak",
    "Nc-Leak": "Nc-Leak",

    # Non-component configuration
    "Nc-Field Install Issue": "Nc-Configuration",
    "Nc-Configuration": "Nc-Configuration",

    # Non-component specific
    "Nc-No Fault Found": "Nc-No Fault Found",
    "Nc-No Fault Found (Noise/Vibration)": "Nc-No Fault Found",
    "Nc-Service Call": "Nc-Service Call",
    "Nc-System Contamination": "Nc-System Contamination",

    # Oil
    "Oil System-Oil Line": "Oil System-Oil Line",

    # Ambiguous
    "Ambiguous": "Ambiguous",
}


def _compact_key(value):
    return (
        str(value)
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("/", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )


def normalize_secondary(label):
    """
    Converts messy original labels into a consistent Title-style form:
    e.g. INPUTDEVICES-TRANSDUCER -> Input Devices-Transducer
    """
    if label is None:
        return ""

    raw = str(label).strip()
    if not raw:
        return ""

    x = raw.upper().strip()

    if "-" not in x:
        return raw

    main, sub = x.split("-", 1)

    main_key = _compact_key(main)

    main_map = {
        "NC": "Nc",
        "INPUTDEVICES": "Input Devices",
        "ELECTRICALCONTROLS": "Electrical Controls",
        "ELECTRONICCONTROLS": "Electronic Controls",
        "STARTERVFD": "Starter/Vfd",
        "COND/EVAP": "Cond/Evap",
        "CONDEVAP": "Cond/Evap",
        "GAS": "Gas",
        "VALVE": "Valve",
        "COMPRESSOR": "Compressor",
        "OILSYSTEM": "Oil System",
    }

    main_clean = main_map.get(main_key, main.title())

    sub_key = _compact_key(sub)

    sub_map = {
        "BOARD": "Board",
        "BOARDS": "Boards",
        "SOFTWARE": "Software",
        "PROGRAM": "Program",
        "PARAMETER": "Parameter",
        "WIRING": "Wiring",
        "WIRE": "Wiring",
        "RELAY": "Relay",
        "RELAYS": "Relays",
        "BREAKER": "Breaker",
        "BREAKERS": "Breakers",
        "FUSE": "Fuse",
        "FUSES": "Fuses",
        "CONTACTOR": "Contactor",
        "CONTACTORS": "Contactors",
        "TRANSFORMER": "Transformer",

        "TEMPSENSOR": "Temp Sensor",
        "TEMPERATURESENSOR": "Temp Sensor",
        "THERMISTOR": "Thermistor",
        "TRANSDUCER": "Transducer",
        "SENSOR": "Sensor",
        "FLOWSWITCH": "Flow Switch",
        "HIGHPRESSURESWITCH": "High Pressure Switch",

        "FANMOTOR": "Fan Motor",
        "FANMOTORS": "Fan Motor",
        "FANBLADE": "Fan Blade",
        "FANBLADES": "Fan Blades",
        "COILLEAK": "Coil Leak",

        "MECHANICAL": "Mechanical",
        "MECHANICALFAILURE": "Mechanical Failure",
        "MOTOR": "Motor",
        "HEATER": "Heater",

        "HX": "Hx",
        "VALVE": "Valve",
        "INDUCER": "Inducer",
        "LEAK": "Leak",
        "BURNER": "Burner",
        "EXHAUST": "Exhaust",

        "EXV/TXV": "Exv/Txv",
        "EXVTXV": "Exv/Txv",
        "ACTUATOR": "Actuator",
        "DAMPER": "Damper",
        "BALL": "Ball",
        "CHECK": "Check",
        "STEPPER": "Stepper",
        "CHARGINGSERVICE": "Charging/Service",
        "ECONOMIZER": "Economizer",

        "CONCESSION": "Concession",
        "NOWARRANTY": "No Warranty",
        "NOTWARRANTY": "Not Warranty",
        "MISSINGPART": "Missing Part",
        "MISSINGPARTS": "Missing Parts",
        "COSMETIC": "Cosmetic",
        "COSMETICDAMAGE": "Cosmetic Damage",
        "FRAME": "Frame",
        "INSULATION": "Insulation",
        "OTHERCOMMENTSBOX": "Other (Comments Box)",
        "OTHER": "Other",

        "AIRLEAK": "Air Leak",
        "WATERLEAK": "Water Leak",
        "REFRIGERANTLEAK": "Refrigerant Leak",
        "REFRIGERANTOVERCHARGE": "Refrigerant Overcharge",
        "REFRIGERANTUNDERCHARGE": "Refrigerant Undercharge",
        "UNKNOWNLEAK": "Unknown Leak",

        "FIELDINSTALLISSUE": "Field Install Issue",
        "CONFIGURATION": "Configuration",

        "NOFAULTFOUND": "No Fault Found",
        "NOFAULTFOUNDNOISEVIBRATION": "No Fault Found (Noise/Vibration)",
        "SERVICECALL": "Service Call",
        "SYSTEMCONTAMINATION": "System Contamination",

        "OILLINE": "Oil Line",
    }

    sub_clean = sub_map.get(sub_key, sub.title())

    return f"{main_clean}-{sub_clean}"


def map_secondary_group(label):
    """
    Maps old detailed secondary labels into grouped secondary labels.
    If label is already grouped, returns it unchanged.
    """
    if label is None:
        return ""

    normalized = normalize_secondary(label)

    # Exact map
    if normalized in SECONDARY_GROUP_MAPPING:
        return SECONDARY_GROUP_MAPPING[normalized]

    # Already valid grouped label
    if normalized in SECONDARY_COMPONENTS:
        return normalized

    # Compact fallback matching
    norm_key = _compact_key(normalized)

    for old_label, grouped_label in SECONDARY_GROUP_MAPPING.items():
        if _compact_key(old_label) == norm_key:
            return grouped_label

    for grouped_label in SECONDARY_COMPONENTS:
        if _compact_key(grouped_label) == norm_key:
            return grouped_label

    return normalized

HVAC_REASONING_GUIDE = """
HVAC WARRANTY CLASSIFICATION GUIDE

EXAMPLES (10 EXAMPLES)

EXAMPLE 

Service:
Adjusted controller parameters.
Corrected PID settings.
Unit operating normally.

Primary:
Non-component

Secondary:
Nc-Configuration

Reason:
Installation

EXAMPLE

Service:
Setpoint configured incorrectly from startup.
Adjusted values and verified operation.

Primary:
Non-component

Secondary:
Nc-Configuration

Reason:
Installation

EXAMPLE

Service:
Found evaporator coil leaking refrigerant.
Recovered charge and replaced coil.

Primary:
Evaporator

Secondary:
Cond/Evap-Coil Leak

Reason:
Part Failure

EXAMPLE

Service:
Leak located in condenser coil.
Replaced leaking coil.

Primary:
Condenser

Secondary:
Cond/Evap-Coil Leak

Reason:
Part Failure

EXAMPLE

Service:
Factory wiring landed on incorrect terminal.
Corrected wiring.

Primary:
Electrical controls

Secondary:
Electrical Controls-Wiring

Reason:
Manufacturing

EXAMPLE

Service:
Installer landed wiring on wrong terminal.
Corrected field wiring.

Primary:
Electrical controls

Secondary:
Electrical Controls-Wiring

Reason:
Installation

EXAMPLE

Service:
Adjusted VFD parameters.
No failed hardware found.

Primary:
Non-component

Secondary:
Nc-Configuration

Reason:
Installation

EXAMPLE

Service:
Control board failed.
Board replaced.

Primary:
Electrical controls

Secondary:
Electrical Controls-Board/Software

Reason:
Part Failure

EXAMPLE

Service:
Could not reproduce complaint.
Unit operating normally.

Primary:
Non-component

Secondary:
Nc-No Fault Found

Reason:
Resettable alarms

EXAMPLE

Service:
Complaint could not be duplicated.
Verified normal operation.

Primary:
Non-component

Secondary:
Nc-No Fault Found

Reason:
Resettable alarms
-------------------------------------------------------------------------------------------
RULES:
LEAK RULE
If the note mentions recovered refrigerant, removed refrigerant, added charge, overcharge, low charge, high head pressure corrected by charge adjustment, leak check, repaired leak, vacuum, nitrogen pressure test, or R410A charging:

Primary = Non-component
Secondary = Nc-Leak

Do not use Ambiguous, Other, or Nc-Service Call.

CONTACTOR RULE
Contactors, relays, breakers, fuses, overload blocks, lugs, and bus bars belong to:

Primary = Electrical controls
Secondary = Electrical Controls-Power

Do not classify these as Starter/VFD unless the VFD/drive itself failed.

AMBIGUOUS RULE

Use Ambiguous for all three fields when the service note does not provide enough information to determine a root cause.

Use Ambiguous when the note only describes symptoms or actions without diagnosis, for example:

* Unit not working
* Alarm present
* Customer complaint
* Checked unit
* Replaced part
* Bad component
* Failed component

without identifying what actually caused the issue.

Do not use Ambiguous if any of these are present:

- refrigerant was removed/recovered/added
- leak was repaired
- component was replaced
- wire/connection issue was found
- factory/shipping issue is described
- settings/parameters were adjusted

Use Ambiguous only when no root system, condition, or component can be identified.
---------------------------------------------------------------
Coil leak vs Nc-Leak

If refrigerant leak originates from a coil:

Secondary = Cond/Evap-Coil Leak

Do NOT use Nc-Leak.

Nc-Leak is only for refrigerant leaks where no failed component is identified.
----------------------------------------------------------------------------
CONFIGURATION

Use Nc-Configuration when the problem is caused by settings, parameters, programming, setup, configuration, commissioning settings, or control values.

Examples:

* Wrong parameter
* Incorrect setting
* Configuration error
* Incorrect setup
* Programming issue
* Setpoint issue
* Control parameter issue

Configuration means:

- PID adjustments
- Setpoints
- Parameters
- Ramp rates
- Programming changes
- Commissioning values
- Controller tuning

If no hardware failed and settings were adjusted:

Primary = Non-component
Secondary = Nc-Configuration

If changing settings resolves the issue without replacing failed hardware, prefer Nc-Configuration.
--------------------------------------------------------
NO FAULT FOUND

Use Nc-No Fault Found when no confirmed failure is found.

Examples:

* Unit operating normally
* Unable to duplicate issue
* Could not reproduce fault
* No issue found
* No fault found
* Intermittent complaint not reproduced
* Unit checked and operating correctly

Use Resettable alarms when the issue was only an alarm or reset condition and no repair was required.

MANUFACTURING RULE
Use Manufacturing when the issue appears caused by how the unit was built or shipped:

- from factory
- factory installed
- factory rivets
- shipped low/overcharged
- missing module/part from shipment
- wire harness too short
- factory sealing issue
- factory assembly issue

Manufacturing overrides Installation when field tech only corrected a factory-built condition.

VFD MISTAKES RULE
Mention of VFD does not mean Starter/VFD failed.

Use Starter/VFD only when the drive/VFD itself failed.

If the issue is:
- loose VFD signal wire
- short wire harness
- wiring reattached
- trip point adjusted
- startup bypass

classify by the root issue:
Electrical Controls-Wiring or Non-component/Nc-Configuration.
"""