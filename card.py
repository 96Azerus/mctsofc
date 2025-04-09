# card.py
"""
Определяет класс Card, наследуя от phevaluator.Card для совместимости,
и добавляет необходимые методы и атрибуты для игры.
"""
from phevaluator import Card as PhevaluatorCard
from phevaluator import evaluate_cards as evaluate_cards_phevaluator # Импортируем функцию оценки

class Card(PhevaluatorCard):
    """
    Расширяет phevaluator.Card, добавляя числовые ранги и сравнение.
    """
    # Ace high, T=10, J=11, Q=12, K=13, A=14
    RANK_ORDER_MAP = {r: i + 2 for i, r in enumerate('23456789')}
    RANK_ORDER_MAP.update({'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14})
    SUIT_ORDER_MAP = {'c': 0, 'd': 1, 'h': 2, 's': 3} # clubs, diamonds, hearts, spades

    @property
    def int_rank(self) -> int:
        """Возвращает числовой ранг карты (2=2, ..., A=14)."""
        return self.RANK_ORDER_MAP[self.rank]

    @property
    def int_suit(self) -> int:
        """Возвращает числовой индекс масти (0-3)."""
        return self.SUIT_ORDER_MAP[self.suit]

    # Переопределяем сравнение для согласованности (ранг > масть)
    def __lt__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        if self.int_rank != other.int_rank:
            return self.int_rank < other.int_rank
        return self.int_suit < other.int_suit

    def __repr__(self):
        # Используем стандартное представление phevaluator
        return f'Card("{self.rank}{self.suit}")'

    def __str__(self):
        # Возвращает стандартное строковое представление, например, "As", "Td", "7c"
        return f"{self.rank}{self.suit}"

    # Используем стандартный __hash__ от phevaluator.Card (основан на int id)
    def __hash__(self):
        return super().__hash__()

    # Используем стандартный __eq__ от phevaluator.Card (основан на int id)
    def __eq__(self, other):
        return super().__eq__(other)


def card_from_str(s: str) -> Card:
    """Создает карту из строки."""
    if len(s) != 2:
        raise ValueError(f"Invalid card string: '{s}'")
    return Card(s)

def card_to_str(c: Optional[Card]) -> str:
    """Конвертирует карту в строку или '__' если None."""
    return str(c) if c else "__"

# Переименовываем импортированную функцию для ясности
evaluate_hand = evaluate_cards_phevaluator
