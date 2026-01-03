---
trigger: model_decision
description: When implenting any database or API-related functionality using Supabase
---

# Supabase Best Practices

## Migrations

- Always use the supabase CLI to create new migration files, for example

```bash
supabase migration new migration_name
```