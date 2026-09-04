"""Агрегаты и ранжирование межгруппового разнообразия scheduled exchange."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field


Pair = tuple[str, str]
PairScore = tuple[int, int, int, int, int]


@dataclass
class ExchangeDiversity:
    """Сводка одного решения; не хранит тексты или состояние между вызовами."""

    other_pairs: Counter[Pair] = field(default_factory=Counter)
    other_bots: Counter[str] = field(default_factory=Counter)
    all_bots: Counter[str] = field(default_factory=Counter)
    initiators: Counter[str] = field(default_factory=Counter)
    responders: Counter[str] = field(default_factory=Counter)
    other_topics: Counter[str] = field(default_factory=Counter)
    other_scenarios: Counter[str] = field(default_factory=Counter)

    @classmethod
    def from_records(
        cls, records: list[dict[str, object]], *, group_id: str | None, group_chat_id: int | None,
    ) -> "ExchangeDiversity":
        """Сопоставляет реальные chat id, используя group id только для legacy-записей."""
        result = cls()
        for row in records:
            chat_id = row.get("group_chat_id")
            if chat_id is not None and group_chat_id is not None:
                same_group = chat_id == group_chat_id
            else:
                same_group = group_id is not None and row.get("group_id") == group_id
            a, b = row.get("initiator_bot_id"), row.get("responder_bot_id")
            for bot_id, roles in ((a, result.initiators), (b, result.responders)):
                if isinstance(bot_id, str):
                    roles[bot_id] += 1
                    result.all_bots[bot_id] += 1
                    if not same_group:
                        result.other_bots[bot_id] += 1
            if same_group:
                continue
            if isinstance(a, str) and isinstance(b, str):
                result.other_pairs[tuple(sorted((a, b)))] += 1
            for key, counter in (("topic_key", result.other_topics), ("important_scenario", result.other_scenarios)):
                value = row.get(key)
                if isinstance(value, str):
                    counter[value] += 1
        return result

    def best_pairs(self, pairs: Iterable[Pair], recent_bot_ids: list[str]) -> tuple[list[Pair], PairScore | None]:
        """Ранжирует пары без запросов к БД; порядок критериев задаёт приоритеты fallback."""
        first_positions = {}
        for index, bot_id in enumerate(recent_bot_ids):
            first_positions.setdefault(bot_id, index)
        size = len(recent_bot_ids)
        best: list[Pair] = []
        best_score: PairScore | None = None
        for a, b in pairs:
            score = (
                self.other_pairs[tuple(sorted((a, b)))],
                size - min(first_positions.get(a, size), first_positions.get(b, size)),
                self.other_bots[a] + self.other_bots[b],
                self.all_bots[a] + self.all_bots[b],
                self.initiators[a] + self.responders[b],
            )
            if best_score is None or score < best_score:
                best, best_score = [(a, b)], score
            elif score == best_score:
                best.append((a, b))
        return best, best_score
