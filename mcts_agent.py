# mcts_agent.py
import math
import time
import random
from typing import Optional, Any, List, Tuple, Set
from mcts_node import MCTSNode
from game_state import GameState
from fantasyland_solver import FantasylandSolver

class MCTSAgent:
    """Агент MCTS для OFC Pineapple."""
    def __init__(self, exploration: float = 1.414, rave_k: float = 500, time_limit_ms: int = 5000):
        self.exploration = exploration # Константа UCB1
        self.rave_k = rave_k # Параметр для RAVE (нужно тюнить)
        self.time_limit = time_limit_ms / 1000.0
        self.fantasyland_solver = FantasylandSolver() # Солвер для реального хода ФЛ

    def choose_action(self, game_state: GameState) -> Optional[Any]:
        """Выбирает лучшее действие с помощью MCTS."""

        # --- Обработка хода в Fantasyland ---
        if game_state.is_fantasyland_round and game_state.fantasyland_status[game_state.current_player_idx]:
             hand = game_state.fantasyland_hands[game_state.current_player_idx]
             if hand:
                 print(f"Player {game_state.current_player_idx} solving Fantasyland with {len(hand)} cards...")
                 start_fl_time = time.time()
                 # Вызываем ПОЛНЫЙ солвер для реального хода
                 placement, discarded = self.fantasyland_solver.solve(hand)
                 print(f"Fantasyland solved in {time.time() - start_fl_time:.2f}s")
                 if placement:
                     # Возвращаем специальное действие для применения в main.py
                     return ("FANTASYLAND_PLACEMENT", placement, discarded)
                 else:
                     print("Warning: Fantasyland solver failed to find a valid placement.")
                     # Возвращаем действие "Фол" (или None для обработки в main)
                     return ("FANTASYLAND_FOUL", hand) # Передаем руку, чтобы сбросить карты
             else:
                 # Руки нет, ход уже сделан?
                 print(f"Warning: Player {game_state.current_player_idx} is in FL but has no hand.")
                 return None

        # --- Обычный ход MCTS ---
        root_node = MCTSNode(game_state)
        start_time = time.time()
        num_rollouts = 0

        # Проверяем, есть ли вообще легальные ходы из корня
        initial_actions = root_node.game_state.get_legal_actions()
        if not initial_actions:
             print("Warning: No legal actions from root state.")
             return None
        root_node.untried_actions = initial_actions # Инициализируем сразу

        while time.time() - start_time < self.time_limit:
            path, leaf_node = self._select(root_node)
            if leaf_node is None: continue # Ошибка выбора

            simulation_actions = set() # Действия, сделанные в симуляции для RAVE

            if not leaf_node.is_terminal():
                # Если лист не терминальный, пытаемся расширить
                new_node = leaf_node.expand()
                if new_node:
                     # Успешно расширили, делаем rollout из нового узла
                     reward, sim_actions_from_rollout = new_node.rollout()
                     simulation_actions.update(sim_actions_from_rollout)
                     if new_node.action: simulation_actions.add(new_node.action)
                     path.append(new_node) # Добавляем новый узел в путь
                else:
                     # Не удалось расширить (возможно, нет ходов из leaf_node)
                     # Делаем rollout из самого leaf_node
                     reward, sim_actions_from_rollout = leaf_node.rollout()
                     simulation_actions.update(sim_actions_from_rollout)
            else:
                # Лист уже терминальный
                reward = leaf_node.game_state.get_terminal_score()

            self._backpropagate(path, reward, simulation_actions)
            num_rollouts += 1

        # print(f"MCTS ran {num_rollouts} rollouts in {time.time() - start_time:.2f}s")

        # --- Выбор лучшего хода ---
        if not root_node.children:
            print("Warning: MCTS root has no children after search. Choosing random initial action.")
            return random.choice(initial_actions) if initial_actions else None

        # Выводим статистику для топ-N ходов
        N_best = 5
        sorted_children = sorted(root_node.children.items(),
                                 key=lambda item: item[1].visits, reverse=True)

        print("--- MCTS Action Stats (Top N) ---")
        for i, (action, child) in enumerate(sorted_children):
             if i >= N_best and child.visits < 10: break # Показываем топ-N или пока визитов > 10
             q_val = child.total_reward / (child.visits + 1e-6)
             # Корректируем Q на перспективу игрока в корне
             if root_node.game_state.current_player_idx != 0: q_val = -q_val
             rave_visits = root_node.rave_visits.get(action, 0)
             rave_q = root_node.rave_total_reward.get(action, 0.0) / (rave_visits + 1e-6)
             if root_node.game_state.current_player_idx != 0: rave_q = -rave_q
             
             print(f"Action: {self._format_action(action)} | Visits: {child.visits} | Q: {q_val:.3f} | RAVE_Q: {rave_q:.3f}")
        print("---------------------------------")

        # Выбираем самый посещаемый ход (Robust Child)
        best_action_robust = max(root_node.children, key=lambda action: root_node.children[action].visits)
        print(f"Chosen action (most visited): {self._format_action(best_action_robust)}")
        return best_action_robust

    def _select(self, node: MCTSNode) -> Tuple[List[MCTSNode], Optional[MCTSNode]]:
        """Фаза выбора и расширения."""
        path = [node]
        while not node.is_terminal():
            if node.untried_actions is None:
                 # Инициализация при первом посещении узла в этой симуляции
                 node.untried_actions = node.game_state.get_legal_actions()
                 random.shuffle(node.untried_actions)
                 # Инициализация RAVE для действий из этого узла
                 for act in node.untried_actions:
                     if act not in node.rave_visits:
                         node.rave_visits[act] = 0
                         node.rave_total_reward[act] = 0.0

            if node.untried_actions:
                # Есть неиспробованные ходы - расширяем
                new_node = node.expand()
                if new_node:
                     path.append(new_node)
                     return path, new_node
                else:
                     # Не удалось расширить (нет легальных ходов?)
                     # print(f"Warning: Expansion failed for node.")
                     return path, node # Возвращаем текущий узел как лист

            elif not node.children:
                 # Лист без потомков и без неиспробованных действий
                 return path, node
            else:
                # Выбираем лучший дочерний узел по UCB+RAVE
                node = node.uct_select_child(self.exploration, self.rave_k)
                if node is None:
                    # print("Warning: Selection returned None child. Returning parent.")
                    return path[:-1], path[-1] if len(path) > 1 else path[0]
                path.append(node)
        # Дошли до терминального узла
        return path, node

    def _backpropagate(self, path: List[MCTSNode], reward: float, simulation_actions: Set[Any]):
        """Фаза обратного распространения с RAVE."""
        actions_in_path_and_sim = set(simulation_actions)
        # Добавляем действия, совершенные на пути выбора узла
        for node in path:
            if node.action is not None:
                actions_in_path_and_sim.add(node.action)

        # Обновляем статистику узлов
        for node in reversed(path):
            # Передаем полный набор действий из симуляции + пути для RAVE
            node.update_stats(reward, actions_in_path_and_sim)

    def _format_action(self, action: Any) -> str:
        """Форматирует действие для вывода."""
        if isinstance(action, tuple) and len(action) == 3 and isinstance(action[0], tuple):
            # Pineapple action: ((c1, r1, i1), (c2, r2, i2), discard)
            p1, p2, d = action
            return f"Place {card_to_str(p1[0])}@{p1[1]}{p1[2]}, {card_to_str(p2[0])}@{p2[1]}{p2[2]}; Discard {card_to_str(d)}"
        elif isinstance(action, tuple) and len(action) == 2 and isinstance(action[0], list):
             # Street 1 action: ([(c, r, i)...], [])
             placements_str = ", ".join([f"{card_to_str(c)}@{r}{i}" for c, r, i in action[0]])
             return f"Street 1: Place {placements_str}"
        elif isinstance(action, tuple) and len(action) == 2 and isinstance(action[0], list) and isinstance(action[0][0], Card):
             # Fantasyland meta-action: (hand, [])
             return f"FANTASYLAND_SOLVE ({len(action[0])} cards)"
        elif isinstance(action, tuple) and action[0] == "FANTASYLAND_PLACEMENT":
             return "FANTASYLAND_PLACEMENT (Solved)"
        elif isinstance(action, tuple) and action[0] == "FANTASYLAND_FOUL":
             return "FANTASYLAND_FOUL (Solver Failed)"
        else:
             return str(action) # Неизвестный формат