# deck.py
"""
Реализация колоды карт с использованием set для эффективности.
"""
import random
import sys # Добавлено для flush
import traceback # Добавлено для traceback
from typing import List, Set, Optional
from card import Card # Наш Card

class Deck:
    """Представляет колоду карт для OFC."""
    # Создаем полный набор строк карт один раз
    FULL_DECK_STRS = {r + s for r in '23456789TJQKA' for s in 'cdhs'}
    # Создаем полный набор объектов Card один раз, с проверкой
    FULL_DECK_CARDS: Set[Card] = set()
    print("DEBUG Deck: Initializing FULL_DECK_CARDS...")
    sys.stdout.flush(); sys.stderr.flush()
    initialization_errors = 0
    for cs in FULL_DECK_STRS:
        try:
            card_obj = Card(cs)
            # --- ДОБАВЛЕНА ПРОВЕРКА ---
            # Проверяем наличие _int_representation, которое должно создаваться базовым классом
            if not hasattr(card_obj, '_int_representation') or card_obj._int_representation is None:
                 print(f"ERROR Deck Init: Card('{cs}') created without valid _int_representation!")
                 initialization_errors += 1
                 # Можно либо пропустить карту, либо вызвать ошибку
                 # raise ValueError(f"Failed to initialize Card('{cs}') correctly.")
            else:
                 FULL_DECK_CARDS.add(card_obj)
            # --------------------------
        except Exception as e:
            print(f"ERROR Deck Init: Failed to create Card('{cs}'): {e}")
            traceback.print_exc()
            initialization_errors += 1
            # Пропускаем эту карту или вызываем ошибку
            # raise e # Остановить загрузку, если карта не создалась

    print(f"DEBUG Deck: Initialized FULL_DECK_CARDS with {len(FULL_DECK_CARDS)} cards. Errors: {initialization_errors}")
    if len(FULL_DECK_CARDS) != 52:
        print(f"CRITICAL ERROR: FULL_DECK_CARDS contains {len(FULL_DECK_CARDS)} cards instead of 52!")
        # Можно добавить sys.exit(1) здесь, если это критично для работы приложения
    sys.stdout.flush(); sys.stderr.flush()


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

        # Проверка на наличие невалидных карт в колоде перед раздачей (для отладки)
        invalid_in_deck = {repr(c) for c in self.cards if not hasattr(c, '_int_representation')}
        if invalid_in_deck:
             print(f"WARNING Deck.deal: Deck contains invalid card objects before dealing: {invalid_in_deck}")
             sys.stdout.flush(); sys.stderr.flush()

        try:
            # Используем list() для sample, как и раньше
            # Преобразуем в список только один раз
            card_list = list(self.cards)
            if n > len(card_list): # Дополнительная проверка после преобразования в список
                 print(f"Error: Requested {n} cards, but only {len(card_list)} available in list form.")
                 n = len(card_list)
                 if n == 0: return []

            dealt_cards = random.sample(card_list, n)
            self.cards.difference_update(dealt_cards) # Удаляем из set

            # Проверка разданных карт (для отладки)
            invalid_dealt = {repr(c) for c in dealt_cards if not hasattr(c, '_int_representation')}
            if invalid_dealt:
                 print(f"WARNING Deck.deal: Dealt invalid card objects: {invalid_dealt}")
                 sys.stdout.flush(); sys.stderr.flush()

            return dealt_cards
        except Exception as e:
             print(f"ERROR in Deck.deal: {e}")
             traceback.print_exc()
             sys.stdout.flush(); sys.stderr.flush()
             return [] # Возвращаем пустой список при ошибке

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
