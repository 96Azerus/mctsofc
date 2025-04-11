# app.py
import os
import json
import random
import traceback
import sys # Добавляем sys для выхода и flush
from typing import List, Set, Optional, Tuple, Any
from flask import Flask, render_template, request, jsonify, session

# --- Логирование начала ---
print("--- Starting app.py execution ---")
sys.stdout.flush(); sys.stderr.flush() # Flush logs

# Импортируем наши модули ИИ
try:
    print("Importing modules...")
    from card import Card, card_from_str, card_to_str
    print("Imported card")
    from game_state import GameState
    print("Imported game_state")
    from board import PlayerBoard
    print("Imported board")
    # Используем версию БЕЗ multiprocessing для диагностики
    # >>>>>>>> ИЗМЕНЕНИЕ: Закомментирован импорт AI <<<<<<<<<<
    # from mcts_agent import MCTSAgent
    # print("Imported mcts_agent")
    # from fantasyland_solver import FantasylandSolver # Он импортируется в mcts_agent
    # print("Imported fantasyland_solver")
    print("--- Imports successful (AI Agent import commented out) ---") # Изменено сообщение
    sys.stdout.flush(); sys.stderr.flush()
except ImportError as e:
    print(f"FATAL ERROR: Import failed: {e}")
    traceback.print_exc()
    sys.stdout.flush(); sys.stderr.flush()
    sys.exit(1) # Завершаем работу, если импорт не удался


try:
    app = Flask(__name__)
    print("--- Flask app created ---")
    sys.stdout.flush(); sys.stderr.flush()

    # Получаем ключ из переменных окружения, КРИТИЧНО для безопасности
    app.secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not app.secret_key:
        print("FATAL ERROR: FLASK_SECRET_KEY environment variable not set.")
        # Проверяем окружение Render (RENDER=true) или другие признаки продакшена
        is_production = os.environ.get('RENDER') == 'true' or os.environ.get('FLASK_ENV') == 'production'
        if not is_production:
            app.secret_key = 'dev_secret_key_only_for_debug_do_not_use_in_prod'
            print("Warning: Using temporary debug secret key. FLASK_SECRET_KEY should be set for production.")
        else:
            print("Exiting due to missing FLASK_SECRET_KEY in production.")
            sys.stdout.flush(); sys.stderr.flush()
            sys.exit(1) # Завершаем работу в продакшене без ключа
    else:
        print("FLASK_SECRET_KEY loaded successfully.")
        sys.stdout.flush(); sys.stderr.flush()


    # --- Инициализация AI ---
    print("--- SKIPPING AI Agent Initialization (Commented Out) ---") # Изменено сообщение
    sys.stdout.flush(); sys.stderr.flush()
    ai_agent = None # Initialize as None
    # >>>>>>>> ИЗМЕНЕНИЕ: Закомментирован блок инициализации AI <<<<<<<<<<
    # try:
    #     mcts_time_limit = int(os.environ.get('MCTS_TIME_LIMIT_MS', 5000))
    #     mcts_rave_k = int(os.environ.get('MCTS_RAVE_K', 500))
    #     # --- ПАРАЛЛЕЛИЗАЦИЯ ВЫКЛЮЧЕНА ДЛЯ ДИАГНОСТИКИ ---
    #     # mcts_workers = 1
    #     # mcts_rollouts_leaf = 1
    #     print(f"AI Params: TimeLimit={mcts_time_limit}, RaveK={mcts_rave_k} (Single-threaded)")
    #     sys.stdout.flush(); sys.stderr.flush()

    #     # Используем конструктор БЕЗ параметров параллелизации
    #     ai_agent = MCTSAgent(time_limit_ms=mcts_time_limit,
    #                          rave_k=mcts_rave_k)

    #     print("--- AI Agent Initialized Successfully ---")
    #     sys.stdout.flush(); sys.stderr.flush()
    # except Exception as e:
    #     print(f"FATAL ERROR: AI Agent initialization failed: {e}")
    #     traceback.print_exc()
    #     sys.stdout.flush(); sys.stderr.flush()
    #     sys.exit(1) # Exit if AI agent fails

    # # Check if ai_agent was successfully created
    # if ai_agent is None:
    #      print("FATAL ERROR: ai_agent is None after initialization block.")
    #      sys.stdout.flush(); sys.stderr.flush()
    #      sys.exit(1)

    # fl_solver не нужен отдельно, т.к. используется внутри MCTSAgent

except Exception as e:
     # Ловим любые другие ошибки на глобальном уровне инициализации
     print(f"FATAL ERROR during global initialization: {e}")
     traceback.print_exc()
     sys.stdout.flush(); sys.stderr.flush()
     sys.exit(1)


# --- Функции для работы с состоянием в сессии (JSON) ---
# ... (save_game_state, load_game_state, get_state_for_frontend - без изменений) ...
def save_game_state(state: Optional[GameState]):
    """Сохраняет состояние игры в сессию как JSON."""
    if state:
        try:
            session['game_state'] = state.to_dict()
            session.modified = True
        except Exception as e:
             print(f"Error saving game state to session: {e}")
             traceback.print_exc()
             session.pop('game_state', None)
    else:
        session.pop('game_state', None)

def load_game_state() -> Optional[GameState]:
    """Загружает состояние игры из сессии (JSON)."""
    state_dict = session.get('game_state')
    if state_dict:
        try:
            if isinstance(state_dict, dict):
                 return GameState.from_dict(state_dict)
            else:
                 print(f"Error: Saved game state is not a dict: {type(state_dict)}")
                 session.pop('game_state', None)
                 return None
        except Exception as e:
            print(f"Error loading game state from dict: {e}")
            traceback.print_exc()
            session.pop('game_state', None)
            return None
    return None

def get_state_for_frontend(state: GameState, player_idx: int) -> dict:
    """Формирует данные для отправки на фронтенд."""
    opponent_idx = 1 - player_idx
    boards_data = []
    for i, board in enumerate(state.boards):
         board_data = {}
         for row_name in PlayerBoard.ROW_NAMES:
             board_data[row_name] = [card_to_str(c) for c in board.rows[row_name]]
         boards_data.append(board_data)

    player_hand_list = state.get_player_hand(player_idx)
    current_hand = [card_to_str(c) for c in player_hand_list] if player_hand_list else []
    fantasyland_hand = current_hand if state.is_fantasyland_round and state.fantasyland_status[player_idx] else []
    regular_hand = current_hand if not (state.is_fantasyland_round and state.fantasyland_status[player_idx]) else []

    message = ""
    is_waiting = False
    can_act = not state.is_round_over() and not state._player_finished_round[player_idx]

    if state.is_round_over():
        message = "Раунд завершен! Нажмите 'Начать Раунд'."
        try:
             score = state.get_terminal_score()
             if player_idx == 1: score = -score
             message += f" Счет за раунд: {score}"
        except Exception as e:
             print(f"Error calculating terminal score: {e}")
             message += " (Ошибка подсчета очков)"
    elif can_act:
        if state.is_fantasyland_round and state.fantasyland_status[player_idx]:
             if state.fantasyland_hands[player_idx]:
                  message = "Ваш ход: Разместите руку Фантазии (перетаскивание)."
             else:
                  message = "Ошибка: Рука Фантазии отсутствует."
                  is_waiting = True
        else:
             if state.current_hands.get(player_idx):
                  message = f"Ваш ход (Улица {state.street}). Разместите карты (перетаскивание)."
             else:
                  message = f"Ожидание карт (Улица {state.street})..."
                  is_waiting = True
    else:
         # >>>>>>>> ИЗМЕНЕНИЕ: Убрано упоминание AI <<<<<<<<<<
         message = "Ожидание завершения раунда другим игроком..."
         is_waiting = True

    player_discard_count = len(state.private_discard[player_idx])

    return {
        "playerBoard": boards_data[player_idx],
        "opponentBoard": boards_data[opponent_idx],
        "humanPlayerIndex": player_idx,
        "street": state.street,
        "hand": regular_hand,
        "fantasylandHand": fantasyland_hand,
        "isFantasylandRound": state.is_fantasyland_round,
        "playerFantasylandStatus": state.fantasyland_status[player_idx],
        "isGameOver": state.is_round_over(),
        "playerDiscardCount": player_discard_count,
        "message": message,
        "isWaiting": is_waiting,
        "playerFinishedRound": state._player_finished_round[player_idx],
    }


# --- Маршруты Flask ---
print("--- Defining Flask routes ---")
sys.stdout.flush(); sys.stderr.flush()

@app.route('/')
def index():
    # print("Route / called") # Убрал для чистоты логов при успехе
    return render_template('index.html')

@app.route('/api/game_state', methods=['GET'])
def get_game_state_api():
    # print("Route /api/game_state called")
    game_state = load_game_state()
    human_player_idx = 0

    if game_state is None:
        dealer_idx = random.choice([0, 1])
        game_state = GameState(dealer_idx=dealer_idx)
        save_game_state(game_state)
        # print("No game state found, created initial empty state.")

    try:
        frontend_state = get_state_for_frontend(game_state, human_player_idx)
        if game_state.street == 0 or (game_state.is_round_over() and game_state.street < 5):
             frontend_state["message"] = "Нажмите 'Начать Раунд'"
             frontend_state["isGameOver"] = True
             frontend_state["isWaiting"] = False
             frontend_state["playerFinishedRound"] = True
        # print("Returning game state via API")
        return jsonify(frontend_state)
    except Exception as e:
         print(f"Error preparing state for frontend API: {e}")
         traceback.print_exc()
         return jsonify({
              "error_message": "Ошибка загрузки состояния игры.",
              "isGameOver": True, "message": "Ошибка. Обновите страницу.",
              "humanPlayerIndex": human_player_idx, "playerBoard": PlayerBoard().to_dict()['rows'],
              "opponentBoard": PlayerBoard().to_dict()['rows'], "street": 0, "hand": [],
              "fantasylandHand": [], "isFantasylandRound": False, "playerFantasylandStatus": False,
              "playerDiscardCount": 0, "isWaiting": False, "playerFinishedRound": True,
         }), 500


@app.route('/start', methods=['POST'])
def start_game():
    print("Route /start called")
    human_player_idx = 0
    ai_idx = 1 - human_player_idx

    old_state = load_game_state()
    fl_status_carryover = [False, False]
    fl_cards_carryover = [0, 0]
    last_dealer = -1
    if old_state:
         fl_status_carryover = old_state.next_fantasyland_status
         fl_cards_carryover = old_state.fantasyland_cards_to_deal
         last_dealer = old_state.dealer_idx

    dealer_idx = (1 - last_dealer) if last_dealer != -1 else random.choice([0, 1])

    game_state = GameState(dealer_idx=dealer_idx,
                           fantasyland_status=fl_status_carryover,
                           fantasyland_cards_to_deal=fl_cards_carryover)
    game_state.start_new_round(dealer_idx)

    print(f"New round started. Dealer: {dealer_idx}. FL Status: {game_state.fantasyland_status}")
    sys.stdout.flush(); sys.stderr.flush()

    # >>>>>>>> ИЗМЕНЕНИЕ: Закомментирован блок первоначального хода AI <<<<<<<<<<
    # ai_needs_to_act = False
    # # ... (логика определения ai_needs_to_act как раньше) ...
    # if game_state.is_fantasyland_round and game_state.fantasyland_status[ai_idx]:
    #      ai_needs_to_act = game_state.fantasyland_hands[ai_idx] is not None
    #      if ai_needs_to_act: print(f"AI Player {ai_idx} starting Fantasyland placement...")
    # elif not game_state.is_fantasyland_round and game_state.current_player_idx == ai_idx:
    #      ai_needs_to_act = game_state.current_hands.get(ai_idx) is not None
    #      if ai_needs_to_act: print(f"AI Player {ai_idx} taking first turn (Street {game_state.street})...")
    # elif game_state.is_fantasyland_round and not game_state.fantasyland_status[ai_idx]:
    #      ai_needs_to_act = game_state.current_hands.get(ai_idx) is not None
    #      if ai_needs_to_act: print(f"AI Player {ai_idx} taking first turn (Regular hand in FL round, Street {game_state.street})...")


    # if ai_needs_to_act:
    #      try:
    #           print("Running initial AI turn...")
    #           sys.stdout.flush(); sys.stderr.flush()
    #           game_state = run_ai_turn(game_state, ai_idx) # <<<<<<<<<< ВЫЗОВ AI
    #           print("Initial AI turn finished.")
    #           sys.stdout.flush(); sys.stderr.flush()
    #           # ... (раздача человеку после хода AI как раньше) ...
    #           if not game_state.is_round_over() and not game_state._player_finished_round[human_player_idx]:
    #                if not game_state.is_fantasyland_round and game_state.current_player_idx == human_player_idx and game_state.current_hands.get(human_player_idx) is None:
    #                     game_state._deal_street_to_player(human_player_idx)
    #                elif game_state.is_fantasyland_round and not game_state.fantasyland_status[human_player_idx] and game_state.current_hands.get(human_player_idx) is None:
    #                     game_state._deal_street_to_player(human_player_idx)

    #      except Exception as e:
    #           print(f"Error during initial AI turn: {e}")
    #           traceback.print_exc()
    #           sys.stdout.flush(); sys.stderr.flush()

    # >>>>>>>> ИЗМЕНЕНИЕ: Раздаем карты человеку сразу, если его очередь <<<<<<<<<<
    if not game_state.is_round_over() and not game_state._player_finished_round[human_player_idx]:
         if not game_state.is_fantasyland_round and game_state.current_player_idx == human_player_idx and game_state.current_hands.get(human_player_idx) is None:
              print(f"Dealing initial hand to human player {human_player_idx}")
              game_state._deal_street_to_player(human_player_idx)
         elif game_state.is_fantasyland_round and not game_state.fantasyland_status[human_player_idx] and game_state.current_hands.get(human_player_idx) is None:
              print(f"Dealing initial hand to human player {human_player_idx} (FL round)")
              game_state._deal_street_to_player(human_player_idx)


    print("Saving state after /start (AI turn skipped)")
    sys.stdout.flush(); sys.stderr.flush()
    save_game_state(game_state)
    frontend_state = get_state_for_frontend(game_state, human_player_idx)
    print("Returning state after /start")
    sys.stdout.flush(); sys.stderr.flush()
    return jsonify(frontend_state)

# >>>>>>>> ИЗМЕНЕНИЕ: Закомментирована функция run_ai_turn <<<<<<<<<<
# def run_ai_turn(current_game_state: GameState, ai_player_index: int) -> GameState:
#     """
#     Выполняет ОДИН ход AI (или полное размещение ФЛ).
#     Возвращает НОВОЕ состояние игры после хода AI.
#     """
#     state = current_game_state
#     if state._player_finished_round[ai_player_index]:
#         return state

#     action = None
#     is_fl_placement = state.is_fantasyland_round and state.fantasyland_status[ai_player_index]

#     try:
#          # print(f"AI Player {ai_player_index} choosing action...")
#          action = ai_agent.choose_action(state) # Передаем текущее состояние # <<<<<<<<<< ВЫЗОВ AI
#          # print(f"AI Player {ai_player_index} chose action: {ai_agent._format_action(action)}")
#     except Exception as e:
#          print(f"Error getting action from AI agent: {e}")
#          traceback.print_exc()
#          sys.stdout.flush(); sys.stderr.flush()
#          action = None

#     new_state = state # По умолчанию

#     if action is None:
#         print(f"AI Player {ai_player_index} could not choose an action or errored. Setting foul.")
#         hand_to_discard = state.get_player_hand(ai_player_index)
#         if is_fl_placement and hand_to_discard:
#              new_state = state.apply_fantasyland_foul(ai_player_index, hand_to_discard)
#         else:
#              new_state = state.copy()
#              new_state.boards[ai_player_index].is_foul = True
#              new_state._player_finished_round[ai_player_index] = True
#              if hand_to_discard:
#                   new_state.private_discard[ai_player_index].extend(hand_to_discard)
#                   new_state.current_hands[ai_player_index] = None
#         print(f"AI Player {ai_player_index} fouled.")

#     elif isinstance(action, tuple) and action[0] == "FANTASYLAND_PLACEMENT":
#          _, placement, discarded = action
#          # print(f"AI applying Fantasyland placement...")
#          new_state = state.apply_fantasyland_placement(ai_player_index, placement, discarded)
#     elif isinstance(action, tuple) and action[0] == "FANTASYLAND_FOUL":
#          _, hand_to_discard = action
#          print(f"AI FAILED Fantasyland placement! Fouling.")
#          new_state = state.apply_fantasyland_foul(ai_player_index, hand_to_discard)
#     else: # Обычный ход AI
#          # print(f"AI applying regular action...")
#          new_state = state.apply_action(ai_player_index, action)

#     # print(f"AI Player {ai_player_index} action applied.")
#     sys.stdout.flush(); sys.stderr.flush()
#     return new_state


@app.route('/move', methods=['POST'])
def handle_move():
    """Обрабатывает ход человека (после нажатия 'Готов')."""
    # print("Route /move called")
    human_player_idx = 0
    ai_idx = 1 - human_player_idx
    game_state = load_game_state()

    if game_state is None: return jsonify({"error": "Игра не найдена."}), 400
    if game_state.is_round_over(): return jsonify({"error": "Раунд завершен."}), 400
    if game_state._player_finished_round[human_player_idx]:
         return jsonify({"error": "Вы уже завершили раунд."}), 400

    move_data = request.json
    new_state = game_state

    try:
        # --- Парсинг и применение хода человека ---
        is_player_in_fl = game_state.is_fantasyland_round and game_state.fantasyland_status[human_player_idx]
        player_hand = game_state.get_player_hand(human_player_idx)

        if is_player_in_fl:
             # ... (логика обработки ФЛ хода человека как раньше) ...
             if not player_hand: raise ValueError("Рука Фантазии уже разыграна.")
             placement_raw = move_data.get('placement')
             discarded_raw = move_data.get('discarded')
             if not placement_raw or discarded_raw is None: raise ValueError("Отсутствуют данные для размещения/сброса Фантазии.")
             placement_dict = {}
             for row, card_strs in placement_raw.items():
                  placement_dict[row] = [card_from_str(s) for s in card_strs]
             discarded_cards = [card_from_str(s) for s in discarded_raw]
             # print("Applying human Fantasyland placement.")
             new_state = game_state.apply_fantasyland_placement(human_player_idx, placement_dict, discarded_cards)

        else: # Обычный ход
             # ... (логика обработки обычного хода человека как раньше) ...
             if not player_hand: raise ValueError("Нет карт для хода.")
             action = None
             if game_state.street == 1:
                  if len(player_hand) != 5: raise ValueError("Неверное количество карт для улицы 1.")
                  placements_raw = move_data.get('placements')
                  if not placements_raw or len(placements_raw) != 5: raise ValueError("Улица 1 требует 5 размещений.")
                  placements = []
                  for p in placements_raw: placements.append((card_from_str(p['card']), p['row'], int(p['index'])))
                  action = (placements, [])
                  # print("Applying human Street 1 action.")
             else: # Улицы 2-5
                  if len(player_hand) != 3: raise ValueError(f"Неверное количество карт для улицы {game_state.street}.")
                  placements_raw = move_data.get('placements')
                  discard_str = move_data.get('discard')
                  if not placements_raw or len(placements_raw) != 2 or not discard_str: raise ValueError("Неверные данные для хода Pineapple.")
                  place1_raw = placements_raw[0]; place2_raw = placements_raw[1]
                  place1 = (card_from_str(place1_raw['card']), place1_raw['row'], int(place1_raw['index']))
                  place2 = (card_from_str(place2_raw['card']), place2_raw['row'], int(place2_raw['index']))
                  discarded_card = card_from_str(discard_str)
                  action = (place1, place2, discarded_card)
                  # print(f"Applying human Pineapple action (Street {game_state.street}).")

             if action:
                  new_state = game_state.apply_action(human_player_idx, action)
             else:
                  raise ValueError("Не удалось сформировать действие для обычного хода.")


        # print(f"Human action applied. Human finished: {new_state._player_finished_round[human_player_idx]}")
        sys.stdout.flush(); sys.stderr.flush()

        # --- Ход AI (если он еще не закончил) ---
        # >>>>>>>> ИЗМЕНЕНИЕ: Закомментирован блок хода AI <<<<<<<<<<
        # ai_made_move = False
        # if not new_state.is_round_over() and not new_state._player_finished_round[ai_idx]:
        #      ai_can_act = False
        #      # ... (логика определения ai_can_act как раньше) ...
        #      if new_state.is_fantasyland_round and new_state.fantasyland_status[ai_idx]:
        #           ai_can_act = new_state.fantasyland_hands[ai_idx] is not None
        #      else:
        #           ai_can_act = new_state.current_hands.get(ai_idx) is not None

        #      if ai_can_act:
        #           print(f"AI Player {ai_idx} making move after human...")
        #           sys.stdout.flush(); sys.stderr.flush()
        #           new_state = run_ai_turn(new_state, ai_idx) # <<<<<<<<<< ВЫЗОВ AI
        #           ai_made_move = True
        #           print(f"AI finished move. AI finished round: {new_state._player_finished_round[ai_idx]}")
        #           sys.stdout.flush(); sys.stderr.flush()

        # >>>>>>>> ИЗМЕНЕНИЕ: Считаем, что AI всегда заканчивает ход сразу <<<<<<<<<<
        if not new_state.is_round_over() and not new_state._player_finished_round[ai_idx]:
             print(f"AI Player {ai_idx} turn skipped (AI disabled). Marking as finished.")
             new_state._player_finished_round[ai_idx] = True # Считаем, что AI закончил
             # Очищаем его возможную руку, если она была
             if new_state.is_fantasyland_round and new_state.fantasyland_status[ai_idx]:
                  new_state.fantasyland_hands[ai_idx] = None
             else:
                  new_state.current_hands[ai_idx] = None


        # --- Переход к следующей улице / Раздача карт ---
        if not new_state.is_round_over():
             needs_dealing = False
             # Переход улицы в обычном раунде
             if not new_state.is_fantasyland_round and all(new_state._player_acted_this_street):
                  new_state.street += 1
                  if new_state.street <= 5:
                       print(f"--- Advancing to Street {new_state.street} ---")
                       sys.stdout.flush(); sys.stderr.flush()
                       new_state._player_acted_this_street = [False] * new_state.NUM_PLAYERS
                       new_state.current_player_idx = 1 - new_state.dealer_idx
                       needs_dealing = True # Раздаем обоим (если они не закончили)

             # Передача хода в обычном раунде (если улица не сменилась)
             elif not new_state.is_fantasyland_round and not all(new_state._player_acted_this_street):
                  current_player = new_state.current_player_idx
                  other_player = 1 - current_player
                  # Если текущий игрок только что сходил (acted=True) и другой еще не ходил
                  if new_state._player_acted_this_street[current_player] and not new_state._player_acted_this_street[other_player]:
                       # И если другой игрок еще не закончил раунд
                       if not new_state._player_finished_round[other_player]:
                            new_state.current_player_idx = other_player
                            if new_state.current_hands.get(other_player) is None:
                                 needs_dealing = True # Раздаем другому

             # Раздача карт (если нужно)
             if needs_dealing or new_state.is_fantasyland_round:
                  players_to_deal = []
                  if needs_dealing and not new_state.is_fantasyland_round:
                       # Раздаем обоим в начале улицы, или текущему при передаче хода
                       if all(not acted for acted in new_state._player_acted_this_street): # Начало улицы
                            for p_idx in range(new_state.NUM_PLAYERS):
                                 if not new_state._player_finished_round[p_idx] and new_state.current_hands.get(p_idx) is None:
                                      players_to_deal.append(p_idx)
                       else: # Передача хода
                            p_idx = new_state.current_player_idx
                            if not new_state._player_finished_round[p_idx] and new_state.current_hands.get(p_idx) is None:
                                 players_to_deal.append(p_idx)
                  elif new_state.is_fantasyland_round:
                       # Ищем не-ФЛ игроков без карт
                       for p_idx_deal in range(new_state.NUM_PLAYERS):
                            if not new_state.fantasyland_status[p_idx_deal] and \
                               not new_state._player_finished_round[p_idx_deal] and \
                               new_state.current_hands.get(p_idx_deal) is None:
                                    players_to_deal.append(p_idx_deal)

                  # Раздаем карты
                  # >>>>>>>> ИЗМЕНЕНИЕ: Убран блок хода AI после раздачи <<<<<<<<<<
                  # ai_needs_to_act_after_deal = False
                  for p_idx_deal in players_to_deal:
                       # Раздаем только человеку
                       if p_idx_deal == human_player_idx:
                            print(f"Dealing cards to player {p_idx_deal} (Street {new_state.street})")
                            sys.stdout.flush(); sys.stderr.flush()
                            new_state._deal_street_to_player(p_idx_deal)
                       # if p_idx_deal == ai_idx:
                       #      ai_needs_to_act_after_deal = True

                  # # Если раздали AI, он должен сходить
                  # if ai_needs_to_act_after_deal and not new_state._player_finished_round[ai_idx]:
                  #      print(f"AI Player {ai_idx} making move after deal...")
                  #      sys.stdout.flush(); sys.stderr.flush()
                  #      new_state = run_ai_turn(new_state, ai_idx) # <<<<<<<<<< ВЫЗОВ AI
                  #      print(f"AI finished move after deal. AI finished round: {new_state._player_finished_round[ai_idx]}")
                  #      sys.stdout.flush(); sys.stderr.flush()


        # --- Сохранение и ответ ---
        # print("Saving state after /move")
        save_game_state(new_state)
        frontend_state = get_state_for_frontend(new_state, human_player_idx)
        # print("Returning state after /move")
        return jsonify(frontend_state)

    # Обработка ошибок
    except ValueError as e:
        print(f"Move Error (ValueError): {e}")
        traceback.print_exc()
        current_state = load_game_state()
        if current_state:
             frontend_state = get_state_for_frontend(current_state, human_player_idx)
             frontend_state["error_message"] = str(e)
             return jsonify(frontend_state), 400
        else:
             return jsonify({"error": f"Invalid move: {e}. Could not load previous state."}), 400
    except Exception as e:
        print(f"Unexpected Error during move: {e}")
        traceback.print_exc()
        return jsonify({"error": "Произошла неожиданная ошибка сервера."}), 500


if __name__ == '__main__':
    print("--- Starting main execution ---")
    sys.stdout.flush(); sys.stderr.flush()
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_DEBUG', '0').lower() in ['true', '1', 'yes']
    if debug_mode:
         os.environ['FLASK_ENV'] = 'development'
    print(f"Starting Flask app on host 0.0.0.0, port {port} with debug={debug_mode}")
    sys.stdout.flush(); sys.stderr.flush()
    # use_reloader=False рекомендуется при использовании multiprocessing или для стабильности
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
    print("--- Flask app exiting ---") # Этот лог может не появиться, если Gunicorn управляет процессом
    sys.stdout.flush(); sys.stderr.flush()
