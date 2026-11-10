# Free fixture provider identity fields

Each normalized fixture observation distinguishes provider-scoped identity from
display labels:

- competition_key: provider competition ID/slug when available.
- competition_name: provider display name.
- season_key: provider season ID/label.
- season_name: provider season display label.
- home_team_key and away_team_key: provider-scoped team IDs when supplied.
- home_team_name and away_team_name: display labels.

OpenLigaDB uses its league ID/shortcut and season value. OpenFootball uses the
season-file competition stem and season directory. Open Matchday uses the
competition directory and fixture season label. LiveScoreFootball uses event
competition/season IDs. Bzzoiro uses league/season IDs.

Missing upstream fixture IDs in static datasets receive deterministic provider- and
competition-scoped observation keys; missing static team IDs receive deterministic
provider- and competition-scoped team keys. These keys are not upstream IDs or
canonical IDs, but they make later explicit crosswalk review possible. Display
names are not substituted for missing dynamic-provider IDs. The strict kickoff
and scheduled-status eligibility gates remain unchanged.
