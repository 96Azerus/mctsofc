# board.py
"""
Представление доски одного игрока.
"""
from typing import List, Tuple, Dict, Optional
from card import Card, card_to_str
from scoring import (get_hand_rank_safe, check_board_foul,
                     get_fantasyland_entry_cards, check_fantasyland_stay,
                     get_row_royalty, RANK_CLASS_HIGH_CARD)
import copy
from collections import Counter

class PlayerBoard:
    ROW_CAPACITY: Dict[str, int] = {'top': 3, 'middle': 5, 'bottom': 5}
    ROW_NAMES: List[str] = ['top', 'middle', 'bottom']

    def __init__(self):
        self.rows: Dict[str, List[Optional[Card]]] = {
            'top': [None] * 3, 'middle': [None] * 5, 'bottom': [None] * 5
        }
        self._cards_placed: int = 0
        self.is_foul: bool = False
        self._cached_ranks: Dict[str, Optional[int]] = {'top': None, 'middle': None, 'bottom': None}
        self._cached_royalties: Dict[str, Optional[int]] = {'top': None, 'middle': None, 'bottom': None}
        self._is_complete: bool = False

    def _get_next_index(self, row_name: str) -> Optional[int]:
        """Находит индекс первого None в ряду."""
        try:
            return self.rows[row_name].index(None)
        except ValueError:
            return None # Ряд полон

    def add_card(self, card: Card, row_name: str, index: Optional[int] = None) -> bool:
        """
        Добавляет карту в указанный слот или в первый свободный.
        Возвращает True при успехе.
        """
        if row_name not in self.ROW_NAMES:
            raise ValueError(f"Invalid row name: {row_name}")

        if index is None:
            index = self._get_next_index(row_name)

        if index is None or not (0 <= index < self.ROW_CAPACITY[row_name]):
            # print(f"Warning: Row '{row_name}' is full or index {index} out of bounds. Cannot add {card}.")
            return False

        if self.rows[row_name][index] is not None:
            # print(f"Warning: Slot {row_name}[{index}] is already occupied. Cannot add {card}.")
            return False

        self.rows[row_name][index] = card
        self._cards_placed += 1
        self._is_complete = (self._cards_placed == 13)
        # Сбрасываем кэши при изменении доски
        self._cached_ranks = {'top': None, 'middle': None, 'bottom': None}
        self._cached_royalties = {'top': None, 'middle': None, 'bottom': None}
        self.is_foul = False # Пересчитается при завершении, если нужно
        return True

    def set_full_board(self, top: List[Card], middle: List[Card], bottom: List[Card]):
        """Устанавливает доску из готовых списков карт (для Фантазии)."""
        if len(top) != 3 or len(middle) != 5 or len(bottom) != 5:
            raise ValueError("Incorrect number of cards for setting full board.")
        self.rows['top'] = list(top) + [None]*(3-len(top)) # Дополняем None, если нужно (хотя не должно)
        self.rows['middle'] = list(middle) + [None]*(5-len(middle))
        self.rows['bottom'] = list(bottom) + [None]*(5-len(bottom))
        self._cards_placed = len(top) + len(middle) + len(bottom)
        self._is_complete = (self._cards_placed == 13)
        # Сбрасываем кэши и проверяем фол
        self._cached_ranks = {'top': None, 'middle': None, 'bottom': None}
        self._cached_royalties = {'top': None, 'middle': None, 'bottom': None}
        self.check_and_set_foul()

    def get_row_cards(self, row_name: str) -> List[Card]:
        """Возвращает список карт в ряду (без None)."""
        return [card for card in self.rows[row_name] if card is not None]

    def is_row_full(self, row_name: str) -> bool:
        """Проверяет, заполнен ли ряд."""
        return all(slot is not None for slot in self.rows[row_name])

    def get_available_slots(self) -> List[Tuple[str, int]]:
        """Возвращает список доступных слотов ('row_name', index)."""
        slots = []
        for row_name in self.ROW_NAMES:
            for i, card in enumerate(self.rows[row_name]):
                if card is None:
                    slots.append((row_name, i))
        return slots

    def get_total_cards(self) -> int:
        """Возвращает количество размещенных карт."""
        return self._cards_placed

    def is_complete(self) -> bool:
        """Проверяет, размещены ли все 13 карт."""
        return self._is_complete

    def _get_rank(self, row_name: str) -> int:
        """Получает ранг руки ряда (из кэша или вычисляет)."""
        if self._cached_ranks[row_name] is None:
             cards = self.get_row_cards(row_name)
             req_len = 3 if row_name == 'top' else 5
             if len(cards) < req_len:
                 # Для неполных рядов возвращаем "худший" ранг + смещение, чтобы они были хуже полных
                 self._cached_ranks[row_name] = RANK_CLASS_HIGH_CARD + 10 + (req_len - len(cards))
             else:
                 self._cached_ranks[row_name] = get_hand_rank_safe(cards)
        return self._cached_ranks[row_name]

    def check_and_set_foul(self) -> bool:
        """Проверяет фол и устанавливает флаг is_foul. Вызывать только на полной доске."""
        if not self.is_complete():
            self.is_foul = False # Не фол, пока не полная
            return False

        # Используем функцию из scoring.py
        self.is_foul = check_board_foul(
            self.get_row_cards('top'),
            self.get_row_cards('middle'),
            self.get_row_cards('bottom')
        )
        # Если фол, обнуляем роялти в кэше
        if self.is_foul:
             self._cached_royalties = {'top': 0, 'middle': 0, 'bottom': 0}
        return self.is_foul

    def get_royalties(self) -> Dict[str, int]:
        """Считает и возвращает роялти для каждой линии (используя кэш)."""
        if self.is_foul:
            return {'top': 0, 'middle': 0, 'bottom': 0}

        for row_name in self.ROW_NAMES:
             if self._cached_royalties[row_name] is None:
                 cards = self.get_row_cards(row_name)
                 # Роялти начисляются только за полные ряды
                 required_len = 3 if row_name == 'top' else 5
                 if len(cards) == required_len:
                     self._cached_royalties[row_name] = get_row_royalty(cards, row_name)
                 else:
                     self._cached_royalties[row_name] = 0
        return self._cached_royalties.copy()

    def get_total_royalty(self) -> int:
        """Возвращает сумму роялти по всем линиям."""
        if self.is_foul: return 0
        # Пересчитываем, если нужно
        if None in self._cached_royalties.values():
            self.get_royalties()
        return sum(self._cached_royalties.values())

    def get_fantasyland_qualification_cards(self) -> int:
        """Возвращает кол-во карт для ФЛ (0 если нет). Проверяет фол."""
        if not self.is_complete(): return 0
        # Сначала проверяем фол
        if self.check_and_set_foul(): return 0
        # Если не фол, проверяем топ
        return get_fantasyland_entry_cards(self.get_row_cards('top'))

    def check_fantasyland_stay_conditions(self) -> bool:
        """Проверяет условия удержания ФЛ. Проверяет фол."""
        if not self.is_complete(): return False
        if self.check_and_set_foul(): return False
        # Если не фол, проверяем условия удержания
        return check_fantasyland_stay(
            self.get_row_cards('top'),
            self.get_row_cards('middle'),
            self.get_row_cards('bottom')
        )

    def get_board_state_tuple(self) -> Tuple[Tuple[Optional[Card], ...], ...]:
        """Возвращает неизменяемое представление доски (включая None)."""
        # Сортируем карты внутри рядов для каноничности, None идут в конец
        key_func = lambda c: c.int_value if c else float('inf')
        top_tuple = tuple(sorted(self.rows['top'], key=key_func))
        mid_tuple = tuple(sorted(self.rows['middle'], key=key_func))
        bot_tuple = tuple(sorted(self.rows['bottom'], key=key_func))
        return (top_tuple, mid_tuple, bot_tuple)

    def copy(self) -> 'PlayerBoard':
        """Создает глубокую копию доски."""
        new_board = PlayerBoard()
        new_board.rows = {r: list(cards) for r, cards in self.rows.items()}
        new_board._cards_placed = self._cards_placed
        new_board.is_foul = self.is_foul
        new_board._cached_ranks = self._cached_ranks.copy()
        new_board._cached_royalties = self._cached_royalties.copy()
        new_board._is_complete = self._is_complete
        return new_board

    def __str__(self) -> str:
        """Строковое представление доски."""
        s = ""
        for r_name in ['top', 'middle', 'bottom']:
            row_str = [card_to_str(c) if c else "__" for c in self.rows[r_name]]
            s += " ".join(row_str) + "\n"
        return s.strip()