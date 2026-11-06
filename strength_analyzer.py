
def analyze_strength(matches, opponent_ratings):
    """
    opponent_ratings:
    {opponent_name: rating from 0 to 100}
    """

    if not matches:
        return {
            "strength_score": None,
            "known_opponents": 0,
            "unknown_opponents": 0,
            "coverage": 0
        }

    ratings = []

    for match in matches:
        opponent = match.get("opponent")

        if opponent in opponent_ratings:
            rating = opponent_ratings[opponent]

            if (
                isinstance(rating, (int, float))
                and 0 <= rating <= 100
            ):
                ratings.append(rating)

    total = len(matches)
    known = len(ratings)

    return {
        "strength_score": (
            round(sum(ratings) / known, 2)
            if known else None
        ),
        "known_opponents": known,
        "unknown_opponents": total - known,
        "coverage": round(known / total * 100, 2)
    }
