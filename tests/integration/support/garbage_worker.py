"""Test-only worker seam: emits protocol-violating stdout.

Run via ``python -m tests.integration.support.garbage_worker`` to exercise
the supervisor's non-JSON stdout path. This is a test seam, never shipped
as a product parser.
"""

print("this is not json")
