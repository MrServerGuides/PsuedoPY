# Security policy

## Supported versions

Security fixes are provided for the latest 1.x release.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature for this repository. Do
not open a public issue containing exploit details, malicious compiled artifacts, or
private information. Include the affected version, reproduction steps, impact, and
any proposed mitigation.

## Security model

- PsuedoPY programs execute with the permissions of their Python process.
- `.ppy`, `.py`, and `.cppy` programs are executable code and must be trusted.
- `.cppy` decoding does not use pickle or marshal and verifies lengths and hashes,
  but integrity hashes do not prove who created an artifact.
- `psuedopy install` invokes pip. Packages can run code during build or installation.
  Use a virtual environment and install only trusted packages.
- PsuedoPY is not a sandbox for untrusted student or downloaded code.

For untrusted workloads, use an operating-system sandbox, container, restricted
account, resource limits, and network isolation appropriate to the threat model.
