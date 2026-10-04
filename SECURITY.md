# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a vulnerability

Open a GitHub Security Advisory on this repository or contact the maintainers
directly. Do not open a public issue for sensitive reports. Expect an initial
response within 3 business days.

## Secrets handling

- Never commit `.env` or credentials; copy `.env.example` to `.env` locally.
- Every push and PR is scanned by Gitleaks (`secret scan` workflow).
- Airflow Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- Rotate any credential that was ever committed, even if later removed from history.
