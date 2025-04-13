# card.py
"""
Обертки для работы с phevaluator.Card
"""
import sys
from typing import Optional, List
# Импортируем напрямую
from phevaluator import Card as PhevaluatorCard
from phevaluator import evaluate_cards as evaluate_cards_phevaluator

# Оставляем только функции-хелперы
def card_from_str(s: str) -> PhevaluatorCard:
    """Создает карту phevaluator из строки."""
    if not isinstance(s, str) or len(s) != 2:
        raise ValueError(f"Invalid card string format: '{s}'")
    rank_char = s[0].upper()
    suit_char = s[1].lower()
    standard_str = rank_char + suit_char
    # Проверка валидности (можно использовать внутренние константы phevaluator, если они доступны, или свои)
    VALID_RANKS = '23456789TJQKA'
    VALID_SUITS = 'cdhs'
    if rank_char not in VALID_RANKS or suit_char not in VALID_SUITS:
         raise ValueError(f"Invalid rank or suit in card string: '{s}'")
    try:
        # Создаем базовый объект phevaluator.Card
        card_obj = PhevaluatorCard(standard_str)
        # --- ДОБАВЛЕНА ПРОВЕРКА (на всякий случай) ---
        if not hasattr(card_obj, '_int_representation') or card_obj._int_representation is None:
             print(f"ERROR card_from_str: PhevaluatorCard('{standard_str}') created without valid _int_representation!")
             # Можно вызвать исключение, если это критично
             # raise ValueError(f"Failed to initialize PhevaluatorCard for '{standard_str}'")
        # --------------------------
        return card_obj
    except Exception as e:
        raise ValueError(f"Failed to create PhevaluatorCard from string '{s}': {e}")

def card_to_str(c: Optional[PhevaluatorCard]) -> str:
    """Конвертирует карту phevaluator в строку или '__' если None."""
    # Используем стандартный __str__ от phevaluator, он должен работать
    # Добавим проверку на None для надежности
    return str(c) if c is not None else "__"

# Переименовываем для совместимости с остальным кодом
Card = PhevaluatorCard # Теперь Card это алиас для phevaluator.Card
evaluate_hand = evaluate_cards_phevaluator

# Добавим RANK_ORDER_MAP и SUIT_ORDER_MAP для совместимости с кодом, который их использует
RANK_ORDER_MAP = {r: i + 2 for i, r in enumerate('23456789')}
RANK_ORDER_MAP.update({'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14})
SUIT_ORDER_MAP = {'c': 0, 'd': 1, 'h': 2, 's': 3}
