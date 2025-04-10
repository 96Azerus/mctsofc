# app.py
import os
import json # Используем json вместо pickle/base64
import random
import traceback # Для вывода ошибок
from typing import List, Set, Optional, Tuple, Any
from flask import Flask, render_template, request, jsonify, session

# Импортируем наши модули ИИ
from card import Card, card_from_str, card_to_str
from game_state import GameState # <-- Импортируем класс
from board import PlayerBoard # Нужен для get_state_for_frontend
from mcts_agent import MCTSAgent
from fantasyland_solver import FantasylandSolver

app = Flask(__name__)
# Получаем ключ из переменных окружения, КРИТИЧНО для безопасности
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    print("FATAL ERROR: FLASK_SECRET_KEY environment variable not set.")
    # Для локальной разработки можно временно установить ключ, но НЕ для продакшена
    if os.environ.get('FLASK_ENV') == 'development' or os.environ.get('FLASK_DEBUG') == '1':
        app.secret_key = 'dev_secret_key_only_for_debug_do_not_use_in_prod'
        print("Warning: Using temporary debug secret key. FLASK_SECRET_KEY should be set for production.")
    else:
        # В продакшене без ключа работать нельзя
        raise ValueError("FLASK_SECRET_KEY environment variable must be set in production environment.")


# --- Инициализация AI ---
# Получаем параметры из окружения или используем дефолты
mcts_time_limit = int(os.environ.get('MCTS_TIME_LIMIT_MS', 5000))
mcts_rave_k = int(os.environ.get('MCTS_RAVE_K', 500))
mcts_workers = int(os.environ.get('NUM_WORKERS', MCTSAgent.DEFAULT_NUM_WORKERS))
mcts_rollouts_leaf = int(os.environ.get('ROLLOUTS_PER_LEAF', MCTSAgent.DEFAULT_ROLLOUTS_PER_LEAF))

ai_agent = MCTSAgent(time_limit_ms=mcts_time_limit,
                     rave_k=mcts_rave_k,
                     num_workers=mcts_workers,
                     rollouts_per_leaf=mcts_rollouts_leaf)
# fl_solver не нужен отдельно, т.к. используется внутри MCTSAgent

# --- Функции для работы с состоянием в сессии (JSON) ---
def save_game_state(state: Optional[GameState]):
    """Сохраняет состояние игры в сессию как JSON."""
    if state:
        try:
            session['game_state'] = state.to_dict()
            session.modified = True # Указываем Flask, что сессия изменена
        except Exception as e:
             print(f"Error saving game state to session: {e}")
             traceback.print_exc()
             # Не сохраняем невалидное состояние
             session.pop('game_state', None)
    else:
        session.pop('game_state', None)

def load_game_state() -> Optional[GameState]:
    """Загружает состояние игры из сессии (JSON)."""
    state_dict = session.get('game_state')
    if state_dict:
        try:
            # Проверяем тип перед десериализацией
            if isinstance(state_dict, dict):
                 return GameState.from_dict(state_dict)
            else:
                 print(f"Error: Saved game state is not a dict: {type(state_dict)}")
                 session.pop('game_state', None)
                 return None
        except Exception as e:
            print(f"Error loading game state from dict: {e}")
            traceback.print_exc()
            session.pop('game_state', None) # Очищаем невалидное состояние
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

    # Рука текущего игрока (обычная или ФЛ)
    player_hand_list = state.get_player_hand(player_idx)
    current_hand = [card_to_str(c) for c in player_hand_list] if player_hand_list else []
    fantasyland_hand = current_hand if state.is_fantasyland_round and state.fantasyland_status[player_idx] else []
    regular_hand = current_hand if not (state.is_fantasyland_round and state.fantasyland_status[player_idx]) else []


    # Сообщение для игрока
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
        else: # Обычный ход
             if state.current_hands.get(player_idx):
                  message = f"Ваш ход (Улица {state.street}). Разместите карты (перетаскивание)."
             else:
                  message = f"Ожидание карт (Улица {state.street})..."
                  is_waiting = True
    else: # Не может действовать
         message = "Ожидание завершения раунда другими игроками..."
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

@app.route('/')
def index():
    # Просто рендерим шаблон. Начальное состояние будет загружено через /api/game_state
    return render_template('index.html')

@app.route('/api/game_state', methods=['GET'])
def get_game_state_api():
    """Возвращает текущее состояние игры в формате JSON."""
    game_state = load_game_state()
    human_player_idx = 0

    if game_state is None:
        dealer_idx = random.choice([0, 1])
        game_state = GameState(dealer_idx=dealer_idx)
        save_game_state(game_state)
        print("No game state found, created initial empty state.")

    try:
        frontend_state = get_state_for_frontend(game_state, human_player_idx)
        # Адаптируем сообщение для начального состояния
        if game_state.street == 0 or (game_state.is_round_over() and game_state.street < 5):
             frontend_state["message"] = "Нажмите 'Начать Раунд'"
             frontend_state["isGameOver"] = True
             frontend_state["isWaiting"] = False
             frontend_state["playerFinishedRound"] = True

        return jsonify(frontend_state)
    except Exception as e:
         print(f"Error preparing state for frontend API: {e}")
         traceback.print_exc()
         # Возвращаем базовое состояние ошибки
         return jsonify({
              "error_message": "Ошибка загрузки состояния игры.",
              "isGameOver": True,
              "message": "Ошибка. Обновите страницу или нажмите 'Начать Раунд'.",
              "humanPlayerIndex": human_player_idx,
              "playerBoard": PlayerBoard().to_dict()['rows'],
              "opponentBoard": PlayerBoard().to_dict()['rows'],
              "street": 0, "hand": [], "fantasylandHand": [], "isFantasylandRound": False,
              "playerFantasylandStatus": False, "playerDiscardCount": 0,
              "isWaiting": False, "playerFinishedRound": True,
         }), 500


@app.route('/start', methods=['POST'])
def start_game():
    """Начинает новый раунд игры."""
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

    # --- Обработка первого хода AI (если применимо) ---
    ai_needs_to_act = False
    if game_state.is_fantasyland_round and game_state.fantasyland_status[ai_idx]:
         ai_needs_to_act = game_state.fantasyland_hands[ai_idx] is not None
         if ai_needs_to_act: print(f"AI Player {ai_idx} starting Fantasyland placement...")
    elif not game_state.is_fantasyland_round and game_state.current_player_idx == ai_idx:
         ai_needs_to_act = game_state.current_hands.get(ai_idx) is not None
         if ai_needs_to_act: print(f"AI Player {ai_idx} taking first turn (Street {game_state.street})...")
    elif game_state.is_fantasyland_round and not game_state.fantasyland_status[ai_idx]:
         ai_needs_to_act = game_state.current_hands.get(ai_idx) is not None
         if ai_needs_to_act: print(f"AI Player {ai_idx} taking first turn (Regular hand in FL round, Street {game_state.street})...")

    if ai_needs_to_act:
         try:
              game_state = run_ai_turn(game_state, ai_idx)
              # После хода AI раздаем карты человеку, если нужно
              if not game_state.is_round_over() and not game_state._player_finished_round[human_player_idx]:
                   if not game_state.is_fantasyland_round and game_state.current_player_idx == human_player_idx and game_state.current_hands.get(human_player_idx) is None:
                        game_state._deal_street_to_player(human_player_idx)
                   elif game_state.is_fantasyland_round and not game_state.fantasyland_status[human_player_idx] and game_state.current_hands.get(human_player_idx) is None:
                        game_state._deal_street_to_player(human_player_idx)
         except Exception as e:
              print(f"Error during initial AI turn: {e}")
              traceback.print_exc()

    save_game_state(game_state)
    frontend_state = get_state_for_frontend(game_state, human_player_idx)
    return jsonify(frontend_state)

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

    try:
         action = ai_agent.choose_action(state)
    except Exception as e:
         print(f"Error getting action from AI agent: {e}")
         traceback.print_exc()
         action = None

    new_state = state # По умолчанию

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
         new_state = state.apply_fantasyland_placement(ai_player_index, placement, discarded)
    elif isinstance(action, tuple) and action[0] == "FANTASYLAND_FOUL":
         _, hand_to_discard = action
         print(f"AI FAILED Fantasyland placement! Fouling.")
         new_state = state.apply_fantasyland_foul(ai_player_index, hand_to_discard)
    else: # Обычный ход AI
         new_state = state.apply_action(ai_player_index, action)

    return new_state


@app.route('/move', methods=['POST'])
def handle_move():
    """Обрабатывает ход человека (после нажатия 'Готов')."""
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


        # --- Логика после хода человека ---
        # print(f"After human action. Round finished for human: {new_state._player_finished_round[human_player_idx]}")

        # --- Ход AI (если он еще не закончил) ---
        ai_made_move = False
        if not new_state.is_round_over() and not new_state._player_finished_round[ai_idx]:
             ai_can_act = False
             if new_state.is_fantasyland_round and new_state.fantasyland_status[ai_idx]:
                  ai_can_act = new_state.fantasyland_hands[ai_idx] is not None
             else:
                  ai_can_act = new_state.current_hands.get(ai_idx) is not None

             if ai_can_act:
                  print(f"AI Player {ai_idx} making move...")
                  new_state = run_ai_turn(new_state, ai_idx)
                  ai_made_move = True


        # --- Переход к следующей улице / Раздача карт ---
        # Эта логика выполняется ПОСЛЕ того, как оба игрока потенциально могли сходить
        if not new_state.is_round_over():
             # Переход улицы в обычном раунде
             if not new_state.is_fantasyland_round and all(new_state._player_acted_this_street):
                  new_state.street += 1
                  if new_state.street <= 5:
                       print(f"--- Advancing to Street {new_state.street} ---")
                       new_state._player_acted_this_street = [False] * new_state.NUM_PLAYERS
                       new_state.current_player_idx = 1 - new_state.dealer_idx
                       # Раздаем карты обоим игрокам, если они еще играют
                       for p_idx_deal in range(new_state.NUM_PLAYERS):
                            if not new_state._player_finished_round[p_idx_deal]:
                                 new_state._deal_street_to_player(p_idx_deal)

                       # Если первый игрок новой улицы - AI, делаем его ход сразу
                       if new_state.current_player_idx == ai_idx and not new_state._player_finished_round[ai_idx]:
                            print(f"AI Player {ai_idx} making move (Start of Street {new_state.street})...")
                            new_state = run_ai_turn(new_state, ai_idx)

             # Передача хода в обычном раунде (если улица не сменилась и AI еще не ходил)
             elif not new_state.is_fantasyland_round and not all(new_state._player_acted_this_street) and not ai_made_move:
                  # Если ходил человек, передаем ход AI
                  if new_state.current_player_idx == human_player_idx and not new_state._player_finished_round[ai_idx] and not new_state._player_acted_this_street[ai_idx]:
                       new_state.current_player_idx = ai_idx
                       if new_state.current_hands.get(ai_idx) is None:
                            new_state._deal_street_to_player(ai_idx)
                       if new_state.current_hands.get(ai_idx):
                            print(f"AI Player {ai_idx} making move (Middle of Street {new_state.street})...")
                            new_state = run_ai_turn(new_state, ai_idx)

             # Раздача карт в FL раунде (не-FL игрокам)
             elif new_state.is_fantasyland_round:
                  for p_idx_deal in range(new_state.NUM_PLAYERS):
                       if not new_state.fantasyland_status[p_idx_deal] and \
                          not new_state._player_finished_round[p_idx_deal] and \
                          new_state.current_hands.get(p_idx_deal) is None:
                               new_state._deal_street_to_player(p_idx_deal)
                               # Если раздали AI, он должен сходить
                               if p_idx_deal == ai_idx:
                                    print(f"AI Player {ai_idx} making move (Regular in FL round, Street {new_state.street})...")
                                    new_state = run_ai_turn(new_state, ai_idx)


        # --- Сохранение и ответ ---
        save_game_state(new_state)
        frontend_state = get_state_for_frontend(new_state, human_player_idx)
        return jsonify(frontend_state)

    # Обработка ошибок
    except ValueError as e: # Ошибки валидации хода
        print(f"Move Error (ValueError): {e}")
        traceback.print_exc() # Печатаем traceback для ValueError тоже
        current_state = load_game_state()
        if current_state:
             frontend_state = get_state_for_frontend(current_state, human_player_idx)
             frontend_state["error_message"] = str(e)
             return jsonify(frontend_state), 400
        else:
             return jsonify({"error": f"Invalid move: {e}. Could not load previous state."}), 400
    except Exception as e: # Неожиданные ошибки сервера
        print(f"Unexpected Error during move: {e}")
        traceback.print_exc()
        return jsonify({"error": "Произошла неожиданная ошибка сервера."}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    if debug_mode:
         os.environ['FLASK_ENV'] = 'development'
    print(f"Starting Flask app on port {port} with debug={debug_mode}")
    # use_reloader=False рекомендуется при использовании multiprocessing
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=False)
