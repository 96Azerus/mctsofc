# mcts_agent.py
import math
import time
import random
# import multiprocessing # УДАЛЕНО
from typing import Optional, Any, List, Tuple, Set
from mcts_node import MCTSNode
from game_state import GameState
from fantasyland_solver import FantasylandSolver
from card import card_to_str
import traceback # Добавлено для отладки ошибок

# Функция-воркер run_parallel_rollout УДАЛЕНА

class MCTSAgent:
    """Агент MCTS для OFC Pineapple с RAVE (БЕЗ параллелизации)."""
    DEFAULT_EXPLORATION = 1.414
    DEFAULT_RAVE_K = 500
    DEFAULT_TIME_LIMIT_MS = 5000
    # Параметры параллелизации УДАЛЕНЫ

    def __init__(self,
                 exploration: Optional[float] = None,
                 rave_k: Optional[float] = None,
                 time_limit_ms: Optional[int] = None):
                 # num_workers, rollouts_per_leaf УДАЛЕНЫ

        self.exploration = exploration if exploration is not None else self.DEFAULT_EXPLORATION
        self.rave_k = rave_k if rave_k is not None else self.DEFAULT_RAVE_K
        time_limit_val = time_limit_ms if time_limit_ms is not None else self.DEFAULT_TIME_LIMIT_MS
        self.time_limit = time_limit_val / 1000.0

        self.fantasyland_solver = FantasylandSolver()
        print(f"MCTS Agent initialized with: TimeLimit={self.time_limit:.2f}s, Exploration={self.exploration}, RaveK={self.rave_k} (Single-threaded)")

        # Вызов set_start_method УДАЛЕН


    def choose_action(self, game_state: GameState) -> Optional[Any]:
        """Выбирает лучшее действие с помощью MCTS (последовательно)."""
        player_to_act = -1
        # ... (логика определения player_to_act как раньше) ...
        gs = game_state
        if gs.is_fantasyland_round:
             for i in range(gs.NUM_PLAYERS):
                  if gs.fantasyland_status[i] and not gs._player_finished_round[i]:
                       player_to_act = i; break
             if player_to_act == -1:
                  for i in range(gs.NUM_PLAYERS):
                       if not gs.fantasyland_status[i] and not gs._player_finished_round[i] and gs.current_hands.get(i):
                            player_to_act = i; break
             if player_to_act == -1: player_to_act = gs.current_player_idx
        else:
             player_to_act = gs.current_player_idx
        if player_to_act == -1:
             print("Error: Could not determine player to act in choose_action.")
             return None

        # --- Обработка хода в Fantasyland (без изменений) ---
        if game_state.is_fantasyland_round and game_state.fantasyland_status[player_to_act]:
             # ... (код как раньше) ...
             hand = game_state.fantasyland_hands[player_to_act]
             if hand:
                 # print(f"Player {player_to_act} solving Fantasyland...")
                 start_fl_time = time.time()
                 placement, discarded = self.fantasyland_solver.solve(hand)
                 solve_time = time.time() - start_fl_time
                 # print(f"Fantasyland solved in {solve_time:.3f}s")
                 if placement:
                     return ("FANTASYLAND_PLACEMENT", placement, discarded)
                 else:
                     print("Warning: Fantasyland solver failed.")
                     return ("FANTASYLAND_FOUL", hand)
             else:
                 return None

        # --- Обычный ход MCTS ---
        initial_actions = game_state.get_legal_actions_for_player(player_to_act)
        if not initial_actions: return None
        if len(initial_actions) == 1: return initial_actions[0]

        root_node = MCTSNode(game_state)
        root_node.untried_actions = list(initial_actions)
        random.shuffle(root_node.untried_actions)
        for act in root_node.untried_actions: # Инициализация RAVE
             if act not in root_node.rave_visits:
                  root_node.rave_visits[act] = 0
                  root_node.rave_total_reward[act] = 0.0

        start_time = time.time()
        num_simulations = 0

        # --- Последовательный MCTS цикл ---
        try:
            while time.time() - start_time < self.time_limit:
                # --- Selection & Expansion ---
                path, leaf_node = self._select(root_node)
                if leaf_node is None: continue

                simulation_actions = set()
                reward = 0.0
                node_to_rollout_from = leaf_node
                expanded_node = None

                if not leaf_node.is_terminal():
                    # --- Expansion (попытка) ---
                    if leaf_node.untried_actions:
                         expanded_node = leaf_node.expand()
                         if expanded_node:
                              node_to_rollout_from = expanded_node
                              path.append(expanded_node)

                    # --- Rollout (последовательный) ---
                    reward, sim_actions = node_to_rollout_from.rollout(perspective_player=0)
                    simulation_actions.update(sim_actions)
                    num_simulations += 1
                else: # Лист терминальный
                    reward = leaf_node.game_state.get_terminal_score()
                    num_simulations += 1

                # --- Backpropagation ---
                # Добавляем действие, приведшее к expanded_node (если было)
                if expanded_node and expanded_node.action:
                     simulation_actions.add(expanded_node.action)
                self._backpropagate(path, reward, simulation_actions) # Используем обычный _backpropagate

        except Exception as e:
             print(f"Error during MCTS sequential execution: {e}")
             traceback.print_exc()
             return random.choice(initial_actions) if initial_actions else None

        elapsed_time = time.time() - start_time
        # print(f"MCTS ran {num_simulations} simulations in {elapsed_time:.3f}s ({num_simulations/elapsed_time:.1f} sims/s) sequentially.")

        # --- Выбор лучшего хода (без изменений) ---
        if not root_node.children:
            return random.choice(initial_actions) if initial_actions else None

        # ... (Вывод статистики и выбор best_action_robust как раньше) ...
        # N_best = 5
        # sorted_children = sorted(root_node.children.items(), key=lambda item: item[1].visits, reverse=True)
        # print(f"--- MCTS Action Stats for Player {player_to_act} (Top {N_best}) ---")
        # total_visits = root_node.visits if root_node.visits > 0 else 1
        # for i, (action, child) in enumerate(sorted_children):
        #      if i >= N_best and child.visits < 1: break
        #      q_val = child.get_q_value(perspective_player=player_to_act)
        #      rave_q = root_node.get_rave_q_value(action, perspective_player=player_to_act)
        #      visit_perc = (child.visits / total_visits) * 100
        #      print(f"  Action: {self._format_action(action)}")
        #      print(f"    Visits: {child.visits} ({visit_perc:.1f}%) | Q: {q_val:.3f} | RAVE_Q: {rave_q:.3f}")
        # print("---------------------------------")

        best_action_robust = max(root_node.children, key=lambda act: root_node.children[act].visits)
        # print(f"Chosen action (most visited): {self._format_action(best_action_robust)}")
        return best_action_robust


    def _select(self, node: MCTSNode) -> Tuple[List[MCTSNode], Optional[MCTSNode]]:
        """Фаза выбора узла для расширения/симуляции (без изменений)."""
        # ... (код как в предыдущей версии) ...
        path = [node]
        current_node = node
        while not current_node.is_terminal():
            player_to_move = current_node._get_player_to_move() # Используем хелпер узла
            if player_to_move == -1: return path, current_node # Терминальный

            if current_node.untried_actions is None:
                 current_node.untried_actions = current_node.game_state.get_legal_actions_for_player(player_to_move)
                 random.shuffle(current_node.untried_actions)
                 for act in current_node.untried_actions:
                     if act not in current_node.rave_visits:
                         current_node.rave_visits[act] = 0
                         current_node.rave_total_reward[act] = 0.0

            if current_node.untried_actions:
                return path, current_node # Возвращаем для расширения

            if not current_node.children:
                 return path, current_node # Лист

            selected_child = current_node.uct_select_child(self.exploration, self.rave_k)
            if selected_child is None:
                print(f"Warning: Selection returned None child from node {current_node}. Returning node as leaf.")
                if current_node.children:
                     try: selected_child = random.choice(list(current_node.children.values()))
                     except IndexError: return path, current_node
                else: return path, current_node
            current_node = selected_child
            path.append(current_node)
        return path, current_node


    def _backpropagate(self, path: List[MCTSNode], reward: float, simulation_actions: Set[Any]):
        """Обычный обратный проход (не параллельный)."""
        # reward - счет с точки зрения игрока 0
        for node in reversed(path):
            node.visits += 1
            player_who_acted = node.parent._get_player_to_move() if node.parent else -1

            if player_who_acted == 0: node.total_reward += reward
            elif player_who_acted == 1: node.total_reward -= reward

            # Обновляем RAVE
            player_to_move_from_node = node._get_player_to_move()
            if player_to_move_from_node != -1: # Не обновляем RAVE для терминального узла
                 possible_actions_from_node = set(node.children.keys())
                 if node.untried_actions: possible_actions_from_node.update(node.untried_actions)
                 relevant_sim_actions = simulation_actions.intersection(possible_actions_from_node)

                 for action in relevant_sim_actions:
                      if action in node.rave_visits:
                           node.rave_visits[action] += 1
                           if player_to_move_from_node == 0: node.rave_total_reward[action] += reward
                           elif player_to_move_from_node == 1: node.rave_total_reward[action] -= reward


    # Метод _backpropagate_parallel УДАЛЕН

    def _format_action(self, action: Any) -> str:
        """Форматирует действие для вывода (без изменений)."""
        # ... (код как в предыдущей версии) ...
        if action is None: return "None"
        try:
            if isinstance(action, tuple) and len(action) == 3 and isinstance(action[0], tuple) and isinstance(action[0][0], Card):
                p1, p2, d = action
                return f"PINEAPPLE: {card_to_str(p1[0])}@{p1[1]}{p1[2]}, {card_to_str(p2[0])}@{p2[1]}{p2[2]}; Discard {card_to_str(d)}"
            elif isinstance(action, tuple) and len(action) == 2 and isinstance(action[0], list) and action[0] and isinstance(action[0][0], tuple):
                 placements_str = ", ".join([f"{card_to_str(c)}@{r}{i}" for c, r, i in action[0]])
                 return f"STREET 1: Place {placements_str}"
            elif isinstance(action, tuple) and len(action) == 2 and isinstance(action[0], list) and action[0] and isinstance(action[0][0], Card):
                 return f"FANTASYLAND_META ({len(action[0])} cards)"
            elif isinstance(action, tuple) and action[0] == "FANTASYLAND_PLACEMENT":
                 return f"FANTASYLAND_PLACE (Discard {len(action[2])})"
            elif isinstance(action, tuple) and action[0] == "FANTASYLAND_FOUL":
                 return f"FANTASYLAND_FOUL (Discard {len(action[1])})"
            else:
                 if isinstance(action, tuple):
                      formatted_items = []
                      for item in action:
                           if isinstance(item, (str, int, float, bool, type(None))): formatted_items.append(repr(item))
                           elif isinstance(item, Card): formatted_items.append(card_to_str(item))
                           elif isinstance(item, list): formatted_items.append("[...]")
                           elif isinstance(item, dict): formatted_items.append("{...}")
                           else: formatted_items.append(self._format_action(item))
                      return f"Unknown Tuple Action: ({', '.join(formatted_items)})"
                 return str(action)
        except Exception as e:
             return "ErrorFormattingAction"
