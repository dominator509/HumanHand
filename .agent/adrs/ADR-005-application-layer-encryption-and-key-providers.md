# ADR-005: Application-Layer Encryption and Key Providers

- Date: 2026-08-12
- Status: Accepted for the Pre-SLM program

## Decision

Retained originals and configured sensitive fields use an application-layer encrypted
blob/field interface. Windows DPAPI is the preferred Windows-first provider, with a
deterministic test provider. Master keys are never stored in the project database.

## Reason

Persistent local evidence needs a clear protection boundary without coupling domain
logic to Windows APIs or storing secrets in schema rows.

## Consequence

Key-provider ports, encrypted stores, rotation/retention behavior, and no-secret tests
must be defined before a production retention claim is made.
