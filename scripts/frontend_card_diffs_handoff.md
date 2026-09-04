# Frontend Handoff: Battlegrounds Card Diffs

## Goal

Use the new `card_diffs` Supabase table to render generated Battlegrounds patch notes. The first sample patch note should compare:

```txt
from_build_number = 239550
to_build_number = 241135
```

The backend script stores structured diffs only. The frontend is responsible for grouping, ordering, visual rendering, image URL derivation, and any prose around the structured changes.

## Table

```sql
card_diffs (
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
)
```

RLS public read policy should already be enabled.

## Query

Fetch all diffs for the sample patch:

```ts
const { data, error } = await supabase
  .from("card_diffs")
  .select("*")
  .eq("from_build_number", "239550")
  .eq("to_build_number", "241135")
  .order("category", { ascending: true })
  .order("change_type", { ascending: true })
  .order("card_id", { ascending: true });
```

Recommended build selector query:

```ts
const { data, error } = await supabase
  .from("build_snapshots")
  .select("build_number, fetched_at, raw_card_count, entity_counts")
  .order("build_number", { ascending: false });
```

## Row Shape

Example modified row:

```json
{
  "from_build_number": "239550",
  "to_build_number": "241135",
  "category": "current_pool_minions",
  "card_id": "BG_example",
  "dbf_id": 123456,
  "change_type": "modified",
  "old_card_json": {
    "name": "Example Minion",
    "attack": 3,
    "health": 4,
    "text": "Old text.",
    "type": "MINION",
    "techLevel": 2
  },
  "new_card_json": {
    "name": "Example Minion",
    "attack": 4,
    "health": 4,
    "text": "New text.",
    "type": "MINION",
    "techLevel": 2
  },
  "field_changes": {
    "attack": { "old": 3, "new": 4 },
    "text": {
      "old": "Old text.",
      "new": "New text.",
      "diff": "Concise summary of the functional text change."
    }
  }
}
```

For `added`, `old_card_json` is `null`.

For `removed`, `new_card_json` is `null`.

For `modified`, both `old_card_json` and `new_card_json` are present and `field_changes` describes changed fields. When `text` or `golden.text` changes, that field change may include a concise LLM-generated `diff` string for readers.

## Stored JSON Notes

`old_card_json` and `new_card_json` are compact normalized card objects. They intentionally do not include:

- `id`, use row `card_id`
- `dbfId`, use row `dbf_id`
- `imageUrl`, derive in frontend
- category flags like `isBattlegroundsPoolMinion`

Text is already sanitized for display. For example, HearthstoneJSON markup like:

```txt
[x]<b>Battlecry:</b> Your <b>Blood
Gems</b> give an extra
+1 Health this game.
```

is stored as:

```txt
Battlecry: Your Blood Gems give an extra +1 Health this game.
```

Nested objects can appear:

- `heroPower`
- `golden`

Nested diffs use dot paths in `field_changes`, such as:

```json
{
  "golden.text": {
    "old": "Old golden text.",
    "new": "New golden text."
  },
  "heroPower.cost": {
    "old": 2,
    "new": 1
  }
}
```

## Image URLs

Derive image URLs from `card_id` and card type/category.

Hero image:

```ts
`https://art.hearthstonejson.com/v1/heroes/latest/enUS/256x/${cardId}.png`
```

Normal Battlegrounds card image:

```ts
`https://art.hearthstonejson.com/v1/bgs/latest/enUS/256x/${cardId}.png`
```

Golden nested card image, if needed:

```ts
`https://art.hearthstonejson.com/v1/bgs/latest/enUS/256x/${goldenCardId}_triple.png`
```

Important: the compact nested `golden` object currently does not include its own ID. For now, use the normal card art for the card row unless the UI gets a backend field for golden image identity later.

Suggested helper:

```ts
function getCardImageUrl(row: CardDiffRow) {
  const card = row.new_card_json ?? row.old_card_json;
  const isHero = row.category === "heroes" || card?.type === "HERO";
  const base = isHero
    ? "https://art.hearthstonejson.com/v1/heroes/latest/enUS/256x"
    : "https://art.hearthstonejson.com/v1/bgs/latest/enUS/256x";

  return `${base}/${row.card_id}.png`;
}
```

## Categories

Expected categories:

```txt
heroes
buddies
current_pool_minions
non_current_pool_minions
trinkets
quests
quest_rewards
current_pool_tavern_spells
non_current_pool_tavern_spells
spells
anomalies
time_warped_minions
```

Recommended display labels:

```ts
const CATEGORY_LABELS: Record<string, string> = {
  heroes: "Heroes",
  buddies: "Buddies",
  current_pool_minions: "Current Pool Minions",
  non_current_pool_minions: "Other Battlegrounds Minions",
  trinkets: "Trinkets",
  quests: "Quests",
  quest_rewards: "Quest Rewards",
  current_pool_tavern_spells: "Current Pool Tavern Spells",
  non_current_pool_tavern_spells: "Other Tavern Spells",
  spells: "Spells",
  anomalies: "Anomalies",
  time_warped_minions: "Timewarped Minions",
};
```

## Rendering Rules

Use `new_card_json ?? old_card_json` as the display card.

Display title:

```ts
const card = row.new_card_json ?? row.old_card_json;
const title = card?.name ?? row.card_id;
```

Recommended grouping:

1. Group by `category`.
2. Within each category, group by `change_type`.
3. Render `added`, `removed`, then `modified`.
4. Within each group, sort by `techLevel`, then `name`, then `card_id`.

Suggested change labels:

```ts
const CHANGE_LABELS = {
  added: "Added",
  removed: "Removed",
  modified: "Changed",
};
```

For modified cards, render compact stat/text chips from `field_changes`.

High-value fields:

```txt
attack
health
cost
armor
techLevel
text
golden.attack
golden.health
golden.text
heroPower.cost
heroPower.text
```

Example stat rendering:

```ts
function renderChange(path: string, change: { old: unknown; new: unknown }) {
  return `${path}: ${change.old ?? "none"} -> ${change.new ?? "none"}`;
}
```

Frontend can later map paths to prettier labels:

```ts
const FIELD_LABELS: Record<string, string> = {
  attack: "Attack",
  health: "Health",
  cost: "Cost",
  armor: "Armor",
  techLevel: "Tier",
  text: "Text",
  "golden.text": "Golden Text",
  "heroPower.text": "Hero Power Text",
};
```

## Types

Suggested TypeScript shape:

```ts
type CardJson = {
  attack?: number;
  cost?: number;
  race?: string;
  races?: string[];
  techLevel?: number;
  mechanics?: string[];
  health?: number;
  armor?: number;
  text?: string;
  type?: string;
  name?: string;
  referencedTags?: string[];
  spellSchool?: string;
  heroPower?: CardJson;
  golden?: CardJson;
};

type FieldChange = {
  old: unknown;
  new: unknown;
};

type CardDiffRow = {
  id: number;
  from_build_number: string;
  to_build_number: string;
  category: string;
  card_id: string;
  dbf_id: number | null;
  change_type: "added" | "removed" | "modified" | "category_added" | "category_removed";
  old_card_json: CardJson | null;
  new_card_json: CardJson | null;
  field_changes: Record<string, FieldChange> | null;
};
```

## Patch Note Page MVP

For the `239550 -> 241135` sample:

1. Query `card_diffs`.
2. Render a page title like `Battlegrounds Changes: 239550 -> 241135`.
3. Show total number of changes.
4. Group rows by category.
5. For each row, show image, name, change type, tier/stats when present, and changed fields.
6. Do not generate prose paragraphs yet; use structured cards/lists first.

## Important Caveat

`card_diffs` contains only adjacent build diffs as generated by the backend. For a patch note between non-adjacent builds, the frontend should either:

- query the exact available `from_build_number` / `to_build_number` pair, or
- ask the backend to generate/store that pair.

For the current sample, use exactly:

```txt
239550 -> 241135
```
