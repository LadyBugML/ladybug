def reorder_rankings(ranked_files: list[tuple], gs_files: list[str]):
    """
    Boosts GS files to the top of the ranking while preserving their relative order.

    Parameters:
        ranked_files: List of tuples (route, similarity_score), sorted by similarity score.
        gs_files: List or set of routes that should be prioritized.

    Returns:
        boosted_rankings: A reordered list with gs_files at the top in their original order.
    """

    gs_ranked = [item for item in ranked_files if item[0] in gs_files]
    non_gs_ranked = [item for item in ranked_files if item[0] not in gs_files]

    return gs_ranked + non_gs_ranked