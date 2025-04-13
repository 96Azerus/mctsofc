# scoring.py
"""
Логика подсчета очков, роялти, проверки фолов и условий Фантазии
для OFC Pineapple согласно предоставленным правилам.
"""
from typing import List, Tuple, Dict, Optional
# Импортируем Card (теперь алиас PhevaluatorCard) и evaluate_hand, RANK_ORDER_MAP
from card import Card, evaluate_hand, RANK_ORDER_MAP
from collections import Counter

# --- Константы рангов phevaluator ---
RANK_CLASS_ROYAL_FLUSH = 1
RANK_CLASS_STRAIGHT_FLUSH = 10
RANK_CLASS_QUADS = 166
RANK_CLASS_FULL_HOUSE = 322
RANK_CLASS_FLUSH = 1599
RANK_CLASS_STRAIGHT = 1609
RANK_CLASS_TRIPS = 2467
RANK_CLASS_TWO_PAIR = 3325
RANK_CLASS_PAIR = 6185
RANK_CLASS_HIGH_CARD = 7462

# --- Таблицы Роялти (Американские правила) ---
ROYALTY_BOTTOM_POINTS = { "Straight": 2, "Flush": 4, "Full House": 6, "Quads": 10, "Straight Flush": 15, "Royal Flush": 25 }
ROYALTY_MIDDLE_POINTS = { "Trips": 2, "Straight": 4, "Flush": 8, "Full House": 12, "Quads": 20, "Straight Flush": 30, "Royal Flush": 50 }
ROYALTY_TOP_PAIRS = { 6: 1, 7: 2, 8: 3, 9: 4, 10: 5, 11: 6, 12: 7, 13: 8, 14: 9 } # 66..AA
ROYALTY_TOP_TRIPS = { 2: 10, 3: 11, 4: 12, 5: 13, 6: 14, 7: 15, 8: 16, 9: 17, 10: 18, 11: 19, 12: 20, 13: 21, 14: 22 } # 222..AAA
ROYALTY_5CARD_BOUNDS = { "Royal Flush": (1, 1), "Straight Flush": (2, 10), "Quads": (11, 166), "Full House": (167, 322), "Flush": (323, 1599), "Straight": (1600, 1609), "Trips": (1610, 2467) }

def get_hand_rank_safe(cards: List[Optional[Card]]) -> int:
    """
    Безопасно вызывает evaluate_hand для списка карт, игнорируя None.
    Возвращает ранг или очень плохой ранг при ошибке/недостатке карт.
    """
    valid_cards = [c for c in cards if c is not None]
    min_cards = 3 if len(cards) == 3 else 5 if len(cards) == 5 else 0
    if len(valid_cards) < min_cards:
        return RANK_CLASS_HIGH_CARD + 100 + (min_cards - len(valid_cards))
    try:
        # evaluate_hand теперь напрямую phevaluator.evaluate_cards
        return evaluate_hand(*valid_cards)
    except Exception as e:
        print(f"Error evaluating hand { [str(c) for c in valid_cards] }: {e}")
        return RANK_CLASS_HIGH_CARD + 200

def get_row_royalty(cards: List[Optional[Card]], row_name: str) -> int:
    """Считает роялти для одного ряда, игнорируя None."""
    valid_cards = [c for c in cards if c is not None]
    num_cards = len(valid_cards)
    royalty = 0

    if row_name == "top":
        if num_cards != 3: return 0
        # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
        ranks = sorted([RANK_ORDER_MAP[c.rank] for c in valid_cards if hasattr(c, 'rank') and c.rank in RANK_ORDER_MAP])
        if len(ranks) != 3: return 0 # Проверка на случай ошибки в карте
        # -----------------------------------------
        counts = Counter(ranks)
        if len(counts) == 1:
            set_rank = ranks[0]
            royalty = ROYALTY_TOP_TRIPS.get(set_rank, 0)
        elif len(counts) == 2:
            pair_rank = -1
            for r, c in counts.items():
                if c == 2: pair_rank = r; break
            if pair_rank != -1: royalty = ROYALTY_TOP_PAIRS.get(pair_rank, 0)
        return royalty

    elif row_name in ["middle", "bottom"]:
        if num_cards != 5: return 0
        rank_eval = get_hand_rank_safe(valid_cards)
        table = ROYALTY_MIDDLE_POINTS if row_name == "middle" else ROYALTY_BOTTOM_POINTS
        bounds = ROYALTY_5CARD_BOUNDS
        max_royalty = 0
        for hand_name, (low_rank, high_rank) in bounds.items():
            if hand_name == "Trips" and row_name != "middle": continue
            points = table.get(hand_name, 0)
            if points > 0 and low_rank <= rank_eval <= high_rank:
                 max_royalty = max(max_royalty, points)
        return max_royalty
    else:
        return 0

def check_board_foul(top: List[Optional[Card]], middle: List[Optional[Card]], bottom: List[Optional[Card]]) -> bool:
    """Проверяет фол доски (только для полных досок)."""
    if sum(1 for c in top if c) != 3 or sum(1 for c in middle if c) != 5 or sum(1 for c in bottom if c) != 5:
        return False
    rank_t = get_hand_rank_safe(top)
    rank_m = get_hand_rank_safe(middle)
    rank_b = get_hand_rank_safe(bottom)
    return not (rank_b <= rank_m <= rank_t)

def get_fantasyland_entry_cards(top: List[Optional[Card]]) -> int:
    """Возвращает кол-во карт для ФЛ при входе (0 если нет квалификации)."""
    valid_cards = [c for c in top if c is not None]
    if len(valid_cards) != 3: return 0
    # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
    ranks = sorted([RANK_ORDER_MAP[c.rank] for c in valid_cards if hasattr(c, 'rank') and c.rank in RANK_ORDER_MAP])
    if len(ranks) != 3: return 0
    # -----------------------------------------
    counts = Counter(ranks)
    if len(counts) == 1: # Сет
        set_rank = ranks[0]
        if set_rank >= 2: return 17
    elif len(counts) == 2: # Пара
        pair_rank = -1
        for r, c in counts.items():
            if c == 2: pair_rank = r; break
        if pair_rank == 12: return 14 # QQ
        if pair_rank == 13: return 15 # KK
        if pair_rank == 14: return 16 # AA
    return 0

def check_fantasyland_stay(top: List[Optional[Card]], middle: List[Optional[Card]], bottom: List[Optional[Card]]) -> bool:
    """Проверяет условия удержания ФЛ (Сет+ топ ИЛИ Каре+ боттом)."""
    valid_top = [c for c in top if c is not None]
    valid_middle = [c for c in middle if c is not None]
    valid_bottom = [c for c in bottom if c is not None]
    if len(valid_top) != 3 or len(valid_middle) != 5 or len(valid_bottom) != 5: return False

    # 1. Сет на топе
    # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
    ranks_top = sorted([RANK_ORDER_MAP[c.rank] for c in valid_top if hasattr(c, 'rank') and c.rank in RANK_ORDER_MAP])
    if len(ranks_top) == 3 and ranks_top[0] == ranks_top[1] == ranks_top[2]:
        return True
    # -----------------------------------------

    # 2. Каре или лучше на боттоме
    rank_b = get_hand_rank_safe(valid_bottom)
    if rank_b <= RANK_CLASS_QUADS: # RANK_CLASS_QUADS = 166
        return True

    return False

def calculate_headsup_score(board1: 'PlayerBoard', board2: 'PlayerBoard') -> int:
    """Считает очки между двумя игроками (с точки зрения Игрока 1)."""
    # board1 и board2 теперь PlayerBoard, который использует phevaluator.Card
    foul1 = board1.is_complete() and board1.check_and_set_foul()
    foul2 = board2.is_complete() and board2.check_and_set_foul()
    r1 = board1.get_total_royalty()
    r2 = board2.get_total_royalty()

    if foul1 and foul2: return 0
    if foul1: return -(6 + r2)
    if foul2: return 6 + r1

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
