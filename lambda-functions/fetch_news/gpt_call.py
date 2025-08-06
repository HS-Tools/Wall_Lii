from openai import OpenAI
import os
from dotenv import load_dotenv
import re

# Load environment variables from .env file
load_dotenv()

# Get API key from environment
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY not found in environment variables. Please check your .env file."
    )

client = OpenAI(api_key=api_key)


def summarize_and_format_patch(patch_notes: str) -> tuple:
    prompt = f"""You are a Hearthstone Battlegrounds patch note processor. Your task is to create a concise summary and structured HTML format for Battlegrounds-related changes.

## TASK
1. Write a one-sentence summary highlighting the most impactful Battlegrounds change
2. Format all gameplay changes into clean HTML using the specified structure

## SUMMARY GUIDELINES
- Focus on core gameplay changes (new content, major balance updates, mechanic changes)
- Prioritize: new minions/heroes/anomalies > stat changes > bug fixes > armor updates
- Include major announcements (mid-season updates, rotations, new mechanics)

## HTML FORMATTING RULES

### Allowed HTML Tags Only:
- `<h2>` for section headers
- `<h3>` for ul headers
- `<ul>`, `<li>` for lists
- `<p>` for paragraphs
- `<a href="URL" target="_blank" rel="noopener noreferrer">` for links
- `<div class="card-grid">` and `<div class="card-grid-item">` for grids
- `<img class="card-grid-img" src="URL" alt="NAME">` for images
- `<div class="card-grid-placeholder">NAME</div>` for missing images
- `<p class="card-grid-text">` for grid descriptions

**Minions, Heroes, Spells, Anomalies, Buddies, Quests:**
- For each entity, show:
  - `Old:` the previous functionality (copied verbatim)
  - `New:` the updated functionality (copied verbatim)
  - `Diff:` a natural language description of what changed functionally — be concise and player-focused
  - Always use exact values or phrases from the old/new descriptions in the `Diff:` line. For example: "Stat changed from 5/3 to 6/4; Deathrattle changed from giving +3/+5 to +4/+6." Avoid vague summaries like "increased stats" or "improved effect".
  - When the `new` description uses vague wording like "improve this", **infer the likely numeric or functional outcome** by comparing to the `old` (e.g., “+1/+1 each turn” if previously it gave only +1 Health)
  - Preserve and reuse any associated image URLs from the original content if provided
  - Ensure spells being reintroduced or removed from the pool are mentioned explicitly
  - Always use <h3> tags for entity names only (e.g. spells, anomalies, minions).
  - If the patch note is a full sentence combining the name and change (e.g., "Channel the Devourer has been returned to the spell pool."), reformat it as:
    <h3>Channel the Devourer</h3>
    <ul>
      <li>has been returned to the spell pool.</li>
    </ul>
  - This ensures consistent formatting across all patch notes and separates the subject (entity name) from the gameplay update using bullet points.
- For armor changes: only include a category (high rank, low rank, duos) if the following value is non-blank or not "nc"
- For trinket cost changes: use the grid format with placeholder and cost change description

**Card Image Handling**:
- If an `<img src="...">` tag appears directly after a gameplay change (Minion, Hero, Spell, Anomaly, Trinket, etc.), preserve it and include it after the corresponding `<ul>` list block for that entity.
- Convert preserved image tags to the following format:
  ```html
  <div class="flex flex-wrap gap-6 mt-2">
    <img src="IMAGE_URL" class="w-64 h-auto object-contain rounded" alt="ENTITY NAME" loading="lazy" decoding="async" />
  </div>
  ```
- If no image is provided in the original notes, fall back to `<div class="card-grid-placeholder">NAME</div>`.

### Content Organization:

**Hero Armor Changes:**
- Only include heroes that have at least one valid armor value change
- For each hero, only include categories (High Rank, Low Rank, Duos) that have non-blank and non-"nc" values
- Examples:
  - High Rank: 8, Low Rank: nc, Duos: 6 → High Rank: 8, Duos: 6
  - High Rank: 14, Low Rank: (blank), Duos: 12 → High Rank: 14, Duos: 12
- Format as:
```html
<h2>Decreased Armor</h2>
<div class="card-grid">
<div class="card-grid-item">
<div class="card-grid-placeholder">Hero Name</div>
<p class="card-grid-text">High Rank: X, Low Rank: Y, Duos: Z</p>
</div>
</div>

<h2>Increased Armor</h2>
<div class="card-grid">
<div class="card-grid-item">
<div class="card-grid-placeholder">Hero Name</div>
<p class="card-grid-text">High Rank: X, Low Rank: Y, Duos: Z</p>
</div>
</div>
```

**Trinket Cost Changes:**
```html
<h2>Trinket Cost Changes</h2>
<div class="card-grid">
<div class="card-grid-item">
<div class="card-grid-placeholder">Trinket Name</div>
<p class="card-grid-text">Cost decreased from 4 to 3 Gold</p>
</div>
</div>
```

**Anomaly Changes:**
1. List functional changes first:
```html
<h3>Anomaly Name</h3>
<ul>
<li><em>Change description</em></li>
</ul>
```

2. Then categorize using grids:
```html
<h3>New Anomalies</h3>
<div class="card-grid">...</div>

<h3>Returning Anomalies</h3>
<div class="card-grid">...</div>

<h3>Removed Anomalies</h3>
<div class="card-grid">...</div>

<h3>Duo Anomalies</h3>
<div class="card-grid">...</div>
```

**Other Cost Changes (non-trinket):**
Use natural language: "Cost decreased from 4 to 3 Gold"

### Content Guidelines:
- Only include Battlegrounds-related changes
- Exclude Constructed/Hearthstone mode updates
- For clarity-only changes, explicitly state "Text updated for clarity, no functional change"
- Include bug fixes that impact gameplay (disconnects, timers, broken mechanics)
- Append "(greater)" or "(lesser)" to anomaly names when specified
- Group adjacent card images in single paragraphs
- Preserve original patch note order within sections

### Output Format:
```
Summary:
<one sentence summary>

HTML:
<html content>
```

## PATCH NOTES TO PROCESS:
{patch_notes}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Hearthstone Battlegrounds patch note processor. You create concise summaries and structured HTML for Battlegrounds changes.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        result = response.choices[0].message.content

        # Split the response into summary and HTML parts
        parts = result.split("HTML:", 1)
        if len(parts) == 2:
            summary = parts[0].replace("Summary:", "").strip()
            html_content = parts[1].strip()
            html_content = re.sub(
                r"^```html\n(.*?)\n```$", r"\1", html_content, flags=re.DOTALL
            ).strip()
        else:
            # If the format isn't as expected, use the entire response as HTML
            # and create a summary from the first 200 characters
            html_content = result.strip()
            html_content = re.sub(
                r"^```html\n(.*?)\n```$", r"\1", html_content, flags=re.DOTALL
            ).strip()
            summary = result[:200].strip() + "..."

        return summary, html_content
    except Exception as e:
        print(f"Error in GPT processing: {e}")
        # Return original content if GPT processing fails
        return patch_notes[:200] + "...", f"<p>{patch_notes}</p>"


def check_battlegrounds_relevance(content: str) -> bool:
    prompt = f"""Determine if this Hearthstone content contains Battlegrounds gameplay updates.

Look for changes to:
- Minions, heroes, anomalies, quests, buddies, trinkets
- Armor values, cost changes, stat adjustments
- Gameplay mechanics, bug fixes affecting gameplay
- New content additions or removals

Answer only "Yes" or "No".

Content:
{content}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a content classifier for Hearthstone Battlegrounds updates. Answer only 'Yes' or 'No'.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        result = response.choices[0].message.content.strip().lower()
        return result == "yes"
    except Exception as e:
        print(f"Error in relevance check: {e}")
        return False
