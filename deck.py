# deck.py
"""
Реализация колоды карт с использованием set для эффективности.
"""
import random
from typing import List, Set, Optional
from card import Card # Наш Card

class Deck:
    """Представляет колоду карт для OFC."""
    # Создаем полный набор строк карт один раз
    FULL_DECK_STRS = {r + s for r in '23456789TJQKA' for s in 'cdhs'}
    # Создаем полный набор объектов Card один раз
    FULL_DECK_CARDS: Set[Card] = {Card(cs) for cs in FULL_DECK_STRS}

    def __init__(self, cards: Optional[Set[Card]] = None):
        """
        Инициализирует колоду.
        Если cards is None, создает полную колоду.
        Иначе использует переданный набор карт (копируя его).
        """
        if cards is None:
            # Копируем из предсозданного набора
            self.cards: Set[Card] = self.FULL_DECK_CARDS.copy()
        else:
            # Важно копировать переданный set
            self.cards: Set[Card] = cards.copy()

    def deal(self, n: int) -> List[Card]:
        """Раздает n случайных карт из колоды и удаляет их."""
        current_len = len(self.cards)
        n_req = n # Сохраняем запрошенное количество для сообщения

        if n <= 0:
            return []

        if n > current_len:
            # В симуляции можем раздать меньше, если карт не хватает
            print(f"Warning: Trying to deal {n_req} cards, only {current_len} left. Dealing {current_len}.")
            n = current_len
            # В реальной игре это была бы ошибка, но для симуляций продолжаем
            # raise ValueError(f"Cannot deal {n_req} cards, only {current_len} left.")

        if n == 0: # Если после корректировки n стало 0
             return []

        # random.sample требует sequence, конвертируем set в list временно
        # Преобразование в list может быть дорогостоящим для больших set
        # Альтернатива: выбрать n элементов по одному с удалением
        # if n < current_len / 2: # Примерная эвристика
        #     dealt_cards = []
        #     temp_list = list(self.cards) # Все равно нужно для random.choice
        #     for _ in range(n):
        #         chosen_card = random.choice(temp_list)
        #         dealt_cards.append(chosen_card)
        #         self.cards.remove(chosen_card) # Удаляем из set
        #         temp_list.remove(chosen_card) # Удаляем из временного списка
        # else:
        #     dealt_cards = random.sample(list(self.cards), n)
        #     self.cards.difference_update(dealt_cards)

        # Пока оставляем простой random.sample
        dealt_cards = random.sample(list(self.cards), n)
        self.cards.difference_update(dealt_cards)

        return dealt_cards

    def remove(self, cards_to_remove: List[Card]):
        """Удаляет конкретные карты из колоды."""
        # difference_update безопасен, даже если каких-то карт нет в self.cards
        self.cards.difference_update(cards_to_remove)

    def add(self, cards_to_add: List[Card]):
        """Добавляет карты обратно в колоду (например, при откате хода)."""
        # update безопасен, дубликаты не добавятся в set
        self.cards.update(cards_to_add)

    def get_remaining_cards(self) -> List[Card]:
        """Возвращает список оставшихся карт."""
        return list(self.cards)

    def copy(self) -> 'Deck':
        """Создает копию колоды."""
        # Копирование set при инициализации обеспечивает независимость
        return Deck(self.cards)

    def __len__(self) -> int:
        """Возвращает количество карт в колоде."""
        return len(self.cards)

    def __contains__(self, card: Card) -> bool:
        """Проверяет наличие карты в колоде O(1)."""
        return card in self.cards

    def __str__(self) -> str:
        """Строковое представление колоды (для отладки)."""
        return f"Deck({len(self.cards)} cards)"

    def __repr__(self) -> str:
        return self.__str__()
