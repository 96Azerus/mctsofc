# game_state.py
"""
Определяет класс GameState, управляющий полным состоянием игры
OFC Pineapple для двух игроков.
"""
import copy
import random
import sys # Добавлено для flush
from itertools import combinations, permutations
from typing import List, Tuple, Optional, Set, Dict, Any

# Импортируем зависимости из других наших модулей
from card import Card, card_to_str, card_from_str # Добавлен card_from_str
from deck import Deck
from board import PlayerBoard
from scoring import calculate_headsup_score # Функция подсчета очков

class GameState:
    NUM_PLAYERS = 2

    def __init__(self,
                 boards: Optional[List[PlayerBoard]] = None,
                 deck: Optional[Deck] = None,
                 private_discard: Optional[List[List[Card]]] = None, # Приватный сброс
                 dealer_idx: int = 0,
                 current_player_idx: Optional[int] = None, # Чья очередь в обычном раунде
                 street: int = 1,
                 # Рука для текущего хода (приватна для игрока)
                 # Используем словарь, чтобы хранить руки для обоих игроков, если нужно (например, в FL)
                 current_hands: Optional[Dict[int, Optional[List[Card]]]] = None,
                 fantasyland_status: Optional[List[bool]] = None, # Статус ФЛ на начало раунда
                 next_fantasyland_status: Optional[List[bool]] = None, # Статус ФЛ на след. раунд
                 fantasyland_cards_to_deal: Optional[List[int]] = None, # Кол-во карт для ФЛ
                 is_fantasyland_round: bool = False, # Это раунд Фантазии?
                 fantasyland_hands: Optional[List[Optional[List[Card]]]] = None, # Руки для ФЛ
                 # Отслеживание прогресса внутри улицы (для Pineapple)
                 _player_acted_this_street: Optional[List[bool]] = None,
                 # Отслеживание завершения раунда игроком (особенно в FL)
                 _player_finished_round: Optional[List[bool]] = None):

        self.boards: List[PlayerBoard] = boards if boards is not None else [PlayerBoard() for _ in range(self.NUM_PLAYERS)]
        self.deck: Deck = deck if deck is not None else Deck()
        self.private_discard: List[List[Card]] = private_discard if private_discard is not None else [[] for _ in range(self.NUM_PLAYERS)]
        self.dealer_idx: int = dealer_idx
        # В ФЛ раунде нет "текущего" игрока в традиционном смысле, но сохраняем для не-ФЛ ходов
        self.current_player_idx: int = (1 - dealer_idx) if current_player_idx is None else current_player_idx
        self.street: int = street
        # Словарь для хранения текущих рук {player_idx: [Card, ...]}
        self.current_hands: Dict[int, Optional[List[Card]]] = current_hands if current_hands is not None else {i: None for i in range(self.NUM_PLAYERS)}
        self.fantasyland_status: List[bool] = fantasyland_status if fantasyland_status is not None else [False] * self.NUM_PLAYERS
        self.next_fantasyland_status: List[bool] = next_fantasyland_status if next_fantasyland_status is not None else [False] * self.NUM_PLAYERS
        self.fantasyland_cards_to_deal: List[int] = fantasyland_cards_to_deal if fantasyland_cards_to_deal is not None else [0] * self.NUM_PLAYERS
        self.is_fantasyland_round: bool = is_fantasyland_round
        self.fantasyland_hands: List[Optional[List[Card]]] = fantasyland_hands if fantasyland_hands is not None else [None] * self.NUM_PLAYERS
        self._player_acted_this_street: List[bool] = _player_acted_this_street if _player_acted_this_street is not None else [False] * self.NUM_PLAYERS
        self._player_finished_round: List[bool] = _player_finished_round if _player_finished_round is not None else [False] * self.NUM_PLAYERS

    def get_player_board(self, player_idx: int) -> PlayerBoard:
        """Возвращает доску указанного игрока."""
        return self.boards[player_idx]

    def get_player_hand(self, player_idx: int) -> Optional[List[Card]]:
         """Возвращает текущую руку игрока (обычную или ФЛ)."""
         if self.is_fantasyland_round and self.fantasyland_status[player_idx]:
              return self.fantasyland_hands[player_idx]
         else:
              return self.current_hands.get(player_idx)


    def start_new_round(self, dealer_button_idx: int):
        """Начинает новый раунд, сохраняя статус ФЛ."""
        current_fl_status = list(self.fantasyland_status) # Сохраняем статус ФЛ
        current_fl_cards = list(self.fantasyland_cards_to_deal) # Сохраняем кол-во карт
        # Сбрасываем состояние, передавая сохраненный статус ФЛ
        self.__init__(dealer_idx=dealer_button_idx,
                      fantasyland_status=current_fl_status,
                      fantasyland_cards_to_deal=current_fl_cards)
        self.is_fantasyland_round = any(self.fantasyland_status)

        if self.is_fantasyland_round:
            self._deal_fantasyland_hands()
            # Раздаем карты 1й улицы не-ФЛ игрокам сразу
            for i in range(self.NUM_PLAYERS):
                if not self.fantasyland_status[i]:
                    self._deal_street_to_player(i) # Раздаем 5 карт
        else:
            # Обычный раунд, раздаем первому игроку
            first_player = 1 - self.dealer_idx
            self.current_player_idx = first_player # Устанавливаем, кто ходит первым
            self._deal_street_to_player(first_player)

    def _deal_street_to_player(self, player_idx: int):
        """Раздает карты для текущей улицы указанному игроку."""
        # Не раздаем, если у игрока уже есть карты на этой улице или он закончил
        if self._player_finished_round[player_idx] or self.current_hands.get(player_idx) is not None:
             return

        num_cards = 5 if self.street == 1 else 3
        try:
            dealt_cards = self.deck.deal(num_cards)
            # --- ДОБАВЛЕНО ЛОГИРОВАНИЕ ---
            print(f"DEBUG: Dealt street cards for player {player_idx}, street {self.street}: {[str(c) for c in dealt_cards]}")
            sys.stdout.flush(); sys.stderr.flush()
            # -----------------------------
            self.current_hands[player_idx] = dealt_cards
            # Сбрасываем флаг действия на улице для этого игрока
            self._player_acted_this_street[player_idx] = False
        except ValueError as e: # Ловим конкретную ошибку нехватки карт
            print(f"Error dealing street {self.street} to player {player_idx}: {e}")
            sys.stdout.flush(); sys.stderr.flush()
            self.current_hands[player_idx] = [] # Пустая рука в случае ошибки
            # Возможно, нужно пометить игрока как закончившего или обработать иначе
            # self._player_finished_round[player_idx] = True # Например так?

    def _deal_fantasyland_hands(self):
        """Раздает N карт игрокам в статусе Фантазии."""
        for i in range(self.NUM_PLAYERS):
            if self.fantasyland_status[i]:
                num_cards = self.fantasyland_cards_to_deal[i]
                if num_cards == 0: num_cards = 14 # Стандарт по умолчанию
                try:
                    dealt_cards = self.deck.deal(num_cards)
                    # --- ДОБАВЛЕНО ЛОГИРОВАНИЕ ---
                    print(f"DEBUG: Dealt fantasyland hand for player {i} ({num_cards} cards): {[str(c) for c in dealt_cards]}")
                    sys.stdout.flush(); sys.stderr.flush()
                    # -----------------------------
                    self.fantasyland_hands[i] = dealt_cards
                except ValueError as e: # Ловим конкретную ошибку нехватки карт
                    print(f"Error dealing Fantasyland to player {i}: {e}")
                    sys.stdout.flush(); sys.stderr.flush()
                    self.fantasyland_hands[i] = []
                    # Если не хватило карт на ФЛ, игрок не сможет сделать ход - фол?
                    # self._player_finished_round[i] = True
                    # self.boards[i].is_foul = True

    def get_legal_actions_for_player(self, player_idx: int) -> List[Any]:
        """Возвращает легальные действия для указанного игрока."""
        if self._player_finished_round[player_idx]:
            return [] # Игрок уже закончил раунд

        # --- Ход Фантазии ---
        if self.is_fantasyland_round and self.fantasyland_status[player_idx]:
            hand = self.fantasyland_hands[player_idx]
            # Возвращаем "мета-действие" для солвера, если рука еще не разыграна
            # Солверу нужна только рука
            return [(hand, [])] if hand else []

        # --- Обычный ход ---
        hand = self.current_hands.get(player_idx)
        if not hand:
             return [] # Нет карт для хода (ожидает раздачи)

        if self.street == 1:
            if len(hand) == 5:
                 return self._get_legal_actions_street1(player_idx, hand)
            else: return [] # Некорректное количество карт
        else: # Улицы 2-5
            if len(hand) == 3:
                 return self._get_legal_actions_pineapple(player_idx, hand)
            else: return [] # Некорректное количество карт

    def _get_legal_actions_street1(self, player_idx: int, hand: List[Card]) -> List[Tuple[List[Tuple[Card, str, int]], List[Card]]]:
        """
        Генерирует ВСЕ легальные действия для первой улицы (размещение 5 карт).
        Возвращает список действий. Формат: ([(карта, ряд, индекс)...], [])
        """
        board = self.boards[player_idx]
        available_slots = board.get_available_slots() # Список кортежей (row_name, index)
        if len(available_slots) < 5: return [] # Недостаточно места

        actions = []
        hand_list = list(hand) # Преобразуем в список для индексации

        # 1. Выбираем 5 слотов из доступных
        slot_combinations = list(combinations(available_slots, 5))

        # Оптимизация: Если комбинаций слотов > N, берем случайную выборку
        MAX_SLOT_COMBOS = 1000 # Ограничение для производительности
        if len(slot_combinations) > MAX_SLOT_COMBOS:
             slot_combinations = random.sample(slot_combinations, MAX_SLOT_COMBOS)

        # 2. Генерируем все перестановки карт для этих 5 слотов
        card_permutations = list(permutations(hand_list))
        # Оптимизация: Если перестановок > M, берем случайную выборку? (120 для 5 карт - немного)

        for slot_combination in slot_combinations:
            for card_permutation in card_permutations:
                placement = []
                valid_placement = True
                temp_placed_slots = set() # Проверка уникальности слотов в действии

                for i in range(5):
                    card = card_permutation[i]
                    slot_info = slot_combination[i]
                    row_name, index = slot_info

                    # Проверка, что слот еще не занят в *этом* действии
                    if slot_info in temp_placed_slots:
                         valid_placement = False; break
                    temp_placed_slots.add(slot_info)
                    placement.append((card, row_name, index))

                if valid_placement:
                    actions.append((placement, [])) # Пустой список для сброса

        # print(f"Generated {len(actions)} actions for Street 1 for player {player_idx}")
        return actions

    def _get_legal_actions_pineapple(self, player_idx: int, hand: List[Card]) -> List[Tuple[Tuple[Card, str, int], Tuple[Card, str, int], Card]]:
        """Генерирует действия для улиц 2-5."""
        board = self.boards[player_idx]
        available_slots = board.get_available_slots()
        if len(available_slots) < 2: return []

        actions = []
        hand_list = list(hand)

        # Итерируем по карте для сброса
        for i in range(3):
            discarded_card = hand_list[i]
            cards_to_place = [hand_list[j] for j in range(3) if i != j]
            card1, card2 = cards_to_place[0], cards_to_place[1]

            # Итерируем по парам доступных слотов
            for slot1_info, slot2_info in combinations(available_slots, 2):
                row1, idx1 = slot1_info
                row2, idx2 = slot2_info
                # Действие 1: card1 в slot1, card2 в slot2
                actions.append(((card1, row1, idx1), (card2, row2, idx2), discarded_card))
                # Действие 2: card2 в slot1, card1 в slot2 (если слоты разные)
                if slot1_info != slot2_info: # Избыточно, combinations не дает одинаковых
                     actions.append(((card2, row1, idx1), (card1, row2, idx2), discarded_card))
        return actions

    def apply_action(self, player_idx: int, action: Any):
        """
        Применяет легальное действие для УКАЗАННОГО игрока.
        Возвращает НОВОЕ состояние игры.
        ВАЖНО: Эта функция НЕ управляет очередностью ходов или завершением раунда.
        """
        new_state = self.copy()
        board = new_state.boards[player_idx]

        if new_state.is_fantasyland_round and new_state.fantasyland_status[player_idx]:
             print(f"Warning: apply_action called for Fantasyland player {player_idx}. Use apply_fantasyland_placement/foul.")
             new_state._player_finished_round[player_idx] = True
             new_state.fantasyland_hands[player_idx] = None
             return new_state

        current_hand = new_state.current_hands.get(player_idx)
        if not current_hand:
             print(f"Error: apply_action called for player {player_idx} but no hand found.")
             return self # Ошибка, возвращаем старое состояние

        if new_state.street == 1:
            if len(current_hand) != 5: return self # Ошибка
            placements, _ = action
            if len(placements) != 5: return self # Ошибка

            success = True
            placed_cards_in_action = set()
            for card, row, index in placements:
                if card not in current_hand or card in placed_cards_in_action:
                     success = False; break # Карта не из руки или дубликат в действии
                if not board.add_card(card, row, index):
                    success = False; break # Не удалось добавить на доску
                placed_cards_in_action.add(card)

            if not success:
                 print(f"Error applying street 1 action for player {player_idx}.")
                 # В идеале нужно откатить изменения на доске, но проще вернуть старое состояние
                 return self

            new_state.current_hands[player_idx] = None # Рука разыграна
            new_state._player_acted_this_street[player_idx] = True
            if board.is_complete(): # Проверка на всякий случай
                 new_state._player_finished_round[player_idx] = True
                 new_state._check_foul_and_update_fl_status(player_idx)

        else: # Улицы 2-5 (Pineapple)
            if len(current_hand) != 3: return self # Ошибка
            place1, place2, discarded_card = action
            card1, row1, idx1 = place1
            card2, row2, idx2 = place2

            # Проверка карт действия
            action_cards = {card1, card2, discarded_card}
            if len(action_cards) != 3 or not action_cards.issubset(set(current_hand)):
                 print(f"Error: Action cards mismatch hand for player {player_idx}.")
                 return self

            success1 = board.add_card(card1, row1, idx1)
            success2 = board.add_card(card2, row2, idx2)
            if not success1 or not success2:
                print(f"Error applying pineapple action for player {player_idx}: failed to add cards.")
                # Откатываем первое добавление, если второе не удалось
                if success1 and not success2: board.remove_card(row1, idx1)
                return self

            new_state.private_discard[player_idx].append(discarded_card)
            new_state.current_hands[player_idx] = None # Рука разыграна
            new_state._player_acted_this_street[player_idx] = True

            if board.is_complete():
                new_state._player_finished_round[player_idx] = True
                new_state._check_foul_and_update_fl_status(player_idx)

        return new_state

    def apply_fantasyland_placement(self, player_idx: int, placement: Dict[str, List[Card]], discarded: List[Card]):
        """Применяет результат FantasylandSolver к доске игрока."""
        new_state = self.copy()
        board = new_state.boards[player_idx]

        # Проверка, что игрок действительно в ФЛ и имеет руку
        if not new_state.is_fantasyland_round or not new_state.fantasyland_status[player_idx] or not new_state.fantasyland_hands[player_idx]:
             print(f"Error: apply_fantasyland_placement called incorrectly for player {player_idx}.")
             return self

        original_hand = set(new_state.fantasyland_hands[player_idx])
        placed_cards_in_placement = set(c for row in placement.values() for c in row)
        discarded_set = set(discarded)

        # Валидация входных данных
        if len(placed_cards_in_placement) != 13 or \
           len(discarded) != len(original_hand) - 13 or \
           not placed_cards_in_placement.union(discarded_set) == original_hand or \
           not placed_cards_in_placement.isdisjoint(discarded_set):
             print(f"Error: Invalid Fantasyland placement/discard data for player {player_idx}.")
             # Считаем это фолом
             return new_state.apply_fantasyland_foul(player_idx, new_state.fantasyland_hands[player_idx])

        try:
            board.set_full_board(placement['top'], placement['middle'], placement['bottom'])
        except ValueError as e:
            print(f"Error setting FL board for player {player_idx}: {e}")
            # Считаем это фолом
            return new_state.apply_fantasyland_foul(player_idx, new_state.fantasyland_hands[player_idx])

        new_state.private_discard[player_idx].extend(discarded)
        new_state.fantasyland_hands[player_idx] = None
        new_state._player_finished_round[player_idx] = True
        new_state._check_foul_and_update_fl_status(player_idx) # Проверяем фол/Re-FL
        return new_state

    def apply_fantasyland_foul(self, player_idx: int, hand_to_discard: List[Card]):
        """Применяет фол в Fantasyland."""
        new_state = self.copy()
        board = new_state.boards[player_idx]
        board.is_foul = True
        # Добавляем всю руку в приватный сброс
        new_state.private_discard[player_idx].extend(hand_to_discard)
        new_state.fantasyland_hands[player_idx] = None
        new_state._player_finished_round[player_idx] = True
        # Статус Re-Fantasy не обновляется при фоле
        new_state.next_fantasyland_status[player_idx] = False
        new_state.fantasyland_cards_to_deal[player_idx] = 0
        return new_state


    def _check_foul_and_update_fl_status(self, player_idx: int):
        """Проверяет фол и обновляет статус FL для игрока, завершившего доску."""
        board = self.boards[player_idx]
        if not board.is_complete(): return

        board.check_and_set_foul()

        # Сбрасываем статус следующего раунда по умолчанию
        self.next_fantasyland_status[player_idx] = False
        self.fantasyland_cards_to_deal[player_idx] = 0

        if not board.is_foul:
            if self.fantasyland_status[player_idx]: # Был в FL -> проверяем удержание
                if board.check_fantasyland_stay_conditions():
                    self.next_fantasyland_status[player_idx] = True
                    self.fantasyland_cards_to_deal[player_idx] = 14
            else: # Не был в FL -> проверяем вход
                fl_cards = board.get_fantasyland_qualification_cards()
                if fl_cards > 0:
                    self.next_fantasyland_status[player_idx] = True
                    self.fantasyland_cards_to_deal[player_idx] = fl_cards

    def is_round_over(self) -> bool:
        """Проверяет, завершили ли все игроки свою часть раунда."""
        return all(self._player_finished_round)

    def get_terminal_score(self) -> int:
        """Возвращает счет раунда с точки зрения Игрока 0."""
        if not self.is_round_over(): return 0
        # Убедимся, что фолы проверены для всех досок
        for board in self.boards:
             if board.is_complete(): # Проверяем только полные доски
                  board.check_and_set_foul()
        return calculate_headsup_score(self.boards[0], self.boards[1])

    def get_known_dead_cards(self, perspective_player_idx: int) -> Set[Card]:
         """Возвращает набор карт, известных игроку как вышедшие из игры."""
         dead_cards = set()
         # Карты на всех досках
         for board in self.boards:
             for row_name in board.ROW_NAMES:
                 for card in board.rows[row_name]:
                     if card:
                         dead_cards.add(card)
         # Карты в своей текущей руке (обычной или ФЛ)
         player_hand = self.get_player_hand(perspective_player_idx)
         if player_hand:
              dead_cards.update(player_hand)
         # Свой приватный сброс
         dead_cards.update(self.private_discard[perspective_player_idx])
         return dead_cards

    def get_state_representation(self) -> tuple:
        """Возвращает неизменяемое представление состояния для MCTS."""
        board_tuples = tuple(b.get_board_state_tuple() for b in self.boards)
        fantasyland_hands_exist_tuple = tuple(bool(h) for h in self.fantasyland_hands)

        # Включаем информацию, важную для определения легальных ходов и конца раунда
        return (
            board_tuples,
            self.current_player_idx, # Чей ход в обычном раунде
            self.street,
            tuple(self.fantasyland_status),
            self.is_fantasyland_round,
            fantasyland_hands_exist_tuple, # Есть ли рука ФЛ у игроков
            tuple(bool(hand) for hand in self.current_hands.values()), # Есть ли обычная рука у игроков
            tuple(self._player_acted_this_street),
            tuple(self._player_finished_round)
        )

    def copy(self) -> 'GameState':
        """Создает глубокую копию состояния."""
        return copy.deepcopy(self)

    def __hash__(self):
        return hash(self.get_state_representation())

    def __eq__(self, other):
        if not isinstance(other, GameState): return NotImplemented
        return self.get_state_representation() == other.get_state_representation()

    # --- Функции для сериализации/десериализации (JSON) ---
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует состояние в словарь для JSON-сериализации."""
        boards_dict = []
        for board in self.boards:
            board_data = {}
            for row_name in PlayerBoard.ROW_NAMES:
                board_data[row_name] = [card_to_str(c) for c in board.rows[row_name]]
            board_data['_cards_placed'] = board._cards_placed
            board_data['is_foul'] = board.is_foul
            board_data['_is_complete'] = board._is_complete
            boards_dict.append(board_data)

        return {
            "boards": boards_dict,
            "private_discard": [[card_to_str(c) for c in p_discard] for p_discard in self.private_discard],
            "dealer_idx": self.dealer_idx,
            "current_player_idx": self.current_player_idx,
            "street": self.street,
            # Сохраняем обе руки
            "current_hands": {idx: [card_to_str(c) for c in hand] if hand else None
                              for idx, hand in self.current_hands.items()},
            "fantasyland_status": self.fantasyland_status,
            "next_fantasyland_status": self.next_fantasyland_status,
            "fantasyland_cards_to_deal": self.fantasyland_cards_to_deal,
            "is_fantasyland_round": self.is_fantasyland_round,
            "fantasyland_hands": [[card_to_str(c) for c in hand] if hand else None
                                  for hand in self.fantasyland_hands],
            "_player_acted_this_street": self._player_acted_this_street,
            "_player_finished_round": self._player_finished_round,
            # Не сохраняем deck
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameState':
        """Восстанавливает состояние из словаря."""
        boards = []
        all_known_cards_strs = set()

        for board_data in data["boards"]:
            board = PlayerBoard()
            cards_on_board = 0
            for row_name in PlayerBoard.ROW_NAMES:
                cards = []
                for card_str in board_data.get(row_name, []): # Используем get для совместимости
                    if card_str != "__":
                        try:
                            card = card_from_str(card_str)
                            cards.append(card)
                            all_known_cards_strs.add(card_str)
                            cards_on_board += 1
                        except ValueError:
                             print(f"Warning: Invalid card string '{card_str}' in saved board state.")
                             cards.append(None) # Добавляем None при ошибке
                    else:
                        cards.append(None)
                # Дополняем None до нужной длины, если нужно
                capacity = PlayerBoard.ROW_CAPACITY[row_name]
                cards.extend([None] * (capacity - len(cards)))
                board.rows[row_name] = cards[:capacity] # Обрезаем, если длиннее

            board._cards_placed = board_data.get('_cards_placed', cards_on_board)
            board.is_foul = board_data.get('is_foul', False)
            board._is_complete = board_data.get('_is_complete', board._cards_placed == 13)
            boards.append(board)

        private_discard = []
        for p_discard_strs in data.get("private_discard", [[] for _ in range(cls.NUM_PLAYERS)]):
            p_discard = []
            for cs in p_discard_strs:
                 try:
                      p_discard.append(card_from_str(cs))
                      all_known_cards_strs.add(cs)
                 except ValueError:
                      print(f"Warning: Invalid card string '{cs}' in saved private discard.")
            private_discard.append(p_discard)

        current_hands = {}
        for idx_str, hand_strs in data.get("current_hands", {}).items():
             idx = int(idx_str)
             if hand_strs:
                  hand = []
                  for cs in hand_strs:
                       try:
                            hand.append(card_from_str(cs))
                            all_known_cards_strs.add(cs)
                       except ValueError:
                            print(f"Warning: Invalid card string '{cs}' in saved current hand.")
                  current_hands[idx] = hand
             else:
                  current_hands[idx] = None
        # Дополняем None для игроков, которых нет в словаре
        for i in range(cls.NUM_PLAYERS):
             if i not in current_hands: current_hands[i] = None


        fantasyland_hands = []
        for hand_strs in data.get("fantasyland_hands", [None]*cls.NUM_PLAYERS):
            if hand_strs:
                hand = []
                for cs in hand_strs:
                     try:
                          hand.append(card_from_str(cs))
                          all_known_cards_strs.add(cs)
                     except ValueError:
                          print(f"Warning: Invalid card string '{cs}' in saved fantasyland hand.")
                fantasyland_hands.append(hand)
            else:
                fantasyland_hands.append(None)

        # Восстанавливаем колоду
        known_cards = set()
        for cs in all_known_cards_strs:
             try: known_cards.add(card_from_str(cs))
             except ValueError: pass # Игнорируем невалидные строки здесь
        remaining_cards = Deck.FULL_DECK_CARDS - known_cards
        deck = Deck(cards=remaining_cards)

        # Получаем остальные данные или используем дефолты
        num_players = len(boards) # Определяем по количеству досок
        default_bool_list = [False] * num_players
        default_int_list = [0] * num_players

        return cls(
            boards=boards,
            deck=deck,
            private_discard=private_discard,
            dealer_idx=data.get("dealer_idx", 0),
            current_player_idx=data.get("current_player_idx", 0),
            street=data.get("street", 1),
            current_hands=current_hands,
            fantasyland_status=data.get("fantasyland_status", list(default_bool_list)),
            next_fantasyland_status=data.get("next_fantasyland_status", list(default_bool_list)),
            fantasyland_cards_to_deal=data.get("fantasyland_cards_to_deal", list(default_int_list)),
            is_fantasyland_round=data.get("is_fantasyland_round", False),
            fantasyland_hands=fantasyland_hands,
            _player_acted_this_street=data.get("_player_acted_this_street", list(default_bool_list)),
            _player_finished_round=data.get("_player_finished_round", list(default_bool_list))
        )
