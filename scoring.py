# scoring.py
"""
Логика подсчета очков, роялти, проверки фолов и условий Фантазии
для OFC Pineapple согласно предоставленным правилам.
"""
from typing import List, Tuple, Dict, Optional
# Убедимся, что импортируем наш Card, а не из phevaluator напрямую
from card import Card, evaluate_hand
from collections import Counter

# --- Константы рангов phevaluator ---
# Значения взяты из документации phevaluator или получены экспериментально
# МЕНЬШЕ = ЛУЧШЕ
RANK_CLASS_ROYAL_FLUSH = 1
RANK_CLASS_STRAIGHT_FLUSH = 10 # До 10 включительно
RANK_CLASS_QUADS = 166 # До 166 включительно
RANK_CLASS_FULL_HOUSE = 322 # До 322 включительно
RANK_CLASS_FLUSH = 1599 # До 1599 включительно
RANK_CLASS_STRAIGHT = 1609 # До 1609 включительно
RANK_CLASS_TRIPS = 2467 # До 2467 включительно
RANK_CLASS_TWO_PAIR = 3325 # До 3325 включительно
RANK_CLASS_PAIR = 6185 # До 6185 включительно
RANK_CLASS_HIGH_CARD = 7462 # До 7462 включительно

# --- Таблицы Роялти (Американские правила) ---
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
# Используем константы phevaluator для точности
ROYALTY_5CARD_BOUNDS = {
    "Royal Flush": (RANK_CLASS_ROYAL_FLUSH, RANK_CLASS_ROYAL_FLUSH),
    "Straight Flush": (RANK_CLASS_ROYAL_FLUSH + 1, RANK_CLASS_STRAIGHT_FLUSH),
    "Quads": (RANK_CLASS_STRAIGHT_FLUSH + 1, RANK_CLASS_QUADS),
    "Full House": (RANK_CLASS_QUADS + 1, RANK_CLASS_FULL_HOUSE),
    "Flush": (RANK_CLASS_FULL_HOUSE + 1, RANK_CLASS_FLUSH),
    "Straight": (RANK_CLASS_FLUSH + 1, RANK_CLASS_STRAIGHT),
    "Trips": (RANK_CLASS_STRAIGHT + 1, RANK_CLASS_TRIPS) # Только для мидла
    # Two Pair, Pair, High Card не дают роялти на мидле/боттоме
}

def get_hand_rank_safe(cards: List[Optional[Card]]) -> int:
    """
    Безопасно вызывает evaluate_hand для списка карт, игнорируя None.
    Возвращает ранг или очень плохой ранг при ошибке/недостатке карт.
    """
    valid_cards = [c for c in cards if c is not None]
    # Определяем минимальное количество карт для оценки
    min_cards = 0
    if len(cards) == 3: min_cards = 3 # Топ
    elif len(cards) == 5: min_cards = 5 # Мидл/Боттом

    if len(valid_cards) < min_cards:
        # Возвращаем очень плохой ранг для неполных рук
        return RANK_CLASS_HIGH_CARD + 100 + (min_cards - len(valid_cards))

    try:
        # Передаем только валидные карты в evaluate_hand
        # *valid_cards распаковывает список в аргументы
        return evaluate_hand(*valid_cards)
    except Exception as e:
        print(f"Error evaluating hand { [str(c) for c in valid_cards] }: {e}")
        # Возвращаем очень плохой ранг при ошибке
        return RANK_CLASS_HIGH_CARD + 200

def get_row_royalty(cards: List[Optional[Card]], row_name: str) -> int:
    """Считает роялти для одного ряда, игнорируя None."""
    valid_cards = [c for c in cards if c is not None]
    num_cards = len(valid_cards)
    royalty = 0

    if row_name == "top":
        if num_cards != 3: return 0 # Роялти только за полный ряд
        ranks = sorted([c.int_rank for c in valid_cards])
        counts = Counter(ranks)
        # Сет (AAA, KKK, ...)
        if len(counts) == 1:
            set_rank = ranks[0]
            royalty = ROYALTY_TOP_TRIPS.get(set_rank, 0)
        # Пара (AAx, KKx, ..., 66x)
        elif len(counts) == 2:
            # Находим ранг пары
            pair_rank = -1
            for r, c in counts.items():
                if c == 2:
                    pair_rank = r
                    break
            if pair_rank != -1:
                 royalty = ROYALTY_TOP_PAIRS.get(pair_rank, 0)
        return royalty

    elif row_name in ["middle", "bottom"]:
        if num_cards != 5: return 0 # Роялти только за полный ряд
        rank_eval = get_hand_rank_safe(valid_cards) # Получаем ранг 5-карточной руки
        table = ROYALTY_MIDDLE_POINTS if row_name == "middle" else ROYALTY_BOTTOM_POINTS
        bounds = ROYALTY_5CARD_BOUNDS

        max_royalty = 0
        # Ищем подходящую комбинацию в таблице границ
        for hand_name, (low_rank, high_rank) in bounds.items():
            # Особая обработка Трипса - только для мидла
            if hand_name == "Trips" and row_name != "middle":
                 continue

            points = table.get(hand_name, 0)
            if points > 0 and low_rank <= rank_eval <= high_rank:
                 # Нашли комбинацию, берем максимальное роялти (на случай пересечения?)
                 max_royalty = max(max_royalty, points)
                 # Можно выйти раньше, если таблицы не пересекаются
                 # break

        return max_royalty
    else:
        # Неизвестное имя ряда
        return 0

def check_board_foul(top: List[Optional[Card]], middle: List[Optional[Card]], bottom: List[Optional[Card]]) -> bool:
    """Проверяет фол доски (только для полных досок)."""
    # Проверяем, что все ряды имеют правильное количество карт (не None)
    if sum(1 for c in top if c) != 3 or \
       sum(1 for c in middle if c) != 5 or \
       sum(1 for c in bottom if c) != 5:
        return False # Неполная доска не считается фолом

    rank_t = get_hand_rank_safe(top)
    rank_m = get_hand_rank_safe(middle)
    rank_b = get_hand_rank_safe(bottom)

    # Меньший ранг -> Сильнее рука. Проверяем нарушение порядка.
    # rank_b должен быть <= rank_m, и rank_m должен быть <= rank_t
    return not (rank_b <= rank_m <= rank_t)

def get_fantasyland_entry_cards(top: List[Optional[Card]]) -> int:
    """
    Возвращает кол-во карт для ФЛ при входе (0 если нет квалификации).
    Принимает список карт верхнего ряда (может содержать None).
    """
    valid_cards = [c for c in top if c is not None]
    if len(valid_cards) != 3: return 0 # Квалификация только по полному ряду

    ranks = sorted([c.int_rank for c in valid_cards])
    counts = Counter(ranks)

    # Сет (222+)
    if len(counts) == 1:
        set_rank = ranks[0]
        if set_rank >= 2: return 17 # Сет от двоек и выше

    # Пара (QQ, KK, AA)
    elif len(counts) == 2:
        pair_rank = -1
        for r, c in counts.items():
            if c == 2:
                pair_rank = r
                break
        if pair_rank == 12: return 14 # QQ
        if pair_rank == 13: return 15 # KK
        if pair_rank == 14: return 16 # AA

    return 0 # Нет квалификации

def check_fantasyland_stay(top: List[Optional[Card]], middle: List[Optional[Card]], bottom: List[Optional[Card]]) -> bool:
    """
    Проверяет условия удержания ФЛ (Сет+ топ ИЛИ Каре+ боттом).
    Принимает списки карт рядов (могут содержать None).
    Доска НЕ должна быть фолом (это проверяется отдельно).
    """
    valid_top = [c for c in top if c is not None]
    valid_middle = [c for c in middle if c is not None]
    valid_bottom = [c for c in bottom if c is not None]

    # Условия проверяются только на полных досках
    if len(valid_top) != 3 or len(valid_middle) != 5 or len(valid_bottom) != 5:
        return False

    # 1. Сет или лучше на топе (Сет - единственная опция для 3 карт)
    ranks_top = sorted([c.int_rank for c in valid_top])
    if ranks_top[0] == ranks_top[1] == ranks_top[2]:
        return True # Сет на топе достаточен

    # 2. Каре или лучше на боттоме
    rank_b = get_hand_rank_safe(valid_bottom)
    # Проверяем, что ранг боттома соответствует Каре или лучше (SF, RF)
    if rank_b <= RANK_CLASS_QUADS:
        return True

    return False # Ни одно из условий не выполнено

def calculate_headsup_score(board1: 'PlayerBoard', board2: 'PlayerBoard') -> int:
    """
    Считает очки между двумя игроками (с точки зрения Игрока 1).
    Учитывает фолы, сравнение линий и роялти.
    """
    # Проверяем фолы на полных досках
    foul1 = board1.is_complete() and board1.check_and_set_foul()
    foul2 = board2.is_complete() and board2.check_and_set_foul()

    # Получаем роялти (get_total_royalty учтет фол)
    r1 = board1.get_total_royalty()
    r2 = board2.get_total_royalty()

    # --- Обработка фолов ---
    if foul1 and foul2:
        # Оба сфолили - счет 0 (роялти не учитываются)
        return 0
    if foul1:
        # Игрок 1 сфолил, Игрок 2 нет. Игрок 1 проигрывает 6 очков + роялти Игрока 2.
        return -(6 + r2)
    if foul2:
        # Игрок 2 сфолил, Игрок 1 нет. Игрок 1 выигрывает 6 очков + свои роялти.
        return 6 + r1

    # --- Никто не сфолил ---
    score1 = 0 # Очки Игрока 1 за сравнение линий

    # Сравниваем ранги рядов (используем кэшированный _get_rank)
    rank_t1 = board1._get_rank('top')
    rank_m1 = board1._get_rank('middle')
    rank_b1 = board1._get_rank('bottom')
    rank_t2 = board2._get_rank('top')
    rank_m2 = board2._get_rank('middle')
    rank_b2 = board2._get_rank('bottom')

    # Сравнение линий (меньший ранг = сильнее)
    wins1 = 0
    if rank_t1 < rank_t2: wins1 += 1
    elif rank_t2 < rank_t1: wins1 -= 1
    # else: ничья, 0 очков

    if rank_m1 < rank_m2: wins1 += 1
    elif rank_m2 < rank_m1: wins1 -= 1

    if rank_b1 < rank_b2: wins1 += 1
    elif rank_b2 < rank_b1: wins1 -= 1

    score1 += wins1 # +1 за каждую выигранную линию, -1 за проигранную

    # Бонус за скуп (scoop)
    if wins1 == 3: score1 += 3 # Выиграл все 3 линии
    elif wins1 == -3: score1 -= 3 # Проиграл все 3 линии

    # Добавляем разницу в роялти
    score1 += (r1 - r2)

    return score1
