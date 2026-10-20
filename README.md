# HL7 FHIR Bridge

A small interface engine in Python that receives HL7 v2 messages over MLLP, validates them, maps them to FHIR R4 resources and answers with an HL7 ACK. It runs on synthetic data only. No real patient data is used anywhere.

I built it to learn the way healthcare interfaces work: a lab system and an admission system speak HL7 v2, newer systems speak FHIR, and something in between has to translate, check and keep a clear record of what was accepted and what was not.

## What it does

1. Listens on a TCP port with MLLP framing and reads HL7 v2.5 messages: ADT^A01 and ADT^A08 (admit and update) and ORU^R01 (lab results).
2. Parses segments, fields and components. MSH-1 is handled as the field separator, so field numbers match the HL7 standard.
3. Validates each message and names the failing field, for example PID-7 birth date or OBX-1 value.
4. Maps accepted messages to FHIR R4 Patient, Encounter and Observation resources with LOINC codes, units, reference ranges and interpretation flags.
5. Answers every message with an ACK: AA (accepted), AE (rejected with the reason) or AR (not parseable).
6. Is idempotent on MSH-10. A retried message gets an ACK and is not processed twice.
7. Writes rejected messages to `quarantine.jsonl` with the reasons, so nobody has to guess.

## Run it

```
python -m bridge demo
python -m pytest -q
```

## Measured result

The demo generator creates 40 patients with an admission and a lab panel each, 12 messages with a planted defect (missing identifier, bad birth date, bad sex code, text in a numeric result, unsupported message type, missing visit number, bad patient class) and 6 retries.

|Measure|Result|
|-|-|
|Messages sent over a real TCP socket|98|
|Accepted and mapped|80|
|Retries recognised|6|
|Rejected and quarantined|12|
|Planted defects caught|12 of 12|
|FHIR resources written|240|

## Design notes

* Timestamps in HL7 carry no zone here, so they are read as UTC and written with a Z. A production interface would take the zone from configuration.
* Patient resources are written under a stable id built from the medical record number, so a second message for the same patient updates the file and does not create a duplicate.
* The ACK for a duplicate says so and still returns AA, because a sender that gets an error will keep retrying.

## What this is not

* The data is synthetic and the sending system is my own generator.
* FHIR output is plain JSON that follows the R4 structure. I have not validated it with the official FHIR validator or sent it to a FHIR server.
* DICOM, HL7 v3, IHE profiles and TLS are not covered. I am learning DICOM next.
