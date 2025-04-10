# mcts_agent.py
import math
import time
import random
import multiprocessing # Добавляем импорт
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
        import traceback
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
             if multiprocessing.get_start_method(allow_none=True) is None:
                  multiprocessing.set_start_method('spawn')
             elif multiprocessing.get_start_method() != 'spawn':
                  print(f"Warning: Multiprocessing start method already set to '{multiprocessing.get_start_method()}'. Trying to force 'spawn'.")
                  # Попытка force=True может вызвать ошибку, если уже используется
                  try:
                       multiprocessing.set_start_method('spawn', force=True)
                  except RuntimeError as e:
                       print(f"Could not force 'spawn': {e}. Using existing method.")
        except Exception as e:
             print(f"Warning: Could not set multiprocessing start method to 'spawn': {e}. Using default.")


    def choose_action(self, game_state: GameState) -> Optional[Any]:
        """Выбирает лучшее действие с помощью MCTS с параллелизацией."""
        # Определяем игрока, для которого выбираем ход
        player_to_act = -1
        # Логика определения игрока, который должен ходить СЕЙЧАС
        if game_state.is_fantasyland_round:
             # Ищем первого игрока, который в ФЛ и еще не закончил
             for i in range(game_state.NUM_PLAYERS):
                  if game_state.fantasyland_status[i] and not game_state._player_finished_round[i]:
                       player_to_act = i
                       break
             # Если таких нет, ищем не-ФЛ игрока, который еще не закончил и имеет карты
             if player_to_act == -1:
                  for i in range(game_state.NUM_PLAYERS):
                       if not game_state.fantasyland_status[i] and not game_state._player_finished_round[i] and game_state.current_hands.get(i):
                            player_to_act = i
                            break
             # Если и таких нет, используем current_player_idx (маловероятно)
             if player_to_act == -1: player_to_act = game_state.current_player_idx
        else: # Обычный раунд
             player_to_act = game_state.current_player_idx

        if player_to_act == -1: # Не смогли определить игрока
             print("Error: Could not determine player to act in choose_action.")
             return None


        # --- Обработка хода в Fantasyland ---
        if game_state.is_fantasyland_round and game_state.fantasyland_status[player_to_act]:
             hand = game_state.fantasyland_hands[player_to_act]
             if hand:
                 # print(f"Player {player_to_act} solving Fantasyland with {len(hand)} cards...")
                 start_fl_time = time.time()
                 placement, discarded = self.fantasyland_solver.solve(hand)
                 solve_time = time.time() - start_fl_time
                 # print(f"Fantasyland solved in {solve_time:.3f}s")
                 if placement:
                     return ("FANTASYLAND_PLACEMENT", placement, discarded)
                 else:
                     print("Warning: Fantasyland solver failed to find a valid placement.")
                     return ("FANTASYLAND_FOUL", hand)
             else:
                 # print(f"Warning: Player {player_to_act} is in FL but has no hand (already finished?).")
                 return None # Ход уже сделан или ошибка

        # --- Обычный ход MCTS ---
        initial_actions = game_state.get_legal_actions_for_player(player_to_act)
        if not initial_actions:
             # Это может быть нормально, если игрок ждет карт
             # print(f"Warning: No legal actions for player {player_to_act} from current state.")
             return None
        if len(initial_actions) == 1:
             # print("Only one legal action, choosing it directly.")
             return initial_actions[0]

        root_node = MCTSNode(game_state)
        # Передаем начальные действия, чтобы MCTS не генерировал их заново
        root_node.untried_actions = list(initial_actions)
        random.shuffle(root_node.untried_actions)
        # Инициализируем RAVE для корня
        for act in root_node.untried_actions:
             if act not in root_node.rave_visits:
                  root_node.rave_visits[act] = 0
                  root_node.rave_total_reward[act] = 0.0


        start_time = time.time()
        num_simulations = 0 # Считаем общее количество симуляций

        # Создаем пул воркеров внутри функции для лучшей совместимости
        # Используем 'with' для автоматического закрытия пула
        try:
            # Используем контекстный менеджер для пула
            with multiprocessing.Pool(processes=self.num_workers) as pool:
                while time.time() - start_time < self.time_limit:
                    # --- Selection ---
                    path, leaf_node = self._select(root_node)
                    if leaf_node is None: continue # Ошибка выбора

                    results = [] # Хранение результатов параллельных роллаутов
                    simulation_actions_aggregated = set() # Агрегация действий для RAVE
                    node_to_rollout_from = leaf_node
                    expanded_node = None

                    if not leaf_node.is_terminal():
                        # --- Expansion (попытка) ---
                        # Расширяем узел, если есть неиспробованные действия
                        if leaf_node.untried_actions:
                             expanded_node = leaf_node.expand()
                             if expanded_node:
                                  node_to_rollout_from = expanded_node
                                  path.append(expanded_node) # Добавляем в путь для backpropagate
                        # Если не расширили (нет действий или все испробованы), роллаут из листа

                        # --- Parallel Rollouts ---
                        try:
                            # Сериализуем состояние узла для передачи воркерам
                            node_state_dict = node_to_rollout_from.game_state.to_dict()
                        except Exception as e:
                             print(f"Error serializing state for parallel rollout: {e}")
                             continue # Пропускаем итерацию

                        # Запускаем задачи в пуле
                        async_results = [pool.apply_async(run_parallel_rollout, (node_state_dict,))
                                         for _ in range(self.rollouts_per_leaf)]

                        # Собираем результаты
                        for res in async_results:
                            try:
                                # Уменьшим таймаут получения результата
                                timeout_get = max(0.1, self.time_limit * 0.1)
                                reward, sim_actions = res.get(timeout=timeout_get)
                                results.append(reward)
                                simulation_actions_aggregated.update(sim_actions)
                                num_simulations += 1
                            except multiprocessing.TimeoutError:
                                print("Warning: Rollout worker timed out.")
                            except Exception as e:
                                print(f"Warning: Error getting result from worker: {e}")
                                # Можно добавить обработку ошибок, например, пропуск результата

                    else: # Лист терминальный
                        reward = leaf_node.game_state.get_terminal_score()
                        results.append(reward)
                        num_simulations += 1 # Считаем как одну "симуляцию"

                    # --- Backpropagation ---
                    if results:
                        total_reward_from_batch = sum(results)
                        num_rollouts_in_batch = len(results)

                        # Добавляем действие, приведшее к expanded_node (если было расширение)
                        if expanded_node and expanded_node.action:
                             simulation_actions_aggregated.add(expanded_node.action)

                        self._backpropagate_parallel(path, total_reward_from_batch, num_rollouts_in_batch, simulation_actions_aggregated)

        except Exception as e:
             print(f"Error during MCTS parallel execution: {e}")
             import traceback
             traceback.print_exc()
             # В случае ошибки возвращаем случайное действие
             return random.choice(initial_actions) if initial_actions else None


        elapsed_time = time.time() - start_time
        # print(f"MCTS ran {num_simulations} simulations in {elapsed_time:.3f}s ({num_simulations/elapsed_time:.1f} sims/s) using {self.num_workers} workers.")

        # --- Выбор лучшего хода ---
        if not root_node.children:
            # print("Warning: MCTS root has no children after search. Choosing random initial action.")
            # Если нет детей, но были начальные действия, выбираем случайное из них
            return random.choice(initial_actions) if initial_actions else None

        # Вывод статистики (можно закомментировать для продакшена)
        # N_best = 5
        # sorted_children = sorted(root_node.children.items(), key=lambda item: item[1].visits, reverse=True)
        # print(f"--- MCTS Action Stats for Player {player_to_act} (Top {N_best}) ---")
        # total_visits = root_node.visits if root_node.visits > 0 else 1
        # for i, (action, child) in enumerate(sorted_children):
        #      if i >= N_best and child.visits < 1: break # Показываем только посещенные
        #      q_val = child.get_q_value(perspective_player=player_to_act)
        #      rave_q = root_node.get_rave_q_value(action, perspective_player=player_to_act)
        #      visit_perc = (child.visits / total_visits) * 100
        #      print(f"  Action: {self._format_action(action)}")
        #      print(f"    Visits: {child.visits} ({visit_perc:.1f}%) | Q: {q_val:.3f} | RAVE_Q: {rave_q:.3f}")
        # print("---------------------------------")

        # Выбираем самый посещаемый ход (Robust Child)
        best_action_robust = max(root_node.children, key=lambda act: root_node.children[act].visits)

        # print(f"Chosen action (most visited): {self._format_action(best_action_robust)}")
        return best_action_robust


    def _select(self, node: MCTSNode) -> Tuple[List[MCTSNode], Optional[MCTSNode]]:
        """Фаза выбора узла для расширения/симуляции."""
        path = [node]
        current_node = node
        while not current_node.is_terminal():
            # Определяем игрока, который ходит из current_node
            player_to_move = -1
            # Логика определения player_to_move
            gs = current_node.game_state
            if gs.is_fantasyland_round:
                 for i in range(gs.NUM_PLAYERS):
                      if gs.fantasyland_status[i] and not gs._player_finished_round[i]:
                           player_to_move = i; break
                 if player_to_move == -1:
                      for i in range(gs.NUM_PLAYERS):
                           if not gs.fantasyland_status[i] and not gs._player_finished_round[i] and gs.current_hands.get(i):
                                player_to_move = i; break
                 if player_to_move == -1: player_to_move = gs.current_player_idx
            else:
                 player_to_move = gs.current_player_idx

            if player_to_move == -1: # Не смогли определить
                 print("Select Error: Could not determine player to move.")
                 return path, current_node # Возвращаем текущий как лист

            # Инициализация неиспробованных действий и RAVE при первом посещении
            if current_node.untried_actions is None:
                 current_node.untried_actions = gs.get_legal_actions_for_player(player_to_move)
                 random.shuffle(current_node.untried_actions)
                 for act in current_node.untried_actions:
                     if act not in current_node.rave_visits:
                         current_node.rave_visits[act] = 0
                         current_node.rave_total_reward[act] = 0.0

            # Если есть неиспробованные действия, возвращаем текущий узел для расширения
            if current_node.untried_actions:
                return path, current_node

            # Если нет неиспробованных и нет детей, это лист
            if not current_node.children:
                 return path, current_node

            # Выбираем лучший дочерний узел по UCB+RAVE
            selected_child = current_node.uct_select_child(self.exploration, self.rave_k)
            if selected_child is None:
                # Этого не должно происходить, если есть дети и все посещены
                print(f"Warning: Selection returned None child from node {current_node}. Returning node as leaf.")
                # Пытаемся выбрать случайного ребенка, если возможно
                if current_node.children:
                     try:
                          selected_child = random.choice(list(current_node.children.values()))
                     except IndexError: # Словарь детей пуст?
                          return path, current_node
                else:
                     return path, current_node # Возвращаем текущий узел как лист
            current_node = selected_child
            path.append(current_node)

        # Дошли до терминального узла игры
        return path, current_node


    def _backpropagate_parallel(self, path: List[MCTSNode], total_reward: float, num_rollouts: int, simulation_actions: Set[Any]):
        """Фаза обратного распространения для параллельных роллаутов."""
        if num_rollouts == 0: return

        for node in reversed(path):
            node.visits += num_rollouts
            player_who_acted = node.parent.game_state.current_player_idx if node.parent else -1

            if player_who_acted == 0: node.total_reward += total_reward
            elif player_who_acted == 1: node.total_reward -= total_reward

            # Обновляем RAVE
            possible_actions_from_node = set(node.children.keys())
            if node.untried_actions: possible_actions_from_node.update(node.untried_actions)
            relevant_sim_actions = simulation_actions.intersection(possible_actions_from_node)

            # Определяем игрока, который ходит ИЗ этого узла
            player_to_move_from_node = -1
            # Логика определения player_to_move
            gs = node.game_state
            if gs.is_fantasyland_round:
                 for i in range(gs.NUM_PLAYERS):
                      if gs.fantasyland_status[i] and not gs._player_finished_round[i]:
                           player_to_move_from_node = i; break
                 if player_to_move_from_node == -1:
                      for i in range(gs.NUM_PLAYERS):
                           if not gs.fantasyland_status[i] and not gs._player_finished_round[i] and gs.current_hands.get(i):
                                player_to_move_from_node = i; break
                 if player_to_move_from_node == -1: player_to_move_from_node = gs.current_player_idx
            else:
                 player_to_move_from_node = gs.current_player_idx


            if player_to_move_from_node == -1: continue # Не можем обновить RAVE

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
                 # Это мета-действие для get_legal_actions, не должно выбираться
                 return f"FANTASYLAND_META ({len(action[0])} cards)"
            elif isinstance(action, tuple) and action[0] == "FANTASYLAND_PLACEMENT":
                 return f"FANTASYLAND_PLACE (Discard {len(action[2])})"
            elif isinstance(action, tuple) and action[0] == "FANTASYLAND_FOUL":
                 return f"FANTASYLAND_FOUL (Discard {len(action[1])})"
            else:
                 # Попробуем более детально для неизвестных кортежей
                 if isinstance(action, tuple):
                      # Рекурсивно форматируем элементы кортежа, если они не базовые типы
                      formatted_items = []
                      for item in action:
                           if isinstance(item, (str, int, float, bool, type(None))):
                                formatted_items.append(repr(item))
                           elif isinstance(item, Card):
                                formatted_items.append(card_to_str(item))
                           elif isinstance(item, list):
                                formatted_items.append("[...]") # Сокращаем списки
                           elif isinstance(item, dict):
                                formatted_items.append("{...}") # Сокращаем словари
                           else:
                                formatted_items.append(self._format_action(item)) # Рекурсия для вложенных
                      return f"Unknown Tuple Action: ({', '.join(formatted_items)})"

                 return str(action) # Возвращаем строку для других типов
        except Exception as e:
             # print(f"Error formatting action {action}: {e}")
             return "ErrorFormattingAction"
