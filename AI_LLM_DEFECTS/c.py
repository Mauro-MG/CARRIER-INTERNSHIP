from best_gemma_classifier import classify
import json
import inspect
import best_gemma_classifier as bgc

service_text = """
"ClaimNumber: CRT2TY1QY
ClaimDate: 2025-02-20 00:00:00
ReplacementPartDescription: HEATER
ServicePerformed: CIRCUIT A&B FAULTY OIL HEATERSFound 2 bad oil heaters, will order new oil heaters and installed them.   CIRCUIT A&B FAULTY OIL HEATERS

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT2TY1QY
ClaimDate: 2025-02-20 00:00:00
ReplacementPartDescription: HEATER
ServicePerformed: CIRCUIT A&B FAULTY OIL HEATERSFound 2 bad oil heaters, will order new oil heaters and installed them.   CIRCUIT A&B FAULTY OIL HEATERS

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT3V7DDW
ClaimDate: 2025-03-13 00:00:00
ReplacementPartDescription: EXTERNAL FAN
ServicePerformed: Arrived to jobsite found machine under alarm for VFD internal fan failure. With further troubleshooting found external fan faulty. Replaced fan monitor operation pick up trash and gather tools Arrived to jobsite removed faulty OIL heater, replace with new one pick up trash and tools. Monitor oil heater performance.

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT3V7DDW
ClaimDate: 2025-03-13 00:00:00
ReplacementPartDescription: INTERNAL FAN
ServicePerformed: Arrived to jobsite found machine under alarm for VFD internal fan failure. With further troubleshooting found external fan faulty. Replaced fan monitor operation pick up trash and gather tools Arrived to jobsite removed faulty OIL heater, replace with new one pick up trash and tools. Monitor oil heater performance.

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT7WQNFV
ClaimDate: 2025-07-07 00:00:00
ReplacementPartDescription: FLOW SWITCH KIT
ServicePerformed: Arrived at site, got to chiller. Turned of water pump. Drained water from chiller. Turned of chiller. Removed Damaged Flow switch, installed a new flow switch, tightened bolt. Open water valve, verified there was no leaks on flow switch. Turned on power, verified we had flow.

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT7WSXPX
ClaimDate: 2025-07-11 00:00:00
ReplacementPartDescription: 
ServicePerformed: Chiller 2 Hrs:6161 Srts: 9788 Description: Bad VFD external fan  Turned off chiller, removed VFD panel, Repalced External VFD fan cleaned area put panel back in place Job completed

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT7WTKXT
ClaimDate: 2025-07-14 00:00:00
ReplacementPartDescription: EXTERNAL FAN
ServicePerformed: Arrived to jobsite for other warranty repairs found external VFD fan bad will order and comeback. Arrived to jobsite LOTO machine removed faulty mixing fan from condenser VFD. Tested mixing fan clear all alarms. Pick up tools and checkout

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT7WTKXT
ClaimDate: 2025-07-14 00:00:00
ReplacementPartDescription: INTERNAL FAN
ServicePerformed: Arrived to jobsite for other warranty repairs found external VFD fan bad will order and comeback. Arrived to jobsite LOTO machine removed faulty mixing fan from condenser VFD. Tested mixing fan clear all alarms. Pick up tools and checkout

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT7WTMZK
ClaimDate: 2025-07-14 00:00:00
ReplacementPartDescription: 
ServicePerformed: Chiller 2 Hrs:6161 Srts: 9788 Description: Bad VFD external fan Turned off chiller, removed VFD panel, Repalced External VFD fan cleaned area put panel back in place Job completed

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRT9XJYCY
ClaimDate: 2025-09-02 00:00:00
ReplacementPartDescription: HEATSINK FAN
ServicePerformed: Bad VFD external fan  Arrived on site and found unit in alarm for external vfd alarm found vfd in alarm for external fault and replace fan went into configuration to disable alarm so unit could run once done clean up site and left

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRTAXZSHL
ClaimDate: 2025-10-03 00:00:00
ReplacementPartDescription: HEATSINK FAN
ServicePerformed: Arrived to site, checked in front office and gained access to chiller yard. Looked at alarms in chillers Chiller 3 - 4420Q40413 CIRCUIT B FAN VFD 1 WARNING Chiller 2 - 4420Q40415 CIRCUIT B FAN VFD WARNING Chiller 1 - 4420Q40414 Mixing Fans W104 Verified that these fans have to be replaced. Will order parts. Closed pannels ,checked out left site COMPLETED

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRTAXZSHL
ClaimDate: 2025-10-03 00:00:00
ReplacementPartDescription: INTERNAL FAN
ServicePerformed: Arrived to site, checked in front office and gained access to chiller yard. Looked at alarms in chillers Chiller 3 - 4420Q40413 CIRCUIT B FAN VFD 1 WARNING Chiller 2 - 4420Q40415 CIRCUIT B FAN VFD WARNING Chiller 1 - 4420Q40414 Mixing Fans W104 Verified that these fans have to be replaced. Will order parts. Closed pannels ,checked out left site COMPLETED

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRTCYS2KK
ClaimDate: 2025-12-01 00:00:00
ReplacementPartDescription: 
ServicePerformed: Shut power off to chiller and removed all panels and removed bad mixing fan once done installed new one and bolted all panels back up then went and change out fan vfd external fan on circuit B removed all covers and panels and unbolted out fan and then installed the new fan once done bolted everything back up and did the same thing to fan vfd On circuit a once done turn on power to chiller and all alarms went away and chiller started to run. Clean up site and left

--- RELATED CLAIM IN SAME SERIAL GROUP ---

ClaimNumber: CRTCYX1N8
ClaimDate: 2025-12-10 00:00:00
ReplacementPartDescription: 
ServicePerformed: I???ll get materials and come back to do repairs Upon arrival at the job site, I checked in at the front desk and was given access to the chiller. I recovered the refrigerant from the circuit and repaired the leak. I then pulled a vacuum to an acceptable micron. The charge the circuit and trimmed the charge. I cleaned up and checked out of job site."


"""
replacement_part="EXTERNAL FAN | FLOW SWITCH KIT | HEATER | HEATSINK FAN | INTERNAL FAN"


result = classify(
    text=service_text,
    replacement_part_description=replacement_part,
    model="gemma4:12B"
)


print(result)
