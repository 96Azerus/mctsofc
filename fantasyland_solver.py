# fantasyland_solver.py
"""
Эвристический солвер для размещения 13 из N (14-17) карт в Фантазии.
Приоритеты: 1. Удержание ФЛ. 2. Максимизация роялти. 3. Не фол.
"""
import random
from typing import List, Tuple, Dict, Optional
# Используем Card (алиас PhevaluatorCard) и RANK_ORDER_MAP
from card import Card, card_to_str, RANK_ORDER_MAP
from board import PlayerBoard
from scoring import (check_fantasyland_stay, get_row_royalty, check_board_foul,
                     get_hand_rank_safe, RANK_CLASS_QUADS, RANK_CLASS_TRIPS,
                     RANK_CLASS_HIGH_CARD)
from itertools import combinations, permutations
from collections import Counter

class FantasylandSolver:

    def solve(self, hand: List[Card]) -> Tuple[Optional[Dict[str, List[Card]]], Optional[List[Card]]]:
        """
        Принимает N карт (14-17), возвращает лучшее размещение 13 карт и список сброшенных.
        Возвращает (None, None) если не найдено валидных размещений (что маловероятно).
        """
        n_cards = len(hand)
        n_place = 13
        if n_cards < n_place:
            print(f"Error in FL Solver: Hand size {n_cards} is less than 13.")
            return None, None
        n_discard = n_cards - n_place

        best_overall_placement = None
        best_overall_discarded = None
        best_overall_score = -2
        best_overall_royalty = -1
        max_discard_combinations = 50

        discard_combinations_list = list(combinations(hand, n_discard))

        if len(discard_combinations_list) > max_discard_combinations:
            # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
            sorted_hand = sorted(hand, key=lambda c: RANK_ORDER_MAP.get(c.rank, 0))
            # -----------------------------------------
            smart_discards = [tuple(sorted_hand[:n_discard])]
            random_discards = random.sample(discard_combinations_list, max_discard_combinations - len(smart_discards))
            combinations_to_check = smart_discards + random_discards
        else:
            combinations_to_check = discard_combinations_list

        for discarded_tuple in combinations_to_check:
            discarded_list = list(discarded_tuple)
            remaining_cards = [c for c in hand if c not in discarded_list]
            if len(remaining_cards) != 13: continue

            current_best_placement = None
            current_best_score = -1
            current_max_royalty = -1
            placements_to_evaluate = []

            placement_opt1 = self._try_build_strong_bottom(remaining_cards)
            if placement_opt1: placements_to_evaluate.append(placement_opt1)
            placement_opt2 = self._try_build_set_top(remaining_cards)
            if placement_opt2: placements_to_evaluate.append(placement_opt2)
            placement_opt3 = self._try_maximize_royalty_heuristic(remaining_cards)
            if placement_opt3: placements_to_evaluate.append(placement_opt3)

            for placement in placements_to_evaluate:
                 score, royalty = self._evaluate_placement(placement)
                 if score > current_best_score or \
                    (score == current_best_score and royalty > current_max_royalty):
                     current_best_score = score
                     current_max_royalty = royalty
                     current_best_placement = placement

            if current_best_placement:
                 if current_best_score > best_overall_score or \
                    (current_best_score == best_overall_score and current_max_royalty > best_overall_royalty):
                     best_overall_score = current_best_score
                     best_overall_royalty = current_max_royalty
                     best_overall_placement = current_best_placement
                     best_overall_discarded = discarded_list

        if best_overall_placement is None:
             print("FL Solver Warning: No valid non-foul placement found for any discard combination.")
             if discard_combinations_list:
                  first_discard = list(discard_combinations_list[0])
                  first_remaining = [c for c in hand if c not in first_discard]
                  if len(first_remaining) == 13:
                       # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
                       sorted_remaining = sorted(first_remaining, key=lambda c: RANK_ORDER_MAP.get(c.rank, 0), reverse=True)
                       # -----------------------------------------
                       simple_placement = {'bottom': sorted_remaining[0:5], 'middle': sorted_remaining[5:10], 'top': sorted_remaining[10:13]}
                       if not check_board_foul(simple_placement['top'], simple_placement['middle'], simple_placement['bottom']):
                            print("FL Solver: Falling back to simple non-foul placement.")
                            return simple_placement, first_discard
             return None, None

        return best_overall_placement, best_overall_discarded

    def _evaluate_placement(self, placement: Dict[str, List[Card]]) -> Tuple[int, int]:
        """Оценивает размещение: (-1 фол, 0 не ФЛ, 1 ФЛ), сумма роялти."""
        if not placement or len(placement.get('top', [])) != 3 or len(placement.get('middle', [])) != 5 or len(placement.get('bottom', [])) != 5:
             return -1, -1
        top, middle, bottom = placement['top'], placement['middle'], placement['bottom']
        if check_board_foul(top, middle, bottom): return -1, -1
        stays_in_fl = check_fantasyland_stay(top, middle, bottom)
        total_royalty = (get_row_royalty(top, 'top') + get_row_royalty(middle, 'middle') + get_row_royalty(bottom, 'bottom'))
        score = 1 if stays_in_fl else 0
        return score, total_royalty

    def _find_best_hand(self, cards: List[Card], n: int) -> Optional[List[Card]]:
        """Находит лучшую n-карточную комбинацию из списка карт."""
        if len(cards) < n: return None
        best_hand = None
        best_rank = RANK_CLASS_HIGH_CARD + 100
        found_hand = False
        for combo in combinations(cards, n):
            combo_list = list(combo)
            rank = get_hand_rank_safe(combo_list)
            if rank < best_rank: best_rank = rank; best_hand = combo_list; found_hand = True
        return list(best_hand) if found_hand else None

    def _try_build_strong_bottom(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Пытается собрать Каре+ на боттоме, остальное эвристически."""
        if len(cards) != 13: return None
        best_stay_placement = None
        max_royalty = -1
        for bottom_combo in combinations(cards, 5):
            bottom_list = list(bottom_combo)
            rank_b = get_hand_rank_safe(bottom_list)
            if rank_b <= RANK_CLASS_QUADS:
                remaining8 = [c for c in cards if c not in bottom_list]
                if len(remaining8) != 8: continue
                middle_list = self._find_best_hand(remaining8, 5)
                if middle_list:
                    top_list = [c for c in remaining8 if c not in middle_list]
                    if len(top_list) == 3:
                        rank_m = get_hand_rank_safe(middle_list)
                        rank_t = get_hand_rank_safe(top_list)
                        if not (rank_b <= rank_m <= rank_t): continue
                        royalty = (get_row_royalty(top_list, 'top') + get_row_royalty(middle_list, 'middle') + get_row_royalty(bottom_list, 'bottom'))
                        if royalty > max_royalty: max_royalty = royalty; best_stay_placement = {'top': top_list, 'middle': middle_list, 'bottom': bottom_list}
        return best_stay_placement

    def _try_build_set_top(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Пытается собрать Сет на топе, остальное эвристически."""
        if len(cards) != 13: return None
        best_stay_placement = None
        max_royalty = -1
        # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
        rank_counts = Counter(RANK_ORDER_MAP.get(c.rank, 0) for c in cards if hasattr(c, 'rank'))
        # -----------------------------------------
        possible_set_ranks = [rank for rank, count in rank_counts.items() if count >= 3]
        for set_rank in possible_set_ranks:
            # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
            set_cards = [c for c in cards if hasattr(c, 'rank') and RANK_ORDER_MAP.get(c.rank, 0) == set_rank][:3]
            # -----------------------------------------
            remaining10 = [c for c in cards if c not in set_cards]
            if len(remaining10) != 10: continue
            bottom_list = self._find_best_hand(remaining10, 5)
            if bottom_list:
                 middle_list = [c for c in remaining10 if c not in bottom_list]
                 if len(middle_list) == 5:
                     rank_b = get_hand_rank_safe(bottom_list)
                     rank_m = get_hand_rank_safe(middle_list)
                     rank_t = get_hand_rank_safe(set_cards)
                     if not (rank_b <= rank_m <= rank_t): continue
                     royalty = (get_row_royalty(set_cards, 'top') + get_row_royalty(middle_list, 'middle') + get_row_royalty(bottom_list, 'bottom'))
                     if royalty > max_royalty: max_royalty = royalty; best_stay_placement = {'top': set_cards, 'middle': middle_list, 'bottom': bottom_list}
        return best_stay_placement

    def _try_maximize_royalty_heuristic(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Простая эвристика: размещаем лучшие возможные руки на боттом/мидл/топ без фола."""
        if len(cards) != 13: return None
        best_placement = None
        max_royalty = -1
        bottom_combinations = list(combinations(cards, 5))
        if len(bottom_combinations) > 100: bottom_combinations = random.sample(bottom_combinations, 100)
        for bottom_combo in bottom_combinations:
            bottom_list = list(bottom_combo)
            rank_b = get_hand_rank_safe(bottom_list)
            remaining8 = [c for c in cards if c not in bottom_list]
            if len(remaining8) != 8: continue
            middle_list = self._find_best_hand(remaining8, 5)
            if middle_list:
                 top_list = [c for c in remaining8 if c not in middle_list]
                 if len(top_list) == 3:
                     rank_m = get_hand_rank_safe(middle_list)
                     rank_t = get_hand_rank_safe(top_list)
                     if not (rank_b <= rank_m <= rank_t): continue
                     royalty = (get_row_royalty(top_list, 'top') + get_row_royalty(middle_list, 'middle') + get_row_royalty(bottom_list, 'bottom'))
                     if royalty > max_royalty: max_royalty = royalty; best_placement = {'top': top_list, 'middle': middle_list, 'bottom': bottom_list}
        if not best_placement:
             # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
             sorted_cards = sorted(cards, key=lambda c: RANK_ORDER_MAP.get(c.rank, 0), reverse=True)
             # -----------------------------------------
             placement = {'bottom': sorted_cards[0:5], 'middle': sorted_cards[5:10], 'top': sorted_cards[10:13]}
             if not check_board_foul(placement['top'], placement['middle'], placement['bottom']):
                 royalty = self._evaluate_placement(placement)[1]
                 if royalty > max_royalty: best_placement = placement
        return best_placement
