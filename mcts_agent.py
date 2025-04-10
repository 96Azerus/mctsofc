# mcts_agent.py
import math
import time
import random
import multiprocessing # Добавляем импорт
import traceback # Для отладки ошибок
from typing import Optional, Any, List, Tuple, Set
from mcts_node import MCTSNode # Импортируем обновленный MCTSNode
from game_state import GameState
from fantasyland_solver import FantasylandSolver
from card import card_to_str # Импортируем для форматирования

# Функция-воркер для параллельного роллаута (должна быть вне класса для pickle)
def run_parallel_rollout(node_state_dict: dict) -> Tuple[float, Set[Any]]:
    """Запускает один роллаут из переданного состояния узла."""
    # Восстанавливаем состояние и создаем временный узел
    try:
        game_state = GameState.from_dict(node_state_dict)
        # Убедимся, что состояние не терминальное перед роллаутом
        if game_state.is_round_over():
             # Если терминальное, возвращаем счет напрямую
             score_p0 = game_state.get_terminal_score()
             return float(score_p0), set()

        temp_node = MCTSNode(game_state) # Parent и action не важны для роллаута
        # Запускаем роллаут с точки зрения игрока 0
        reward, sim_actions = temp_node.rollout(perspective_player=0)
        return reward, sim_actions
    except Exception as e:
        print(f"Error in parallel rollout worker: {e}")
        traceback.print_exc()
        return 0.0, set() # Возвращаем нейтральный результат в случае ошибки


class MCTSAgent:
    """Агент MCTS для OFC Pineapple с RAVE и параллелизацией."""
    DEFAULT_EXPLORATION = 1.414
    DEFAULT_RAVE_K = 500
    DEFAULT_TIME_LIMIT_MS = 5000
    # Используем N-1 ядер, но не менее 1
    DEFAULT_NUM_WORKERS = max(1, multiprocessing.cpu_count() - 1 if multiprocessing.cpu_count() > 1 else 1)
    DEFAULT_ROLLOUTS_PER_LEAF = 4 # Количество роллаутов на лист за одну параллельную итерацию

    def __init__(self,
                 exploration: Optional[float] = None,
                 rave_k: Optional[float] = None,
                 time_limit_ms: Optional[int] = None,
                 num_workers: Optional[int] = None, # Параметр для кол-ва воркеров
                 rollouts_per_leaf: Optional[int] = None): # Параметр для кол-ва роллаутов на лист

        self.exploration = exploration if exploration is not None else self.DEFAULT_EXPLORATION
        self.rave_k = rave_k if rave_k is not None else self.DEFAULT_RAVE_K
        time_limit_val = time_limit_ms if time_limit_ms is not None else self.DEFAULT_TIME_LIMIT_MS
        self.time_limit = time_limit_val / 1000.0 # Конвертируем в секунды
        # Ограничиваем num_workers максимальным количеством ядер
        max_cpus = multiprocessing.cpu_count()
        requested_workers = num_workers if num_workers is not None else self.DEFAULT_NUM_WORKERS
        self.num_workers = max(1, min(requested_workers, max_cpus))

        self.rollouts_per_leaf = rollouts_per_leaf if rollouts_per_leaf is not None else self.DEFAULT_ROLLOUTS_PER_LEAF
        # Уменьшаем rollouts_per_leaf, если воркеров мало, чтобы избежать простоя
        if self.num_workers == 1 and self.rollouts_per_leaf > 1:
             print(f"Warning: num_workers=1, reducing rollouts_per_leaf from {self.rollouts_per_leaf} to 1.")
             self.rollouts_per_leaf = 1

        self.fantasyland_solver = FantasylandSolver()
        print(f"MCTS Agent initialized with: TimeLimit={self.time_limit:.2f}s, Exploration={self.exploration}, RaveK={self.rave_k}, Workers={self.num_workers}, RolloutsPerLeaf={self.rollouts_per_leaf}")

        # Устанавливаем метод старта процессов (важно для некоторых ОС и окружений)
        # Делаем это один раз глобально, если возможно
        try:
             # Проверяем, установлен ли метод, и если нет, или не 'spawn', пытаемся установить 'spawn'
             current_method = multiprocessing.get_start_method(allow_none=True)
             if current_method != 'spawn':
                  # print(f"Attempting to set multiprocessing start method to 'spawn' (current: {current_method}).")
                  multiprocessing.set_start_method('spawn', force=True) # force=True может быть необходимо
                  # print(f"Multiprocessing start method set to: {multiprocessing.get_start_method()}")
        except Exception as e:
             print(f"Warning: Could not set multiprocessing start method to 'spawn': {e}. Using default ({multiprocessing.get_start_method()}).")


    def choose_action(self, game_state: GameState) -> Optional[Any]:
        """Выбирает лучшее действие с помощью MCTS с параллелизацией."""
        # Определяем игрока, для которого выбираем ход
        player_to_act = -1
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

        # --- Обработка хода в Fantasyland ---
        if game_state.is_fantasyland_round and game_state.fantasyland_status[player_to_act]:
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

        try:
            # Используем контекстный менеджер для пула
            with multiprocessing.Pool(processes=self.num_workers) as pool:
                while time.time() - start_time < self.time_limit:
                    # --- Selection ---
                    path, leaf_node = self._select(root_node)
                    if leaf_node is None: continue

                    results = []
                    simulation_actions_aggregated = set()
                    node_to_rollout_from = leaf_node
                    expanded_node = None

                    if not leaf_node.is_terminal():
                        # --- Expansion (попытка) ---
                        if leaf_node.untried_actions:
                             expanded_node = leaf_node.expand()
                             if expanded_node:
                                  node_to_rollout_from = expanded_node
                                  path.append(expanded_node)

                        # --- Parallel Rollouts ---
                        try:
                            node_state_dict = node_to_rollout_from.game_state.to_dict()
                        except Exception as e:
                             print(f"Error serializing state for parallel rollout: {e}")
                             continue

                        async_results = [pool.apply_async(run_parallel_rollout, (node_state_dict,))
                                         for _ in range(self.rollouts_per_leaf)]

                        for res in async_results:
                            try:
                                timeout_get = max(0.1, self.time_limit * 0.1)
                                reward, sim_actions = res.get(timeout=timeout_get)
                                results.append(reward)
                                simulation_actions_aggregated.update(sim_actions)
                                num_simulations += 1
                            except multiprocessing.TimeoutError:
                                print("Warning: Rollout worker timed out.")
                            except Exception as e:
                                print(f"Warning: Error getting result from worker: {e}")

                    else: # Лист терминальный
                        reward = leaf_node.game_state.get_terminal_score()
                        results.append(reward)
                        num_simulations += 1

                    # --- Backpropagation ---
                    if results:
                        total_reward_from_batch = sum(results)
                        num_rollouts_in_batch = len(results)
                        if expanded_node and expanded_node.action:
                             simulation_actions_aggregated.add(expanded_node.action)
                        self._backpropagate_parallel(path, total_reward_from_batch, num_rollouts_in_batch, simulation_actions_aggregated)

        except Exception as e:
             print(f"Error during MCTS parallel execution: {e}")
             traceback.print_exc()
             return random.choice(initial_actions) if initial_actions else None

        elapsed_time = time.time() - start_time
        # print(f"MCTS ran {num_simulations} simulations in {elapsed_time:.3f}s ({num_simulations/elapsed_time:.1f} sims/s) using {self.num_workers} workers.")

        # --- Выбор лучшего хода ---
        if not root_node.children:
            return random.choice(initial_actions) if initial_actions else None

        # Вывод статистики (опционально)
        # ...

        best_action_robust = max(root_node.children, key=lambda act: root_node.children[act].visits)
        return best_action_robust


    def _select(self, node: MCTSNode) -> Tuple[List[MCTSNode], Optional[MCTSNode]]:
        """Фаза выбора узла для расширения/симуляции."""
        path = [node]
        current_node = node
        while not current_node.is_terminal():
            player_to_move = current_node._get_player_to_move()
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


    def _backpropagate_parallel(self, path: List[MCTSNode], total_reward: float, num_rollouts: int, simulation_actions: Set[Any]):
        """Фаза обратного распространения для параллельных роллаутов."""
        if num_rollouts == 0: return

        for node in reversed(path):
            node.visits += num_rollouts
            # Игрок, который сделал ход СЮДА
            player_who_acted = node.parent._get_player_to_move() if node.parent else -1

            if player_who_acted == 0: node.total_reward += total_reward
            elif player_who_acted == 1: node.total_reward -= total_reward

            # Обновляем RAVE
            player_to_move_from_node = node._get_player_to_move()
            if player_to_move_from_node != -1: # Не обновляем RAVE для терминального узла
                 possible_actions_from_node = set(node.children.keys())
                 if node.untried_actions: possible_actions_from_node.update(node.untried_actions)
                 relevant_sim_actions = simulation_actions.intersection(possible_actions_from_node)

                 for action in relevant_sim_actions:
                      if action in node.rave_visits:
                           # Приближение: увеличиваем на num_rollouts
                           node.rave_visits[action] += num_rollouts
                           # RAVE награда обновляется с точки зрения игрока player_to_move_from_node
                           if player_to_move_from_node == 0: node.rave_total_reward[action] += total_reward
                           elif player_to_move_from_node == 1: node.rave_total_reward[action] -= total_reward


    def _format_action(self, action: Any) -> str:
        """Форматирует действие для вывода."""
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
