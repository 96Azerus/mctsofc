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
    from mcts_agent import MCTSAgent
    print("Imported mcts_agent")
    print("--- Imports successful ---")
    sys.stdout.flush(); sys.stderr.flush()
except ImportError as e:
    print(f"FATAL ERROR: Import failed: {e}")
    traceback.print_exc()
    sys.stdout.flush(); sys.stderr.flush()
    sys.exit(1)


try:
    app = Flask(__name__)
    print("--- Flask app created ---")
    sys.stdout.flush(); sys.stderr.flush()

    # Получаем ключ из переменных окружения
    app.secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not app.secret_key:
        print("FATAL ERROR: FLASK_SECRET_KEY environment variable not set.")
        is_production = os.environ.get('RENDER') == 'true' or os.environ.get('FLASK_ENV') == 'production'
        if not is_production:
            app.secret_key = 'dev_secret_key_only_for_debug_do_not_use_in_prod'
            print("Warning: Using temporary debug secret key. FLASK_SECRET_KEY should be set for production.")
        else:
            print("Exiting due to missing FLASK_SECRET_KEY in production.")
            sys.stdout.flush(); sys.stderr.flush()
            sys.exit(1)
    else:
        print("FLASK_SECRET_KEY loaded successfully.")
        sys.stdout.flush(); sys.stderr.flush()


    # --- Инициализация AI ---
    print("--- Initializing AI Agent ---")
    sys.stdout.flush(); sys.stderr.flush()
    ai_agent = None
    try:
        mcts_time_limit = int(os.environ.get('MCTS_TIME_LIMIT_MS', 5000))
        mcts_rave_k = int(os.environ.get('MCTS_RAVE_K', 500))
        mcts_workers = int(os.environ.get('NUM_WORKERS', 1))
        mcts_rollouts_leaf = int(os.environ.get('ROLLOUTS_PER_LEAF', 4))

        print(f"AI Params: TimeLimit={mcts_time_limit}ms, RaveK={mcts_rave_k}, Workers={mcts_workers}, RolloutsPerLeaf={mcts_rollouts_leaf}")
        sys.stdout.flush(); sys.stderr.flush()

        ai_agent = MCTSAgent(time_limit_ms=mcts_time_limit,
                             rave_k=mcts_rave_k,
                             num_workers=mcts_workers,
                             rollouts_per_leaf=mcts_rollouts_leaf)

        print("--- AI Agent Initialized Successfully ---")
        sys.stdout.flush(); sys.stderr.flush()
    except Exception as e:
        print(f"FATAL ERROR: AI Agent initialization failed: {e}")
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush()
        sys.exit(1)

    if ai_agent is None:
         print("FATAL ERROR: ai_agent is None after initialization block.")
         sys.stdout.flush(); sys.stderr.flush()
         sys.exit(1)

except Exception as e:
     print(f"FATAL ERROR during global initialization: {e}")
     traceback.print_exc()
     sys.stdout.flush(); sys.stderr.flush()
     sys.exit(1)


# --- Функции для работы с состоянием в сессии (JSON) ---
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
    # Определяем, может ли игрок действовать СЕЙЧАС
    can_act_now = False
    if not state.is_round_over() and not state._player_finished_round[player_idx]:
         if state.is_fantasyland_round and state.fantasyland_status[player_idx]:
              can_act_now = state.fantasyland_hands[player_idx] is not None
         else: # Обычный ход или не-ФЛ в ФЛ раунде
              can_act_now = state.current_hands.get(player_idx) is not None

    if state.is_round_over():
        message = "Раунд завершен! Нажмите 'Начать Раунд'."
        # is_waiting остается False по умолчанию
        try:
             score = state.get_terminal_score()
             if player_idx == 1: score = -score
             message += f" Счет за раунд: {score}"
        except Exception as e:
             print(f"Error calculating terminal score: {e}")
             message += " (Ошибка подсчета очков)"
    elif can_act_now:
         # Если игрок может ходить, он не ждет
         is_waiting = False
         if state.is_fantasyland_round and state.fantasyland_status[player_idx]:
              message = "Ваш ход: Разместите руку Фантазии (перетаскивание)."
         else:
              message = f"Ваш ход (Улица {state.street}). Разместите карты (перетаскивание)."
    else: # Игрок не может ходить сейчас
         is_waiting = True
         # Определяем причину ожидания
         if state._player_finished_round[player_idx]:
              message = "Вы завершили раунд. Ожидание AI..."
         elif state.current_hands.get(player_idx) is None and not (state.is_fantasyland_round and state.fantasyland_status[player_idx]):
              message = f"Ожидание карт (Улица {state.street})..."
         else:
              message = "Ожидание хода AI..."

    player_discard_count = len(state.private_discard[player_idx])

    # Собираем финальный стейт
    frontend_state = {
        "playerBoard": boards_data[player_idx],
        "opponentBoard": boards_data[opponent_idx],
        "humanPlayerIndex": player_idx,
        "street": state.street,
        "hand": regular_hand,
        "fantasylandHand": fantasyland_hand,
        "isFantasylandRound": state.is_fantasyland_round,
        "playerFantasylandStatus": state.fantasyland_status[player_idx],
        "isGameOver": state.is_round_over(), # Определяется только по завершению раунда
        "playerDiscardCount": player_discard_count,
        "message": message,
        "isWaiting": is_waiting, # Это значение будет использоваться JS
        "playerFinishedRound": state._player_finished_round[player_idx],
    }
    return frontend_state


# --- Маршруты Flask ---
print("--- Defining Flask routes ---")
sys.stdout.flush(); sys.stderr.flush()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/game_state', methods=['GET'])
def get_game_state_api():
    game_state = load_game_state()
    human_player_idx = 0
    is_initial_request = False # Флаг для самого первого запроса

    if game_state is None:
        print("No game state in session, creating initial state.")
        dealer_idx = random.choice([0, 1])
        game_state = GameState(dealer_idx=dealer_idx)
        # Важно: НЕ начинаем раунд здесь, просто создаем пустое состояние
        game_state.street = 0 # Явно указываем, что раунд не начат
        game_state._player_finished_round = [True, True] # Считаем "завершенным" до старта
        save_game_state(game_state)
        is_initial_request = True
        print("Initial empty state created and saved.")

    try:
        frontend_state = get_state_for_frontend(game_state, human_player_idx)

        # --- ИЗМЕНЕНИЕ: Улучшенная логика для начального состояния ---
        # Если это самый первый запрос ИЛИ раунд реально завершен (все закончили)
        # ИЛИ если улица 0 (состояние до нажатия "Начать раунд")
        if is_initial_request or game_state.is_round_over() or game_state.street == 0:
             print(f"Setting initial/game over state for frontend: is_initial={is_initial_request}, is_over={game_state.is_round_over()}, street={game_state.street}")
             frontend_state["message"] = "Нажмите 'Начать Раунд'"
             frontend_state["isGameOver"] = True
             frontend_state["isWaiting"] = False # Явно ставим False
             frontend_state["playerFinishedRound"] = True # Считаем игрока "закончившим" до старта
             # Очищаем руки на всякий случай для начального отображения
             frontend_state["hand"] = []
             frontend_state["fantasylandHand"] = []
        # -------------------------------------------------------------

        # print(f"Returning state: {frontend_state}") # Отладка
        return jsonify(frontend_state)
    except Exception as e:
         print(f"Error preparing state for frontend API: {e}")
         traceback.print_exc()
         # Возвращаем состояние ошибки
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
    if old_state and old_state.street > 0: # Берем статус только из ЗАВЕРШЕННОГО раунда
         fl_status_carryover = old_state.next_fantasyland_status
         fl_cards_carryover = old_state.fantasyland_cards_to_deal
         last_dealer = old_state.dealer_idx
    else:
         print("Starting first round or after error, FL status reset.")


    dealer_idx = (1 - last_dealer) if last_dealer != -1 else random.choice([0, 1])

    game_state = GameState(dealer_idx=dealer_idx,
                           fantasyland_status=fl_status_carryover,
                           fantasyland_cards_to_deal=fl_cards_carryover)
    # start_new_round вызывается ЗДЕСЬ
    game_state.start_new_round(dealer_idx)

    print(f"New round started. Dealer: {dealer_idx}. FL Status: {game_state.fantasyland_status}. Street: {game_state.street}")
    sys.stdout.flush(); sys.stderr.flush()

    # Определяем, нужно ли AI ходить первым
    ai_needs_to_act = False
    if game_state.is_fantasyland_round and game_state.fantasyland_status[ai_idx]:
         ai_needs_to_act = game_state.fantasyland_hands[ai_idx] is not None
         if ai_needs_to_act: print(f"AI Player {ai_idx} starting Fantasyland placement...")
    elif not game_state.is_fantasyland_round and game_state.current_player_idx == ai_idx:
         ai_needs_to_act = game_state.current_hands.get(ai_idx) is not None
         if ai_needs_to_act: print(f"AI Player {ai_idx} taking first turn (Street {game_state.street})...")
    elif game_state.is_fantasyland_round and not game_state.fantasyland_status[ai_idx]: # Не-ФЛ игрок в ФЛ раунде
         ai_needs_to_act = game_state.current_hands.get(ai_idx) is not None
         if ai_needs_to_act: print(f"AI Player {ai_idx} taking first turn (Regular hand in FL round, Street {game_state.street})...")


    if ai_needs_to_act:
         try:
              print("Running initial AI turn...")
              sys.stdout.flush(); sys.stderr.flush()
              game_state = run_ai_turn(game_state, ai_idx) # <<<<<<<<<< ВЫЗОВ AI
              print("Initial AI turn finished.")
              sys.stdout.flush(); sys.stderr.flush()
              # Раздаем человеку после хода AI, если нужно
              if not game_state.is_round_over() and not game_state._player_finished_round[human_player_idx]:
                   if not game_state.is_fantasyland_round and game_state.current_player_idx == human_player_idx and game_state.current_hands.get(human_player_idx) is None:
                        print(f"Dealing hand to human player {human_player_idx} after AI turn")
                        game_state._deal_street_to_player(human_player_idx)
                   elif game_state.is_fantasyland_round and not game_state.fantasyland_status[human_player_idx] and game_state.current_hands.get(human_player_idx) is None:
                        print(f"Dealing hand to human player {human_player_idx} after AI turn (FL round)")
                        game_state._deal_street_to_player(human_player_idx)

         except Exception as e:
              print(f"Error during initial AI turn: {e}")
              traceback.print_exc()
              sys.stdout.flush(); sys.stderr.flush()
              # В случае ошибки AI, все равно пытаемся раздать человеку, если его очередь
              if not game_state.is_round_over() and not game_state._player_finished_round[human_player_idx]:
                   if not game_state.is_fantasyland_round and game_state.current_player_idx == human_player_idx and game_state.current_hands.get(human_player_idx) is None:
                        print(f"Dealing hand to human player {human_player_idx} after AI error")
                        game_state._deal_street_to_player(human_player_idx)
                   elif game_state.is_fantasyland_round and not game_state.fantasyland_status[human_player_idx] and game_state.current_hands.get(human_player_idx) is None:
                        print(f"Dealing hand to human player {human_player_idx} after AI error (FL round)")
                        game_state._deal_street_to_player(human_player_idx)
    else:
         # Если AI не ходил первым, раздаем человеку, если его очередь
         if not game_state.is_round_over() and not game_state._player_finished_round[human_player_idx]:
              if not game_state.is_fantasyland_round and game_state.current_player_idx == human_player_idx and game_state.current_hands.get(human_player_idx) is None:
                   print(f"Dealing initial hand to human player {human_player_idx}")
                   game_state._deal_street_to_player(human_player_idx)
              elif game_state.is_fantasyland_round and not game_state.fantasyland_status[human_player_idx] and game_state.current_hands.get(human_player_idx) is None:
                   print(f"Dealing initial hand to human player {human_player_idx} (FL round)")
                   game_state._deal_street_to_player(human_player_idx)


    print("Saving state after /start")
    sys.stdout.flush(); sys.stderr.flush()
    save_game_state(game_state)
    frontend_state = get_state_for_frontend(game_state, human_player_idx)
    print("Returning state after /start")
    sys.stdout.flush(); sys.stderr.flush()
    return jsonify(frontend_state)

# Функция run_ai_turn остается без изменений (как в версии с раскомментированным AI)
def run_ai_turn(current_game_state: GameState, ai_player_index: int) -> GameState:
    """
    Выполняет ОДИН ход AI (или полное размещение ФЛ).
    Возвращает НОВОЕ состояние игры после хода AI.
    """
    state = current_game_state
    if state._player_finished_round[ai_player_index]:
        return state

    action = None
    is_fl_placement = state.is_fantasyland_round and state.fantasyland_status[ai_player_index]

    if ai_agent is None:
         print(f"FATAL ERROR in run_ai_turn: ai_agent is None!")
         new_state = state.copy()
         new_state.boards[ai_player_index].is_foul = True
         new_state._player_finished_round[ai_player_index] = True
         hand_to_discard = state.get_player_hand(ai_player_index)
         if hand_to_discard:
              new_state.private_discard[ai_player_index].extend(hand_to_discard)
              if is_fl_placement: new_state.fantasyland_hands[ai_player_index] = None
              else: new_state.current_hands[ai_player_index] = None
         return new_state

    try:
         print(f"AI Player {ai_player_index} choosing action...")
         sys.stdout.flush(); sys.stderr.flush()
         action = ai_agent.choose_action(state)
         print(f"AI Player {ai_player_index} chose action: {ai_agent._format_action(action)}")
         sys.stdout.flush(); sys.stderr.flush()
    except Exception as e:
         print(f"Error getting action from AI agent: {e}")
         traceback.print_exc()
         sys.stdout.flush(); sys.stderr.flush()
         action = None

    new_state = state

    if action is None:
        print(f"AI Player {ai_player_index} could not choose an action or errored. Setting foul.")
        hand_to_discard = state.get_player_hand(ai_player_index)
        if is_fl_placement and hand_to_discard:
             new_state = state.apply_fantasyland_foul(ai_player_index, hand_to_discard)
        else:
             new_state = state.copy()
             new_state.boards[ai_player_index].is_foul = True
             new_state._player_finished_round[ai_player_index] = True
             if hand_to_discard:
                  new_state.private_discard[ai_player_index].extend(hand_to_discard)
                  new_state.current_hands[ai_player_index] = None
        print(f"AI Player {ai_player_index} fouled.")

    elif isinstance(action, tuple) and action[0] == "FANTASYLAND_PLACEMENT":
         _, placement, discarded = action
         print(f"AI applying Fantasyland placement...")
         sys.stdout.flush(); sys.stderr.flush()
         new_state = state.apply_fantasyland_placement(ai_player_index, placement, discarded)
    elif isinstance(action, tuple) and action[0] == "FANTASYLAND_FOUL":
         _, hand_to_discard = action
         print(f"AI FAILED Fantasyland placement! Fouling.")
         sys.stdout.flush(); sys.stderr.flush()
         new_state = state.apply_fantasyland_foul(ai_player_index, hand_to_discard)
    else:
         print(f"AI applying regular action...")
         sys.stdout.flush(); sys.stderr.flush()
         new_state = state.apply_action(ai_player_index, action)

    print(f"AI Player {ai_player_index} action applied.")
    sys.stdout.flush(); sys.stderr.flush()
    return new_state


@app.route('/move', methods=['POST'])
def handle_move():
    """Обрабатывает ход человека (после нажатия 'Готов')."""
    print("Route /move called")
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
             if not player_hand: raise ValueError("Рука Фантазии уже разыграна.")
             placement_raw = move_data.get('placement')
             discarded_raw = move_data.get('discarded')
             if not placement_raw or discarded_raw is None: raise ValueError("Отсутствуют данные для размещения/сброса Фантазии.")
             placement_dict = {}
             for row, card_strs in placement_raw.items():
                  placement_dict[row] = [card_from_str(s) for s in card_strs]
             discarded_cards = [card_from_str(s) for s in discarded_raw]
             print("Applying human Fantasyland placement.")
             new_state = game_state.apply_fantasyland_placement(human_player_idx, placement_dict, discarded_cards)

        else: # Обычный ход
             if not player_hand: raise ValueError("Нет карт для хода.")
             action = None
             if game_state.street == 1:
                  if len(player_hand) != 5: raise ValueError("Неверное количество карт для улицы 1.")
                  placements_raw = move_data.get('placements')
                  if not placements_raw or len(placements_raw) != 5: raise ValueError("Улица 1 требует 5 размещений.")
                  placements = []
                  for p in placements_raw: placements.append((card_from_str(p['card']), p['row'], int(p['index'])))
                  action = (placements, [])
                  print("Applying human Street 1 action.")
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
                  print(f"Applying human Pineapple action (Street {game_state.street}).")

             if action:
                  new_state = game_state.apply_action(human_player_idx, action)
             else:
                  raise ValueError("Не удалось сформировать действие для обычного хода.")


        print(f"Human action applied. Human finished: {new_state._player_finished_round[human_player_idx]}")
        sys.stdout.flush(); sys.stderr.flush()

        # --- Ход AI (если он еще не закончил) ---
        ai_made_move = False
        if not new_state.is_round_over() and not new_state._player_finished_round[ai_idx]:
             ai_can_act = False
             if new_state.is_fantasyland_round and new_state.fantasyland_status[ai_idx]:
                  ai_can_act = new_state.fantasyland_hands[ai_idx] is not None
             else:
                  ai_can_act = new_state.current_hands.get(ai_idx) is not None

             if ai_can_act:
                  print(f"AI Player {ai_idx} making move after human...")
                  sys.stdout.flush(); sys.stderr.flush()
                  new_state = run_ai_turn(new_state, ai_idx)
                  ai_made_move = True
                  print(f"AI finished move. AI finished round: {new_state._player_finished_round[ai_idx]}")
                  sys.stdout.flush(); sys.stderr.flush()
             else:
                  print(f"AI Player {ai_idx} cannot act yet (waiting for cards or finished).")
                  sys.stdout.flush(); sys.stderr.flush()


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
                       needs_dealing = True

             # Передача хода в обычном раунде
             elif not new_state.is_fantasyland_round and not all(new_state._player_acted_this_street):
                  current_player = new_state.current_player_idx
                  other_player = 1 - current_player
                  if new_state._player_acted_this_street[current_player] and not new_state._player_acted_this_street[other_player]:
                       if not new_state._player_finished_round[other_player]:
                            new_state.current_player_idx = other_player
                            if new_state.current_hands.get(other_player) is None:
                                 needs_dealing = True

             # Раздача карт
             if needs_dealing or new_state.is_fantasyland_round:
                  players_to_deal = []
                  if needs_dealing and not new_state.is_fantasyland_round:
                       if all(not acted for acted in new_state._player_acted_this_street):
                            for p_idx in range(new_state.NUM_PLAYERS):
                                 if not new_state._player_finished_round[p_idx] and new_state.current_hands.get(p_idx) is None:
                                      players_to_deal.append(p_idx)
                       else:
                            p_idx = new_state.current_player_idx
                            if not new_state._player_finished_round[p_idx] and new_state.current_hands.get(p_idx) is None:
                                 players_to_deal.append(p_idx)
                  elif new_state.is_fantasyland_round:
                       for p_idx_deal in range(new_state.NUM_PLAYERS):
                            if not new_state.fantasyland_status[p_idx_deal] and \
                               not new_state._player_finished_round[p_idx_deal] and \
                               new_state.current_hands.get(p_idx_deal) is None:
                                    players_to_deal.append(p_idx_deal)

                  ai_needs_to_act_after_deal = False
                  for p_idx_deal in players_to_deal:
                       print(f"Dealing cards to player {p_idx_deal} (Street {new_state.street})")
                       sys.stdout.flush(); sys.stderr.flush()
                       new_state._deal_street_to_player(p_idx_deal)
                       if p_idx_deal == ai_idx:
                            ai_needs_to_act_after_deal = True

                  if ai_needs_to_act_after_deal and not new_state._player_finished_round[ai_idx]:
                       print(f"AI Player {ai_idx} making move after deal...")
                       sys.stdout.flush(); sys.stderr.flush()
                       new_state = run_ai_turn(new_state, ai_idx)
                       print(f"AI finished move after deal. AI finished round: {new_state._player_finished_round[ai_idx]}")
                       sys.stdout.flush(); sys.stderr.flush()


        # --- Сохранение и ответ ---
        print("Saving state after /move")
        save_game_state(new_state)
        frontend_state = get_state_for_frontend(new_state, human_player_idx)
        print("Returning state after /move")
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
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
    print("--- Flask app exiting ---")
    sys.stdout.flush(); sys.stderr.flush()
