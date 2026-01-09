---
trigger: model_decision
description: When deciding which git branch to use or how to commit code.
---

# Branch Strategy - Git and Deployment Environments

This document explains how Git branches align with deployment environments in the Legal-AI CI/CD pipeline.

## Overview

We use a **four-tier branching strategy**:

```text
Git Branch     → Deployment Environment → Purpose
──────────────────────────────────────────────────────────────────────────────────────
feature/*      → None (local only)      → Individual feature development
local          → E2E Testing            → Integration testing, automated E2E tests
staging        → Staging                → Manual testing and QA validation
main           → Production             → Production-ready code, auto-deployed
```

---

## Git Branches

### **Feature Branches** (`feature/*`, `fix/*`, `refactor/*`)

- **Purpose:** Individual feature development and bug fixes
- **Created from:** `local` branch
- **Merged into:** `local` branch
- **Testing:** Local unit tests
- **Deployment:** None (local development only)
- **Naming:** `feature/scraper-improvements`, `fix/citation-parser`, `refactor/database-schema`

### **`local` Branch**

- **Purpose:** Integration branch for local development and E2E testing
- **Triggers:** E2E test suite, automated integration tests
- **Testing:** Full test suite (unit, integration, E2E)
- **Deployment:** E2E testing environment
- **Merges from:** Feature branches
- **Merges into:** `staging` branch

### **`staging` Branch**

- **Purpose:** Pre-production manual testing and QA validation
- **Triggers:** Staging environment deployment
- **Testing:** Manual QA testing, acceptance testing
- **Deployment:** Staging environment
- **Merges from:** `local` branch
- **Merges into:** `main` branch

### **`main` Branch**

- **Purpose:** Production-ready code
- **Triggers:** Automatic production deployment
- **Testing:** Smoke tests in production
- **Deployment:** Production environment (auto-deployed)
- **Merges from:** `staging` branch only
- **Protected:** Requires PR approval, passing CI checks

## Database Instances

### **Local Database**

- **Environment:** Local development
- **Data:** Test data (seeded)
- **Access:** Local machine only
- **Schema:** Built from migrations
- **Lifetime:** Can be reset anytime

### **E2E Testing Database**

- **Environment:** E2E testing (linked to `local` branch)
- **Data:** Test data (reset between test runs)
- **Access:** CI/CD pipeline
- **Schema:** Synced with migrations
- **Lifetime:** Ephemeral (reset after tests)

### **Staging Database**

- **Environment:** Staging (linked to `staging` branch)
- **Data:** Production-like test data
- **Access:** QA team and developers
- **Schema:** Mirrors production
- **Lifetime:** Persistent (refreshed periodically from production)

### **Production Database**

- **Environment:** Production (linked to `main` branch)
- **Data:** Real user data
- **Access:** Production builds only
- **Schema:** Master schema
- **Lifetime:** Permanent

## CI/CD Workflow

### **Push to Feature Branch**

```
1. Lint & TypeCheck ✓
2. Unit Tests ✓
```

### **Merge to `local` Branch**

```
1. Lint & TypeCheck ✓
2. Unit Tests ✓
3. Integration Tests ✓
4. E2E Tests ✓
5. Deploy to E2E Environment
```

### **Merge to `staging` Branch**

```
1. Lint & TypeCheck ✓
2. Unit Tests ✓
3. Integration Tests ✓
4. Deploy to Staging Environment
5. Manual QA Testing (Required)
```

### **Merge to `main` Branch**

```
1. Verify Staging Approval ✓
2. Lint & TypeCheck ✓
3. Unit Tests ✓
4. Integration Tests ✓
5. Deploy to Production
6. Run Smoke Tests
7. Monitor Deployment
```

## Development Flow

### Creating a New Feature

```bash
# Start from local branch
git checkout local
git pull origin local

# Create feature branch
git checkout -b feature/my-feature

# Make changes and commit
git add .
git commit -m "feat: implement my feature"

# Push and create PR to local
git push origin feature/my-feature
# Open PR: feature/my-feature → local
```

### Promoting to Staging

```bash
# After feature merged to local and E2E tests pass
git checkout staging
git pull origin staging
git merge local
git push origin staging

# Or create PR: local → staging
```

### Promoting to Production

```bash
# After manual QA approval in staging
git checkout main
git pull origin main
git merge staging
git push origin main

# Or create PR: staging → main (requires approval)
```

## Commit Messages

✅ Good:
```
feat: add judiciary scraper resume capability

Implements state persistence for resuming interrupted scrapes.
Closes #123
```

❌ Bad:
```
fixed stuff
```
