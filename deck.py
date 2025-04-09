# deck.py
"""
Реализация колоды карт с использованием set для эффективности.
"""
import random
from typing import List, Set, Optional
from card import Card # Наш Card

class Deck:
    """Представляет колоду карт для OFC."""
    FULL_DECK_CARDS: Set[Card] = {Card(i) for i in range(52)}

    def __init__(self, cards: Optional[Set[Card]] = None):
        """
        Инициализирует колоду.
        Если cards is None, создает полную колоду.
        Иначе использует переданный набор карт (копируя его).
        """
        if cards is None:
            self.cards: Set[Card] = self.FULL_DECK_CARDS.copy()
        else:
            self.cards: Set[Card] = cards.copy() # Важно копировать

    def deal(self, n: int) -> List[Card]:
        """Раздает n случайных карт из колоды и удаляет их."""
        current_len = len(self.cards)
        if n > current_len:
            # В симуляции можем раздать меньше, если карт не хватает
            n = current_len
            # print(f"Warning: Trying to deal {n_req} cards, only {current_len} left. Dealing {n}.")
            # В реальной игре это была бы ошибка
            # raise ValueError(f"Cannot deal {n_req} cards, only {current_len} left.")

        if n == 0:
            return []

        # random.sample требует sequence, конвертируем set в list временно
        dealt_cards = random.sample(list(self.cards), n)

        # Удаляем розданные карты из set
        self.cards.difference_update(dealt_cards)

        return dealt_cards

    def remove(self, cards_to_remove: List[Card]):
        """Удаляет конкретные карты из колоды."""
        self.cards.difference_update(cards_to_remove)

    def add(self, cards_to_add: List[Card]):
        """Добавляет карты обратно в колоду (например, при откате хода)."""
        self.cards.update(cards_to_add)

    def get_remaining_cards(self) -> List[Card]:
        """Возвращает список оставшихся карт."""
        return list(self.cards)

    def copy(self) -> 'Deck':
        """Создает копию колоды."""
        # Копирование set при инициализации обеспечивает независимость
        return Deck(self.cards)

    def __len__(self) -> int:
        return len(self.cards)

    def __contains__(self, card: Card) -> bool:
        """Проверяет наличие карты в колоде O(1)."""
        return card in self.cards