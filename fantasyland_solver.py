# fantasyland_solver.py
"""
Эвристический солвер для размещения 13 из N (14-17) карт в Фантазии.
Приоритеты: 1. Удержание ФЛ. 2. Максимизация роялти. 3. Не фол.
"""
from typing import List, Tuple, Dict, Optional
from card import Card
from board import PlayerBoard # Нужен для создания временных досок
from scoring import (check_fantasyland_stay, get_row_royalty, check_board_foul,
                     get_hand_rank_safe, RANK_CLASS_QUADS, RANK_CLASS_TRIPS)
from itertools import combinations, permutations
from collections import Counter

class FantasylandSolver:

    def solve(self, hand: List[Card]) -> Tuple[Optional[Dict[str, List[Card]]], Optional[List[Card]]]:
        """
        Принимает N карт (14-17), возвращает лучшее размещение 13 карт и список сброшенных.
        Возвращает (None, None) если не найдено валидных размещений.
        """
        n_cards = len(hand)
        n_place = 13
        if n_cards < n_place: return None, None
        n_discard = n_cards - n_place

        best_overall_placement = None
        best_overall_discarded = None
        best_overall_score = -1 # (-1: фол, 0: не ФЛ, 1: ФЛ)
        best_overall_royalty = -1

        # Ограничиваем количество перебираемых вариантов сброса для производительности
        max_discard_combinations = 20 # Можно настроить
        
        discard_combinations = list(combinations(hand, n_discard))
        if len(discard_combinations) > max_discard_combinations:
            discard_combinations_sample = random.sample(discard_combinations, max_discard_combinations)
        else:
            discard_combinations_sample = discard_combinations

        for discarded_tuple in discard_combinations_sample:
            discarded_list = list(discarded_tuple)
            remaining_cards = [c for c in hand if c not in discarded_list] # 13 карт

            # Ищем лучшее размещение для этих 13 карт
            current_best_placement = None
            current_best_score = -1
            current_max_royalty = -1

            # Попытка 1: Собрать Каре+ на боттоме для удержания ФЛ
            placement_opt1 = self._try_build_strong_bottom(remaining_cards)
            if placement_opt1:
                 score, royalty = self._evaluate_placement(placement_opt1)
                 if score > current_best_score or (score == current_best_score and royalty > current_max_royalty):
                     current_best_score = score
                     current_max_royalty = royalty
                     current_best_placement = placement_opt1

            # Попытка 2: Собрать Сет на топе для удержания ФЛ
            placement_opt2 = self._try_build_set_top(remaining_cards)
            if placement_opt2:
                 score, royalty = self._evaluate_placement(placement_opt2)
                 if score > current_best_score or (score == current_best_score and royalty > current_max_royalty):
                     current_best_score = score
                     current_max_royalty = royalty
                     current_best_placement = placement_opt2

            # Попытка 3: Просто максимизировать роялти (базовая эвристика)
            # Запускаем, только если не нашли вариант с удержанием ФЛ
            if current_best_score < 1:
                placement_opt3 = self._try_maximize_royalty_heuristic(remaining_cards)
                if placement_opt3:
                     score, royalty = self._evaluate_placement(placement_opt3)
                     if score > current_best_score or (score == current_best_score and royalty > current_max_royalty):
                         current_best_score = score
                         current_max_royalty = royalty
                         current_best_placement = placement_opt3

            # Обновляем лучший общий результат
            if current_best_score > best_overall_score or \
               (current_best_score == best_overall_score and current_max_royalty > best_overall_royalty):
                best_overall_score = current_best_score
                best_overall_royalty = current_max_royalty
                best_overall_placement = current_best_placement
                best_overall_discarded = discarded_list

        # print(f"FL Solver Best: Score={best_overall_score}, Royalty={best_overall_royalty}")
        return best_overall_placement, best_overall_discarded

    def _evaluate_placement(self, placement: Dict[str, List[Card]]) -> Tuple[int, int]:
        """Оценивает размещение: (-1 фол, 0 не ФЛ, 1 ФЛ), сумма роялти."""
        top, middle, bottom = placement['top'], placement['middle'], placement['bottom']
        if check_board_foul(top, middle, bottom):
            return -1, -1
        stays_in_fl = check_fantasyland_stay(top, middle, bottom)
        total_royalty = (get_row_royalty(top, 'top') +
                         get_row_royalty(middle, 'middle') +
                         get_row_royalty(bottom, 'bottom'))
        score = 1 if stays_in_fl else 0
        return score, total_royalty

    def _find_best_hand(self, cards: List[Card], n: int) -> Optional[List[Card]]:
        """Находит лучшую n-карточную комбинацию из списка карт."""
        if len(cards) < n: return None
        best_hand = None
        best_rank = RANK_CLASS_HIGH_CARD + 1
        for combo in combinations(cards, n):
            rank = get_hand_rank_safe(list(combo))
            if rank < best_rank:
                best_rank = rank
                best_hand = list(combo)
        return best_hand

    def _try_build_strong_bottom(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Пытается собрать Каре+ на боттоме, остальное эвристически."""
        if len(cards) != 13: return None
        
        best_stay_placement = None
        max_royalty = -1

        # Ищем Каре+ комбинации из 5 карт
        for bottom_combo in combinations(cards, 5):
            bottom_list = list(bottom_combo)
            rank_b = get_hand_rank_safe(bottom_list)
            if rank_b <= RANK_CLASS_QUADS: # Нашли Каре или лучше
                remaining8 = [c for c in cards if c not in bottom_list]
                # Пытаемся разместить оставшиеся 8 на мидл(5) и топ(3)
                for middle_combo in combinations(remaining8, 5):
                    middle_list = list(middle_combo)
                    top_list = [c for c in remaining8 if c not in middle_list]
                    if len(top_list) == 3:
                        rank_m = get_hand_rank_safe(middle_list)
                        rank_t = get_hand_rank_safe(top_list)
                        # Проверяем фол
                        if not (rank_b <= rank_m <= rank_t): continue
                        
                        # Считаем роялти
                        royalty = (get_row_royalty(top_list, 'top') +
                                   get_row_royalty(middle_list, 'middle') +
                                   get_row_royalty(bottom_list, 'bottom'))
                                   
                        if royalty > max_royalty:
                             max_royalty = royalty
                             best_stay_placement = {'top': top_list, 'middle': middle_list, 'bottom': bottom_list}
                             
        return best_stay_placement # Возвращаем лучший найденный вариант с Каре+ на боттоме

    def _try_build_set_top(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Пытается собрать Сет на топе, остальное эвристически."""
        if len(cards) != 13: return None

        best_stay_placement = None
        max_royalty = -1

        # Ищем Сет комбинации из 3 карт
        rank_counts = Counter(c.int_rank for c in cards)
        possible_sets = [rank for rank, count in rank_counts.items() if count >= 3]

        for set_rank in possible_sets:
            # Выбираем 3 карты для сета
            set_cards = [c for c in cards if c.int_rank == set_rank][:3]
            remaining10 = [c for c in cards if c not in set_cards]
            
            # Пытаемся разместить оставшиеся 10 на мидл(5) и боттом(5)
            for middle_combo in combinations(remaining10, 5):
                 middle_list = list(middle_combo)
                 bottom_list = [c for c in remaining10 if c not in middle_list]
                 if len(bottom_list) == 5:
                     rank_m = get_hand_rank_safe(middle_list)
                     rank_b = get_hand_rank_safe(bottom_list)
                     rank_t = get_hand_rank_safe(set_cards) # Ранг сета

                     # Проверяем фол
                     if not (rank_b <= rank_m <= rank_t): continue
                     
                     royalty = (get_row_royalty(set_cards, 'top') +
                                get_row_royalty(middle_list, 'middle') +
                                get_row_royalty(bottom_list, 'bottom'))
                                
                     if royalty > max_royalty:
                          max_royalty = royalty
                          best_stay_placement = {'top': set_cards, 'middle': middle_list, 'bottom': bottom_list}

        return best_stay_placement # Возвращаем лучший найденный вариант с Сетом на топе

    def _try_maximize_royalty_heuristic(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Простая эвристика: размещаем лучшие возможные руки на боттом/мидл/топ без фола."""
        if len(cards) != 13: return None

        best_placement = None
        max_royalty = -1

        # Генерируем несколько кандидатов на размещение (не все 72072!)
        # Кандидат 1: Лучшие 5 боттом, лучшие 5 из 8 мидл, остаток топ
        for bottom_combo in combinations(cards, 5):
            bottom_list = list(bottom_combo)
            rank_b = get_hand_rank_safe(bottom_list)
            remaining8 = [c for c in cards if c not in bottom_list]
            
            middle_list = self._find_best_hand(remaining8, 5)
            if middle_list:
                 rank_m = get_hand_rank_safe(middle_list)
                 top_list = [c for c in remaining8 if c not in middle_list]
                 if len(top_list) == 3:
                     rank_t = get_hand_rank_safe(top_list)
                     
                     if not (rank_b <= rank_m <= rank_t): continue # Фол
                     
                     royalty = (get_row_royalty(top_list, 'top') +
                                get_row_royalty(middle_list, 'middle') +
                                get_row_royalty(bottom_list, 'bottom'))
                                
                     if royalty > max_royalty:
                          max_royalty = royalty
                          best_placement = {'top': top_list, 'middle': middle_list, 'bottom': bottom_list}
            # Ограничим количество проверяемых комбинаций боттома для скорости
            # if max_royalty > -1: break # Можно остановиться после первого валидного, но лучше проверить еще

        # Если не нашли валидного, пробуем простую сортировку
        if not best_placement:
             sorted_cards = sorted(cards, key=lambda c: c.int_rank, reverse=True)
             placement = {'bottom': sorted_cards[0:5], 'middle': sorted_cards[5:10], 'top': sorted_cards[10:13]}
             if not check_board_foul(placement['top'], placement['middle'], placement['bottom']):
                 royalty = self._evaluate_placement(placement)[1]
                 if royalty > max_royalty:
                      best_placement = placement
                      
        return best_placement