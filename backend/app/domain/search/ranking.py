from difflib import SequenceMatcher

from app.domain.catalog.schemas import STEItemRead
from app.domain.personalization.schemas import SearchProfileRead
from app.domain.search.normalizer import extract_query_terms
from app.domain.search.schemas import CandidateItem


def build_candidate(
    item: STEItemRead,
    normalized_query: str,
    profile: SearchProfileRead,
    query_terms: list[str] | None = None,
    retrieval_score: float = 0.0,
    retrieval_reasons: list[str] | None = None,
    retrieval_channel_scores: dict[str, float] | None = None,
    retrieval_channel_ranks: dict[str, int] | None = None,
    retrieval_features: dict[str, float] | None = None,
    retrieval_only: bool = False,
) -> CandidateItem:
    title = item.title.lower()
    description = item.description.lower()
    attributes_blob = " ".join(item.attributes.values()).lower()
    lexical_score = 0.0
    reasons: list[str] = []
    query_tokens = query_terms or extract_query_terms(normalized_query)
    structured_features = retrieval_features or {}

    if retrieval_only:
        retrieval_only_score = round(float(retrieval_score), 4)
        reasons = list(dict.fromkeys(retrieval_reasons or ["retrieval_rrf"]))
        return CandidateItem(
            id=item.id,
            title=item.title,
            category=item.category_name,
            supplier=item.supplier_name,
            description=item.description,
            score=retrieval_only_score,
            reasons=reasons,
            category_id=item.category_id,
            supplier_id=item.supplier_id,
            status=item.status,
            attributes=item.attributes,
            baseline_score=retrieval_only_score,
            retrieval_score=retrieval_only_score,
            retrieval_reasons=list(dict.fromkeys(retrieval_reasons or [])),
            retrieval_channel_scores=dict(retrieval_channel_scores or {}),
            retrieval_channel_ranks=dict(retrieval_channel_ranks or {}),
            retrieval_features=dict(structured_features),
        )

    if normalized_query:
        if normalized_query == title:
            lexical_score += 0.75
            reasons.append("exact_title_match")
        elif title.startswith(normalized_query):
            lexical_score += 0.6
            reasons.append("prefix_title_match")
        elif normalized_query in title:
            lexical_score += 0.45
            reasons.append("partial_title_match")
        elif normalized_query in description:
            lexical_score += 0.22
            reasons.append("description_match")
        else:
            fuzzy_score = SequenceMatcher(None, normalized_query, title).ratio()
            if fuzzy_score >= 0.45:
                lexical_score += round(fuzzy_score * 0.25, 4)
                reasons.append("fuzzy_title_match")

    token_matches = sum(
        1
        for token in query_tokens
        if token in title
        or token in description
        or token in attributes_blob
        or any(word.startswith(token) for word in title.split())
    )
    if token_matches:
        lexical_score += min(token_matches * 0.08, 0.24)
        reasons.append("token_match")

    attribute_overlap = structured_features.get("attribute_overlap_count", 0.0)
    if attribute_overlap:
        lexical_score += min(float(attribute_overlap) * 0.035, 0.14)
        reasons.append("attribute_match")

    if structured_features.get("brand_match_flag"):
        lexical_score += 0.08
        reasons.append("brand_match")

    if structured_features.get("numeric_constraint_match_flag"):
        lexical_score += 0.1
        reasons.append("numeric_constraint_match")

    if structured_features.get("category_match_flag"):
        lexical_score += 0.06
        reasons.append("category_match")

    if retrieval_score > 0:
        lexical_score += min(retrieval_score * 0.55, 0.55)
        reasons.extend(retrieval_reasons or ["hybrid_retrieval"])

    if item.category_name in profile.top_categories:
        lexical_score += 0.2
        reasons.append("matches_purchase_history")

    if item.id in profile.recent_ste_ids:
        lexical_score += 0.15
        reasons.append("recent_interaction")

    if item.supplier_name in profile.top_suppliers:
        lexical_score += 0.1
        reasons.append("popular_supplier")

    if item.id in profile.popular_ste_ids:
        lexical_score += 0.08
        reasons.append("popular_in_organization")

    return CandidateItem(
        id=item.id,
        title=item.title,
        category=item.category_name,
        supplier=item.supplier_name,
        description=item.description,
        score=round(lexical_score, 4),
        reasons=list(dict.fromkeys(reasons or ["baseline_retrieval"])),
        category_id=item.category_id,
        supplier_id=item.supplier_id,
        status=item.status,
        attributes=item.attributes,
        baseline_score=round(lexical_score, 4),
        retrieval_score=round(retrieval_score, 4),
        retrieval_reasons=list(dict.fromkeys(retrieval_reasons or [])),
        retrieval_channel_scores=dict(retrieval_channel_scores or {}),
        retrieval_channel_ranks=dict(retrieval_channel_ranks or {}),
        retrieval_features=dict(structured_features),
    )
