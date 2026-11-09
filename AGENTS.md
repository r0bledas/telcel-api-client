# AGENTS.md — Telcel API Client Guidelines

Any AI agent working on `telcel-api-client` must adhere strictly to the following invariants:

## 1. Zero PII & Privacy Standard
- **Never include real user phone numbers, account names, email addresses, or passwords** in any code file, markdown documentation, or test script committed to this repository.
- Always use standard dummy placeholders for documentation and usage examples:
  - Phone: `5512345678` or `<PHONE_NUMBER>`
  - Password: `YOUR_PASSWORD` or `<PASSWORD>`
  - Account: `Usuario` / `usuario@ejemplo.com`
- Real credentials provided during interactive chat sessions are strictly for temporary runtime execution and must **never** be persisted in git history or files pushed to GitHub.
