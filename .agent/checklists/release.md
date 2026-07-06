# Release Checklist

- [ ] Version updated in single source of truth.
- [ ] CHANGELOG updated.
- [ ] Release candidate criteria met.
- [ ] `sh scripts/verify.sh` passes.
- [ ] `sh scripts/build.sh` passes.
- [ ] Wheel installs in clean Python 3.11 environment.
- [ ] Staging/local smoke tests pass.
- [ ] Artifacts inspected for `.env`, `.cache`, secrets, user text.
- [ ] Release notes drafted.
- [ ] Maintainer approval obtained for tag/publish.
- [ ] Production publish performed manually only after approval.
- [ ] Post-release smoke tests pass.
- [ ] Issue tracker/security channels monitored.
