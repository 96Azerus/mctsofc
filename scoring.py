# scoring.py
"""
Логика подсчета очков, роялти, проверки фолов и условий Фантазии
для OFC Pineapple согласно предоставленным правилам.
"""
from typing import List, Tuple, Dict, Optional
from card import Card, evaluate_hand # Наш Card и функция оценки
from collections import Counter

# --- Константы рангов phevaluator ---
RANK_CLASS_HIGH_CARD = 7462
RANK_CLASS_PAIR = 6185
RANK_CLASS_TWO_PAIR = 3325
RANK_CLASS_TRIPS = 2467
RANK_CLASS_STRAIGHT = 1609
RANK_CLASS_FLUSH = 1599
RANK_CLASS_FULL_HOUSE = 322
RANK_CLASS_QUADS = 166
RANK_CLASS_STRAIGHT_FLUSH = 10
RANK_CLASS_ROYAL_FLUSH = 1

# --- Таблицы Роялти ---
# Боттом
ROYALTY_BOTTOM_POINTS = {
    "Straight": 2, "Flush": 4, "Full House": 6, "Quads": 10,
    "Straight Flush": 15, "Royal Flush": 25
}
# Мидл
ROYALTY_MIDDLE_POINTS = {
    "Trips": 2, "Straight": 4, "Flush": 8, "Full House": 12, "Quads": 20,
    "Straight Flush": 30, "Royal Flush": 50
}
# Топ (Пары 66+ и Сеты)
ROYALTY_TOP_PAIRS = {
    6: 1, 7: 2, 8: 3, 9: 4, 10: 5, 11: 6, 12: 7, 13: 8, 14: 9 # 66..AA
}
ROYALTY_TOP_TRIPS = {
    2: 10, 3: 11, 4: 12, 5: 13, 6: 14, 7: 15, 8: 16, 9: 17,
    10: 18, 11: 19, 12: 20, 13: 21, 14: 22 # 222..AAA
}

# Границы рангов для 5-карточных комбинаций (включая Trips для Мидла)
# МЕНЬШЕ = ЛУЧШЕ
ROYALTY_5CARD_BOUNDS = {
    "Royal Flush": (1, 1), "Straight Flush": (2, 10), "Quads": (11, 166),
    "Full House": (167, 322), "Flush": (323, 1599), "Straight": (1600, 1609),
    "Trips": (1610, 2467)
    # Two Pair, Pair, High Card не дают роялти на мидле/боттоме
}

def get_hand_rank_safe(cards: List[Card]) -> int:
    """Безопасно вызывает evaluate_hand."""
    if not cards: return RANK_CLASS_HIGH_CARD + 1
    try:
        return evaluate_hand(*cards)
    except Exception:
        return RANK_CLASS_HIGH_CARD + 1

def get_row_royalty(cards: List[Card], row_name: str) -> int:
    """Считает роялти для одного ряда."""
    num_cards = len(cards)
    royalty = 0

    if row_name == "top":
        if num_cards != 3: return 0
        ranks = sorted([c.int_rank for c in cards])
        counts = Counter(ranks)
        if len(counts) == 1: # Сет
            royalty = ROYALTY_TOP_TRIPS.get(ranks[0], 0)
        elif len(counts) == 2: # Пара
            pair_rank = [r for r, c in counts.items() if c == 2][0]
            royalty = ROYALTY_TOP_PAIRS.get(pair_rank, 0)
        return royalty

    elif row_name in ["middle", "bottom"]:
        if num_cards != 5: return 0
        rank_eval = get_hand_rank_safe(cards)
        table = ROYALTY_MIDDLE_POINTS if row_name == "middle" else ROYALTY_BOTTOM_POINTS

        max_royalty = 0
        for hand_name, (low_rank, high_rank) in ROYALTY_5CARD_BOUNDS.items():
            points = table.get(hand_name, 0)
            if points > 0 and low_rank <= rank_eval <= high_rank:
                 max_royalty = max(max_royalty, points)
        return max_royalty
    else:
        return 0

def check_board_foul(top: List[Card], middle: List[Card], bottom: List[Card]) -> bool:
    """Проверяет фол доски."""
    if not (len(top) == 3 and len(middle) == 5 and len(bottom) == 5):
        return False # Неполная доска не фол

    rank_t = get_hand_rank_safe(top)
    rank_m = get_hand_rank_safe(middle)
    rank_b = get_hand_rank_safe(bottom)

    # Меньший ранг -> Сильнее рука
    return not (rank_b <= rank_m <= rank_t)

def get_fantasyland_entry_cards(top: List[Card]) -> int:
    """Возвращает кол-во карт для ФЛ при входе (0 если нет квалификации)."""
    if len(top) != 3: return 0
    ranks = sorted([c.int_rank for c in top])
    counts = Counter(ranks)
    if len(counts) == 1: # Сет
        set_rank = ranks[0]
        if set_rank >= 2: return 17 # Сет 222+
    elif len(counts) == 2: # Пара
        pair_rank = [r for r, c in counts.items() if c == 2][0]
        if pair_rank == 12: return 14 # QQ
        if pair_rank == 13: return 15 # KK
        if pair_rank == 14: return 16 # AA
    return 0

def check_fantasyland_stay(top: List[Card], middle: List[Card], bottom: List[Card]) -> bool:
    """Проверяет условия удержания ФЛ (Сет топ ИЛИ Каре+ боттом)."""
    if not (len(top) == 3 and len(middle) == 5 and len(bottom) == 5):
        return False

    # 1. Сет на топе
    ranks_top = sorted([c.int_rank for c in top])
    if ranks_top[0] == ranks_top[1] == ranks_top[2]:
        return True

    # 2. Каре или лучше на боттоме
    rank_b = get_hand_rank_safe(bottom)
    if rank_b <= RANK_CLASS_QUADS: # Каре или Стрит-Флеш/Роял-Флеш
        return True

    return False

def calculate_headsup_score(board1: 'PlayerBoard', board2: 'PlayerBoard') -> int:
    """Считает очки между двумя игроками (с точки зрения Игрока 1)."""
    foul1 = board1.is_foul
    foul2 = board2.is_foul
    r1 = board1.get_total_royalty() # Роялти считаются даже если доска не полная, но только если не фол
    r2 = board2.get_total_royalty()

    if foul1 and foul2: return 0
    if foul1: return -(6 + r2)
    if foul2: return 6 + r1

    # Никто не сфолил
    score1 = 0
    rank_t1 = board1._get_rank('top')
    rank_m1 = board1._get_rank('middle')
    rank_b1 = board1._get_rank('bottom')
    rank_t2 = board2._get_rank('top')
    rank_m2 = board2._get_rank('middle')
    rank_b2 = board2._get_rank('bottom')

    wins1 = 0
    if rank_t1 < rank_t2: wins1 += 1
    elif rank_t2 < rank_t1: wins1 -= 1
    if rank_m1 < rank_m2: wins1 += 1
    elif rank_m2 < rank_m1: wins1 -= 1
    if rank_b1 < rank_b2: wins1 += 1
    elif rank_b2 < rank_b1: wins1 -= 1

    score1 += wins1
    if wins1 == 3: score1 += 3
    elif wins1 == -3: score1 -= 3

    score1 += (r1 - r2)
    return score1