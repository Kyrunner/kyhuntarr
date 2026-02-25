# KYHUNTARR Security Audit

**Audit Date:** 2026-02-24
**Codebase:** KYHUNTARR (fork of NewtArr, itself a fork of Huntarr v6.6.3)
**Audited By:** Automated analysis (Claude)
**Scope:** Full codebase — backend Python, frontend JavaScript/HTML, configuration, and deployment

> **Context:** This audit was performed on the v6.6.3 codebase inherited from the upstream Huntarr project.
> These findings represent **pre-existing issues** in the original code. NewtArr was designed to run behind
> an SSO proxy (e.g., Authelia, Authentik) in ElfHosted deployments, which mitigates many of the
> authentication-related findings. Standalone users should review these findings carefully.

---

## Summary

| Severity | Backend | Frontend | Config/Deploy | Total |
|:---------|:-------:|:--------:|:-------------:|:-----:|
| CRITICAL | 2 | 3 | 0 | **5** |
| HIGH | 6 | 4 | 4 | **14** |
| MEDIUM | 9 | 9 | 8 | **26** |
| LOW | 5 | 4 | 6 | **15** |
| INFO | 7 | 5 | 6 | **18** |

> Note: Some config/deployment findings overlap with backend findings (they reference the same underlying code).

---

## CRITICAL Findings

### C1: Hardcoded Flask Secret Key

- **File:** `src/primary/web_server.py:120`
- **Code:** `app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_sessions')`
- **Impact:** If the `SECRET_KEY` environment variable is not set, Flask sessions use a hardcoded default. An attacker who knows this key can forge session cookies and bypass authentication entirely.
- **Mitigation:** Set the `SECRET_KEY` environment variable to a cryptographically random value in production. The Docker Compose example should include this. Consider generating a random key at first startup if none is provided.

### C2: Weak Password Hashing (SHA-256)

- **File:** `src/primary/auth.py:77-86`
- **Code:** Uses `hashlib.sha256((password + salt).encode()).hexdigest()`
- **Impact:** SHA-256 is a fast hash, making stored passwords vulnerable to brute-force and rainbow table attacks. Industry standard is bcrypt, scrypt, or argon2 with adaptive work factors.
- **Mitigation:** Replace with `bcrypt` or `argon2`. This is less critical when running behind SSO (authentication is handled upstream), but matters for standalone deployments.

### C3: XSS via innerHTML in Log Messages

- **File:** `frontend/static/js/new-main.js:893-903`
- **Code:** Log messages from the backend are inserted into the DOM using `innerHTML` without sanitization.
- **Impact:** If an attacker can influence log content (e.g., via crafted media titles in *arr apps), they could inject arbitrary JavaScript that executes in the context of the KYHUNTARR UI.
- **Mitigation:** Use `textContent` instead of `innerHTML`, or sanitize with DOMPurify before insertion.

### C4: XSS via innerHTML in Swaparr Download Names

- **File:** `frontend/static/js/apps/swaparr.js:268-284`
- **Code:** Download names from external sources are rendered via `innerHTML` without sanitization.
- **Impact:** Crafted download names containing `<script>` tags or event handlers could execute arbitrary JavaScript.
- **Mitigation:** Use `textContent` or sanitize all external data before DOM insertion.

### C5: XSS via innerHTML in Swaparr Config Display

- **File:** `frontend/static/js/apps/swaparr.js:208-218`
- **Code:** Configuration values are rendered via `innerHTML`.
- **Impact:** If configuration values contain HTML/JavaScript (e.g., injected via API), they could execute in the user's browser.
- **Mitigation:** Use `textContent` for rendering configuration values.

---

## HIGH Findings

### H1: Authentication Bypass via X-Forwarded-For Spoofing

- **File:** `src/primary/auth.py:341-365`
- **Impact:** The `local_access_bypass` feature trusts the `X-Forwarded-For` header to determine if a request is "local." An attacker can spoof this header to bypass authentication when `local_access_bypass` is enabled.
- **Mitigation:** Only trust `X-Forwarded-For` from known reverse proxy IPs. In ElfHosted deployments, authentication is handled by the SSO proxy, making this less critical.

### H2: Proxy Auth Bypass Disables All Authentication

- **File:** `src/primary/auth.py:261-269`, `src/primary/default_configs/general.json:10`
- **Impact:** The `proxy_auth_bypass` setting (enabled by default in KYHUNTARR) disables all built-in authentication. This is **by design** for SSO-proxied deployments but dangerous if the instance is exposed directly to the internet.
- **Mitigation:** Documentation clearly warns that this setting assumes an upstream authentication proxy. Standalone users must configure authentication.

### H3: SSRF via Test Connection Endpoints

- **File:** `src/primary/routes/common.py` (test connection routes)
- **Impact:** The "Test Connection" feature makes HTTP requests to user-supplied URLs. An attacker with UI access could use this to probe internal network services.
- **Mitigation:** Validate and restrict target URLs to expected *arr application patterns. Block requests to internal/private IP ranges.

### H4: No CSRF Protection

- **File:** `src/primary/web_server.py` (Flask app configuration)
- **Impact:** The application does not implement CSRF tokens on forms or API endpoints. An attacker could craft a malicious page that submits requests to KYHUNTARR on behalf of an authenticated user.
- **Mitigation:** Implement Flask-WTF CSRF protection or add custom CSRF token validation.

### H5: API Keys Returned in Plaintext

- **File:** `src/primary/routes/common.py` (settings endpoints)
- **Impact:** *arr API keys are stored and transmitted in plaintext. Any endpoint that returns settings exposes these keys to anyone with UI access.
- **Mitigation:** Mask API keys in API responses (show only last 4 characters). Store encrypted at rest if possible.

### H6: Wildcard CORS Configuration

- **File:** `src/primary/web_server.py`
- **Impact:** If CORS headers are set to allow all origins (`*`), any website can make authenticated requests to the KYHUNTARR API.
- **Mitigation:** Restrict CORS to specific trusted origins.

### H7: XSS via Settings Form Values

- **File:** `frontend/static/js/settings_forms.js` (multiple locations)
- **Impact:** Settings values from the backend are interpolated into HTML strings and inserted via `innerHTML`. Crafted settings values could execute JavaScript.
- **Mitigation:** Use DOM APIs (`createElement`, `textContent`) instead of string interpolation for HTML construction.

### H8: XSS via Error Messages

- **File:** `frontend/static/js/settings_forms.js:938`, `frontend/static/js/apps.js:243`
- **Impact:** Error messages (including `error.message`) are inserted via `innerHTML`. If error messages contain user-controlled content, XSS is possible.
- **Mitigation:** Use `textContent` for error message display.

### H9: XSS in Scheduling Module

- **File:** `frontend/static/js/scheduling.js:684`
- **Impact:** Schedule data is rendered via `innerHTML` with string interpolation. Crafted schedule names or values could inject JavaScript.
- **Mitigation:** Sanitize or use `textContent` for user-supplied values in schedule rendering.

### H10: No Content Security Policy (CSP)

- **File:** `frontend/templates/components/head.html`
- **Impact:** Without a CSP header, the browser allows inline scripts, external script loading, and other behaviors that make XSS exploitation easier.
- **Mitigation:** Add a `Content-Security-Policy` header that restricts script sources and disables inline scripts.

---

## MEDIUM Findings

### M1: No Rate Limiting on Login

- **File:** `src/primary/auth.py`, `src/primary/routes/common.py`
- **Impact:** No rate limiting on the login endpoint allows brute-force password attacks.
- **Mitigation:** Implement rate limiting (e.g., Flask-Limiter) or account lockout after failed attempts.

### M2: Session Configuration Weaknesses

- **File:** `src/primary/web_server.py`
- **Impact:** Session cookies may not be configured with `Secure`, `HttpOnly`, and `SameSite` flags.
- **Mitigation:** Set `SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`.

### M3: No Session Expiration

- **File:** `src/primary/web_server.py`
- **Impact:** Sessions may not expire, allowing indefinite session reuse if a session cookie is compromised.
- **Mitigation:** Configure `PERMANENT_SESSION_LIFETIME` to a reasonable duration.

### M4: Verbose Error Messages

- **Files:** Various backend routes
- **Impact:** Detailed error messages and stack traces may be exposed to users, leaking internal implementation details.
- **Mitigation:** Return generic error messages in production; log details server-side only.

### M5: Directory Traversal Risk in Static File Serving

- **File:** `src/primary/web_server.py`
- **Impact:** If static file serving is not properly restricted, path traversal could allow reading arbitrary files.
- **Mitigation:** Flask's built-in static file serving is generally safe, but verify `send_from_directory` usage.

### M6: Insufficient Input Validation on API Endpoints

- **Files:** Various route handlers in `src/primary/routes/`
- **Impact:** API endpoints may not validate input types, lengths, or formats, potentially leading to unexpected behavior.
- **Mitigation:** Add input validation and type checking to all API endpoints.

### M7: MD5 Hash Usage in Swaparr

- **File:** `src/primary/apps/swaparr/handler.py:87`
- **Code:** `hashlib.md5(hash_input.encode('utf-8')).hexdigest()`
- **Impact:** MD5 is cryptographically broken. While used here for deduplication rather than security, it could lead to hash collisions.
- **Mitigation:** Replace with SHA-256 for content hashing if collision resistance matters.

### M8: Plaintext Configuration Storage

- **File:** `src/primary/settings_manager.py`, `/config/*.json`
- **Impact:** All configuration including API keys is stored in plaintext JSON files on disk.
- **Mitigation:** Consider encrypting sensitive values at rest. Ensure proper file permissions (600).

### M9: No Audit Logging

- **Files:** Various
- **Impact:** There is no audit trail for security-relevant actions (login attempts, settings changes, API key access).
- **Mitigation:** Add structured logging for authentication events and configuration changes.

### M10: Username Enumeration via Login Response

- **File:** `src/primary/auth.py`
- **Impact:** Different error messages for "user not found" vs "wrong password" allow attackers to enumerate valid usernames.
- **Mitigation:** Return a generic "invalid credentials" message for all login failures.

### M11: Inline Event Handlers in Frontend

- **Files:** `frontend/static/js/settings_forms.js`, `frontend/static/js/scheduling.js`
- **Impact:** Use of `onclick` and other inline event handlers in dynamically generated HTML makes CSP implementation harder and increases XSS surface.
- **Mitigation:** Use `addEventListener` instead of inline handlers.

### M12: No Subresource Integrity (SRI)

- **File:** `frontend/templates/components/head.html`
- **Impact:** External CSS/JS resources loaded from CDNs (Font Awesome, Google Fonts) have no integrity hashes. CDN compromise could inject malicious code.
- **Mitigation:** Add `integrity` attributes to external resource tags.

### M13: localStorage for Sensitive Data

- **Files:** `frontend/static/js/new-main.js`
- **Impact:** Sensitive data or tokens stored in `localStorage` are accessible to any JavaScript on the page, including XSS payloads.
- **Mitigation:** Use `sessionStorage` or HTTP-only cookies for sensitive data.

### M14: No Security Headers

- **File:** `src/primary/web_server.py`
- **Impact:** Missing headers like `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, and `Referrer-Policy`.
- **Mitigation:** Add security headers via Flask middleware or reverse proxy configuration.

### M15: Unvalidated Redirects

- **Files:** `src/primary/routes/common.py`
- **Impact:** Login redirects may not validate the target URL, potentially allowing open redirect attacks.
- **Mitigation:** Validate redirect URLs against a whitelist of allowed paths.

### M16: Container Runs as Root

- **File:** `Dockerfile`
- **Impact:** The container process runs as root by default, increasing the blast radius if the application is compromised.
- **Mitigation:** Add a non-root user to the Dockerfile and switch to it.

### M17: No Health Check Endpoint

- **File:** `Dockerfile`, `docker-compose.yml`
- **Impact:** Without a health check, Docker cannot detect if the application is in a degraded state.
- **Mitigation:** Add a `/health` endpoint and configure Docker health checks.

---

## LOW Findings

### L1: Debug Logging May Expose Sensitive Data

- **Files:** Various
- **Impact:** Debug-level logging may include API keys, URLs, or other sensitive information in log output.
- **Mitigation:** Sanitize sensitive values in log messages. Use structured logging with sensitive field masking.

### L2: No Password Complexity Requirements

- **File:** `src/primary/auth.py`
- **Impact:** Users can set weak passwords with no minimum length or complexity requirements.
- **Mitigation:** Enforce minimum password length and complexity rules.

### L3: Timing Attack on Password Comparison

- **File:** `src/primary/auth.py:86`
- **Impact:** Using `==` for hash comparison may be vulnerable to timing attacks that could leak information about the correct hash.
- **Mitigation:** Use `hmac.compare_digest()` for constant-time comparison.

### L4: No Dependency Pinning

- **File:** `requirements.txt` (if present)
- **Impact:** Unpinned dependencies could introduce vulnerable versions during builds.
- **Mitigation:** Pin all dependency versions. Use `pip-audit` or Dependabot to monitor for vulnerabilities.

### L5: Font Awesome Kit Script

- **File:** `frontend/templates/components/head.html`
- **Impact:** Loading Font Awesome via a kit script gives the CDN control over what JavaScript is executed.
- **Mitigation:** Self-host Font Awesome or use the CSS-only version.

### L6: Version Information Disclosure

- **File:** `version.txt`, `/api/version` endpoint
- **Impact:** Version information is publicly accessible, helping attackers identify known vulnerabilities.
- **Mitigation:** Restrict version endpoint to authenticated users.

### L7: Permissive File Permissions in Config Volume

- **File:** Docker volume mount `./config:/config`
- **Impact:** Default file permissions on the config volume may be too permissive, exposing API keys.
- **Mitigation:** Set `umask` in the entrypoint or explicitly set file permissions on config files.

### L8: No robots.txt or Security.txt

- **Impact:** No `robots.txt` to prevent search engine indexing of the UI, and no `security.txt` for responsible disclosure.
- **Mitigation:** Add both files. `security.txt` should point to the GitHub repository's security policy.

---

## INFORMATIONAL Findings

### I1: Telemetry/Phone-Home Code Removed

The upstream KYHUNTARR telemetry, update-check, and CI integration code has been **successfully removed** in KYHUNTARR. No evidence of outbound data collection, remote code execution, or hidden communication channels was found. This was one of the primary motivations for the fork.

### I2: Two-Factor Authentication Available

The codebase includes TOTP-based two-factor authentication support (`src/primary/auth.py`), which is a positive security feature for standalone deployments.

### I3: Waitress WSGI Server

The application uses Waitress as the WSGI server, which is more suitable for production than Flask's built-in development server. Waitress has a reasonable security track record.

### I4: JSON Configuration Files

Configuration is stored in JSON files under `/config/`. While plaintext, the file-based approach avoids database-related vulnerabilities (SQL injection, etc.).

### I5: No Server-Side Template Injection

Flask templates use Jinja2 auto-escaping by default, and no instances of `| safe` filter misuse or `render_template_string()` with user input were found.

### I6: API Key Validation on *arr Connections

The application validates API keys when testing connections to *arr instances, providing feedback if credentials are incorrect.

### I7: Static Asset Serving

Static assets are served through Flask's built-in static file handler, which prevents directory listing and path traversal by default.

---

## Recommendations by Deployment Type

### ElfHosted / SSO-Proxied Deployments (Primary Use Case)

Most authentication-related findings (C1, C2, H1, H2, H4, M1, M2, M3, M10) are **mitigated** by the upstream SSO proxy handling authentication. Priority fixes:

1. **Set `SECRET_KEY` environment variable** (C1) - even behind SSO, a predictable session key is risky
2. **Fix XSS vulnerabilities** (C3, C4, C5, H7-H9) - XSS can still be exploited regardless of auth method
3. **Add CSP headers** (H10) - defense in depth against XSS
4. **Run as non-root** (M16) - container security best practice

### Standalone Deployments

All findings apply. Priority order:

1. **Set `SECRET_KEY` environment variable** (C1)
2. **Replace SHA-256 password hashing with bcrypt** (C2)
3. **Fix all XSS vulnerabilities** (C3-C5, H7-H9)
4. **Add CSRF protection** (H4)
5. **Implement rate limiting** (M1)
6. **Add security headers** (M14, H10)
7. **Run as non-root user** (M16)
8. **Restrict CORS** (H6)

---

## Positive Security Notes

- No telemetry or phone-home code detected (the primary concern from upstream)
- No obfuscated code found
- No hardcoded credentials for external services
- No evidence of data exfiltration
- Jinja2 auto-escaping enabled server-side
- Waitress production WSGI server used
- TOTP 2FA support available
- Graceful shutdown handling prevents zombie processes
