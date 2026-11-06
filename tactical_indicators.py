
def analyze_tactics(stats):
    """
    Expected statistics:
    possession, shots, shots_on_target,
    big_chances, pass_accuracy, tackles,
    interceptions, blocked_shots
    """

    if not stats:
        return {
            "attack_score": None,
            "defence_score": None,
            "data_coverage": 0
        }

    def get_value(key):
        value = stats.get(key)

        if isinstance(value, (int, float)):
            return value

        return None

    metrics = {
        "possession": get_value("possession"),
        "shots": get_value("shots"),
        "shots_on_target": get_value("shots_on_target"),
        "big_chances": get_value("big_chances"),
        "pass_accuracy": get_value("pass_accuracy"),
        "tackles": get_value("tackles"),
        "interceptions": get_value("interceptions"),
        "blocked_shots": get_value("blocked_shots")
    }

    attack_weights = {
        "shots": 0.25,
        "shots_on_target": 0.35,
        "big_chances": 0.25,
        "pass_accuracy": 0.15
    }

    defence_weights = {
        "tackles": 0.30,
        "interceptions": 0.30,
        "blocked_shots": 0.20,
        "possession": 0.20
    }

    def calculate_score(weights):
        available = [
            key for key in weights
            if metrics[key] is not None
        ]

        if not available:
            return None

        total_weight = sum(
            weights[key] for key in available
        )

        score = sum(
            min(max(metrics[key], 0), 100)
            * weights[key]
            for key in available
        )

        return round(score / total_weight, 2)

    coverage = sum(
        value is not None for value in metrics.values()
    )

    return {
        "attack_score": calculate_score(attack_weights),
        "defence_score": calculate_score(defence_weights),
        "data_coverage": round(coverage / 8 * 100, 2),
        "raw_statistics": metrics
    }
