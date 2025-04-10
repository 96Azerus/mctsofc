# app.py
import os
import pickle
import base64
import random
from flask import Flask, render_template, request, jsonify, session

# Импортируем наши модули ИИ
from card import Card, card_from_str, card_to_str
from game_state import GameState
from mcts_agent import MCTSAgent
from fantasyland_solver import FantasylandSolver

app = Flask(__name__)
# Обязательно установите секретный ключ для сессий!
# В реальном приложении используйте переменную окружения.
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_key_for_dev')

# --- Инициализация AI ---
# Создаем агента один раз при старте приложения
# Параметры можно вынести в конфигурацию или переменные окружения
ai_agent = MCTSAgent(time_limit_ms=3000, rave_k=500) # 3 секунды на ход AI
fl_solver = FantasylandSolver()

# --- Функции для работы с состоянием в сессии ---

def save_game_state(state: GameState):
    """Сериализует и сохраняет состояние игры в сессию."""
    pickled_state = pickle.dumps(state)
    session['game_state'] = base64.b64encode(pickled_state).decode('utf-8')

def load_game_state() -> Optional[GameState]:
    """Загружает и десериализует состояние игры из сессии."""
    encoded_state = session.get('game_state')
    if encoded_state:
        try:
            pickled_state = base64.b64decode(encoded_state.encode('utf-8'))
            return pickle.loads(pickled_state)
        except (pickle.UnpicklingError, TypeError, base64.binascii.Error) as e:
            print(f"Error loading game state: {e}")
            session.pop('game_state', None) # Очищаем невалидное состояние
            return None
    return None

def get_state_for_frontend(state: GameState, player_idx: int) -> dict:
    """Формирует данные для отправки на фронтенд."""
    opponent_idx = 1 - player_idx
    
    # Формируем представление досок
    boards_data = []
    for i, board in enumerate(state.boards):
         board_data = {}
         for row_name in PlayerBoard.ROW_NAMES:
             board_data[row_name] = [card_to_str(c) for c in board.rows[row_name]]
         boards_data.append(board_data)
         
    # Карты на руках текущего игрока (если его ход и карты есть)
    current_hand = []
    if state.current_player_idx == player_idx and state.cards_dealt_current_street:
        current_hand = [card_to_str(c) for c in state.cards_dealt_current_street]
        
    # Рука для Фантазии (если сейчас раунд ФЛ и это ход игрока)
    fantasyland_hand = []
    if state.is_fantasyland_round and state.fantasyland_status[player_idx] and state.fantasyland_hands[player_idx]:
         fantasyland_hand = [card_to_str(c) for c in state.fantasyland_hands[player_idx]]

    return {
        "playerBoard": boards_data[player_idx],
        "opponentBoard": boards_data[opponent_idx],
        "currentPlayer": state.current_player_idx,
        "humanPlayerIndex": player_idx, # Передаем индекс человека
        "street": state.street,
        "hand": current_hand, # 3 или 5 карт на улице
        "fantasylandHand": fantasyland_hand, # 14-17 карт для ФЛ
        "isFantasylandRound": state.is_fantasyland_round,
        "playerFantasylandStatus": state.fantasyland_status[player_idx],
        "isGameOver": state.is_round_over(), # Флаг конца раунда
        "discardPile": [card_to_str(c) for c in state.discard_pile],
        # Можно добавить сообщение для пользователя
        "message": f"Player {state.current_player_idx}'s turn. Street {state.street}." if not state.is_round_over() else "Round Over!"
    }


# --- Маршруты Flask ---

@app.route('/')
def index():
    """Отображает главную страницу игры."""
    # При первом заходе или ошибке состояния начинаем новую игру
    game_state = load_game_state()
    if game_state is None:
        # Устанавливаем человека как игрока 0 по умолчанию
        human_player_idx = 0
        dealer_idx = random.choice([0, 1])
        game_state = GameState(dealer_idx=dealer_idx)
        game_state.start_new_round(dealer_idx) # Начинаем первый раунд
        save_game_state(game_state)
        print("New game started.")
    else:
        # Определяем индекс человека (можно хранить в сессии или передавать)
        human_player_idx = 0 # Предполагаем, что человек всегда игрок 0
        print("Loaded existing game state.")

    frontend_state = get_state_for_frontend(game_state, human_player_idx)
    return render_template('index.html', game_state=frontend_state)

@app.route('/start', methods=['POST'])
def start_game():
    """Начинает новый раунд игры."""
    human_player_idx = 0 # Или получить из запроса/сессии
    dealer_idx = random.choice([0, 1]) # Новый дилер для нового раунда
    
    # Создаем новое состояние, но сохраняем статус ФЛ из старого, если он был
    old_state = load_game_state()
    fl_status_carryover = old_state.fantasyland_status if old_state else [False, False]
    
    game_state = GameState(dealer_idx=dealer_idx, fantasyland_status=fl_status_carryover)
    game_state.start_new_round(dealer_idx)
    save_game_state(game_state)
    print(f"New round started. Dealer: {dealer_idx}. FL Status: {game_state.fantasyland_status}")
    
    frontend_state = get_state_for_frontend(game_state, human_player_idx)
    return jsonify(frontend_state)

@app.route('/move', methods=['POST'])
def handle_move():
    """Обрабатывает ход игрока (Pineapple или Street 1)."""
    human_player_idx = 0 # Предполагаем, что человек - игрок 0
    game_state = load_game_state()
    if game_state is None or game_state.current_player_idx != human_player_idx:
        return jsonify({"error": "Not your turn or game state error."}), 400

    move_data = request.json
    print(f"Received move data: {move_data}")

    action = None
    try:
        if game_state.street == 1:
            # Формат для улицы 1: { placements: [ {card: "As", row: "top", index: 0}, ... ] }
            placements_raw = move_data.get('placements')
            if not placements_raw or len(placements_raw) != 5:
                raise ValueError("Invalid number of placements for street 1.")
            placements = []
            for p in placements_raw:
                card = card_from_str(p['card'])
                # Проверяем, что карта действительно на руке
                if card not in game_state.cards_dealt_current_street:
                     raise ValueError(f"Card {card} not in hand.")
                placements.append((card, p['row'], int(p['index'])))
            action = (placements, []) # Пустой сброс для улицы 1
        else:
            # Формат для улиц 2-5: { placements: [ {card: "Ks", row: "mid", index: 1}, {card: "Qh", ...} ], discard: "Td" }
            placements_raw = move_data.get('placements')
            discard_str = move_data.get('discard')
            if not placements_raw or len(placements_raw) != 2 or not discard_str:
                raise ValueError("Invalid data for pineapple move.")

            discarded_card = card_from_str(discard_str)
            place1_raw = placements_raw[0]
            place2_raw = placements_raw[1]
            card1 = card_from_str(place1_raw['card'])
            card2 = card_from_str(place2_raw['card'])

            # Проверяем, что карты и сброс соответствуют руке
            hand_set = set(game_state.cards_dealt_current_street)
            action_cards = {card1, card2, discarded_card}
            if len(action_cards) != 3 or not action_cards.issubset(hand_set):
                 raise ValueError("Mismatch between action cards and hand.")

            place1 = (card1, place1_raw['row'], int(place1_raw['index']))
            place2 = (card2, place2_raw['row'], int(place2_raw['index']))
            action = (place1, place2, discarded_card)

        # Проверяем легальность действия (хотя бы базово)
        # TODO: Добавить более строгую проверку легальности на бэкенде
        if action not in game_state.get_legal_actions():
             # Временное решение - если эвристика на 1й улице генерит 1 ход, он может не совпасть
             if game_state.street == 1 and len(game_state.get_legal_actions()) <= 1:
                 print("Warning: Allowing street 1 action assuming it's the only heuristic one.")
             else:
                 # print(f"Legal actions: {game_state.get_legal_actions()}")
                 # raise ValueError("Illegal action submitted.")
                 print("Warning: Potentially illegal action submitted, proceeding anyway.")


        # Применяем ход человека
        game_state = game_state.apply_action(action)
        print(f"Applied human action. New state: Player {game_state.current_player_idx}'s turn, Street {game_state.street}")

        # Ход AI (если не конец раунда и его очередь)
        ai_idx = 1 - human_player_idx
        while not game_state.is_round_over() and game_state.current_player_idx == ai_idx:
            print(f"\nAI Player {ai_idx} thinking...")
            ai_action = ai_agent.choose_action(game_state)

            if ai_action is None:
                print(f"AI Player {ai_idx} could not choose an action. Setting foul.")
                game_state.boards[ai_idx].is_foul = True
                game_state._player_acted_this_street[ai_idx] = True # Считаем ход сделанным (фол)
                # Передаем ход обратно или завершаем раунд
                if not all(game_state._player_acted_this_street):
                     game_state.current_player_idx = 1 - ai_idx
                     if game_state.cards_dealt_current_street is None: game_state._deal_street()
                break # Выходим из цикла AI ходов

            # Проверяем, не ФЛ ли это действие
            if isinstance(ai_action, tuple) and ai_action[0] == "FANTASYLAND_PLACEMENT":
                 _, placement, discarded = ai_action
                 print(f"AI applying Fantasyland placement, discarding: {[card_to_str(c) for c in discarded]}")
                 game_state.apply_fantasyland_placement(ai_idx, placement, discarded)
                 # После ФЛ ход обычно завершен для этого игрока
            elif isinstance(ai_action, tuple) and ai_action[0] == "FANTASYLAND_FOUL":
                 _, hand_to_discard = ai_action
                 print(f"AI FAILED Fantasyland placement! Fouling.")
                 game_state.boards[ai_idx].is_foul = True
                 game_state.discard_pile.extend(hand_to_discard)
                 game_state.fantasyland_hands[ai_idx] = None
                 game_state._player_acted_this_street[ai_idx] = True
            else:
                 # Обычный ход AI
                 print(f"AI applied action: {ai_agent._format_action(ai_action)}")
                 game_state = game_state.apply_action(ai_action)

            print(f"After AI action: Player {game_state.current_player_idx}'s turn, Street {game_state.street}")
            # Цикл while продолжится, если снова ход AI (маловероятно в HU)

        save_game_state(game_state)
        frontend_state = get_state_for_frontend(game_state, human_player_idx)
        return jsonify(frontend_state)

    except ValueError as e:
        print(f"Move Error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Unexpected Error during move: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An unexpected error occurred."}), 500


@app.route('/fantasyland_placement', methods=['POST'])
def handle_fantasyland():
    """Обрабатывает размещение Фантазии игроком."""
    human_player_idx = 0
    game_state = load_game_state()
    if game_state is None or not game_state.is_fantasyland_round or \
       not game_state.fantasyland_status[human_player_idx] or \
       game_state.current_player_idx != human_player_idx:
        return jsonify({"error": "Not your turn for Fantasyland or game state error."}), 400

    data = request.json
    print(f"Received Fantasyland placement data: {data}")
    
    try:
        placement_raw = data.get('placement') # Ожидаем {'top': ["As", "Kc", ...], 'middle': [...], 'bottom': [...]}
        discarded_raw = data.get('discarded') # Ожидаем ["2d", "3c", ...]
        
        if not placement_raw or not discarded_raw:
             raise ValueError("Missing placement or discard data for Fantasyland.")

        # Конвертируем карты
        placement_dict = {}
        placed_cards_set = set()
        for row, card_strs in placement_raw.items():
            cards = [card_from_str(s) for s in card_strs]
            placement_dict[row] = cards
            placed_cards_set.update(cards)

        discarded_cards = [card_from_str(s) for s in discarded_raw]
        discarded_set = set(discarded_cards)

        # Проверяем корректность
        original_hand = set(game_state.fantasyland_hands[human_player_idx])
        if len(placed_cards_set) != 13: raise ValueError("Must place exactly 13 cards.")
        if len(discarded_cards) != len(original_hand) - 13: raise ValueError("Incorrect number of discarded cards.")
        if not placed_cards_set.union(discarded_set) == original_hand: raise ValueError("Placed/discarded cards do not match hand.")
        if not placed_cards_set.isdisjoint(discarded_set): raise ValueError("Cannot place and discard the same card.")

        # Применяем размещение к состоянию
        game_state.apply_fantasyland_placement(human_player_idx, placement_dict, discarded_cards)
        print(f"Applied human Fantasyland placement.")

        # Ход AI (если он тоже в ФЛ или играет обычную руку)
        ai_idx = 1 - human_player_idx
        while not game_state.is_round_over() and game_state.current_player_idx == ai_idx:
             # Логика хода AI аналогична /move
             print(f"\nAI Player {ai_idx} thinking (during FL round)...")
             ai_action = ai_player.choose_action(game_state)
             if ai_action is None:
                 print(f"AI Player {ai_idx} could not choose an action. Setting foul.")
                 game_state.boards[ai_idx].is_foul = True
                 game_state._player_acted_this_street[ai_idx] = True
                 if not all(game_state._player_acted_this_street):
                      game_state.current_player_idx = 1 - ai_idx
                      # Раздать ли обычному игроку? Логика ФЛ сложна.
                 break

             if isinstance(ai_action, tuple) and ai_action[0] == "FANTASYLAND_PLACEMENT":
                 _, placement, discarded = ai_action
                 print(f"AI applying Fantasyland placement, discarding: {[card_to_str(c) for c in discarded]}")
                 game_state.apply_fantasyland_placement(ai_idx, placement, discarded)
             elif isinstance(ai_action, tuple) and ai_action[0] == "FANTASYLAND_FOUL":
                 _, hand_to_discard = ai_action
                 print(f"AI FAILED Fantasyland placement! Fouling.")
                 game_state.boards[ai_idx].is_foul = True
                 game_state.discard_pile.extend(hand_to_discard)
                 game_state.fantasyland_hands[ai_idx] = None
                 game_state._player_acted_this_street[ai_idx] = True
             else: # Обычный ход AI (если он не в ФЛ)
                 print(f"AI applied action: {ai_player._format_action(ai_action)}")
                 game_state = game_state.apply_action(ai_action)
                 # Раздаем следующую улицу, если нужно
                 if not game_state.boards[ai_idx].is_complete() and current_state.cards_dealt_current_street is None:
                      current_state._deal_street()


        save_game_state(game_state)
        frontend_state = get_state_for_frontend(game_state, human_player_idx)
        return jsonify(frontend_state)

    except ValueError as e:
        print(f"Fantasyland Placement Error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Unexpected Error during Fantasyland placement: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An unexpected error occurred."}), 500


if __name__ == '__main__':
    # Используем порт, который Render ожидает (обычно 10000 или из $PORT)
    port = int(os.environ.get('PORT', 8080))
    # Запускаем для доступа извне контейнера
    app.run(host='0.0.0.0', port=port, debug=False) # debug=False для продакшена
