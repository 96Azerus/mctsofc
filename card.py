# card.py
"""
Определяет класс Card, наследуя от phevaluator.Card для совместимости,
и добавляет необходимые методы и атрибуты для игры.
"""
import sys # Добавлено для flush
from typing import Optional
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
        if not hasattr(self, 'rank') or self.rank not in self.RANK_ORDER_MAP:
             print(f"Warning: Card object missing or invalid rank: {getattr(self, 'rank', 'N/A')}")
             return 0
        return self.RANK_ORDER_MAP[self.rank]

    @property
    def int_suit(self) -> int:
        """Возвращает числовой индекс масти (0-3)."""
        if not hasattr(self, 'suit') or self.suit not in self.SUIT_ORDER_MAP:
             print(f"Warning: Card object missing or invalid suit: {getattr(self, 'suit', 'N/A')}")
             return -1
        return self.SUIT_ORDER_MAP[self.suit]

    def __lt__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        if self.int_rank != other.int_rank:
            return self.int_rank < other.int_rank
        return self.int_suit < other.int_suit

    def __repr__(self):
        if hasattr(self, 'rank') and hasattr(self, 'suit'):
             return f'Card("{self.rank}{self.suit}")'
        else:
             return 'Card("Invalid")'

    def __str__(self):
        # Возвращает стандартное строковое представление, например, "As", "Td", "7c"
        if hasattr(self, 'rank') and hasattr(self, 'suit') and self.rank is not None and self.suit is not None:
             return f"{self.rank}{self.suit}"
        else:
             # --- ДОБАВЛЕНО ЛОГИРОВАНИЕ ---
             print(f"DEBUG Card.__str__: Returning 'InvalidCard'. Rank={getattr(self, 'rank', 'N/A')}, Suit={getattr(self, 'suit', 'N/A')}")
             sys.stdout.flush(); sys.stderr.flush()
             # -----------------------------
             return "InvalidCard"

    def __hash__(self):
        return super().__hash__()

    def __eq__(self, other):
        if not isinstance(other, Card):
             return NotImplemented
        return super().__eq__(other)


def card_from_str(s: str) -> Card:
    """Создает карту из строки."""
    if not isinstance(s, str) or len(s) != 2:
        raise ValueError(f"Invalid card string format: '{s}'")
    rank_char = s[0].upper()
    suit_char = s[1].lower()
    standard_str = rank_char + suit_char
    rank_lookup = rank_char
    if rank_lookup not in Card.RANK_ORDER_MAP or suit_char not in Card.SUIT_ORDER_MAP:
         raise ValueError(f"Invalid rank or suit in card string: '{s}'")
    try:
        return Card(standard_str)
    except Exception as e:
        raise ValueError(f"Failed to create Card from string '{s}': {e}")


def card_to_str(c: Optional[Card]) -> str:
    """Конвертирует карту в строку или '__' если None."""
    return str(c) if c else "__"

evaluate_hand = evaluate_cards_phevaluator
