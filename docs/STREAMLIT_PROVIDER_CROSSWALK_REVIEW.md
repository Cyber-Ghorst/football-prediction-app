# Streamlit provider crosswalk review

The Provider Readiness expander now includes a free-fixture entity crosswalk
review tool for OpenLigaDB, OpenFootball, LiveScoreFootball, Bzzoiro and
football-data.org (with restricted providers shown only after their required
terms acknowledgements).

1. Ensure PROVIDER_DATABASE_URL is configured and the provider observation
   archive has at least one batch for the selected source.
2. Select the provider and build the review report.
3. Inspect source IDs, source names, suggested canonical IDs, match status and
   the reason for each suggestion.
4. For each league, season or team, select a canonical entity ID from the
   existing repository and tick its approval checkbox.
5. Enter a reason explaining how the identities were verified, then save the
   selected mappings.

Exact unique name/country or parent-scoped matches are suggestions, not
automatic links. The editor also permits manual canonical selection for
unmatched source IDs. Every saved link is checked against an existing canonical
record, conflicting links are rejected, and the approval reason is written to
provider_entity_link_approval_audit.

Approve competition links before season links. Team and competition mapping
does not activate a fixture provider; fixture-level kickoff, freshness,
deduplication and data-coverage checks remain separate activation gates.
