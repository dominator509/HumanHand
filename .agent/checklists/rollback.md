# Rollback Checklist

- [ ] Rollback trigger identified.
- [ ] Rollback decision owner identified.
- [ ] Previous known-good version identified.
- [ ] Application rollback method chosen: reinstall previous wheel.
- [ ] Config rollback values identified without exposing secrets.
- [ ] Database consideration: no primary DB; optional cache can be deleted.
- [ ] Rollback command/procedure documented.
- [ ] Verification after rollback completed.
- [ ] Communication drafted if release affected users.
- [ ] Postmortem created for security/privacy/critical regressions.
