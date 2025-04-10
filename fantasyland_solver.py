# fantasyland_solver.py
"""
Эвристический солвер для размещения 13 из N (14-17) карт в Фантазии.
Приоритеты: 1. Удержание ФЛ. 2. Максимизация роялти. 3. Не фол.
"""
import random # Добавлен импорт random
from typing import List, Tuple, Dict, Optional
from card import Card, card_to_str # Добавлен card_to_str
from board import PlayerBoard # Нужен для создания временных досок
from scoring import (check_fantasyland_stay, get_row_royalty, check_board_foul,
                     get_hand_rank_safe, RANK_CLASS_QUADS, RANK_CLASS_TRIPS,
                     RANK_CLASS_HIGH_CARD) # Добавлены импорты
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
            return None, None # Невозможно разместить
        n_discard = n_cards - n_place

        best_overall_placement = None
        best_overall_discarded = None
        best_overall_score = -2 # (-2: не найдено, -1: фол, 0: не ФЛ, 1: ФЛ)
        best_overall_royalty = -1

        # Ограничиваем количество перебираемых вариантов сброса для производительности
        # Можно сделать параметром конструктора
        max_discard_combinations = 50 # Увеличим немного для лучшего поиска

        discard_combinations_list = list(combinations(hand, n_discard))

        # Если комбинаций слишком много, делаем выборку
        if len(discard_combinations_list) > max_discard_combinations:
            # Добавляем "умные" варианты сброса (самые низкие карты)
            sorted_hand = sorted(hand, key=lambda c: c.int_rank)
            smart_discards = [tuple(sorted_hand[:n_discard])]
            # Добавляем случайные
            random_discards = random.sample(discard_combinations_list, max_discard_combinations - len(smart_discards))
            combinations_to_check = smart_discards + random_discards
        else:
            combinations_to_check = discard_combinations_list

        # Проверяем каждую комбинацию сброса
        for discarded_tuple in combinations_to_check:
            discarded_list = list(discarded_tuple)
            remaining_cards = [c for c in hand if c not in discarded_list] # 13 карт

            if len(remaining_cards) != 13: continue # Проверка на всякий случай

            # Ищем лучшее размещение для этих 13 карт
            current_best_placement = None
            current_best_score = -1 # (-1 фол, 0 не ФЛ, 1 ФЛ)
            current_max_royalty = -1

            # --- Стратегии поиска размещения ---
            placements_to_evaluate = []

            # Попытка 1: Собрать Каре+ на боттоме для удержания ФЛ
            placement_opt1 = self._try_build_strong_bottom(remaining_cards)
            if placement_opt1: placements_to_evaluate.append(placement_opt1)

            # Попытка 2: Собрать Сет на топе для удержания ФЛ
            placement_opt2 = self._try_build_set_top(remaining_cards)
            if placement_opt2: placements_to_evaluate.append(placement_opt2)

            # Попытка 3: Просто максимизировать роялти (базовая эвристика)
            placement_opt3 = self._try_maximize_royalty_heuristic(remaining_cards)
            if placement_opt3: placements_to_evaluate.append(placement_opt3)

            # Оцениваем найденные варианты размещений
            for placement in placements_to_evaluate:
                 score, royalty = self._evaluate_placement(placement)
                 # Отдаем приоритет удержанию ФЛ (score=1), затем роялти, затем просто не фол (score=0)
                 if score > current_best_score or \
                    (score == current_best_score and royalty > current_max_royalty):
                     current_best_score = score
                     current_max_royalty = royalty
                     current_best_placement = placement

            # Обновляем лучший общий результат по всем вариантам сброса
            if current_best_placement: # Если для этого сброса нашли валидное размещение
                 if current_best_score > best_overall_score or \
                    (current_best_score == best_overall_score and current_max_royalty > best_overall_royalty):
                     best_overall_score = current_best_score
                     best_overall_royalty = current_max_royalty
                     best_overall_placement = current_best_placement
                     best_overall_discarded = discarded_list

        # Если вообще не нашли валидного размещения ни для одного сброса
        if best_overall_placement is None:
             print("FL Solver Warning: No valid non-foul placement found for any discard combination.")
             # Пытаемся вернуть хоть какое-то не фол размещение, даже с 0 роялти
             # Берем первый попавшийся сброс и пытаемся разместить хоть как-то
             if discard_combinations_list:
                  first_discard = list(discard_combinations_list[0])
                  first_remaining = [c for c in hand if c not in first_discard]
                  if len(first_remaining) == 13:
                       # Простое размещение по убыванию ранга
                       sorted_remaining = sorted(first_remaining, key=lambda c: c.int_rank, reverse=True)
                       simple_placement = {'bottom': sorted_remaining[0:5], 'middle': sorted_remaining[5:10], 'top': sorted_remaining[10:13]}
                       if not check_board_foul(simple_placement['top'], simple_placement['middle'], simple_placement['bottom']):
                            print("FL Solver: Falling back to simple non-foul placement.")
                            return simple_placement, first_discard

             # Если и это не помогло, возвращаем None (что приведет к фолу в вызывающем коде)
             return None, None


        # print(f"FL Solver Best: Score={best_overall_score}, Royalty={best_overall_royalty}, Discarded: {[card_to_str(c) for c in best_overall_discarded]}")
        return best_overall_placement, best_overall_discarded

    def _evaluate_placement(self, placement: Dict[str, List[Card]]) -> Tuple[int, int]:
        """Оценивает размещение: (-1 фол, 0 не ФЛ, 1 ФЛ), сумма роялти."""
        if not placement or len(placement.get('top', [])) != 3 or len(placement.get('middle', [])) != 5 or len(placement.get('bottom', [])) != 5:
             return -1, -1 # Некорректное размещение

        top, middle, bottom = placement['top'], placement['middle'], placement['bottom']
        if check_board_foul(top, middle, bottom):
            return -1, -1 # Фол

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
        # Инициализируем худшим возможным рангом + запас
        best_rank = RANK_CLASS_HIGH_CARD + 100
        found_hand = False

        for combo in combinations(cards, n):
            combo_list = list(combo)
            rank = get_hand_rank_safe(combo_list)
            if rank < best_rank:
                best_rank = rank
                best_hand = combo_list
                found_hand = True

        # Возвращаем копию списка, чтобы избежать мутаций
        return list(best_hand) if found_hand else None


    def _try_build_strong_bottom(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Пытается собрать Каре+ на боттоме, остальное эвристически."""
        if len(cards) != 13: return None

        best_stay_placement = None
        max_royalty = -1

        # Ищем Каре+ комбинации из 5 карт на боттоме
        for bottom_combo in combinations(cards, 5):
            bottom_list = list(bottom_combo)
            rank_b = get_hand_rank_safe(bottom_list)
            # Проверяем, что это Каре или лучше (меньший ранг = лучше)
            if rank_b <= RANK_CLASS_QUADS:
                remaining8 = [c for c in cards if c not in bottom_list]
                if len(remaining8) != 8: continue # Проверка

                # Пытаемся разместить оставшиеся 8 на мидл(5) и топ(3)
                # Ищем лучшую руку для мидла
                middle_list = self._find_best_hand(remaining8, 5)
                if middle_list:
                    top_list = [c for c in remaining8 if c not in middle_list]
                    if len(top_list) == 3:
                        rank_m = get_hand_rank_safe(middle_list)
                        rank_t = get_hand_rank_safe(top_list)

                        # Проверяем фол (rank_b <= rank_m <= rank_t)
                        if not (rank_b <= rank_m <= rank_t): continue

                        # Считаем роялти
                        royalty = (get_row_royalty(top_list, 'top') +
                                   get_row_royalty(middle_list, 'middle') +
                                   get_row_royalty(bottom_list, 'bottom'))

                        # Обновляем лучший вариант с удержанием ФЛ по роялти
                        if royalty > max_royalty:
                             max_royalty = royalty
                             best_stay_placement = {'top': top_list, 'middle': middle_list, 'bottom': bottom_list}

        return best_stay_placement # Возвращаем лучший найденный вариант с Каре+ на боттоме

    def _try_build_set_top(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Пытается собрать Сет на топе, остальное эвристически."""
        if len(cards) != 13: return None

        best_stay_placement = None
        max_royalty = -1

        # Ищем Сет комбинации из 3 карт на топе
        rank_counts = Counter(c.int_rank for c in cards)
        possible_set_ranks = [rank for rank, count in rank_counts.items() if count >= 3]

        for set_rank in possible_set_ranks:
            # Выбираем 3 карты для сета (берем первые попавшиеся)
            set_cards = [c for c in cards if c.int_rank == set_rank][:3]
            remaining10 = [c for c in cards if c not in set_cards]
            if len(remaining10) != 10: continue # Проверка

            # Пытаемся разместить оставшиеся 10 на мидл(5) и боттом(5)
            # Ищем лучшую руку для боттома из 10 карт
            bottom_list = self._find_best_hand(remaining10, 5)
            if bottom_list:
                 middle_list = [c for c in remaining10 if c not in bottom_list]
                 if len(middle_list) == 5:
                     rank_b = get_hand_rank_safe(bottom_list)
                     rank_m = get_hand_rank_safe(middle_list)
                     rank_t = get_hand_rank_safe(set_cards) # Ранг сета

                     # Проверяем фол (rank_b <= rank_m <= rank_t)
                     if not (rank_b <= rank_m <= rank_t): continue

                     # Считаем роялти
                     royalty = (get_row_royalty(set_cards, 'top') +
                                get_row_royalty(middle_list, 'middle') +
                                get_row_royalty(bottom_list, 'bottom'))

                     # Обновляем лучший вариант с удержанием ФЛ по роялти
                     if royalty > max_royalty:
                          max_royalty = royalty
                          best_stay_placement = {'top': set_cards, 'middle': middle_list, 'bottom': bottom_list}

        return best_stay_placement # Возвращаем лучший найденный вариант с Сетом на топе

    def _try_maximize_royalty_heuristic(self, cards: List[Card]) -> Optional[Dict[str, List[Card]]]:
        """Простая эвристика: размещаем лучшие возможные руки на боттом/мидл/топ без фола."""
        if len(cards) != 13: return None

        best_placement = None
        max_royalty = -1

        # Генерируем несколько кандидатов на размещение
        # Перебираем все комбинации для боттома (может быть много!)
        # Ограничим количество итераций для скорости
        bottom_combinations = list(combinations(cards, 5))
        if len(bottom_combinations) > 100: # Ограничение
             bottom_combinations = random.sample(bottom_combinations, 100)

        for bottom_combo in bottom_combinations:
            bottom_list = list(bottom_combo)
            rank_b = get_hand_rank_safe(bottom_list)
            remaining8 = [c for c in cards if c not in bottom_list]
            if len(remaining8) != 8: continue

            # Ищем лучшую руку для мидла из оставшихся 8
            middle_list = self._find_best_hand(remaining8, 5)
            if middle_list:
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

                     # Обновляем лучшее размещение по роялти
                     if royalty > max_royalty:
                          max_royalty = royalty
                          best_placement = {'top': top_list, 'middle': middle_list, 'bottom': bottom_list}

        # Если не нашли валидного (маловероятно, но возможно), пробуем простую сортировку
        if not best_placement:
             sorted_cards = sorted(cards, key=lambda c: c.int_rank, reverse=True)
             placement = {'bottom': sorted_cards[0:5], 'middle': sorted_cards[5:10], 'top': sorted_cards[10:13]}
             if not check_board_foul(placement['top'], placement['middle'], placement['bottom']):
                 royalty = self._evaluate_placement(placement)[1]
                 if royalty > max_royalty: # max_royalty все еще -1
                      best_placement = placement

        return best_placement
