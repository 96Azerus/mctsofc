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
from card import Card, card_to_str, card_from_str
from deck import Deck
from board import PlayerBoard
from scoring import calculate_headsup_score # Функция подсчета очков

class GameState:
    NUM_PLAYERS = 2

    def __init__(self,
                 boards: Optional[List[PlayerBoard]] = None,
                 deck: Optional[Deck] = None,
                 private_discard: Optional[List[List[Card]]] = None,
                 dealer_idx: int = 0,
                 current_player_idx: Optional[int] = None,
                 street: int = 1,
                 current_hands: Optional[Dict[int, Optional[List[Card]]]] = None,
                 fantasyland_status: Optional[List[bool]] = None,
                 next_fantasyland_status: Optional[List[bool]] = None,
                 fantasyland_cards_to_deal: Optional[List[int]] = None,
                 is_fantasyland_round: bool = False,
                 fantasyland_hands: Optional[List[Optional[List[Card]]]] = None,
                 _player_acted_this_street: Optional[List[bool]] = None,
                 _player_finished_round: Optional[List[bool]] = None):

        self.boards: List[PlayerBoard] = boards if boards is not None else [PlayerBoard() for _ in range(self.NUM_PLAYERS)]
        self.deck: Deck = deck if deck is not None else Deck()
        self.private_discard: List[List[Card]] = private_discard if private_discard is not None else [[] for _ in range(self.NUM_PLAYERS)]
        self.dealer_idx: int = dealer_idx
        self.current_player_idx: int = (1 - dealer_idx) if current_player_idx is None else current_player_idx
        self.street: int = street
        self.current_hands: Dict[int, Optional[List[Card]]] = current_hands if current_hands is not None else {i: None for i in range(self.NUM_PLAYERS)}
        self.fantasyland_status: List[bool] = fantasyland_status if fantasyland_status is not None else [False] * self.NUM_PLAYERS
        self.next_fantasyland_status: List[bool] = next_fantasyland_status if next_fantasyland_status is not None else [False] * self.NUM_PLAYERS
        self.fantasyland_cards_to_deal: List[int] = fantasyland_cards_to_deal if fantasyland_cards_to_deal is not None else [0] * self.NUM_PLAYERS
        self.is_fantasyland_round: bool = is_fantasyland_round
        self.fantasyland_hands: List[Optional[List[Card]]] = fantasyland_hands if fantasyland_hands is not None else [None] * self.NUM_PLAYERS
        self._player_acted_this_street: List[bool] = _player_acted_this_street if _player_acted_this_street is not None else [False] * self.NUM_PLAYERS
        self._player_finished_round: List[bool] = _player_finished_round if _player_finished_round is not None else [False] * self.NUM_PLAYERS

    def get_player_board(self, player_idx: int) -> PlayerBoard:
        return self.boards[player_idx]

    def get_player_hand(self, player_idx: int) -> Optional[List[Card]]:
         if self.is_fantasyland_round and self.fantasyland_status[player_idx]:
              return self.fantasyland_hands[player_idx]
         else:
              return self.current_hands.get(player_idx)

    def start_new_round(self, dealer_button_idx: int):
        current_fl_status = list(self.fantasyland_status)
        current_fl_cards = list(self.fantasyland_cards_to_deal)
        self.__init__(dealer_idx=dealer_button_idx,
                      fantasyland_status=current_fl_status,
                      fantasyland_cards_to_deal=current_fl_cards)
        self.is_fantasyland_round = any(self.fantasyland_status)
        if self.is_fantasyland_round:
            self._deal_fantasyland_hands()
            for i in range(self.NUM_PLAYERS):
                if not self.fantasyland_status[i]:
                    self._deal_street_to_player(i)
        else:
            first_player = 1 - self.dealer_idx
            self.current_player_idx = first_player
            self._deal_street_to_player(first_player)

    def _deal_street_to_player(self, player_idx: int):
        if self._player_finished_round[player_idx] or self.current_hands.get(player_idx) is not None:
             return
        num_cards = 5 if self.street == 1 else 3
        try:
            dealt_cards = self.deck.deal(num_cards)
            # --- ЛОГИРОВАНИЕ ---
            print(f"DEBUG: Dealt street cards for player {player_idx}, street {self.street}: {[repr(c) for c in dealt_cards]}")
            sys.stdout.flush(); sys.stderr.flush()
            # --------------------
            self.current_hands[player_idx] = dealt_cards
            self._player_acted_this_street[player_idx] = False
        except ValueError as e:
            print(f"Error dealing street {self.street} to player {player_idx}: {e}")
            sys.stdout.flush(); sys.stderr.flush()
            self.current_hands[player_idx] = []

    def _deal_fantasyland_hands(self):
        for i in range(self.NUM_PLAYERS):
            if self.fantasyland_status[i]:
                num_cards = self.fantasyland_cards_to_deal[i]
                if num_cards == 0: num_cards = 14
                try:
                    dealt_cards = self.deck.deal(num_cards)
                    # --- ЛОГИРОВАНИЕ ---
                    print(f"DEBUG: Dealt fantasyland hand for player {i} ({num_cards} cards): {[repr(c) for c in dealt_cards]}")
                    sys.stdout.flush(); sys.stderr.flush()
                    # --------------------
                    self.fantasyland_hands[i] = dealt_cards
                except ValueError as e:
                    print(f"Error dealing Fantasyland to player {i}: {e}")
                    sys.stdout.flush(); sys.stderr.flush()
                    self.fantasyland_hands[i] = []

    def get_legal_actions_for_player(self, player_idx: int) -> List[Any]:
        if self._player_finished_round[player_idx]: return []
        if self.is_fantasyland_round and self.fantasyland_status[player_idx]:
            hand = self.fantasyland_hands[player_idx]
            return [(hand, [])] if hand else []
        hand = self.current_hands.get(player_idx)
        if not hand: return []
        if self.street == 1:
            return self._get_legal_actions_street1(player_idx, hand) if len(hand) == 5 else []
        else:
            return self._get_legal_actions_pineapple(player_idx, hand) if len(hand) == 3 else []

    def _get_legal_actions_street1(self, player_idx: int, hand: List[Card]) -> List[Tuple[List[Tuple[Card, str, int]], List[Card]]]:
        board = self.boards[player_idx]
        available_slots = board.get_available_slots()
        if len(available_slots) < 5: return []
        actions = []
        hand_list = list(hand)
        slot_combinations = list(combinations(available_slots, 5))
        MAX_SLOT_COMBOS = 1000
        if len(slot_combinations) > MAX_SLOT_COMBOS:
             slot_combinations = random.sample(slot_combinations, MAX_SLOT_COMBOS)
        card_permutations = list(permutations(hand_list))
        for slot_combination in slot_combinations:
            for card_permutation in card_permutations:
                placement = []
                valid_placement = True
                temp_placed_slots = set()
                for i in range(5):
                    card = card_permutation[i]
                    slot_info = slot_combination[i]
                    row_name, index = slot_info
                    if slot_info in temp_placed_slots: valid_placement = False; break
                    temp_placed_slots.add(slot_info)
                    placement.append((card, row_name, index))
                if valid_placement: actions.append((placement, []))
        return actions

    def _get_legal_actions_pineapple(self, player_idx: int, hand: List[Card]) -> List[Tuple[Tuple[Card, str, int], Tuple[Card, str, int], Card]]:
        board = self.boards[player_idx]
        available_slots = board.get_available_slots()
        if len(available_slots) < 2: return []
        actions = []
        hand_list = list(hand)
        for i in range(3):
            discarded_card = hand_list[i]
            cards_to_place = [hand_list[j] for j in range(3) if i != j]
            card1, card2 = cards_to_place[0], cards_to_place[1]
            for slot1_info, slot2_info in combinations(available_slots, 2):
                row1, idx1 = slot1_info
                row2, idx2 = slot2_info
                actions.append(((card1, row1, idx1), (card2, row2, idx2), discarded_card))
                if slot1_info != slot2_info:
                     actions.append(((card2, row1, idx1), (card1, row2, idx2), discarded_card))
        return actions

    def apply_action(self, player_idx: int, action: Any):
        new_state = self.copy()
        board = new_state.boards[player_idx]
        if new_state.is_fantasyland_round and new_state.fantasyland_status[player_idx]:
             print(f"Warning: apply_action called for Fantasyland player {player_idx}.")
             new_state._player_finished_round[player_idx] = True
             new_state.fantasyland_hands[player_idx] = None
             return new_state
        current_hand = new_state.current_hands.get(player_idx)
        if not current_hand: print(f"Error: apply_action called for player {player_idx} but no hand found."); return self
        if new_state.street == 1:
            if len(current_hand) != 5: return self
            placements, _ = action
            if len(placements) != 5: return self
            success = True
            placed_cards_in_action = set()
            for card, row, index in placements:
                if card not in current_hand or card in placed_cards_in_action: success = False; break
                if not board.add_card(card, row, index): success = False; break
                placed_cards_in_action.add(card)
            if not success: print(f"Error applying street 1 action for player {player_idx}."); return self
            new_state.current_hands[player_idx] = None
            new_state._player_acted_this_street[player_idx] = True
            if board.is_complete(): new_state._player_finished_round[player_idx] = True; new_state._check_foul_and_update_fl_status(player_idx)
        else: # Улицы 2-5 (Pineapple)
            if len(current_hand) != 3: return self
            place1, place2, discarded_card = action
            card1, row1, idx1 = place1
            card2, row2, idx2 = place2
            action_cards = {card1, card2, discarded_card}
            if len(action_cards) != 3 or not action_cards.issubset(set(current_hand)): print(f"Error: Action cards mismatch hand for player {player_idx}."); return self

            success1 = board.add_card(card1, row1, idx1)
            success2 = board.add_card(card2, row2, idx2)

            # --- ИСПРАВЛЕННЫЙ БЛОК ОБРАБОТКИ ОШИБКИ ---
            if not success1 or not success2:
                print(f"Error applying pineapple action for player {player_idx}: failed to add cards.")
                # Откатываем первое добавление, если оно было успешным, а второе нет
                if success1 and not success2:
                    board.remove_card(row1, idx1) # Откатываем только если первая карта была добавлена
                return self # Возвращаем старое состояние при любой ошибке добавления
            # ------------------------------------------

            new_state.private_discard[player_idx].append(discarded_card)
            new_state.current_hands[player_idx] = None
            new_state._player_acted_this_street[player_idx] = True
            if board.is_complete(): new_state._player_finished_round[player_idx] = True; new_state._check_foul_and_update_fl_status(player_idx)
        return new_state

    def apply_fantasyland_placement(self, player_idx: int, placement: Dict[str, List[Card]], discarded: List[Card]):
        new_state = self.copy()
        board = new_state.boards[player_idx]
        if not new_state.is_fantasyland_round or not new_state.fantasyland_status[player_idx] or not new_state.fantasyland_hands[player_idx]: print(f"Error: apply_fantasyland_placement called incorrectly for player {player_idx}."); return self
        original_hand = set(new_state.fantasyland_hands[player_idx])
        placed_cards_in_placement = set(c for row in placement.values() for c in row)
        discarded_set = set(discarded)
        if len(placed_cards_in_placement) != 13 or len(discarded) != len(original_hand) - 13 or not placed_cards_in_placement.union(discarded_set) == original_hand or not placed_cards_in_placement.isdisjoint(discarded_set): print(f"Error: Invalid Fantasyland placement/discard data for player {player_idx}."); return new_state.apply_fantasyland_foul(player_idx, new_state.fantasyland_hands[player_idx])
        try: board.set_full_board(placement['top'], placement['middle'], placement['bottom'])
        except ValueError as e: print(f"Error setting FL board for player {player_idx}: {e}"); return new_state.apply_fantasyland_foul(player_idx, new_state.fantasyland_hands[player_idx])
        new_state.private_discard[player_idx].extend(discarded)
        new_state.fantasyland_hands[player_idx] = None
        new_state._player_finished_round[player_idx] = True
        new_state._check_foul_and_update_fl_status(player_idx)
        return new_state

    def apply_fantasyland_foul(self, player_idx: int, hand_to_discard: List[Card]):
        new_state = self.copy()
        board = new_state.boards[player_idx]
        board.is_foul = True
        new_state.private_discard[player_idx].extend(hand_to_discard)
        new_state.fantasyland_hands[player_idx] = None
        new_state._player_finished_round[player_idx] = True
        new_state.next_fantasyland_status[player_idx] = False
        new_state.fantasyland_cards_to_deal[player_idx] = 0
        return new_state

    def _check_foul_and_update_fl_status(self, player_idx: int):
        board = self.boards[player_idx]
        if not board.is_complete(): return
        board.check_and_set_foul()
        self.next_fantasyland_status[player_idx] = False
        self.fantasyland_cards_to_deal[player_idx] = 0
        if not board.is_foul:
            if self.fantasyland_status[player_idx]:
                if board.check_fantasyland_stay_conditions(): self.next_fantasyland_status[player_idx] = True; self.fantasyland_cards_to_deal[player_idx] = 14
            else:
                fl_cards = board.get_fantasyland_qualification_cards()
                if fl_cards > 0: self.next_fantasyland_status[player_idx] = True; self.fantasyland_cards_to_deal[player_idx] = fl_cards

    def is_round_over(self) -> bool:
        return all(self._player_finished_round)

    def get_terminal_score(self) -> int:
        if not self.is_round_over(): return 0
        for board in self.boards:
             if board.is_complete(): board.check_and_set_foul()
        return calculate_headsup_score(self.boards[0], self.boards[1])

    def get_known_dead_cards(self, perspective_player_idx: int) -> Set[Card]:
         dead_cards = set()
         for board in self.boards:
             for row_name in board.ROW_NAMES:
                 for card in board.rows[row_name]:
                     if card: dead_cards.add(card)
         player_hand = self.get_player_hand(perspective_player_idx)
         if player_hand: dead_cards.update(player_hand)
         dead_cards.update(self.private_discard[perspective_player_idx])
         return dead_cards

    def get_state_representation(self) -> tuple:
        board_tuples = tuple(b.get_board_state_tuple() for b in self.boards)
        fantasyland_hands_exist_tuple = tuple(bool(h) for h in self.fantasyland_hands)
        return (board_tuples, self.current_player_idx, self.street, tuple(self.fantasyland_status), self.is_fantasyland_round, fantasyland_hands_exist_tuple, tuple(bool(hand) for hand in self.current_hands.values()), tuple(self._player_acted_this_street), tuple(self._player_finished_round))

    def copy(self) -> 'GameState':
        return copy.deepcopy(self)

    def __hash__(self):
        return hash(self.get_state_representation())

    def __eq__(self, other):
        if not isinstance(other, GameState): return NotImplemented
        return self.get_state_representation() == other.get_state_representation()

    def to_dict(self) -> Dict[str, Any]:
        boards_dict = []
        for board in self.boards:
            board_data = {}
            for row_name in PlayerBoard.ROW_NAMES:
                board_data[row_name] = [card_to_str(c) for c in board.rows[row_name]]
            board_data['_cards_placed'] = board._cards_placed
            board_data['is_foul'] = board.is_foul
            board_data['_is_complete'] = board._is_complete
            boards_dict.append(board_data)

        # --- ЛОГИРОВАНИЕ ---
        print(f"DEBUG to_dict: current_hands before str conversion: { {idx: [repr(c) for c in hand] if hand else None for idx, hand in self.current_hands.items()} }")
        print(f"DEBUG to_dict: fantasyland_hands before str conversion: { [[repr(c) for c in hand] if hand else None for hand in self.fantasyland_hands] }")
        sys.stdout.flush(); sys.stderr.flush()
        # --------------------

        return {
            "boards": boards_dict,
            "private_discard": [[card_to_str(c) for c in p_discard] for p_discard in self.private_discard],
            "dealer_idx": self.dealer_idx,
            "current_player_idx": self.current_player_idx,
            "street": self.street,
            "current_hands": {idx: [card_to_str(c) for c in hand] if hand else None for idx, hand in self.current_hands.items()},
            "fantasyland_status": self.fantasyland_status,
            "next_fantasyland_status": self.next_fantasyland_status,
            "fantasyland_cards_to_deal": self.fantasyland_cards_to_deal,
            "is_fantasyland_round": self.is_fantasyland_round,
            "fantasyland_hands": [[card_to_str(c) for c in hand] if hand else None for hand in self.fantasyland_hands],
            "_player_acted_this_street": self._player_acted_this_street,
            "_player_finished_round": self._player_finished_round,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameState':
        boards = []
        all_known_cards_strs = set()
        for board_data in data["boards"]:
            board = PlayerBoard()
            cards_on_board = 0
            for row_name in PlayerBoard.ROW_NAMES:
                cards = []
                for card_str in board_data.get(row_name, []):
                    if card_str != "__":
                        try:
                            card = card_from_str(card_str)
                            cards.append(card)
                            all_known_cards_strs.add(card_str)
                            cards_on_board += 1
                        except ValueError:
                             print(f"Warning: Invalid card string '{card_str}' in saved board state.")
                             cards.append(None)
                    else: cards.append(None)
                capacity = PlayerBoard.ROW_CAPACITY[row_name]
                cards.extend([None] * (capacity - len(cards)))
                board.rows[row_name] = cards[:capacity]
            board._cards_placed = board_data.get('_cards_placed', cards_on_board)
            board.is_foul = board_data.get('is_foul', False)
            board._is_complete = board_data.get('_is_complete', board._cards_placed == 13)
            boards.append(board)

        private_discard = []
        for p_discard_strs in data.get("private_discard", [[] for _ in range(cls.NUM_PLAYERS)]):
            p_discard = []
            for cs in p_discard_strs:
                 try: p_discard.append(card_from_str(cs)); all_known_cards_strs.add(cs)
                 except ValueError: print(f"Warning: Invalid card string '{cs}' in saved private discard.")
            private_discard.append(p_discard)

        current_hands = {}
        for idx_str, hand_strs in data.get("current_hands", {}).items():
             idx = int(idx_str)
             if hand_strs:
                  hand = []
                  for cs in hand_strs:
                       try: hand.append(card_from_str(cs)); all_known_cards_strs.add(cs)
                       except ValueError: print(f"Warning: Invalid card string '{cs}' in saved current hand.")
                  current_hands[idx] = hand
             else: current_hands[idx] = None
        for i in range(cls.NUM_PLAYERS):
             if i not in current_hands: current_hands[i] = None

        fantasyland_hands = []
        for hand_strs in data.get("fantasyland_hands", [None]*cls.NUM_PLAYERS):
            if hand_strs:
                hand = []
                for cs in hand_strs:
                     try: hand.append(card_from_str(cs)); all_known_cards_strs.add(cs)
                     except ValueError: print(f"Warning: Invalid card string '{cs}' in saved fantasyland hand.")
                fantasyland_hands.append(hand)
            else: fantasyland_hands.append(None)

        known_cards = set()
        for cs in all_known_cards_strs:
             try: known_cards.add(card_from_str(cs))
             except ValueError: pass
        remaining_cards = Deck.FULL_DECK_CARDS - known_cards
        deck = Deck(cards=remaining_cards)

        num_players = len(boards)
        default_bool_list = [False] * num_players
        default_int_list = [0] * num_players

        return cls(
            boards=boards, deck=deck, private_discard=private_discard,
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
