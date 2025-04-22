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
    2. Extract and format all gameplay-relevant Battlegrounds updates into clean, structured HTML using the tags specified below.
    3. When mentioning new cards, heroes, anomalies, trinkets, buddies, or quests, embed their image links directly beneath their mention using the following format:
    <p><img src="IMAGE_URL" alt="CARD_NAME"></p>

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
