# Sample Run — structured output summary

Generated: 2026-04-26T10:37:27.315830+00:00
Records: 5

| # | Source | Category | Priority | Confidence | Queue | Escalated? | Reasons |
|---|--------|----------|----------|------------|-------|------------|---------|
| 1 | chat | bug_report | medium | 0.83 | engineering | no | — |
| 2 | web_form | feature_request | low | 0.92 | product | no | — |
| 3 | chat | bug_report | medium | 0.86 | engineering | no | — |
| 4 | chat | technical_question | low | 0.81 | product | no | — |
| 5 | web_form | incident_outage | high | 0.94 | it_security | YES | category_incident_outage |

## Records

### Sample 1 (chat)

**Input:**
> Hi, I'm trying to book a math tutor for IGCSE but I can't see any available time slots after selecting the teacher.

**Summary:**
> Bug Report reported via the platform with priority medium. Routed to engineering (SLA 60m). User wrote: "Hi, I'm trying to book a math tutor for IGCSE but I can't see any available time slots after selecting the teacher."

**Routing:** `engineering` (SLA 60m)

---

### Sample 2 (web_form)

**Input:**
> It would be really helpful if we could compare tutors based on ratings, price, and availability in one view before booking.

**Summary:**
> Feature Request reported via the platform with priority low. Routed to product (SLA 240m). User wrote: "It would be really helpful if we could compare tutors based on ratings, price, and availability in one view before booking."

**Routing:** `product` (SLA 240m)

---

### Sample 3 (chat)

**Input:**
> I booked a session yesterday but I didn't receive any confirmation email or session details. Can you check if my booking went through?

**Summary:**
> Bug Report reported via the platform with priority medium. Routed to engineering (SLA 60m). User wrote: "I booked a session yesterday but I didn't receive any confirmation email or session details. Can you check if my booking went through?"

**Routing:** `engineering` (SLA 60m)

---

### Sample 4 (chat)

**Input:**
> Is there a way to get help choosing the right major or university based on my interests?

**Summary:**
> Technical Question reported via the platform with priority low. Routed to product (SLA 240m). User wrote: "Is there a way to get help choosing the right major or university based on my interests?"

**Routing:** `product` (SLA 240m)

---

### Sample 5 (web_form)

**Input:**
> The platform is not loading properly and none of the tutors are showing up. Multiple users are facing the same issue.

**Summary:**
> Incident Outage reported via the platform with priority high. Routed to it_security (SLA 15m). User wrote: "The platform is not loading properly and none of the tutors are showing up. Multiple users are facing the same issue."

**Routing:** `it_security` (SLA 15m)

**Escalation triggered:**
- `category_incident_outage`

---
