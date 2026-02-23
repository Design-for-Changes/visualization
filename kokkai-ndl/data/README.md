# Data cache

This folder stores fetched JSON snapshots from the NDL Kokkai API.

- `speeches.raw.json`: normalized speech list (merged, de-duped)
- `sessions.summary.json`: grouped by session (第◯回国会) for timeline UI

Regenerate:

```sh
node scripts/fetch_speeches.mjs
```

