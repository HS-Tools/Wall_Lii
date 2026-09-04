

# Hearthstone Battlegrounds Entity Snapshot + Diff Pipeline

## Goal

Create a script/system that periodically checks HearthstoneJSON for the latest Hearthstone build, extracts normalized Battlegrounds entities, stores them in Supabase/Postgres by build number, and computes structured diffs between builds for future patch note generation.

The frontend should eventually consume structured diff data and render aesthetic patch notes. Do not generate prose patch notes in this backend script.

---

## Source

Fetch cards from:

```txt
https://api.hearthstonejson.com/v1/latest/enUS/cards.json
```

Use the redirect behavior to determine the actual build number. Example final resolved URL:

```txt
https://api.hearthstonejson.com/v1/241135/enUS/cards.json
```

Extract `241135` as `build_number`.

Do not scrape HTML if the redirected cards URL exposes the build number. If the
runtime client receives a non-redirected `/latest/.../cards.json` response,
fallback to the `/v1/latest/enUS/` directory page only to resolve the latest
build number.

---

## Entity Categories

Extract and store the following categories:

- `heroes`
- `buddies`
- `current_pool_minions`
- `non_current_pool_minions`
- `trinkets`
- `quests`
- `quest_rewards`
- `current_pool_tavern_spells`
- `non_current_pool_tavern_spells`
- `spells`
- `anomalies`
- `time_warped_minions`

Use the existing classification logic from `scripts/get_hsbg_entities.js`.

Important rules:

- Heroes: `battlegroundsHero === true`
- Current BG minions: `isBattlegroundsPoolMinion === true`
- Non-current BG minions: Battlegrounds minions where `type === "MINION"` and not current pool
- Tavern spells: `type === "BATTLEGROUND_SPELL"` and `spellSchool === "TAVERN"`
- Current tavern spells: tavern spells where `isBattlegroundsPoolSpell === true`
- Timewarped minions: `battlegroundsTimewarpCard === 1`
- Hero powers: look up using `heroPowerDbfId` against a `dbfId -> card` map
- Golden versions: for minions, buddies, and timewarped minions, use `battlegroundsPremiumDbfId` and look it up in the same `dbfId -> card` map

Avoid extra network fetches. Fetch the full cards JSON once, then use in-memory maps.

---

## Stored Card JSON

Store compact normalized card JSON, not the full raw card unless explicitly needed.
The table columns already store `card_id`, `dbf_id`, `category`, and
`build_number`, so do not duplicate those values inside `card_json`.

Include only patch-note-relevant fields when present:

- `attack`
- `cost`
- `race`
- `races`
- `techLevel`
- `mechanics`
- `health`
- `armor`
- `text`
- `type`
- `name`
- `referencedTags`
- `spellSchool`

Sanitize stored `text` values before hashing and diffing:

- remove HearthstoneJSON layout prefix `[x]`
- remove HTML-style formatting tags such as `<b>`, `</b>`, `<i>`, and `</i>`
- convert newlines and non-breaking spaces to normal spaces
- collapse repeated whitespace

Nested objects such as `heroPower` and `golden` should use the same compact
shape. For example:

```json
{
  "name": "Money Match",
  "cost": 0,
  "text": "Start at 10 Gold.",
  "type": "BATTLEGROUND_ANOMALY"
}
```

Exclude noisy fields unless needed:

- `id` inside top-level `card_json`; use `card_snapshots.card_id`
- `dbfId` inside top-level `card_json`; use `card_snapshots.dbf_id`
- `imageUrl`; derive this in the frontend from `card_id` and category/type
- `isBattlegroundsPoolMinion` and `isBattlegroundsPoolSpell`; category encodes pool state
- `battlegroundsHero` and `battlegroundsTimewarpCard`; category encodes this state
- `battlegroundsPremiumDbfId` and `battlegroundsNormalDbfId`; store compact nested `golden` data instead
- `artist`
- `flavor`
- `howToEarn`
- `howToEarnGolden`
- localization-only metadata

---

## Image URLs

Do not store image URLs in `card_snapshots.card_json` or use them for hashing or
diffing. Generate them in the frontend from card IDs.

Normal Battlegrounds card image:

```js
`https://art.hearthstonejson.com/v1/bgs/latest/enUS/256x/${id}.png`
```

Hero image:

```js
`https://art.hearthstonejson.com/v1/heroes/latest/enUS/256x/${id}.png`
```

Golden BG minion, buddy, or timewarped image:

```js
`https://art.hearthstonejson.com/v1/bgs/latest/enUS/256x/${id}_triple.png`
```

---

## Database Schema

Use Supabase/Postgres.

If you want to recreate the schema from scratch, run this first:

```sql
drop table if exists card_diffs;
drop table if exists card_snapshots;
drop table if exists build_snapshots;
```

### `build_snapshots`

One row per successfully ingested HearthstoneJSON build.

```sql
create table build_snapshots (
  build_number text primary key,
  source_url text not null,
  fetched_at timestamptz not null default now(),
  raw_card_count int not null,
  entity_counts jsonb not null
);

alter table build_snapshots enable row level security;

create policy "Public read build_snapshots"
on build_snapshots
for select
to anon, authenticated
using (true);
```

### `card_snapshots`

One row per normalized entity per build/category.

```sql
create table card_snapshots (
  build_number text not null references build_snapshots(build_number),
  category text not null,
  card_id text not null,
  dbf_id int,
  card_json jsonb not null,
  content_hash text not null,

  primary key (build_number, category, card_id)
);

create index card_snapshots_category_idx
on card_snapshots(category);

create index card_snapshots_card_id_idx
on card_snapshots(card_id);

create index card_snapshots_dbf_id_idx
on card_snapshots(dbf_id);

create index card_snapshots_content_hash_idx
on card_snapshots(content_hash);

alter table card_snapshots enable row level security;

create policy "Public read card_snapshots"
on card_snapshots
for select
to anon, authenticated
using (true);
```

### `card_diffs`

Structured diffs between adjacent builds.

```sql
create table card_diffs (
  id bigserial primary key,
  from_build_number text not null,
  to_build_number text not null,
  category text not null,
  card_id text not null,
  dbf_id int,
  change_type text not null,
  old_card_json jsonb,
  new_card_json jsonb,
  field_changes jsonb,

  unique (from_build_number, to_build_number, category, card_id)
);

alter table card_diffs enable row level security;

create policy "Public read card_diffs"
on card_diffs
for select
to anon, authenticated
using (true);
```

Allowed `change_type` values:

- `added`
- `removed`
- `modified`
- `category_added`
- `category_removed`

---

## Ingestion Flow

1. Fetch `https://api.hearthstonejson.com/v1/latest/enUS/cards.json`.
2. Extract `build_number` from the final resolved response URL.
3. Check whether `build_snapshots.build_number` already exists.
4. If it exists, exit without doing work.
5. Parse all cards.
6. Build `cardsByDbfId`.
7. Extract all entity categories.
8. Normalize cards to compact patch-note fields.
9. Attach hero powers to heroes.
10. Attach golden versions to minions, buddies, and timewarped minions.
11. Remove duplicated/derived fields from `card_json`.
12. Compute stable `content_hash` for each stored `card_json`.
13. Insert `build_snapshots`.
14. Insert `card_snapshots`.
15. Find previous build number.
16. Compute diffs between previous build and current build.
17. Insert `card_diffs`.

Use a transaction where practical so partial ingests do not leave inconsistent data.

---

## Diff Logic

Compare adjacent builds.

For each `(category, card_id)` pair:

- Exists only in new build → `added`
- Exists only in old build → `removed`
- Exists in both but `content_hash` differs → `modified`
- Exists in both and hash same → no diff row

For modified cards, compute per-field changes:

```json
{
  "attack": { "old": 3, "new": 4 },
  "text": { "old": "...", "new": "..." },
  "golden.text": { "old": "...", "new": "..." }
}
```

Use normalized JSON for diffing, not raw HearthstoneJSON.

---

## Important Implementation Details

- Use `id` as the primary logical card identity.
- Use `dbfId` for lookup relationships like hero powers and golden versions.
- Store top-level `id` and `dbfId` as `card_snapshots.card_id` and
  `card_snapshots.dbf_id`, not inside `card_json`.
- Use deterministic JSON stringification before hashing so field order does not create false diffs.
- Do not store or compare image URLs. Image URLs are derived frontend data and
  can create noise if path logic changes.
- Store both `old_card_json` and `new_card_json` in `card_diffs` for easy frontend rendering.
- Keep frontend prose/rendering separate from backend diff computation.

---

## Script Output

At the end of the script, log:

- build number
- whether the build was new or already existed
- raw card count
- entity counts by category
- number of diffs inserted
- previous build compared against, if any
