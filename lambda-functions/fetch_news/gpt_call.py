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
    2. Extract and format all gameplay-relevant Battlegrounds updates into clean, structured HTML. Use only the HTML tags listed below.

        For any **minion, hero, trinket, spell, anomaly, buddy, or quest** that has undergone a **gameplay-affecting stat or text change**, summarize the change in a single bullet under the card’s name.

        - Your one-line summary must **always include both the old and new values or text** for clarity.
        - If the patch notes indicate that a change is only for clarity (e.g., “Dev Comment: The text update is a non-functional change just for clarity.”), explicitly mention this in the summary — for example:
          <li><em>Text updated for clarity (“all your Quilboar”), but no functional change to gameplay.</em></li>
        - Do not include any "Old:" or "New:" prefixes — just describe the change fully and clearly in natural language.
        - Do not include the phrase "Summarized Change:" in your output.

        Use this format:

        ```html
        <h3>Card Name</h3>
        <ul>
        <li><em>Cost reduced from 6 Gold to 2 Gold, and now gets a Goldgrubber and an Aureate Laureate.</em></li>
        </ul>
        ```
    3. Embed card images whenever they are provided in the patch notes. This includes both newly added cards and existing cards with changes.
       If multiple images are adjacent (e.g. several new cards added in a row), group them within the same paragraph:
       <p><img src="URL1" alt="CARD1"><img src="URL2" alt="CARD2"></p>
       Only show images if they are explicitly included in the source material.
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

    Tables (for armor changes or other structured data):
    <table>
      <thead>
        <tr><th>Header 1</th><th>Header 2</th></tr>
      </thead>
      <tbody>
        <tr><td>Data</td><td>Data</td></tr>
      </tbody>
    </table>

    Content Guidelines:
    - Only include Battlegrounds-related gameplay changes.
    - Exclude constructed/Hearthstone mode updates.
    - Prioritize updates in this order: added/removed minions, card stat/text changes, mechanic changes (anomalies, quests), bug fixes, hero bans, armor updates.
    - Embed images only for new cards, heroes, anomalies, trinkets, buddies, or quests as specified.
    - Output valid HTML only — no extra explanations, markdown, or comments.
    - For any card with an “Old” and “New” description, clearly identify not just stat changes, but also any change in card text wording, especially key terms (e.g. spell → Tavern spell). Treat even subtle text changes as meaningful and include them in the summary.

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
