# mcts_node.py
import math
import random
import traceback
from typing import Optional, Dict, Any, List, Tuple, Set
from game_state import GameState
# Используем Card (алиас PhevaluatorCard) и RANK_ORDER_MAP, SUIT_ORDER_MAP
from card import Card, card_to_str, RANK_ORDER_MAP, SUIT_ORDER_MAP
from scoring import (RANK_CLASS_QUADS, RANK_CLASS_TRIPS, get_hand_rank_safe,
                     check_board_foul, get_row_royalty, RANK_CLASS_PAIR,
                     RANK_CLASS_HIGH_CARD)
from itertools import combinations
from fantasyland_solver import FantasylandSolver
from collections import Counter # Добавлен импорт Counter

class MCTSNode:
    """Узел дерева MCTS для OFC Pineapple с RAVE."""
    def __init__(self, game_state: GameState, parent: Optional['MCTSNode'] = None, action: Optional[Any] = None):
        self.game_state: GameState = game_state
        self.parent: Optional['MCTSNode'] = parent
        self.action: Optional[Any] = action
        self.children: Dict[Any, 'MCTSNode'] = {}
        self.untried_actions: Optional[List[Any]] = None
        self.visits: int = 0
        self.total_reward: float = 0.0
        self.rave_visits: Dict[Any, int] = {}
        self.rave_total_reward: Dict[Any, float] = {}

    def _get_player_to_move(self) -> int:
         gs = self.game_state
         player_to_move = -1
         if gs.is_fantasyland_round:
              for i in range(gs.NUM_PLAYERS):
                   if not gs._player_finished_round[i]:
                        if gs.fantasyland_status[i]:
                             if gs.fantasyland_hands[i] is not None: player_to_move = i; break
                        else:
                             if gs.current_hands.get(i) is not None: player_to_move = i; break
              if player_to_move == -1 and not gs.is_round_over():
                   if gs.current_player_idx != -1 and not gs._player_finished_round[gs.current_player_idx]: player_to_move = gs.current_player_idx
                   else:
                        for i in range(gs.NUM_PLAYERS):
                             if not gs._player_finished_round[i]: player_to_move = i; break
         else: player_to_move = gs.current_player_idx
         if player_to_move == -1 and not gs.is_round_over(): return 0
         elif gs.is_round_over(): return -1
         else: return player_to_move

    def expand(self) -> Optional['MCTSNode']:
        player_to_move = self._get_player_to_move()
        if player_to_move == -1: return None
        if self.untried_actions is None:
             self.untried_actions = self.game_state.get_legal_actions_for_player(player_to_move)
             random.shuffle(self.untried_actions)
             for act in self.untried_actions:
                 if act not in self.rave_visits: self.rave_visits[act] = 0; self.rave_total_reward[act] = 0.0
        if not self.untried_actions: return None
        action = self.untried_actions.pop()
        next_state = None
        if self.game_state.is_fantasyland_round and self.game_state.fantasyland_status[player_to_move]:
             print(f"Warning: expand called for Fantasyland player {player_to_move}."); return None
        else:
             try: next_state = self.game_state.apply_action(player_to_move, action)
             except Exception as e: print(f"Error applying action during expand for player {player_to_move}: {e}"); traceback.print_exc(); return None
        if next_state is None: return None
        child_node = MCTSNode(next_state, parent=self, action=action)
        self.children[action] = child_node
        return child_node

    def is_terminal(self) -> bool:
        return self.game_state.is_round_over()

    def rollout(self, perspective_player: int = 0) -> Tuple[float, Set[Any]]:
        current_rollout_state = self.game_state.copy()
        simulation_actions_set = set()
        MAX_ROLLOUT_STEPS = 50
        steps = 0
        while not current_rollout_state.is_round_over() and steps < MAX_ROLLOUT_STEPS:
            steps += 1; made_move_this_iter = False; player_acted_in_iter = -1
            player_to_act_rollout = -1
            gs_rollout = current_rollout_state
            if gs_rollout.is_fantasyland_round:
                 for i in range(gs_rollout.NUM_PLAYERS):
                      if not gs_rollout._player_finished_round[i]:
                           if gs_rollout.fantasyland_status[i] and gs_rollout.fantasyland_hands[i] is not None: player_to_act_rollout = i; break
                           elif not gs_rollout.fantasyland_status[i] and gs_rollout.current_hands.get(i) is not None: player_to_act_rollout = i; break
                 if player_to_act_rollout == -1 and not gs_rollout.is_round_over(): player_to_act_rollout = gs_rollout.current_player_idx
            else: player_to_act_rollout = gs_rollout.current_player_idx

            if player_to_act_rollout != -1 and not current_rollout_state._player_finished_round[player_to_act_rollout]:
                action = None
                is_fl_placement = current_rollout_state.is_fantasyland_round and current_rollout_state.fantasyland_status[player_to_act_rollout]
                if is_fl_placement:
                    hand = current_rollout_state.fantasyland_hands[player_to_act_rollout]
                    if hand:
                        placement, discarded = self._heuristic_fantasyland_placement(hand)
                        if placement: current_rollout_state = current_rollout_state.apply_fantasyland_placement(player_to_act_rollout, placement, discarded)
                        else: current_rollout_state = current_rollout_state.apply_fantasyland_foul(player_to_act_rollout, hand)
                        made_move_this_iter = True; player_acted_in_iter = player_to_act_rollout
                else:
                    hand = current_rollout_state.current_hands.get(player_to_act_rollout)
                    if hand:
                        possible_moves = current_rollout_state.get_legal_actions_for_player(player_to_act_rollout)
                        if possible_moves:
                            action = self._heuristic_rollout_policy(current_rollout_state, player_to_act_rollout, possible_moves)
                            if action: simulation_actions_set.add(action); current_rollout_state = current_rollout_state.apply_action(player_to_act_rollout, action); made_move_this_iter = True; player_acted_in_iter = player_to_act_rollout
                            else: current_rollout_state.boards[player_to_act_rollout].is_foul = True; current_rollout_state._player_finished_round[player_to_act_rollout] = True; current_rollout_state.current_hands[player_to_act_rollout] = None; made_move_this_iter = True; player_acted_in_iter = player_to_act_rollout
                        else: current_rollout_state.boards[player_to_act_rollout].is_foul = True; current_rollout_state._player_finished_round[player_to_act_rollout] = True; current_rollout_state.current_hands[player_to_act_rollout] = None; made_move_this_iter = True; player_acted_in_iter = player_to_act_rollout

            if not current_rollout_state.is_round_over():
                 needs_dealing = False
                 if not current_rollout_state.is_fantasyland_round and all(current_rollout_state._player_acted_this_street):
                      current_rollout_state.street += 1
                      if current_rollout_state.street <= 5: current_rollout_state._player_acted_this_street = [False] * current_rollout_state.NUM_PLAYERS; current_rollout_state.current_player_idx = 1 - current_rollout_state.dealer_idx; needs_dealing = True
                 elif not current_rollout_state.is_fantasyland_round and made_move_this_iter and player_acted_in_iter != -1:
                      next_player = 1 - player_acted_in_iter
                      if not current_rollout_state._player_acted_this_street[next_player] and not current_rollout_state._player_finished_round[next_player]: current_rollout_state.current_player_idx = next_player; needs_dealing = current_rollout_state.current_hands.get(next_player) is None
                 if needs_dealing or current_rollout_state.is_fantasyland_round:
                      players_to_deal = []
                      if needs_dealing and not current_rollout_state.is_fantasyland_round:
                           p_idx = current_rollout_state.current_player_idx
                           if not current_rollout_state._player_finished_round[p_idx] and current_rollout_state.current_hands.get(p_idx) is None: players_to_deal.append(p_idx)
                      elif current_rollout_state.is_fantasyland_round:
                           for p_idx_deal in range(current_rollout_state.NUM_PLAYERS):
                                if not current_rollout_state.fantasyland_status[p_idx_deal] and not current_rollout_state._player_finished_round[p_idx_deal] and current_rollout_state.current_hands.get(p_idx_deal) is None: players_to_deal.append(p_idx_deal)
                      for p_idx_deal in players_to_deal: current_rollout_state._deal_street_to_player(p_idx_deal)
            if not current_rollout_state.is_round_over() and not made_move_this_iter and steps > 1: break
        if steps >= MAX_ROLLOUT_STEPS: pass
        final_score_p0 = current_rollout_state.get_terminal_score()
        if perspective_player == 0: return float(final_score_p0), simulation_actions_set
        elif perspective_player == 1: return float(-final_score_p0), simulation_actions_set
        else: return 0.0, simulation_actions_set

    def _heuristic_rollout_policy(self, state: GameState, player_idx: int, actions: List[Any]) -> Optional[Any]:
        """Улучшенная эвристика для выбора хода в симуляции."""
        if not actions: return None
        if state.street == 1:
            best_action = None; best_score = -float('inf'); num_actions_to_check = min(len(actions), 50); actions_sample = random.sample(actions, num_actions_to_check)
            for action in actions_sample:
                placements, _ = action; score = 0; temp_board = state.boards[player_idx].copy(); valid = True
                for card, row, index in placements:
                     if not temp_board.add_card(card, row, index): valid = False; break
                if not valid: continue
                score += temp_board.get_total_royalty() * 0.1
                for r_name in temp_board.ROW_NAMES:
                     row_cards = temp_board.get_row_cards(r_name);
                     if not row_cards: continue
                     # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
                     rank_sum = sum(RANK_ORDER_MAP.get(c.rank, 0) for c in row_cards if hasattr(c, 'rank'))
                     # -----------------------------------------
                     if len(row_cards) == 0: continue # Добавлена проверка деления на ноль
                     avg_rank = rank_sum / len(row_cards)
                     if r_name == 'top': score += avg_rank * 0.5
                     elif r_name == 'middle': score += avg_rank * 0.8
                     else: score += avg_rank * 1.0
                     if r_name == 'top' and avg_rank > 9: score -= (avg_rank - 9) * 2
                     if r_name == 'middle' and avg_rank > 11: score -= (avg_rank - 11)
                rank_t = temp_board._get_rank('top'); rank_m = temp_board._get_rank('middle'); rank_b = temp_board._get_rank('bottom')
                if rank_m < rank_b - 500: score -= 20
                if rank_t < rank_m - 500: score -= 20
                score += random.uniform(-0.1, 0.1)
                if score > best_score: best_score = score; best_action = action
            return best_action if best_action else random.choice(actions)
        else: # Улицы 2-5
            hand = state.current_hands.get(player_idx)
            if not hand or len(hand) != 3: return random.choice(actions)
            best_action = None; best_score = -float('inf'); current_board = state.boards[player_idx]; num_actions_to_check = min(len(actions), 100); actions_sample = random.sample(actions, num_actions_to_check)
            for action in actions_sample:
                place1, place2, discarded = action; card1, row1, idx1 = place1; card2, row2, idx2 = place2; score = 0
                # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
                score -= RANK_ORDER_MAP.get(discarded.rank, 0) * 0.5
                # -----------------------------------------
                def placement_score(card, row, index, board):
                    b = 0; temp_board_eval = board.copy()
                    if not temp_board_eval.add_card(card, row, index): return -1000
                    current_row_cards = temp_board_eval.get_row_cards(row)
                    # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
                    rank_counts = Counter(RANK_ORDER_MAP.get(c.rank, 0) for c in current_row_cards if hasattr(c, 'rank'))
                    card_rank = RANK_ORDER_MAP.get(card.rank, 0)
                    # -----------------------------------------
                    card_rank_count = rank_counts.get(card_rank, 0)
                    if card_rank_count == 2: b += 5
                    if card_rank_count == 3: b += 15
                    if card_rank_count == 4: b += 30
                    # --- ИЗМЕНЕНИЕ: Используем SUIT_ORDER_MAP ---
                    suits = {SUIT_ORDER_MAP.get(c.suit, -1) for c in current_row_cards if hasattr(c, 'suit')}
                    # -----------------------------------------
                    if len(suits) == 1 and len(current_row_cards) >= 3: b += len(current_row_cards)
                    if row == 'top':
                         if card_rank >= 12: b += 10 # Q+
                         if card_rank_count == 2 and card_rank >= 6: b += 5 # Pair 66+
                         if card_rank_count == 3: b += 15 # Trips
                         if card_rank < 6: b -= 5 # Low card
                    elif row == 'middle':
                         if card_rank < 5: b -= 3 # Very low card
                    rank_t = temp_board_eval._get_rank('top'); rank_m = temp_board_eval._get_rank('middle'); rank_b = temp_board_eval._get_rank('bottom')
                    if rank_m < rank_b - 500: b -= 10
                    if rank_t < rank_m - 500: b -= 10
                    return b
                temp_board1 = current_board.copy()
                if not temp_board1.add_card(card1, row1, idx1): continue
                score1 = placement_score(card1, row1, idx1, current_board)
                score2 = placement_score(card2, row2, idx2, temp_board1)
                score += score1 + score2
                score += random.uniform(-0.1, 0.1)
                if score > best_score: best_score = score; best_action = action
            return best_action if best_action else random.choice(actions)

    def _heuristic_fantasyland_placement(self, hand: List[Card]) -> Tuple[Optional[Dict[str, List[Card]]], Optional[List[Card]]]:
        """Быстрая эвристика для ФЛ в симуляции."""
        solver = FantasylandSolver(); n_cards = len(hand); n_place = 13
        if n_cards < n_place: return None, None
        n_discard = n_cards - n_place
        try:
             if any(c is None for c in hand): print(f"Error: None found in FL hand during heuristic: {[str(c) for c in hand]}"); return None, None
             # --- ИЗМЕНЕНИЕ: Используем RANK_ORDER_MAP ---
             sorted_hand = sorted(hand, key=lambda c: RANK_ORDER_MAP.get(c.rank, 0))
             # -----------------------------------------
        except AttributeError as e: print(f"Error sorting FL hand in heuristic: {e}. Hand: {[str(c) for c in hand]}"); return None, None
        discarded_list = sorted_hand[:n_discard]; remaining = sorted_hand[n_discard:]
        if len(remaining) != 13: return None, None
        placement = solver._try_maximize_royalty_heuristic(remaining)
        if not placement:
              discard_combinations = list(combinations(hand, n_discard))
              if discard_combinations:
                   for _ in range(min(5, len(discard_combinations))):
                        discarded_list_alt = list(random.choice(discard_combinations))
                        remaining_alt = [c for c in hand if c not in discarded_list_alt]
                        if len(remaining_alt) == 13:
                             placement = solver._try_maximize_royalty_heuristic(remaining_alt)
                             if placement: discarded_list = discarded_list_alt; break
        return placement, discarded_list if placement else None

    def get_q_value(self, perspective_player: int) -> float:
        if self.visits == 0: return 0.0
        player_who_acted = self.parent._get_player_to_move() if self.parent else -1
        raw_q = self.total_reward / self.visits
        if player_who_acted == perspective_player: return raw_q
        elif player_who_acted != -1: return -raw_q
        else: return raw_q

    def get_rave_q_value(self, action: Any, perspective_player: int) -> float:
         rave_visits = self.rave_visits.get(action, 0)
         if rave_visits == 0: return 0.0
         rave_reward = self.rave_total_reward.get(action, 0.0)
         raw_rave_q = rave_reward / rave_visits
         player_to_move = self._get_player_to_move()
         if player_to_move == -1: return 0.0
         if player_to_move == perspective_player: return raw_rave_q
         else: return -raw_rave_q

    def uct_select_child(self, exploration_constant: float, rave_k: float) -> Optional['MCTSNode']:
        best_score = -float('inf'); best_child = None
        current_player_perspective = self._get_player_to_move()
        if current_player_perspective == -1: return None
        parent_visits = self.visits if self.visits > 0 else 1
        children_items = list(self.children.items())
        if not children_items: return None
        for action, child in children_items:
            child_visits = child.visits; rave_visits = self.rave_visits.get(action, 0); score = -float('inf')
            if child_visits == 0:
                if rave_visits > 0 and rave_k > 0: rave_q = self.get_rave_q_value(action, current_player_perspective); score = rave_q + exploration_constant * math.sqrt(math.log(parent_visits + 1e-6) / (rave_visits + 1e-6))
                else: score = float('inf')
            else:
                q_child = child.get_q_value(current_player_perspective); exploit_term = q_child; explore_term = exploration_constant * math.sqrt(math.log(parent_visits) / child_visits); ucb1_score = exploit_term + explore_term
                if rave_visits > 0 and rave_k > 0: rave_q = self.get_rave_q_value(action, current_player_perspective); beta = math.sqrt(rave_k / (3 * parent_visits + rave_k)); score = (1 - beta) * ucb1_score + beta * rave_q
                else: score = ucb1_score
            if score > best_score: best_score = score; best_child = child
            elif score == best_score and score != float('inf') and score != -float('inf'):
                 if random.choice([True, False]): best_child = child
        if best_child is None and children_items: best_child = random.choice([child for _, child in children_items])
        return best_child

    def __repr__(self):
        player_idx = self._get_player_to_move()
        player = f'P{player_idx}' if player_idx != -1 else 'T'
        q_val_p0 = self.get_q_value(0)
        return f"[{player} V={self.visits} Q0={q_val_p0:.2f} N_Act={len(self.children)} U_Act={len(self.untried_actions or [])}]"
