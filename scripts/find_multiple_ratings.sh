#!/bin/bash
aws dynamodb scan \
  --table-name HearthstoneLeaderboard \
  --endpoint-url http://localhost:8000 \
  --filter-expression "attribute_exists(RatingHistory)" \
  --projection-expression "PlayerName, GameModeServerPlayer, RatingHistory" \
  --no-cli-pager \
  --output json \
  | tee /tmp/scan_output.json \
  | jq '
    # First filter for items with multiple history entries
    .Items[] | select(.RatingHistory.L | length > 1) | {
      player: .PlayerName.S,
      mode: (if (.GameModeServerPlayer.S | split("#")[0]) == "0" then "BG" else "Duos" end),
      region: .GameModeServerPlayer.S | split("#")[1],
      history: .RatingHistory.L | map({
        rating: .L[0].N | tonumber,
        timestamp: .L[1].N | tonumber | strftime("%Y-%m-%d %H:%M:%S")
      }),
      games: ((.RatingHistory.L | length) - 1),
      mmr_change: (
        (.RatingHistory.L[-1].L[0].N | tonumber) -
        (.RatingHistory.L[0].L[0].N | tonumber)
      )
    } | "\(.player) (\(.region) \(.mode)): \(if .mmr_change >= 0 then "+" + (.mmr_change | tostring) else .mmr_change | tostring end) MMR in \(.games) games [\(.history[0].rating) → \(.history[-1].rating)]"'

# Print debug info
echo "Raw scan output saved to /tmp/scan_output.json"
echo "Number of items found: $(jq '.Items | length' /tmp/scan_output.json)"
echo "Items with multiple history entries: $(jq '.Items[] | select(.RatingHistory.L | length > 1) | .PlayerName.S' /tmp/scan_output.json | wc -l)"
