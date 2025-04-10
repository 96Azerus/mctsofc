# game_state.py
"""
Определяет класс GameState, управляющий полным состоянием игры
OFC Pineapple для двух игроков.
"""
import copy
import random
from itertools import combinations, permutations
from typing import List, Tuple, Optional, Set, Dict, Any

# Импортируем зависимости из других наших модулей
from card import Card, card_to_str
from deck import Deck
from board import PlayerBoard
from scoring import calculate_headsup_score # Функция подсчета очков

class GameState:
    NUM_PLAYERS = 2

    def __init__(self,
                 boards: Optional[List[PlayerBoard]] = None,
                 deck: Optional[Deck] = None,
                 discard_pile: Optional[List[Card]] = None,
                 dealer_idx: int = 0,
                 current_player_idx: Optional[int] = None,
                 street: int = 1,
                 cards_dealt_current_street: Optional[List[Card]] = None,
                 fantasyland_status: Optional[List[bool]] = None,
                 next_fantasyland_status: Optional[List[bool]] = None,
                 fantasyland_cards_to_deal: Optional[List[int]] = None,
                 is_fantasyland_round: bool = False,
                 fantasyland_hands: Optional[List[Optional[List[Card]]]] = None,
                 _player_acted_this_street: Optional[List[bool]] = None):

        self.boards: List[PlayerBoard] = boards if boards is not None else [PlayerBoard() for _ in range(self.NUM_PLAYERS)]
        self.deck: Deck = deck if deck is not None else Deck()
        self.discard_pile: List[Card] = discard_pile if discard_pile is not None else []
        self.dealer_idx: int = dealer_idx
        self.current_player_idx: int = (1 - dealer_idx) if current_player_idx is None else current_player_idx
        self.street: int = street
        self.cards_dealt_current_street: Optional[List[Card]] = cards_dealt_current_street
        self.fantasyland_status: List[bool] = fantasyland_status if fantasyland_status is not None else [False] * self.NUM_PLAYERS
        self.next_fantasyland_status: List[bool] = next_fantasyland_status if next_fantasyland_status is not None else [False] * self.NUM_PLAYERS
        self.fantasyland_cards_to_deal: List[int] = fantasyland_cards_to_deal if fantasyland_cards_to_deal is not None else [0] * self.NUM_PLAYERS
        self.is_fantasyland_round: bool = is_fantasyland_round
        self.fantasyland_hands: List[Optional[List[Card]]] = fantasyland_hands if fantasyland_hands is not None else [None] * self.NUM_PLAYERS
        self._player_acted_this_street: List[bool] = _player_acted_this_street if _player_acted_this_street is not None else [False] * self.NUM_PLAYERS

    def get_current_player_board(self) -> PlayerBoard: return self.boards[self.current_player_idx]
    def get_opponent_board(self) -> PlayerBoard: return self.boards[1 - self.current_player_idx]

    def start_new_round(self, dealer_button_idx: int):
        """Начинает новый раунд, сохраняя статус ФЛ."""
        current_fl_status = list(self.fantasyland_status) # Сохраняем статус ФЛ
        # Сбрасываем состояние, передавая сохраненный статус ФЛ
        self.__init__(dealer_idx=dealer_button_idx, fantasyland_status=current_fl_status)
        self.is_fantasyland_round = any(self.fantasyland_status)

        if self.is_fantasyland_round:
            self._deal_fantasyland_hands()
            first_player = 1 - self.dealer_idx
            if not self.fantasyland_status[first_player]:
                self.current_player_idx = first_player
                self._deal_street()
            else:
                self.current_player_idx = first_player
        else:
            self._deal_street()

    def _deal_street(self):
        """Раздает карты для текущей улицы текущему игроку."""
        if self.cards_dealt_current_street is not None: return
        num_cards = 5 if self.street == 1 else 3
        try:
            self.cards_dealt_current_street = self.deck.deal(num_cards)
        except ValueError:
            self.cards_dealt_current_street = []

    def _deal_fantasyland_hands(self):
        """Раздает 14-17 карт игрокам в статусе Фантазии."""
        for i in range(self.NUM_PLAYERS):
            if self.fantasyland_status[i]:
                num_cards = self.fantasyland_cards_to_deal[i]
                if num_cards == 0: num_cards = 14 # Стандарт по умолчанию
                try:
                    self.fantasyland_hands[i] = self.deck.deal(num_cards)
                except ValueError:
                    print(f"Error: Not enough cards for Fantasyland player {i}")
                    self.fantasyland_hands[i] = []

    def get_legal_actions(self) -> List[Any]:
        """Возвращает легальные действия для текущего состояния."""
        if self.is_fantasyland_round and self.fantasyland_status[self.current_player_idx]:
            hand = self.fantasyland_hands[self.current_player_idx]
            return [(hand, [])] if hand else [] # Мета-действие для солвера
        elif self.street == 1:
            return self._get_legal_actions_street1()
        else:
            return self._get_legal_actions_pineapple()

    def _get_legal_actions_street1(self) -> List[Tuple[List[Tuple[Card, str, int]], List[Card]]]:
        """
        Генерирует действия для первой улицы (размещение 5 карт).
        Возвращает список действий. Формат: ([(карта, ряд, индекс)...], [])
        РЕАЛИЗОВАНА ПРОСТАЯ ЭВРИСТИКА - ВОЗВРАЩАЕТ ОДИН ВАРИАНТ.
        """
        hand = self.cards_dealt_current_street
        if not hand or len(hand) != 5: return []
        board = self.get_current_player_board()
        available_slots = board.get_available_slots()
        if len(available_slots) < 5: return []

        # Эвристика: Попробуем разные базовые размещения и выберем лучшее по простой оценке
        best_placement_action = None
        best_score = -float('inf')

        # Вариант 1: Все на боттом
        bot_indices = [s[1] for s in available_slots if s[0] == 'bottom']
        if len(bot_indices) >= 5:
            placement = [(hand[i], 'bottom', bot_indices[i]) for i in range(5)]
            score = self._evaluate_street1_placement(placement)
            if score > best_score:
                best_score = score
                best_placement_action = (placement, [])

        # Вариант 2: 3 на боттом, 2 на мидл (сильнейшие 3 вниз)
        mid_indices = [s[1] for s in available_slots if s[0] == 'middle']
        if len(bot_indices) >= 3 and len(mid_indices) >= 2:
            sorted_hand = sorted(hand, key=lambda c: c.int_rank, reverse=True)
            placement = []
            placement.extend([(sorted_hand[i], 'bottom', bot_indices[i]) for i in range(3)])
            placement.extend([(sorted_hand[i+3], 'middle', mid_indices[i]) for i in range(2)])
            score = self._evaluate_street1_placement(placement)
            if score > best_score:
                best_score = score
                best_placement_action = (placement, [])

        # Вариант 3: 3 на мидл, 2 на топ (сильнейшие 3 в середину)
        top_indices = [s[1] for s in available_slots if s[0] == 'top']
        if len(mid_indices) >= 3 and len(top_indices) >= 2:
             sorted_hand = sorted(hand, key=lambda c: c.int_rank, reverse=True)
             placement = []
             placement.extend([(sorted_hand[i], 'middle', mid_indices[i]) for i in range(3)])
             placement.extend([(sorted_hand[i+3], 'top', top_indices[i]) for i in range(2)])
             score = self._evaluate_street1_placement(placement)
             if score > best_score:
                 best_score = score
                 best_placement_action = (placement, [])
                 
        # TODO: Добавить больше эвристических вариантов размещения

        return [best_placement_action] if best_placement_action else []

    def _evaluate_street1_placement(self, placements: List[Tuple[Card, str, int]]) -> float:
        """Простая оценка эвристики размещения 5 карт."""
        # Пример: сумма рангов карт (чем выше, тем лучше), штраф за высокие карты на топе
        score = 0
        for card, row, idx in placements:
            score += card.int_rank
            if row == 'top' and card.int_rank > 10: # Штраф за J+ на топе
                score -= 10
            if row == 'middle' and card.int_rank > 12: # Небольшой штраф за K,A на мидле
                 score -= 5
        return score


    def _get_legal_actions_pineapple(self) -> List[Tuple[Tuple[Card, str, int], Tuple[Card, str, int], Card]]:
        """Генерирует действия для улиц 2-5."""
        hand = self.cards_dealt_current_street
        if not hand or len(hand) != 3: return []
        board = self.get_current_player_board()
        available_slots = board.get_available_slots()
        if len(available_slots) < 2: return []
        actions = []
        for i in range(3):
            discarded_card = hand[i]
            cards_to_place = [hand[j] for j in range(3) if i != j]
            card1, card2 = cards_to_place[0], cards_to_place[1]
            for slot1_info, slot2_info in combinations(available_slots, 2):
                row1, idx1 = slot1_info
                row2, idx2 = slot2_info
                # Действие 1
                actions.append(((card1, row1, idx1), (card2, row2, idx2), discarded_card))
                # Действие 2 (карты в слотах меняются местами)
                actions.append(((card2, row1, idx1), (card1, row2, idx2), discarded_card))
        return actions

    def apply_action(self, action: Any):
        """Применяет любое легальное действие."""
        if self.is_fantasyland_round and self.fantasyland_status[self.current_player_idx]:
            # Обработка "мета-действия" ФЛ - просто передаем ход
            new_state = self.copy()
            new_state._player_acted_this_street[self.current_player_idx] = True
            new_state.fantasyland_hands[self.current_player_idx] = None # Рука "разыграна"

            if all(new_state._player_acted_this_street):
                 pass # Раунд ФЛ завершен (обработка в main)
            else:
                 new_state.current_player_idx = 1 - new_state.current_player_idx
                 if not new_state.fantasyland_status[new_state.current_player_idx]:
                      new_state._deal_street()
            return new_state
        elif self.street == 1:
            return self._apply_action_street1(action)
        else:
            return self._apply_action_pineapple(action)

    def _apply_action_street1(self, action: Tuple[List[Tuple[Card, str, int]], List[Card]]):
        """Применяет действие для первой улицы."""
        new_state = self.copy()
        board = new_state.boards[self.current_player_idx]
        placements, _ = action
        success = True
        for card, row, index in placements:
            if not board.add_card(card, row, index): success = False; break
        if not success: return self # Ошибка

        new_state.cards_dealt_current_street = None
        new_state._player_acted_this_street[self.current_player_idx] = True

        if all(new_state._player_acted_this_street):
            new_state.street += 1
            new_state._player_acted_this_street = [False] * self.NUM_PLAYERS
            new_state.current_player_idx = 1 - new_state.dealer_idx
            new_state._deal_street()
        else:
            new_state.current_player_idx = 1 - new_state.current_player_idx
            new_state._deal_street()
        return new_state

    def _apply_action_pineapple(self, action: Tuple[Tuple[Card, str, int], Tuple[Card, str, int], Card]):
        """Применяет действие Pineapple (улицы 2-5)."""
        new_state = self.copy()
        board = new_state.boards[self.current_player_idx]
        place1, place2, discarded_card = action
        card1, row1, idx1 = place1
        card2, row2, idx2 = place2

        success1 = board.add_card(card1, row1, idx1)
        success2 = board.add_card(card2, row2, idx2)
        if not success1 or not success2: return self # Ошибка

        new_state.discard_pile.append(discarded_card)
        new_state.cards_dealt_current_street = None
        new_state._player_acted_this_street[self.current_player_idx] = True

        if board.is_complete():
            board.check_and_set_foul()
            if not board.is_foul:
                if not self.fantasyland_status[self.current_player_idx]:
                    fl_cards = board.get_fantasyland_qualification_cards()
                    if fl_cards > 0:
                        new_state.next_fantasyland_status[self.current_player_idx] = True
                        new_state.fantasyland_cards_to_deal[self.current_player_idx] = fl_cards

        if all(new_state._player_acted_this_street) or new_state.is_round_over():
            if new_state.street < 5 and not new_state.is_round_over():
                new_state.street += 1
                new_state._player_acted_this_street = [False] * self.NUM_PLAYERS
                new_state.current_player_idx = 1 - new_state.dealer_idx
                new_state._deal_street()
        else:
            new_state.current_player_idx = 1 - new_state.current_player_idx
            if new_state.cards_dealt_current_street is None:
                 new_state._deal_street()
        return new_state

    def apply_fantasyland_placement(self, player_idx: int, placement: Dict[str, List[Card]], discarded: List[Card]):
        """Применяет результат FantasylandSolver к доске игрока."""
        board = self.boards[player_idx]
        board.set_full_board(placement['top'], placement['middle'], placement['bottom'])
        self.discard_pile.extend(discarded)
        self.fantasyland_hands[player_idx] = None
        self._player_acted_this_street[player_idx] = True

        if not board.is_foul:
            if board.check_fantasyland_stay_conditions():
                self.next_fantasyland_status[player_idx] = True
                self.fantasyland_cards_to_deal[player_idx] = 14

    def is_round_over(self) -> bool:
        """Проверяет, завершили ли все игроки свои доски."""
        if self.is_fantasyland_round:
             # В ФЛ раунде все должны были "сыграть" (либо ФЛ, либо обычную руку)
             return all(self._player_acted_this_street)
        else: # Обычный раунд
             return all(b.is_complete() for b in self.boards)

    def get_terminal_score(self) -> int:
        """Возвращает счет раунда с точки зрения Игрока 0."""
        if not self.is_round_over(): return 0 # Счет только для завершенного раунда
        return calculate_headsup_score(self.boards[0], self.boards[1])

    def get_state_representation(self) -> tuple:
        """Возвращает неизменяемое представление состояния для MCTS."""
        board_tuples = tuple(b.get_board_state_tuple() for b in self.boards)
        discard_tuple = tuple(sorted(self.discard_pile, key=lambda c: c.int_value))
        current_hand_tuple = tuple(sorted(self.cards_dealt_current_street, key=lambda c: c.int_value)) if self.cards_dealt_current_street else tuple()
        fantasyland_hands_tuple = tuple(tuple(sorted(h, key=lambda c: c.int_value)) if h else tuple() for h in self.fantasyland_hands)

        return (
            board_tuples, discard_tuple, self.current_player_idx, self.street,
            current_hand_tuple, tuple(self.fantasyland_status),
            self.is_fantasyland_round, fantasyland_hands_tuple,
            tuple(self._player_acted_this_street)
        )

    def copy(self) -> 'GameState':
        """Создает глубокую копию состояния."""
        # Используем deepcopy для простоты и надежности
        return copy.deepcopy(self)

    def __hash__(self):
        return hash(self.get_state_representation())

    def __eq__(self, other):
        if not isinstance(other, GameState): return NotImplemented
        return self.get_state_representation() == other.get_state_representation()
