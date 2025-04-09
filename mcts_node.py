# mcts_node.py
import math
import random
from typing import Optional, Dict, Any, List, Tuple, Set
from game_state import GameState # Импортируем GameState
from card import Card
from scoring import RANK_CLASS_QUADS, RANK_CLASS_TRIPS, get_hand_rank_safe # Для эвристик

class MCTSNode:
    """Узел дерева MCTS для OFC Pineapple с RAVE."""
    def __init__(self, game_state: GameState, parent: Optional['MCTSNode'] = None, action: Optional[Any] = None):
        self.game_state: GameState = game_state
        self.parent: Optional['MCTSNode'] = parent
        self.action: Optional[Any] = action
        self.children: Dict[Any, 'MCTSNode'] = {}
        self.untried_actions: Optional[List[Any]] = None

        self.visits: int = 0
        # total_reward хранит сумму наград с точки зрения игрока, который СДЕЛАЛ ход, ведущий в этот узел
        self.total_reward: float = 0.0

        # RAVE / AMAF stats (для действий, ВОЗМОЖНЫХ из этого узла)
        self.rave_visits: Dict[Any, int] = {}
        self.rave_total_reward: Dict[Any, float] = {}

    def expand(self) -> Optional['MCTSNode']:
        """Расширяет узел, выбирая одно неиспробованное действие."""
        if self.untried_actions is None:
             self.untried_actions = self.game_state.get_legal_actions()
             random.shuffle(self.untried_actions)

        if not self.untried_actions:
             return None

        action = self.untried_actions.pop()
        next_state = self.game_state.apply_action(action) # apply_action обрабатывает все типы ходов
        child_node = MCTSNode(next_state, parent=self, action=action)
        self.children[action] = child_node

        # Инициализируем RAVE для действий ИЗ нового дочернего узла
        child_actions = child_node.game_state.get_legal_actions()
        for act in child_actions:
            child_node.rave_visits[act] = 0
            child_node.rave_total_reward[act] = 0.0

        return child_node

    def is_terminal(self) -> bool:
        return self.game_state.is_round_over()

    def rollout(self) -> Tuple[float, Set[Any]]:
        """Симуляция до конца раунда. Возвращает счет и набор действий симуляции."""
        current_rollout_state = self.game_state.copy()
        simulation_actions_set = set()
        
        # Обработка начального состояния ФЛ, если узел соответствует ему
        player_idx_rollout = current_rollout_state.current_player_idx
        if current_rollout_state.is_fantasyland_round and \
           current_rollout_state.fantasyland_status[player_idx_rollout] and \
           current_rollout_state.fantasyland_hands[player_idx_rollout]:
            hand = current_rollout_state.fantasyland_hands[player_idx_rollout]
            if hand:
                placement, discarded = self._heuristic_fantasyland_placement(hand)
                if placement:
                    current_rollout_state.apply_fantasyland_placement(player_idx_rollout, placement, discarded)
                    # Не добавляем "мета-действие" ФЛ в RAVE, т.к. оно уникально
                else: # Фол
                    current_rollout_state.boards[player_idx_rollout].is_foul = True
                    current_rollout_state._player_acted_this_street[player_idx_rollout] = True
                    current_rollout_state.fantasyland_hands[player_idx_rollout] = None
                    # Передаем ход, если нужно
                    if not all(current_rollout_state._player_acted_this_street):
                         current_rollout_state.current_player_idx = 1 - player_idx_rollout
                         if not current_rollout_state.fantasyland_status[current_rollout_state.current_player_idx]:
                              current_rollout_state._deal_street()

        # Основной цикл симуляции
        while not current_rollout_state.is_round_over():
            player_idx_rollout = current_rollout_state.current_player_idx

            # Обработка ФЛ хода внутри цикла
            if current_rollout_state.is_fantasyland_round and current_rollout_state.fantasyland_status[player_idx_rollout]:
                 hand = current_rollout_state.fantasyland_hands[player_idx_rollout]
                 if hand:
                     placement, discarded = self._heuristic_fantasyland_placement(hand)
                     if placement:
                          current_rollout_state.apply_fantasyland_placement(player_idx_rollout, placement, discarded)
                     else: # Фол
                          current_rollout_state.boards[player_idx_rollout].is_foul = True
                          current_rollout_state._player_acted_this_street[player_idx_rollout] = True
                          current_rollout_state.fantasyland_hands[player_idx_rollout] = None
                          if not all(current_rollout_state._player_acted_this_street):
                               current_rollout_state.current_player_idx = 1 - player_idx_rollout
                               if not current_rollout_state.fantasyland_status[current_rollout_state.current_player_idx]:
                                    current_rollout_state._deal_street()
                     continue # К следующей итерации while
                 else: # Руки нет, но раунд не закончен? Ошибка или ждем другого игрока
                      if not all(current_rollout_state._player_acted_this_street):
                           current_rollout_state.current_player_idx = 1 - player_idx_rollout
                           if not current_rollout_state.fantasyland_status[current_rollout_state.current_player_idx]:
                                current_rollout_state._deal_street()
                           continue
                      else: # Все сходили, раунд должен быть закончен
                           break


            # Обычный ход
            possible_moves = current_rollout_state.get_legal_actions()
            if not possible_moves: break

            action = self._heuristic_rollout_policy(current_rollout_state, possible_moves)
            simulation_actions_set.add(action)
            current_rollout_state = current_rollout_state.apply_action(action)

        final_score = current_rollout_state.get_terminal_score()
        return float(final_score), simulation_actions_set

    def _heuristic_rollout_policy(self, state: GameState, actions: List[Any]) -> Any:
        """Эвристика для выбора хода в симуляции."""
        if state.street == 1:
            # Для первой улицы берем случайное из сгенерированных (если они есть)
            return random.choice(actions) if actions else None

        # Улицы 2-5
        hand = state.cards_dealt_current_street
        if not hand or len(hand) != 3: return random.choice(actions) if actions else None

        best_action = None
        best_score = -float('inf')
        
        current_board = state.get_current_player_board()

        # Пытаемся найти "лучший" ход по простой оценке
        for action in actions:
            place1, place2, discarded = action
            card1, row1, idx1 = place1
            card2, row2, idx2 = place2
            
            # Оценка хода
            score = 0
            
            # 1. Оценка сброшенной карты (чем ниже, тем лучше сбросить)
            score -= discarded.int_rank * 0.1 # Небольшой вес

            # 2. Бонусы за размещение
            def placement_bonus(card, row, board):
                b = 0
                # Бонус за пару/сет
                current_row_cards = board.get_row_cards(row)
                for c in current_row_cards:
                    if c.int_rank == card.int_rank: b += 5
                # Бонус за ФЛ (QQ+ на топ)
                if row == 'top' and card.int_rank >= 12: b += 10
                # Штраф за мусор на топе
                if row == 'top' and card.int_rank < 7: b -= 3
                # Бонус за коннекторы/масть (упрощенно)
                for c in current_row_cards:
                    if abs(c.int_rank - card.int_rank) <= 2: b += 0.5
                    if c.int_suit == card.int_suit: b += 1
                return b

            score += placement_bonus(card1, row1, current_board)
            score += placement_bonus(card2, row2, current_board)
            
            # 3. Штраф за потенциальный фол (очень грубо)
            # Если кладем на мидл карту старше чем на боттоме, или на топ старше мидла
            # Это очень неточно, т.к. руки не полные
            # TODO: Можно добавить более умную проверку на фол-риск

            # Добавляем случайность
            score += random.uniform(-0.5, 0.5)

            if score > best_score:
                best_score = score
                best_action = action

        return best_action if best_action else random.choice(actions) # Возвращаем лучший или случайный

    def _heuristic_fantasyland_placement(self, hand: List[Card]) -> Tuple[Optional[Dict[str, List[Card]]], Optional[List[Card]]]:
         """Быстрая эвристика для ФЛ в симуляции."""
         solver = FantasylandSolver()
         n_cards = len(hand)
         n_place = 13
         if n_cards < n_place: return None, None
         n_discard = n_cards - n_place

         # Пробуем сбросить N самых низких карт
         sorted_hand = sorted(hand, key=lambda c: c.int_rank)
         discarded_list = sorted_hand[:n_discard]
         remaining = sorted_hand[n_discard:]
         
         placement = solver._try_maximize_royalty_heuristic(remaining)
         
         # Если первая попытка привела к фолу, пробуем сбросить другие карты (случайно)
         if not placement:
              discard_combinations = list(combinations(hand, n_discard))
              if discard_combinations:
                   discarded_list = list(random.choice(discard_combinations))
                   remaining = [c for c in hand if c not in discarded_list]
                   if len(remaining) == 13:
                        placement = solver._try_maximize_royalty_heuristic(remaining)

         return placement, discarded_list if placement else None


    def update_stats(self, reward: float, simulation_actions: Set[Any]):
        """Обновляет статистику узла и RAVE."""
        self.visits += 1
        # Награда reward - это очки с точки зрения игрока 0
        # Обновляем total_reward с точки зрения игрока, который сделал ход СЮДА (родительский игрок)
        if self.parent:
            parent_player_idx = self.parent.game_state.current_player_idx
            if parent_player_idx == 0:
                 self.total_reward += reward
            else:
                 self.total_reward -= reward # Инвертируем для оппонента

            # RAVE Update (Обновляем RAVE в РОДИТЕЛЕ для действий, сделанных в симуляции)
            possible_parent_actions = self.parent.children.keys()
            relevant_sim_actions = simulation_actions.intersection(possible_parent_actions)

            for action in relevant_sim_actions:
                 if action in self.parent.rave_visits:
                     self.parent.rave_visits[action] += 1
                     # RAVE награда обновляется с точки зрения игрока, который ходил в РОДИТЕЛЕ
                     if parent_player_idx == 0:
                          self.parent.rave_total_reward[action] += reward
                     else:
                          self.parent.rave_total_reward[action] -= reward
                 # else: # Ошибка инициализации RAVE?
                 #    print(f"Warning: Action {action} not found in parent's rave_visits during RAVE update.")


    def uct_select_child(self, exploration_constant: float, rave_k: float) -> Optional['MCTSNode']:
        """Выбирает лучший дочерний узел по UCB1-RAVE."""
        best_score = -float('inf')
        best_child = None

        current_player_perspective = self.game_state.current_player_idx

        # Инициализация RAVE, если нужно (для действий из ТЕКУЩЕГО узла)
        if not self.rave_visits and self.children:
             for action in self.children.keys():
                 self.rave_visits[action] = 0
                 self.rave_total_reward[action] = 0.0

        for action, child in self.children.items():
            if child.visits == 0:
                # First Play Urgency (FPU) с использованием RAVE
                rave_visits = self.rave_visits.get(action, 0)
                if rave_visits > 0:
                    # Используем RAVE оценку как начальную эвристику
                    rave_q = self.rave_total_reward.get(action, 0.0) / rave_visits
                    # Корректируем RAVE оценку на перспективу текущего игрока
                    if current_player_perspective != 0: rave_q = -rave_q
                    score = rave_q + exploration_constant * math.sqrt(math.log(self.visits + 1) / (rave_visits + 1))
                else:
                    score = float('inf') # Стандартный UCB для неисследованных
            else:
                # UCB1 part (с точки зрения игрока, который будет ходить ИЗ child)
                # total_reward в child уже с точки зрения игрока, сделавшего ход В child
                # Нам нужна оценка с точки зрения игрока, который будет ходить ИЗ child
                q_child_perspective = child.total_reward / child.visits
                # Если игрок в child (тот, кто будет ходить) не совпадает с текущим игроком (кто выбирает), инвертируем Q
                if child.game_state.current_player_idx != current_player_perspective:
                     q_child_perspective = -q_child_perspective

                exploit_term = q_child_perspective
                explore_term = exploration_constant * math.sqrt(math.log(self.visits) / child.visits)
                ucb1_score = exploit_term + explore_term

                # RAVE part (с точки зрения игрока, который ходит СЕЙЧАС в self)
                rave_visits = self.rave_visits.get(action, 0)
                if rave_visits > 0:
                    rave_q_parent_perspective = self.rave_total_reward.get(action, 0.0) / rave_visits
                    # Корректируем RAVE оценку на перспективу текущего игрока
                    if current_player_perspective != 0: rave_q_parent_perspective = -rave_q_parent_perspective
                    
                    rave_exploit_term = rave_q_parent_perspective
                    beta = math.sqrt(rave_k / (3 * self.visits + rave_k))
                    score = (1 - beta) * ucb1_score + beta * rave_exploit_term
                else:
                    score = ucb1_score

            if score > best_score:
                best_score = score
                best_child = child

        return best_child

    def __repr__(self):
        player = self.game_state.current_player_idx
        return f"[P{player} V={self.visits} Q={self.total_reward:.2f} N_Act={len(self.children)}]"