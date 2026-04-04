from app.core.config import settings
from app.domain.catalog.service import CatalogService
from app.domain.events.service import EventService
from app.domain.personalization.service import PersonalizationService
from app.domain.search.normalizer import (
    correct_query,
    correct_query_fuzzy,
    correct_keyboard_layout,
    expand_fuzzy_term_variants,
    expand_term_variants,
    extract_query_terms,
    lemmatize_query_terms,
    normalize_query,
)
from app.domain.search.query_analysis import analyze_search_text
from app.domain.search.ranking import build_candidate
from app.domain.search.schemas import (
    CurrentActor,
    SearchHistoryResponse,
    SearchMeta,
    SearchRequest,
    SearchResponse,
    SearchSuggestion,
    SearchSuggestionsMeta,
    SearchSessionRead,
    SearchSuggestionsResponse,
    SpellcheckResponse,
)
from app.db.repositories.search import SearchRepository
from app.integrations.ml.base import RankingProvider, RankingQueryContext, RankingRequest


class SearchService:
    def __init__(
        self,
        catalog_service: CatalogService,
        event_service: EventService,
        personalization_service: PersonalizationService,
        search_repository: SearchRepository,
        ranking_provider: RankingProvider,
    ) -> None:
        self.catalog_service = catalog_service
        self.event_service = event_service
        self.personalization_service = personalization_service
        self.search_repository = search_repository
        self.ranking_provider = ranking_provider

    def _get_profile_for_actor(self, actor: CurrentActor):
        if not actor.personalization_enabled:
            return self.personalization_service.get_search_profile(
                user_id="",
                organization_id="",
            )

        return self.personalization_service.get_search_profile(
            user_id=actor.user_id,
            organization_id=actor.organization_id,
        )

    def _build_fuzzy_retrieval_terms(
        self,
        *,
        base_terms: list[str],
        blocked_terms: list[str],
    ) -> list[str]:
        if not base_terms:
            return []

        search_vocabulary = self.search_repository.get_search_vocabulary()
        fuzzy_terms = expand_fuzzy_term_variants(base_terms, search_vocabulary)
        expanded_fuzzy_terms = expand_term_variants(fuzzy_terms)
        blocked = set(blocked_terms)

        return list(
            dict.fromkeys(
                term
                for term in [*fuzzy_terms, *expanded_fuzzy_terms]
                if term and term not in blocked
            )
        )

    @staticmethod
    def _build_semantic_query_texts(
        *values: str,
        extra_values: list[str] | None = None,
    ) -> list[str]:
        semantic_texts = [value for value in values if value]
        semantic_texts.extend(extra_values or [])
        return list(dict.fromkeys(text for text in semantic_texts if text))

    @staticmethod
    def _build_morphology_terms(*term_groups: list[str]) -> list[str]:
        terms: list[str] = []
        for values in term_groups:
            terms.extend(lemmatize_query_terms(values))
        return list(dict.fromkeys(term for term in terms if term))

    def _resolve_query(self, query: str) -> tuple[str, str | None, str]:
        normalized_query = normalize_query(query)
        search_vocabulary = self.search_repository.get_search_vocabulary()

        spell_corrections = self.search_repository.get_spell_corrections(normalized_query)
        spell_corrected_query = correct_query(normalized_query, spell_corrections)
        fuzzy_corrected_query = (
            None
            if spell_corrected_query
            else correct_query_fuzzy(normalized_query, search_vocabulary)
        )

        layout_corrected_query = correct_keyboard_layout(normalized_query)
        layout_spell_corrected_query = None
        layout_fuzzy_corrected_query = None
        if layout_corrected_query and not spell_corrected_query and not fuzzy_corrected_query:
            layout_spell_corrections = self.search_repository.get_spell_corrections(
                layout_corrected_query
            )
            layout_spell_corrected_query = correct_query(
                layout_corrected_query,
                layout_spell_corrections,
            )
            layout_fuzzy_corrected_query = (
                layout_spell_corrected_query
                or correct_query_fuzzy(layout_corrected_query, search_vocabulary)
            )

        corrected_query = (
            spell_corrected_query
            or fuzzy_corrected_query
            or layout_spell_corrected_query
            or layout_fuzzy_corrected_query
            or layout_corrected_query
        )

        correction_type = (
            "spellcheck"
            if spell_corrected_query
            else "fuzzy_spellcheck"
            if fuzzy_corrected_query
            else "keyboard_layout_spellcheck"
            if layout_spell_corrected_query or layout_fuzzy_corrected_query
            else "keyboard_layout"
            if layout_corrected_query
            else "none"
        )

        return normalized_query, corrected_query, correction_type

    @staticmethod
    def _build_explanations(
        *,
        corrected_query: str | None,
        normalized_query: str,
        applied_synonyms: list[str],
        profile,
    ) -> list[str]:
        explanations: list[str] = []

        if corrected_query and corrected_query != normalized_query:
            explanations.append(
                f'Запрос скорректирован до "{corrected_query}" для более точного поиска'
            )

        if applied_synonyms:
            explanations.append(
                f"Учтены синонимы: {', '.join(applied_synonyms[:3])}"
            )

        explanations.extend(profile.active_signals)

        if profile.top_categories:
            explanations.append(
                f"В приоритете категории из вашего контекста: {', '.join(profile.top_categories[:2])}"
            )

        return explanations[:4]

    def search(
        self,
        payload: SearchRequest,
        actor: CurrentActor,
    ) -> SearchResponse:
        normalized_query, corrected_query, correction_type = self._resolve_query(payload.query)
        effective_query = corrected_query or normalized_query
        structured_query = analyze_search_text(effective_query)
        original_query_terms = extract_query_terms(normalized_query)
        query_terms = extract_query_terms(effective_query)
        expanded_query_terms = expand_term_variants(query_terms)
        expanded_original_query_terms = (
            []
            if original_query_terms == query_terms
            else expand_term_variants(original_query_terms)
        )
        synonym_lookup_terms = list(
            dict.fromkeys(
                [
                    *original_query_terms,
                    *query_terms,
                    *expanded_original_query_terms,
                    *expanded_query_terms,
                ]
            )
        )
        synonym_expansions = self.search_repository.get_synonym_expansions(synonym_lookup_terms)
        applied_synonyms = list(
            dict.fromkeys(item.synonym for item in synonym_expansions if item.synonym)
        )
        synonym_terms: list[str] = []
        for synonym in applied_synonyms:
            synonym_terms.extend(expand_term_variants(extract_query_terms(synonym)))
        synonym_sources = {
            item.synonym: item.source
            for item in synonym_expansions
            if item.synonym
        }
        synonym_confidence = {
            item.synonym: item.weight
            for item in synonym_expansions
            if item.synonym
        }
        search_terms = list(
            dict.fromkeys(
                [
                    normalized_query,
                    effective_query,
                    *original_query_terms,
                    *query_terms,
                    *expanded_original_query_terms,
                    *expanded_query_terms,
                ]
            )
        )
        morphology_query_terms = self._build_morphology_terms(
            original_query_terms,
            query_terms,
            expanded_original_query_terms,
            expanded_query_terms,
            structured_query.category_hints,
            structured_query.attribute_terms,
        )
        synonym_query_terms = list(dict.fromkeys([*applied_synonyms, *synonym_terms]))
        fuzzy_search_terms = self._build_fuzzy_retrieval_terms(
            base_terms=[
                *original_query_terms,
                *query_terms,
                *expanded_original_query_terms,
                *expanded_query_terms,
            ],
            blocked_terms=search_terms,
        )
        semantic_query_texts = self._build_semantic_query_texts(
            effective_query,
            normalized_query,
            extra_values=applied_synonyms,
        )
        ranking_query_terms = list(
            dict.fromkeys([*expanded_query_terms, *morphology_query_terms, *synonym_terms])
        )

        profile = self._get_profile_for_actor(actor)

        session = self.search_repository.create_session(
            user_id=actor.user_id,
            organization_id=actor.organization_id,
            query=payload.query,
            normalized_query=effective_query,
        )
        self.event_service.create_system_event(
            session_id=session.id,
            user_id=actor.user_id,
            organization_id=actor.organization_id,
            role=actor.role,
            event_type="search_submitted",
            payload={
                "query": payload.query,
                "normalized_query": effective_query,
                "corrected_query": corrected_query or "",
                "correction_type": correction_type,
                "synonyms_count": len(applied_synonyms),
            },
        )
        items = self.catalog_service.search_ste_candidates(
            query_terms=search_terms,
            morphology_query_terms=morphology_query_terms,
            fuzzy_query_terms=fuzzy_search_terms,
            synonym_query_terms=synonym_query_terms,
            semantic_query_texts=semantic_query_texts,
            structured_query=structured_query,
            strict_match=payload.filters.strict_match,
            category_id=payload.filters.category_id,
            supplier_id=payload.filters.supplier_id,
        )
        candidates = [
            build_candidate(
                item=item,
                normalized_query=effective_query,
                profile=profile,
                query_terms=ranking_query_terms,
                retrieval_score=item.retrieval_score,
                retrieval_reasons=item.retrieval_reasons,
                retrieval_channel_scores=item.retrieval_channel_scores,
                retrieval_channel_ranks=item.retrieval_channel_ranks,
                retrieval_features=item.retrieval_features,
            )
            for item in items
        ]

        candidates = [candidate for candidate in candidates if candidate.score > 0]
        ranked_items = self.ranking_provider.rank(
            RankingRequest(
                query=RankingQueryContext(
                    original=payload.query,
                    normalized=normalized_query,
                    corrected=corrected_query,
                    applied_synonyms=applied_synonyms,
                ),
                actor=actor,
                profile=profile,
                candidates=candidates,
            )
        )

        return SearchResponse(
            items=ranked_items,
            meta=SearchMeta(
                session_id=session.id,
                query=payload.query,
                normalized_query=normalized_query,
                corrected_query=corrected_query,
                applied_synonyms=applied_synonyms,
                synonym_sources=synonym_sources,
                synonym_confidence=synonym_confidence,
                explanations=self._build_explanations(
                    corrected_query=corrected_query,
                    normalized_query=normalized_query,
                    applied_synonyms=applied_synonyms,
                    profile=profile,
                ),
                ranking_mode=settings.ranking_mode,
            ),
        )

    def get_suggestions(
        self,
        query: str,
        actor: CurrentActor,
    ) -> SearchSuggestionsResponse:
        normalized_query, corrected_query, correction_type = self._resolve_query(query)
        effective_query = corrected_query or normalized_query
        structured_query = analyze_search_text(effective_query)
        profile = self._get_profile_for_actor(actor)

        suggestions: list[SearchSuggestion] = []

        if effective_query:
            suggestions.extend(
                [
                    SearchSuggestion(
                        label=item,
                        type="history",
                        group="history",
                        description="Из истории запросов",
                    )
                    for item in profile.popular_queries
                    if effective_query in item
                ]
            )

            suggestions.extend(
                [
                    SearchSuggestion(
                        label=item.name,
                        type="category",
                        group="categories",
                        description="Категория",
                    )
                    for item in self.catalog_service.list_categories()
                    if effective_query in item.name.lower()
                ][:3]
            )

            original_product_terms = extract_query_terms(normalized_query)
            product_terms = extract_query_terms(effective_query)
            expanded_original_product_terms = (
                []
                if original_product_terms == product_terms
                else expand_term_variants(original_product_terms)
            )
            expanded_product_terms = expand_term_variants(product_terms)
            product_synonym_lookup_terms = list(
                dict.fromkeys(
                    [
                        *original_product_terms,
                        *product_terms,
                        *expanded_original_product_terms,
                        *expanded_product_terms,
                    ]
                )
            )
            product_synonym_expansions = self.search_repository.get_synonym_expansions(
                product_synonym_lookup_terms
            )
            product_applied_synonyms = list(
                dict.fromkeys(
                    item.synonym for item in product_synonym_expansions if item.synonym
                )
            )
            product_synonym_terms: list[str] = []
            for synonym in product_applied_synonyms:
                product_synonym_terms.extend(
                    expand_term_variants(extract_query_terms(synonym))
                )
            morphology_product_terms = self._build_morphology_terms(
                original_product_terms,
                product_terms,
                expanded_original_product_terms,
                expanded_product_terms,
                structured_query.category_hints,
                structured_query.attribute_terms,
            )
            fuzzy_product_terms = self._build_fuzzy_retrieval_terms(
                base_terms=[
                    *original_product_terms,
                    *product_terms,
                    *expanded_original_product_terms,
                    *expanded_product_terms,
                ],
                blocked_terms=[
                    normalized_query,
                    effective_query,
                    *original_product_terms,
                    *product_terms,
                    *expanded_original_product_terms,
                    *expanded_product_terms,
                ],
            )
            product_candidates = self.catalog_service.search_ste_items(
                query_terms=[
                    normalized_query,
                    effective_query,
                    *original_product_terms,
                    *product_terms,
                    *expanded_original_product_terms,
                    *expanded_product_terms,
                ],
                morphology_query_terms=morphology_product_terms,
                fuzzy_query_terms=fuzzy_product_terms,
                synonym_query_terms=[
                    *product_applied_synonyms,
                    *product_synonym_terms,
                ],
                semantic_query_texts=self._build_semantic_query_texts(
                    effective_query,
                    normalized_query,
                    extra_values=product_applied_synonyms,
                ),
                structured_query=structured_query,
                strict_match=False,
            )
            suggestions.extend(
                [
                    SearchSuggestion(
                        label=item.title,
                        type="product",
                        group="products",
                        description=item.category_name,
                    )
                    for item in product_candidates[:5]
                ]
            )
        else:
            suggestions.extend(
                [
                    SearchSuggestion(
                        label=item,
                        type="history",
                        group="history",
                        description="Из истории запросов",
                    )
                    for item in profile.popular_queries[:6]
                ]
            )

        deduplicated: list[SearchSuggestion] = []
        seen_labels: set[tuple[str, str]] = set()
        for item in suggestions:
            key = (item.group, item.label)
            if key in seen_labels:
                continue
            seen_labels.add(key)
            deduplicated.append(item)

        return SearchSuggestionsResponse(
            items=deduplicated[:8],
            meta=SearchSuggestionsMeta(
                query=query,
                normalized_query=normalized_query,
                effective_query=effective_query,
                corrected_query=corrected_query,
                correction_type=correction_type,
            ),
        )

    def get_spellcheck(self, query: str) -> SpellcheckResponse:
        normalized_query, corrected_query, _ = self._resolve_query(query)
        return SpellcheckResponse(
            original_query=query,
            corrected_query=corrected_query or correct_keyboard_layout(normalized_query),
        )

    def get_history(
        self,
        actor: CurrentActor,
        limit: int = 20,
    ) -> SearchHistoryResponse:
        if not actor.personalization_enabled:
            return SearchHistoryResponse(items=[])

        sessions = self.search_repository.list_sessions(
            user_id=actor.user_id,
            organization_id=actor.organization_id,
            limit=limit,
        )
        return SearchHistoryResponse(
            items=[
                SearchSessionRead(
                    id=item.id,
                    query=item.query,
                    normalized_query=item.normalized_query,
                    created_at=item.created_at,
                )
                for item in sessions
            ]
        )
