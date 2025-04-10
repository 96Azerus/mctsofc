# board.py
"""
Представление доски одного игрока.
"""
from typing import List, Tuple, Dict, Optional
from card import Card, card_to_str
from scoring import (get_hand_rank_safe, check_board_foul,
                     get_fantasyland_entry_cards, check_fantasyland_stay,
                     get_row_royalty, RANK_CLASS_HIGH_CARD)
import copy # Используем для copy()
from collections import Counter

class PlayerBoard:
    ROW_CAPACITY: Dict[str, int] = {'top': 3, 'middle': 5, 'bottom': 5}
    ROW_NAMES: List[str] = ['top', 'middle', 'bottom']

    def __init__(self):
        # Инициализируем ряды пустыми списками None
        self.rows: Dict[str, List[Optional[Card]]] = {
            name: [None] * capacity for name, capacity in self.ROW_CAPACITY.items()
        }
        self._cards_placed: int = 0
        self.is_foul: bool = False
        # Кэши для рангов и роялти
        self._cached_ranks: Dict[str, Optional[int]] = {name: None for name in self.ROW_NAMES}
        self._cached_royalties: Dict[str, Optional[int]] = {name: None for name in self.ROW_NAMES}
        self._is_complete: bool = False

    def _get_next_index(self, row_name: str) -> Optional[int]:
        """Находит индекс первого None в ряду."""
        try:
            # Используем list.index() для поиска первого None
            return self.rows[row_name].index(None)
        except ValueError:
            return None # Ряд полон (None не найден)

    def add_card(self, card: Card, row_name: str, index: int) -> bool:
        """
        Добавляет карту в УКАЗАННЫЙ слот.
        Возвращает True при успехе, False при неудаче (слот занят, индекс неверный).
        """
        if row_name not in self.ROW_NAMES:
            # print(f"Error: Invalid row name '{row_name}'")
            return False

        capacity = self.ROW_CAPACITY[row_name]
        if not (0 <= index < capacity):
            # print(f"Error: Index {index} out of bounds for row '{row_name}' (0-{capacity-1}).")
            return False

        if self.rows[row_name][index] is not None:
            # print(f"Warning: Slot {row_name}[{index}] is already occupied. Cannot add {card_to_str(card)}.")
            return False

        # Добавляем карту
        self.rows[row_name][index] = card
        self._cards_placed += 1
        self._is_complete = (self._cards_placed == 13)

        # Сбрасываем кэши при изменении доски
        self._reset_caches()
        # Фол будет пересчитан при завершении доски
        self.is_foul = False
        return True

    def remove_card(self, row_name: str, index: int) -> Optional[Card]:
         """Удаляет карту из указанного слота (для UI отмены хода)."""
         if row_name not in self.ROW_NAMES or not (0 <= index < self.ROW_CAPACITY[row_name]):
              return None
         card = self.rows[row_name][index]
         if card is not None:
              self.rows[row_name][index] = None
              self._cards_placed -= 1
              self._is_complete = False
              self._reset_caches()
              self.is_foul = False
         return card


    def set_full_board(self, top: List[Card], middle: List[Card], bottom: List[Card]):
        """Устанавливает доску из готовых списков карт (для Фантазии)."""
        if len(top) != 3 or len(middle) != 5 or len(bottom) != 5:
            raise ValueError("Incorrect number of cards for setting full board.")

        # Проверяем уникальность карт перед установкой
        all_cards = top + middle + bottom
        if len(all_cards) != len(set(all_cards)):
             raise ValueError("Duplicate cards provided for setting full board.")

        self.rows['top'] = list(top)
        self.rows['middle'] = list(middle)
        self.rows['bottom'] = list(bottom)

        self._cards_placed = 13
        self._is_complete = True
        # Сбрасываем кэши и проверяем фол
        self._reset_caches()
        self.check_and_set_foul() # Проверяем фол сразу после установки

    def get_row_cards(self, row_name: str) -> List[Card]:
        """Возвращает список карт в ряду (без None)."""
        if row_name not in self.rows: return []
        return [card for card in self.rows[row_name] if card is not None]

    def is_row_full(self, row_name: str) -> bool:
        """Проверяет, заполнен ли ряд."""
        if row_name not in self.rows: return False
        # Проверяем, что все слоты в ряду не None
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

    def _reset_caches(self):
         """Сбрасывает внутренние кэши рангов и роялти."""
         self._cached_ranks = {name: None for name in self.ROW_NAMES}
         self._cached_royalties = {name: None for name in self.ROW_NAMES}

    def _get_rank(self, row_name: str) -> int:
        """Получает ранг руки ряда (из кэша или вычисляет)."""
        if row_name not in self.ROW_NAMES: return RANK_CLASS_HIGH_CARD + 100 # Худший ранг

        if self._cached_ranks[row_name] is None:
             cards = self.get_row_cards(row_name)
             req_len = self.ROW_CAPACITY[row_name]
             if len(cards) < req_len:
                 # Для неполных рядов возвращаем "худший" ранг + смещение, чтобы они были хуже полных
                 # Смещение зависит от количества недостающих карт
                 self._cached_ranks[row_name] = RANK_CLASS_HIGH_CARD + 10 + (req_len - len(cards))
             else:
                 # Вычисляем ранг только для полных рядов
                 self._cached_ranks[row_name] = get_hand_rank_safe(cards)
        return self._cached_ranks[row_name]

    def check_and_set_foul(self) -> bool:
        """Проверяет фол и устанавливает флаг is_foul. Вызывать только на полной доске."""
        if not self.is_complete():
            self.is_foul = False # Не фол, пока не полная
            return False

        # Используем функцию из scoring.py
        # Передаем карты напрямую, т.к. get_row_cards() вернет пустые списки, если ряд не существует
        self.is_foul = check_board_foul(
            self.rows['top'],
            self.rows['middle'],
            self.rows['bottom']
        )
        # Если фол, обнуляем роялти в кэше
        if self.is_foul:
             self._cached_royalties = {'top': 0, 'middle': 0, 'bottom': 0}
        return self.is_foul

    def get_royalties(self) -> Dict[str, int]:
        """Считает и возвращает роялти для каждой линии (используя кэш)."""
        # Если фол (проверенный на полной доске), роялти 0
        if self.is_foul and self.is_complete():
            return {'top': 0, 'middle': 0, 'bottom': 0}

        # Пересчитываем, если нужно
        recalculated = False
        for row_name in self.ROW_NAMES:
             if self._cached_royalties[row_name] is None:
                 recalculated = True
                 cards = self.get_row_cards(row_name)
                 required_len = self.ROW_CAPACITY[row_name]
                 # Роялти начисляются только за полные ряды
                 if len(cards) == required_len:
                     # Перед подсчетом роялти убедимся, что доска не фол (если она полная)
                     if self.is_complete() and check_board_foul(self.rows['top'], self.rows['middle'], self.rows['bottom']):
                          self._cached_royalties[row_name] = 0
                     else:
                          self._cached_royalties[row_name] = get_row_royalty(cards, row_name)
                 else:
                     self._cached_royalties[row_name] = 0

        # Если пересчитывали и доска полная, проверяем фол еще раз
        # if recalculated and self.is_complete():
        #      self.check_and_set_foul()
        #      if self.is_foul: return {'top': 0, 'middle': 0, 'bottom': 0}

        # Возвращаем копию кэша
        return self._cached_royalties.copy()


    def get_total_royalty(self) -> int:
        """Возвращает сумму роялти по всем линиям."""
        # Вызов get_royalties() обновит кэш и учтет фол, если нужно
        royalties = self.get_royalties()
        return sum(royalties.values())

    def get_fantasyland_qualification_cards(self) -> int:
        """Возвращает кол-во карт для ФЛ (0 если нет). Проверяет фол."""
        if not self.is_complete(): return 0
        # Сначала проверяем фол
        if self.check_and_set_foul(): return 0
        # Если не фол, проверяем топ
        return get_fantasyland_entry_cards(self.rows['top'])

    def check_fantasyland_stay_conditions(self) -> bool:
        """Проверяет условия удержания ФЛ. Проверяет фол."""
        if not self.is_complete(): return False
        if self.check_and_set_foul(): return False
        # Если не фол, проверяем условия удержания
        return check_fantasyland_stay(
            self.rows['top'],
            self.rows['middle'],
            self.rows['bottom']
        )

    def get_board_state_tuple(self) -> Tuple[Tuple[Optional[str], ...], ...]:
        """
        Возвращает неизменяемое представление доски (строки карт, включая '__').
        Сортирует строки внутри рядов для каноничности.
        """
        # Сортируем строки карт внутри рядов для каноничности, '__' идут в конец
        key_func = lambda s: Card.RANK_ORDER_MAP.get(s[0].upper(), 0) if s != "__" else float('inf')

        top_tuple = tuple(sorted([card_to_str(c) for c in self.rows['top']], key=key_func))
        mid_tuple = tuple(sorted([card_to_str(c) for c in self.rows['middle']], key=key_func))
        bot_tuple = tuple(sorted([card_to_str(c) for c in self.rows['bottom']], key=key_func))
        return (top_tuple, mid_tuple, bot_tuple)

    def copy(self) -> 'PlayerBoard':
        """Создает глубокую копию доски."""
        # Используем copy.deepcopy для надежности копирования списков карт
        new_board = PlayerBoard()
        # Копируем ряды глубоко
        new_board.rows = {r: list(cards) for r, cards in self.rows.items()}
        new_board._cards_placed = self._cards_placed
        new_board.is_foul = self.is_foul
        # Копируем кэши (они содержат простые типы)
        new_board._cached_ranks = self._cached_ranks.copy()
        new_board._cached_royalties = self._cached_royalties.copy()
        new_board._is_complete = self._is_complete
        return new_board

    def __str__(self) -> str:
        """Строковое представление доски."""
        s = ""
        max_len = max(len(self.rows[r_name]) for r_name in self.ROW_NAMES)
        for r_name in self.ROW_NAMES:
            row_str = [card_to_str(c) for c in self.rows[r_name]]
            # Дополняем пробелами для выравнивания
            row_str += ["  "] * (max_len - len(row_str))
            s += " ".join(row_str) + "\n"
        if self.is_complete():
             s += f"Complete: Yes, Foul: {self.is_foul}\n"
             s += f"Royalties: {self.get_total_royalty()} {self.get_royalties()}\n"
        else:
             s += f"Complete: No, Cards: {self._cards_placed}\n"
        return s.strip()

    def __repr__(self) -> str:
         return f"PlayerBoard(Cards={self._cards_placed}, Complete={self._is_complete}, Foul={self.is_foul})"
