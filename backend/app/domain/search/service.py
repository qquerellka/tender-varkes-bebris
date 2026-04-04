from app.core.config import settings
from app.domain.catalog.service import CatalogService
from app.domain.events.schemas import SearchEventRead
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
    SearchActivityItemRead,
    SearchActivityResponse,
    SearchDebugCandidateRead,
    SearchDebugQueryRead,
    SearchDebugRankingRead,
    SearchDebugResponse,
    SearchDebugStructuredQueryRead,
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
    _activity_event_types = {
        "search_submitted",
        "search_results_rendered",
        "suggestion_clicked",
        "result_clicked",
        "result_opened",
        "result_opened_new_tab",
        "item_copy",
        "favorite_added",
        "favorite_removed",
        "comparison_added",
        "comparison_removed",
        "cart_added",
        "cart_removed",
        "cart_quantity_changed",
        "filter_applied",
        "filter_removed",
        "filters_cleared",
        "sort_changed",
        "purchase_completed",
        "search_refined",
        "purchase_intent",
        "irrelevant_marked",
    }

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

    def _release_read_connection(self) -> None:
        try:
            self.search_repository.session.rollback()
        except Exception:
            pass

    @staticmethod
    def _format_query_label(query: str | None) -> str:
        return f"«{query}»" if query else "без запроса"

    @staticmethod
    def _stringify_payload_value(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "включено" if value else "выключено"
        return str(value)

    def _build_activity_item(
        self,
        *,
        event: SearchEventRead,
        session_queries: dict[str, str],
        ste_titles: dict[str, str | None],
    ) -> SearchActivityItemRead | None:
        if event.event_type not in self._activity_event_types:
            return None

        query = event.query_text or event.normalized_query or session_queries.get(event.session_id)
        ste_title = ste_titles.get(event.ste_id) if event.ste_id else None
        subject = ste_title or event.ste_id or "позиция"
        payload = event.payload or {}

        title = "Недавнее действие"
        description = "Действие зафиксировано в поисковой сессии пользователя."

        if event.event_type == "search_submitted":
            title = f"Новый запрос {self._format_query_label(query)}"
            description = "Создана поисковая сессия и сохранен исходный поисковый запрос."
        elif event.event_type == "search_results_rendered":
            title = f"Получена выдача по запросу {self._format_query_label(query)}"
            results_count = payload.get("results_count")
            if results_count is not None:
                description = f"В каталоге отрисовано {results_count} результатов для этого сценария."
            else:
                description = "Результаты поиска отрисованы в каталоге."
        elif event.event_type == "search_refined":
            next_query = self._stringify_payload_value(payload.get("next_query")) or query or "новый запрос"
            title = "Запрос уточнен"
            description = (
                f"Пользователь перешел от {self._format_query_label(query)} "
                f"к {self._format_query_label(next_query)}."
            )
        elif event.event_type == "suggestion_clicked":
            label = self._stringify_payload_value(payload.get("label")) or query or "подсказка"
            source = self._stringify_payload_value(payload.get("source"))
            title = f"Выбрана подсказка {self._format_query_label(label)}"
            description = (
                f"Подсказка использована из блока {source}." if source else "Подсказка применена к поиску."
            )
        elif event.event_type == "result_clicked":
            title = f"Открыт результат: {subject}"
            description = (
                f"Пользователь перешел к карточке из выдачи по запросу {self._format_query_label(query)}."
                if query
                else "Пользователь открыл карточку из поисковой выдачи."
            )
        elif event.event_type == "result_opened":
            title = f"Карточка просмотрена: {subject}"
            description = "Позиция открыта в основном потоке просмотра каталога."
        elif event.event_type == "result_opened_new_tab":
            title = f"Карточка открыта в новой вкладке: {subject}"
            description = "Пользователь сохранил контекст выдачи и открыл позицию параллельно."
        elif event.event_type == "item_copy":
            copied_text = self._stringify_payload_value(payload.get("copied_text"))
            title = f"Скопирован фрагмент карточки: {subject}"
            description = (
                f"С карточки скопирован текст: {copied_text}." if copied_text else "Пользователь скопировал часть описания позиции."
            )
        elif event.event_type == "favorite_added":
            title = f"Добавлено в избранное: {subject}"
            description = "Позиция закреплена в shortlist пользователя."
        elif event.event_type == "favorite_removed":
            title = f"Убрано из избранного: {subject}"
            description = "Позиция больше не считается приоритетной в shortlist."
        elif event.event_type == "comparison_added":
            title = f"Добавлено в сравнение: {subject}"
            description = "Позиция отправлена в compare-flow для сопоставления с альтернативами."
        elif event.event_type == "comparison_removed":
            title = f"Убрано из сравнения: {subject}"
            description = "Позиция исключена из текущего compare-flow."
        elif event.event_type == "cart_added":
            quantity = self._stringify_payload_value(payload.get("quantity")) or "1"
            title = f"Добавлено в корзину: {subject}"
            description = f"Позиция вошла в закупочный черновик с количеством {quantity}."
        elif event.event_type == "cart_removed":
            title = f"Удалено из корзины: {subject}"
            description = "Позиция удалена из закупочного черновика."
        elif event.event_type == "cart_quantity_changed":
            quantity = self._stringify_payload_value(payload.get("quantity")) or "1"
            title = f"Изменено количество в корзине: {subject}"
            description = f"В закупочном черновике установлено количество {quantity}."
        elif event.event_type == "filter_applied":
            filter_name = self._stringify_payload_value(payload.get("filter_name")) or "фильтр"
            filter_value = self._stringify_payload_value(payload.get("filter_value")) or "значение"
            title = "Применен фильтр"
            description = f"Фильтр {filter_name} установлен в значение {self._format_query_label(filter_value)}."
        elif event.event_type == "filter_removed":
            filter_name = self._stringify_payload_value(payload.get("filter_name")) or "фильтр"
            filter_value = self._stringify_payload_value(payload.get("filter_value"))
            title = "Фильтр снят"
            description = (
                f"Убран фильтр {filter_name} со значением {self._format_query_label(filter_value)}."
                if filter_value
                else f"Убран фильтр {filter_name}."
            )
        elif event.event_type == "filters_cleared":
            title = "Фильтры очищены"
            description = "Пользователь вернулся к более широкому просмотру каталога без ограничений."
        elif event.event_type == "sort_changed":
            sort_mode = self._stringify_payload_value(payload.get("sort_mode")) or "relevance"
            title = "Изменен режим сортировки"
            description = f"Каталог переключен в режим сортировки {self._format_query_label(sort_mode)}."
        elif event.event_type == "purchase_intent":
            items_count = self._stringify_payload_value(payload.get("items_count")) or "0"
            title = "Подготовлен закупочный черновик"
            description = f"Пользователь перешел к оформлению черновика, позиций в подборке: {items_count}."
        elif event.event_type == "purchase_completed":
            quantity = self._stringify_payload_value(payload.get("quantity")) or "1"
            title = f"Оформлена закупка: {subject}"
            description = f"Позиция оформлена как закупка с количеством {quantity}."
        elif event.event_type == "irrelevant_marked":
            title = f"Позиция отмечена как нерелевантная: {subject}"
            description = "Система получила негативный сигнал по этой карточке."

        return SearchActivityItemRead(
            id=event.id,
            session_id=event.session_id,
            event_type=event.event_type,
            title=title,
            description=description,
            ste_id=event.ste_id,
            ste_title=ste_title,
            page_type=event.page_type,
            query=query,
            created_at=event.created_at,
        )

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

    @staticmethod
    def _serialize_structured_query(structured_query) -> SearchDebugStructuredQueryRead:
        return SearchDebugStructuredQueryRead(
            normalized_text=structured_query.normalized_text,
            text_terms=structured_query.text_terms,
            lemma_terms=structured_query.lemma_terms,
            brand_terms=structured_query.brand_terms,
            model_terms=structured_query.model_terms,
            code_terms=structured_query.code_terms,
            numeric_terms=structured_query.numeric_terms,
            unit_terms=structured_query.unit_terms,
            size_terms=structured_query.size_terms,
            package_terms=structured_query.package_terms,
            color_terms=structured_query.color_terms,
            material_terms=structured_query.material_terms,
            category_hints=structured_query.category_hints,
            attribute_terms=structured_query.attribute_terms,
            quantity_constraints=[
                constraint.normalized for constraint in structured_query.quantity_constraints
            ],
            is_hard_query=structured_query.is_hard_query,
        )

    def _prepare_search_execution(
        self,
        payload: SearchRequest,
        actor: CurrentActor,
    ) -> dict:
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
        retrieval_only_mode = settings.ranking_mode.strip().lower() == "retrieval_only"
        profile = self._get_profile_for_actor(actor)

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
        raw_candidates_count = len(items)
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
                retrieval_only=retrieval_only_mode,
            )
            for item in items
        ]
        candidates = [candidate for candidate in candidates if candidate.score > 0]
        if retrieval_only_mode:
            ranked_items = sorted(candidates, key=lambda item: item.score, reverse=True)
        else:
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

        return {
            "normalized_query": normalized_query,
            "effective_query": effective_query,
            "corrected_query": corrected_query,
            "correction_type": correction_type,
            "structured_query": structured_query,
            "applied_synonyms": applied_synonyms,
            "synonym_sources": synonym_sources,
            "synonym_confidence": synonym_confidence,
            "search_terms": search_terms,
            "morphology_query_terms": morphology_query_terms,
            "synonym_query_terms": synonym_query_terms,
            "fuzzy_search_terms": fuzzy_search_terms,
            "semantic_query_texts": semantic_query_texts,
            "ranking_query_terms": ranking_query_terms,
            "profile": profile,
            "candidates": candidates,
            "ranked_items": ranked_items,
            "raw_candidates_count": raw_candidates_count,
        }

    def _build_fuzzy_retrieval_terms(
        self,
        *,
        base_terms: list[str],
        blocked_terms: list[str],
    ) -> list[str]:
        if not base_terms:
            return []

        search_vocabulary = self.search_repository.get_search_spell_vocabulary()
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
        search_vocabulary = self.search_repository.get_search_spell_vocabulary()

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
        prepared = self._prepare_search_execution(payload, actor)
        self._release_read_connection()

        session = self.search_repository.create_session(
            user_id=actor.user_id,
            organization_id=actor.organization_id,
            query=payload.query,
            normalized_query=prepared["effective_query"],
        )
        self.event_service.create_system_event(
            session_id=session.id,
            user_id=actor.user_id,
            organization_id=actor.organization_id,
            role=actor.role,
            event_type="search_submitted",
            payload={
                "query": payload.query,
                "normalized_query": prepared["effective_query"],
                "corrected_query": prepared["corrected_query"] or "",
                "correction_type": prepared["correction_type"],
                "synonyms_count": len(prepared["applied_synonyms"]),
            },
        )

        return SearchResponse(
            items=prepared["ranked_items"],
            meta=SearchMeta(
                session_id=session.id,
                query=payload.query,
                normalized_query=prepared["normalized_query"],
                corrected_query=prepared["corrected_query"],
                applied_synonyms=prepared["applied_synonyms"],
                synonym_sources=prepared["synonym_sources"],
                synonym_confidence=prepared["synonym_confidence"],
                explanations=self._build_explanations(
                    corrected_query=prepared["corrected_query"],
                    normalized_query=prepared["normalized_query"],
                    applied_synonyms=prepared["applied_synonyms"],
                    profile=prepared["profile"],
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

        self._release_read_connection()
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
        self._release_read_connection()
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

    def debug_search_ranking(
        self,
        payload: SearchRequest,
        actor: CurrentActor,
    ) -> SearchDebugResponse:
        prepared = self._prepare_search_execution(payload, actor)
        ranked_items = prepared["ranked_items"]
        baseline_candidates = prepared["candidates"]
        baseline_rank_by_id = {
            item.id: index for index, item in enumerate(baseline_candidates, start=1)
        }
        final_rank_by_id = {
            item.id: index for index, item in enumerate(ranked_items, start=1)
        }
        final_items_by_id = {item.id: item for item in ranked_items}
        provider_name = self.ranking_provider.__class__.__name__
        provider_mode = settings.ranking_provider
        provider_ready = bool(getattr(self.ranking_provider, "ready", True))
        model_type = getattr(self.ranking_provider, "model_type", None)
        ml_rerank_applied = any("ml_rerank" in item.reasons for item in ranked_items)

        candidates = [
            SearchDebugCandidateRead(
                id=item.id,
                title=item.title,
                category=item.category,
                supplier=item.supplier,
                category_id=item.category_id,
                supplier_id=item.supplier_id,
                status=item.status,
                baseline_score=item.baseline_score,
                retrieval_score=item.retrieval_score,
                final_score=final_items_by_id.get(item.id, item).score,
                score_delta=round(
                    float(final_items_by_id.get(item.id, item).score - item.baseline_score),
                    4,
                ),
                baseline_rank=baseline_rank_by_id[item.id],
                final_rank=final_rank_by_id.get(item.id, baseline_rank_by_id[item.id]),
                baseline_reasons=item.reasons,
                final_reasons=final_items_by_id.get(item.id, item).reasons,
                retrieval_reasons=item.retrieval_reasons,
                retrieval_channel_scores=item.retrieval_channel_scores,
                retrieval_channel_ranks=item.retrieval_channel_ranks,
                retrieval_features=item.retrieval_features,
            )
            for item in baseline_candidates
        ]
        candidates.sort(key=lambda item: item.final_rank)

        return SearchDebugResponse(
            query=SearchDebugQueryRead(
                original=payload.query,
                normalized=prepared["normalized_query"],
                effective=prepared["effective_query"],
                corrected=prepared["corrected_query"],
                correction_type=prepared["correction_type"],
                filters=payload.filters,
                applied_synonyms=prepared["applied_synonyms"],
                synonym_sources=prepared["synonym_sources"],
                synonym_confidence=prepared["synonym_confidence"],
                search_terms=prepared["search_terms"],
                morphology_terms=prepared["morphology_query_terms"],
                synonym_terms=prepared["synonym_query_terms"],
                fuzzy_terms=prepared["fuzzy_search_terms"],
                semantic_query_texts=prepared["semantic_query_texts"],
                ranking_query_terms=prepared["ranking_query_terms"],
                structured_query=self._serialize_structured_query(prepared["structured_query"]),
            ),
            profile=prepared["profile"],
            ranking=SearchDebugRankingRead(
                provider_name=provider_name,
                provider_mode=provider_mode,
                provider_ready=provider_ready,
                model_type=model_type,
                ml_rerank_applied=ml_rerank_applied,
                fallback_to_baseline=provider_mode != "noop" and not ml_rerank_applied,
                raw_candidates_count=prepared["raw_candidates_count"],
                scored_candidates_count=len(baseline_candidates),
            ),
            candidates=candidates,
        )

    def get_recent_activity(
        self,
        actor: CurrentActor,
        limit: int = 20,
    ) -> SearchActivityResponse:
        if not actor.personalization_enabled:
            return SearchActivityResponse(items=[])

        events = self.event_service.list_events(
            user_id=actor.user_id,
            limit=max(limit * 4, 40),
        ).items
        sessions = self.search_repository.list_sessions(
            user_id=actor.user_id,
            organization_id=actor.organization_id,
            limit=max(limit * 4, 40),
        )
        session_queries = {item.id: item.query for item in sessions}

        ste_ids = [event.ste_id for event in events if event.ste_id]
        ste_titles: dict[str, str | None] = {}
        for ste_id in dict.fromkeys(ste_ids):
            item = self.catalog_service.get_ste_by_id(ste_id)
            ste_titles[ste_id] = item.title if item else None

        activity_items: list[SearchActivityItemRead] = []
        for event in events:
            activity_item = self._build_activity_item(
                event=event,
                session_queries=session_queries,
                ste_titles=ste_titles,
            )
            if activity_item is None:
                continue
            activity_items.append(activity_item)
            if len(activity_items) >= limit:
                break

        return SearchActivityResponse(items=activity_items)
