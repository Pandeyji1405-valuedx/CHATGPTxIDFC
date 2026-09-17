# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

---

## Security Architecture & Guarantees

**CHATGPTxIDFC** is engineered specifically for secure banking and enterprise conversational environments:

1. **Zero-Internet Airgap Execution**:
   - The user query and chat reasoning pipeline runs strictly locally without querying external public search engines or untrusted web endpoints.
   - External web requests are restricted strictly to administrative document ingestion when explicitly enabled by authorized administrators.

2. **Data & Multi-Tenant Isolation**:
   - Application-level row isolation ensures users can only access their own conversation history and extracted entities.
   - All conversation endpoints strictly enforce `WHERE user_id == current_user.id`.

3. **Authentication & Password Hashing**:
   - Passwords are encrypted using modern `bcrypt` algorithms with salt rounds.
   - JWT tokens use HMAC SHA-256 signatures with customizable token expiration.

4. **Hallucination & Anti-Injection Guardrails**:
   - Fact grounding validation compares entities, circular numbers, and financial quantities against retrieved context.
   - Prompt injection mitigations prevent system prompt leaks or bypasses.

---

## Reporting a Vulnerability

If you discover a security vulnerability within this project:

1. **Do NOT open a public issue.**
2. Please send an email to `www.pande.devesh04@gmail.com` detailing:
   - Nature of the vulnerability.
   - Steps to reproduce or proof-of-concept.
   - Potential impact.
3. We will acknowledge receipt within 48 hours and work on an appropriate patch immediately.
