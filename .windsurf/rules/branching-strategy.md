---
trigger: model_decision
description: When deciding which git branch to use or how to commit code.
---

# Branch Strategy - Git, Netlify and Supabase

This document explains how Git branches, Netlify preview/production deployments, and Supabase branches work together in the TutorMart CI/CD pipeline.

## Overview

We use a **two-tier branching strategy** that aligns across all systems:

```text
Git Branch → Netlify Preview/Production → Supabase Instance → Purpose
────────────────────────────────────────────────────────────────────────────────────────────
local      → preview deploy             → local             → Local development and testing
main       → production                 → main              → CI/CD Unit & Integration Tests and Production
```

---

## Git Branches

### **`local` Branch**

- **Purpose:** Local development and testing
- **Triggers:** Nothing
- **Testing:** Manually run tests
- **Deployment:** Preview deploy, dev environment

### **`main` Branch**

- **Purpose:** Production-ready code
- **Triggers:** Production builds and updates
- **Testing:** Unit and Integration Tests
- **Deployment:** Production deploy, main environment

## Supabase Instances

### **Local Instance**

- **Data:** Test data
- **Access:** Local development testing only
- **Schema:** Built from migrations
- **Lifetime:** Permanent (can be reset)

### **Main Instance**

- **Data:** Real user data
- **Access:** Production builds only
- **Schema:** Master schema
- **Lifetime:** Permanent

## CI/CD Workflow

### **Push to `local` Branch**

```
1. Lint & TypeCheck ✓
2. Unit Tests ✓
3. Integration Tests ✓
```

### **Push to `main` Branch**

```
1. Lint & TypeCheck ✓
2. Unit Tests ✓
3. Integration Tests ✓
4. Deploy to AWS S3/CloudFront
5. Deploy to Supabase Main Instance
```

## Commit Messages

✅ Good:
feat: add user authentication flow

Implements OAuth2 login process with Google
Related to #123

❌ Bad:
fixed stuff