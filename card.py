# card.py
"""
Определяет класс Card, наследуя от phevaluator.Card для совместимости,
и добавляет необходимые методы и атрибуты для игры.
"""
from typing import Optional # <--- ДОБАВЛЕН ЭТОТ ИМПОРТ
from phevaluator import Card as PhevaluatorCard
from phevaluator import evaluate_cards as evaluate_cards_phevaluator

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
        # Добавим проверку на случай неинициализированного объекта
        if not hasattr(self, 'rank') or self.rank not in self.RANK_ORDER_MAP:
             # В идеале здесь должна быть ошибка, но для совместимости вернем 0
             print(f"Warning: Card object missing or invalid rank: {getattr(self, 'rank', 'N/A')}")
             return 0
        return self.RANK_ORDER_MAP[self.rank]

    @property
    def int_suit(self) -> int:
        """Возвращает числовой индекс масти (0-3)."""
        if not hasattr(self, 'suit') or self.suit not in self.SUIT_ORDER_MAP:
             print(f"Warning: Card object missing or invalid suit: {getattr(self, 'suit', 'N/A')}")
             return -1 # Или другое значение по умолчанию
        return self.SUIT_ORDER_MAP[self.suit]

    # Переопределяем сравнение для согласованности (ранг > масть)
    def __lt__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        # Используем свойства int_rank и int_suit для безопасного сравнения
        if self.int_rank != other.int_rank:
            return self.int_rank < other.int_rank
        return self.int_suit < other.int_suit

    def __repr__(self):
        # Используем стандартное представление phevaluator
        # Добавим проверку для надежности
        if hasattr(self, 'rank') and hasattr(self, 'suit'):
             return f'Card("{self.rank}{self.suit}")'
        else:
             return 'Card("Invalid")'


    def __str__(self):
        # Возвращает стандартное строковое представление, например, "As", "Td", "7c"
        # Убедимся, что rank и suit существуют перед форматированием
        if hasattr(self, 'rank') and hasattr(self, 'suit'):
             # Убедимся, что rank и suit не None
             rank = self.rank if self.rank is not None else '?'
             suit = self.suit if self.suit is not None else '?'
             return f"{rank}{suit}"
        else:
             # Возвращаем что-то осмысленное или вызываем ошибку, если объект не инициализирован
             return "InvalidCard"

    # Используем стандартный __hash__ от phevaluator.Card (основан на int id)
    # Он должен быть стабильным, если объект Card создан корректно
    def __hash__(self):
        return super().__hash__()

    # Используем стандартный __eq__ от phevaluator.Card (основан на int id)
    def __eq__(self, other):
        # Добавим проверку типа для надежности
        if not isinstance(other, Card):
             return NotImplemented
        return super().__eq__(other)


def card_from_str(s: str) -> Card:
    """Создает карту из строки."""
    if not isinstance(s, str) or len(s) != 2:
        raise ValueError(f"Invalid card string format: '{s}'")
    # Приводим к стандартному виду для phevaluator (e.g., 'Ah', 'Td', '7c')
    rank_char = s[0].upper()
    suit_char = s[1].lower()
    standard_str = rank_char + suit_char

    # Проверяем корректность ранга и масти перед созданием
    rank_lookup = rank_char if rank_char not in 'TJQKA' else rank_char # Используем T, J, Q, K, A
    if rank_lookup not in Card.RANK_ORDER_MAP or suit_char not in Card.SUIT_ORDER_MAP:
         raise ValueError(f"Invalid rank or suit in card string: '{s}'")

    try:
        # phevaluator ожидает строку типа 'Ah', 'Td', '7c'
        return Card(standard_str)
    except Exception as e:
        # Ловим возможные ошибки при создании Card из phevaluator
        raise ValueError(f"Failed to create Card from string '{s}': {e}")


def card_to_str(c: Optional[Card]) -> str:
    """Конвертирует карту в строку или '__' если None."""
    # Используем __str__ нашего класса Card, который включает проверки
    return str(c) if c else "__"

# Переименовываем импортированную функцию для ясности
evaluate_hand = evaluate_cards_phevaluator
