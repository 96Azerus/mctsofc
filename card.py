# card.py
import sys
from typing import Optional
from phevaluator import Card as PhevaluatorCard
from phevaluator import evaluate_cards as evaluate_cards_phevaluator

class Card(PhevaluatorCard):
    RANK_ORDER_MAP = {r: i + 2 for i, r in enumerate('23456789')}
    RANK_ORDER_MAP.update({'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14})
    SUIT_ORDER_MAP = {'c': 0, 'd': 1, 'h': 2, 's': 3}

    # --- ДОБАВЛЕН ЯВНЫЙ КОНСТРУКТОР ---
    def __init__(self, card_str: str):
        try:
            # Вызываем конструктор базового класса phevaluator.Card
            super().__init__(card_str)
            # Проверяем сразу после инициализации базового класса
            if not hasattr(self, '_int_representation') or self._int_representation is None:
                 print(f"ERROR Card.__init__: super().__init__('{card_str}') did not set _int_representation!")
                 # Можно здесь вызвать исключение, чтобы остановить инициализацию Deck
                 # raise ValueError(f"Failed to initialize base Card for '{card_str}'")
        except Exception as e:
            print(f"ERROR Card.__init__: Exception during super().__init__('{card_str}'): {e}")
            # Перевызываем исключение, чтобы показать проблему
            raise e
    # ------------------------------------

    @property
    def int_rank(self) -> int:
        if not hasattr(self, 'rank') or self.rank not in self.RANK_ORDER_MAP:
             print(f"Warning: Card object missing or invalid rank: {getattr(self, 'rank', 'N/A')}")
             return 0
        return self.RANK_ORDER_MAP[self.rank]

    @property
    def int_suit(self) -> int:
        if not hasattr(self, 'suit') or self.suit not in self.SUIT_ORDER_MAP:
             print(f"Warning: Card object missing or invalid suit: {getattr(self, 'suit', 'N/A')}")
             return -1
        return self.SUIT_ORDER_MAP[self.suit]

    def __lt__(self, other):
        if not isinstance(other, Card): return NotImplemented
        # Используем _int_representation для сравнения, если он есть, т.к. он уникален
        if hasattr(self, '_int_representation') and hasattr(other, '_int_representation'):
             # Сравнение может быть не тем, что нужно для игры, но для сортировки подойдет
             return self._int_representation < other._int_representation
        # Фоллбэк на ранг/масть, если _int_representation нет (хотя его отсутствие - ошибка)
        if self.int_rank != other.int_rank: return self.int_rank < other.int_rank
        return self.int_suit < other.int_suit

    def __repr__(self):
        # Используем rank и suit, если они есть, иначе показываем Invalid
        if hasattr(self, 'rank') and hasattr(self, 'suit') and self.rank and self.suit:
             return f'Card("{self.rank}{self.suit}")'
        else:
             # Добавляем _int_representation для отладки, если он есть
             int_repr = getattr(self, '_int_representation', 'N/A')
             return f'Card("Invalid", int_repr={int_repr})'


    def __str__(self):
        if hasattr(self, 'rank') and hasattr(self, 'suit') and self.rank is not None and self.suit is not None:
             return f"{self.rank}{self.suit}"
        else:
             # print(f"DEBUG Card.__str__: Returning 'InvalidCard'. Rank={getattr(self, 'rank', 'N/A')}, Suit={getattr(self, 'suit', 'N/A')}")
             # sys.stdout.flush(); sys.stderr.flush()
             return "InvalidCard" # Оставляем возврат строки

    def __hash__(self):
        if not hasattr(self, '_int_representation') or self._int_representation is None:
             print(f"Warning: Card object missing _int_representation for hashing: {self!r}")
             return hash(repr(self))
        return super().__hash__()

    def __eq__(self, other):
        if not isinstance(other, Card): return NotImplemented
        if not hasattr(self, '_int_representation') or not hasattr(other, '_int_representation'):
             return repr(self) == repr(other)
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
        # Вызываем наш конструктор Card, который вызовет super().__init__
        return Card(standard_str)
    except Exception as e:
        raise ValueError(f"Failed to create Card from string '{s}': {e}")


def card_to_str(c: Optional[Card]) -> str:
    """Конвертирует карту в строку или '__' если None."""
    return str(c) if c else "__"

evaluate_hand = evaluate_cards_phevaluator
