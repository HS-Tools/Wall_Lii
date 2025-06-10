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
    prompt = f"""
You are a Hearthstone Battlegrounds patch summarizer. I will provide full patch notes or blog posts. Your job is to:

1. Write a one-sentence summary highlighting the most important Battlegrounds gameplay changes.

- Always prioritize changes that affect core gameplay or player experience.
- Include major announcements such as mid-season updates, minion/hero rotations, new minion types, mechanic overhauls, or system-wide balance changes.
- Mention the most impactful stat or ability changes (e.g., tier drops, text changes, major buffs/nerfs).
- Include critical bug fixes that impact gameplay flow, such as disconnects, reconnection failures, or timer issues.
- If multiple categories are relevant, summarize the most global or impactful change (e.g., “Patch introduces Naga and removes Quests” is higher priority than “X minion buffed”).

2. Extract and format all gameplay-relevant Battlegrounds updates into clean, structured HTML. Use only the HTML tags listed below.

    For any **minion, hero, trinket, spell, anomaly, buddy, or quest** that has undergone a **gameplay-affecting stat or text change**, summarize the change in a single bullet under the card’s name.

    - Your one-line summary must **always include both the old and new values or text** for clarity.
    - If the patch notes indicate that a change is only for clarity (e.g., “Dev Comment: The text update is a non-functional change just for clarity.”), explicitly mention this in the summary — for example:
      <li><em>Text updated for clarity (“all your Quilboar”), but no functional change to gameplay.</em></li>
    - Do not include any "Old:" or "New:" prefixes — just describe the change fully and clearly in natural language.
    - Do not include the phrase "Summarized Change:" in your output.

    For hero armor changes:
    - Present under two headings using card-grid format:
      <h2>Decreased Armor</h2>
      <div class="card-grid">
        <div class="card-grid-item">
          <div class="card-grid-placeholder">Hero Name</div>
          <p class="card-grid-text">high rank: X, low rank: Y, duos: Z</p>
        </div>
      </div>
      <h2>Increased Armor</h2>
      <div class="card-grid">
        <div class="card-grid-item">
          <div class="card-grid-placeholder">Hero Name</div>
          <p class="card-grid-text">high rank: X, low rank: Y, duos: Z</p>
        </div>
      </div>
    - Only include heroes in each category.
    - List only the new armor values; omit any unchanged fields.
    - Preserve original patch note order within each section.

    For cost changes (e.g., trinkets or cards):
    - Describe in natural language: "Cost decreased from 4 to 3 Gold" or "Cost increased from 3 to 4 Gold".
    - Do not use arrow notation for cost changes.

    Use this format:

    ```html
    <h3>Card Name</h3>
    <ul>
    <li><em>Cost decreased from 4 Gold to 2 Gold</em></li>
    </ul>
    ```

3. Embed card images whenever they are provided in the patch notes. This includes both newly added cards and existing cards with changes.
   If multiple images are adjacent (e.g. several new cards added in a row), group them within the same paragraph:
   <p><img src="URL1" alt="CARD1"><img src="URL2" alt="CARD2"></p>
   Only show images if they are explicitly included in the source material.
   When appropriate, group cards into visual grids for better readability and mobile viewing.

Output Format:
Summary:
<one sentence summary here>

HTML:
<html content here>

Use these HTML tags only (no styling classes):

Section headers:
<h2>Section Title</h2>

Lists:
<ul>
  <li><strong>Thing Changed:</strong> description</li>
</ul>

Paragraphs:
<p>Paragraph content here.</p>

Links:
<a href="URL" target="_blank" rel="noopener noreferrer">Link text</a>

- Always use the card-grid format for any stat or cost changes; do not use plain lists or tables for those.

Grid Layouts (for armor tiers, cost changes, or grouped updates):
Instead of tables, display changes using responsive card grids. For each card or entity with a change:
- Use the following structure and class names:
  <div class="card-grid">
    <div class="card-grid-item">
      <img class="card-grid-img" src="IMAGE_URL" alt="ENTITY_NAME">
      <p class="card-grid-text">Cost decreased from 4 Gold to 2 Gold</p>
    </div>
  </div>
- If an image is not available, display a placeholder using:
  <div class="card-grid-item">
    <div class="card-grid-placeholder">ENTITY_NAME</div>
    <p class="card-grid-text">Cost decreased from 4 Gold to 2 Gold</p>
  </div>
- Use divs and paragraphs only — never tables. Ensure content is skimmable and mobile-friendly.

Content Guidelines:
- Only include Battlegrounds-related gameplay changes.
- Exclude Constructed/Hearthstone mode updates.
- Always highlight and prioritize any major Battlegrounds announcements, such as mid-season updates, mode-wide changes, or new patch schedules, especially if they affect core gameplay (e.g., new mechanics arriving soon, temporary removals, or rotation warnings).
- Prioritize updates in this order:
  1. Added or removed minions, trinkets, anomalies, quests, or buddies
  2. Gameplay-affecting stat or text changes
  3. Mechanics changes (anomalies, quest logic, rules)
  4. **Bug fixes or performance improvements that directly impact gameplay**, such as:
     - Disconnects or failure to reconnect
     - Excessively long turn timers
     - Broken Deathrattles, combat logic, or battlecry sequences
  5. Hero bans, armor updates, or other balance tweaks
- If an anomaly is referenced as being “greater” or “lesser” in the patch notes, append (greater) or (lesser) to the anomaly name when summarizing and displaying it. This ensures correct image injection and matching with database entries.

- If no section exists for bug fixes, create one:
  <h2>Bug Fixes and Improvements</h2>

- Output valid HTML only — no extra explanations, markdown, or comments.
- Never use tables — use <div>-based card grids instead.
– For any card with an “Old” and “New” description, clearly identify not just stat changes, but also any change in card text wording, especially key terms (e.g. spell → Tavern spell). Treat even subtle text changes as meaningful and include them in the summary.

Here are the patch notes:
{patch_notes}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
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
    prompt = f"""
    Does the following Hearthstone patch note or blog post contain any specific Battlegrounds gameplay updates such as changes to minions, heroes, anomalies, quests, buddies, trinkets, armor, or other gameplay mechanics? 
    Answer "Yes" or "No" only.

    Content:
    {content}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        result = response.choices[0].message.content.strip().lower()
        return result == "yes"
    except Exception as e:
        print(f"Error in relevance check: {e}")
        return False
