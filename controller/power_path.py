"""Power Path Lab: source-independent, observation-driven HM-10 / Uno fault triage.

No voltage measurement is performed. Reported LED state is not a reliable
instrument for module supply voltage or an active Bluetooth connection.
"""
from __future__ import annotations

from typing import Mapping

UNKNOWN = "NOT CHECKED"
POWER = ("ON", "OFF", UNKNOWN)
METER = ("ABOUT 3.3V", "LOW / ZERO", UNKNOWN)
REGULATOR = ("BARE 3.3V MODULE", "5V-TOLERANT BREAKOUT", UNKNOWN)


def explain_power_failure(observations: Mapping[str, str]) -> str:
    usb = observations.get("usb_ble", UNKNOWN)
    battery = observations.get("battery_ble", UNKNOWN)
    uno = observations.get("battery_uno_led", UNKNOWN)
    meter = observations.get("meter_3v3", UNKNOWN)
    module = observations.get("module_type", UNKNOWN)
    common = observations.get("common_ground", UNKNOWN)
    for label, value, allowed in (
        ("USB BLE", usb, POWER), ("battery BLE", battery, POWER),
        ("Uno battery LED", uno, POWER), ("3.3V meter", meter, METER),
        ("HM-10 type", module, REGULATOR), ("common GND", common, POWER)):
        if value not in allowed:
            raise ValueError(f"Invalid {label} observation: {value}")

    recommendations = []
    def add(item):
        if item not in recommendations:
            recommendations.append(item)

    if usb == "ON" and battery == "OFF":
        add("The symptom isolates a CHANGE OF POWER SOURCE, not proof of a Bluetooth-code bug. Compare the HM-10's actual VCC/GND voltage under USB versus battery power.")
        if uno == "OFF":
            add("If the Uno power LED is also OFF on battery: first inspect battery switch, supply polarity, battery condition and whether its connector actually feeds Uno VIN/barrel as intended.")
        if meter == "LOW / ZERO":
            add("You reported a low/absent 3.3V rail on battery. Stop motor testing; verify Uno input supply and regulation before troubleshooting UART or BLE pairing.")
        elif meter == "ABOUT 3.3V":
            add("If 3.3V is actually measured at HM-10 VCC-to-GND under battery power, check connector continuity, module LED/advertising state and whether the BLE adapter is already paired elsewhere.")
        else:
            add("Measure Uno 3.3V-to-GND AND HM-10 VCC-to-GND under BOTH sources using a multimeter, with motors safely disconnected. An Uno power LED alone does not prove the 3.3V regulator's output.")
        add("Battery VIN/barrel operation can fail if the pack voltage falls below what the particular Uno board/regulator requires, especially under motor load. Do not assume Uno 5V/3.3V rails equal USB values.")
    elif battery == "ON" and usb == "OFF":
        add("USB-specific trouble: check USB cable DATA capability, plug, laptop USB supply, HM-10 current draw and competing Bluetooth clients; first compare VCC voltage under each source.")
    elif usb == "OFF" and battery == "OFF":
        add("Neither source appears to power the Bluetooth module: verify HM-10 VCC and common ground with motors disconnected, then inspect module rating and any shorted 3.3V wires.")
    elif usb == "ON" and battery == "ON":
        add("Power appearance is consistent across sources. If connections still fail, check advertisement vs LED status, Windows BLE scan, characteristic UUID and crossed 9600-baud UART wires.")
    else:
        add("Compare module behavior on USB and battery power separately, with the motor battery safely isolated. Observe advertising in the BLE scan, not just module LED activity.")

    if common == "OFF":
        add("STOP: grounds are not confirmed common. With all power OFF, verify Uno GND, HM-10 GND, TB6612 GND and motor battery negative share the required reference.")
    elif common == UNKNOWN:
        add("With all power OFF, trace Uno GND to HM-10 GND and TB6612 GND. A floating reference can make UART/driver behavior unreliable even if LEDs illuminate.")
    if module == "BARE 3.3V MODULE":
        add("Bare 3.3V HM-10: power VCC only as specified by its board. Uno D3 TX is 5V logic and needs a proper divider/level shifter into HM-10 RXD.")
    elif module == "5V-TOLERANT BREAKOUT":
        add("The breakout may accept 5V at its regulated VCC input, but check its actual silkscreen/datasheet. RXD logic tolerance is a SEPARATE specification; keep a level shifter unless proven 5V tolerant.")
    else:
        add("Identify whether your HM-10 is a bare 3.3V board or a breakout with an onboard regulator. Do NOT move VCC to 5V based only on an LED symptom.")
    add("Uno D2 (software RX) <- HM-10 TXD; Uno D3 (software TX) -> HM-10 RXD through 5V-to-3.3V level conversion; both sides 9600 baud.")
    add("The Uno 3.3V pin has limited current capacity and its availability depends on the actual board/regulator. Do not use it to power motors.")
    add("Without a multimeter reading and board/module inspection, exact fault location remains UNKNOWN. Neither LEDs nor GATT connection proves physical supply regulation.")

    result = ["CABBAGE CONTROL STUDIO / POWER PATH LAB",
              "Manual observations only — not sensor readings or electrical verification.",
              "",
              f"BLE appears ON over USB: {usb}",
              f"BLE appears ON over battery: {battery}",
              f"Uno power LED on battery: {uno}",
              f"Measured 3.3V rail on battery: {meter}",
              f"HM-10 supply hardware type: {module}",
              f"Common ground confirmed (power off): {common}",
              "", "NEXT CHECKS:"]
    result.extend(f"{i}. {item}" for i, item in enumerate(recommendations, 1))
    return "\n".join(result) + "\n"
