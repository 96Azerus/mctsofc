# app.py
import os
import pickle
import base64
import random
from typing import List, Set, Optional, Tuple, Any
from flask import Flask, render_template, request, jsonify, session

# Импортируем наши модули ИИ
from card import Card, card_from_str, card_to_str
from game_state import GameState # <-- Импортируем класс
from board import PlayerBoard # Нужен для get_state_for_frontend
from mcts_agent import MCTSAgent
from fantasyland_solver import FantasylandSolver

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_key_for_dev')

# --- Инициализация AI ---
ai_agent = MCTSAgent(time_limit_ms=3000, rave_k=500)
fl_solver = FantasylandSolver() # Используется внутри агента и напрямую

# --- Функции для работы с состоянием в сессии ---
def save_game_state(state: GameState):
    pickled_state = pickle.dumps(state)
    session['game_state'] = base64.b64encode(pickled_state).decode('utf-8')

def load_game_state() -> Optional[GameState]:
    encoded_state = session.get('game_state')
    if encoded_state:
        try:
            pickled_state = base64.b64decode(encoded_state.encode('utf-8'))
            return pickle.loads(pickled_state)
        except Exception as e:
            print(f"Error loading game state: {e}")
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

    current_hand = []
    if state.current_player_idx == player_idx and state.cards_dealt_current_street:
        current_hand = [card_to_str(c) for c in state.cards_dealt_current_street]

    fantasyland_hand = []
    if state.is_fantasyland_round and state.fantasyland_status[player_idx] and state.fantasyland_hands[player_idx]:
         fantasyland_hand = [card_to_str(c) for c in state.fantasyland_hands[player_idx]]

    message = f"Player {state.current_player_idx}'s turn. Street {state.street}."
    if state.is_fantasyland_round and state.fantasyland_status[state.current_player_idx]:
        message = f"Player {state.current_player_idx}'s turn (FANTASYLAND)."
    elif state.is_round_over():
        message = "Round Over! Click 'Start Round' for next."
        # Добавляем счет в сообщение о конце раунда
        score = state.get_terminal_score() # Счет с точки зрения игрока 0
        if player_idx == 1: score = -score # Инвертируем для игрока 1
        message += f" Your score for round: {score}"


    return {
        "playerBoard": boards_data[player_idx],
        "opponentBoard": boards_data[opponent_idx],
        "currentPlayer": state.current_player_idx,
        "humanPlayerIndex": player_idx,
        "street": state.street,
        "hand": current_hand,
        "fantasylandHand": fantasyland_hand,
        "isFantasylandRound": state.is_fantasyland_round,
        "playerFantasylandStatus": state.fantasyland_status[player_idx],
        "isGameOver": state.is_round_over(), # Используем is_round_over
        "discardPile": [card_to_str(c) for c in state.discard_pile],
        "message": message
    }

# --- Маршруты Flask ---

@app.route('/')
def index():
    game_state = load_game_state()
    human_player_idx = 0 # Человек всегда игрок 0
    if game_state is None:
        dealer_idx = random.choice([0, 1])
        game_state = GameState(dealer_idx=dealer_idx)
        game_state.start_new_round(dealer_idx)
        save_game_state(game_state)
        print("New game started.")
    else:
        print("Loaded existing game state.")

    frontend_state = get_state_for_frontend(game_state, human_player_idx)
    return render_template('index.html', game_state=frontend_state)

@app.route('/start', methods=['POST'])
def start_game():
    human_player_idx = 0
    dealer_idx = random.choice([0, 1])
    old_state = load_game_state()
    fl_status_carryover = old_state.fantasyland_status if old_state else [False, False]

    game_state = GameState(dealer_idx=dealer_idx, fantasyland_status=fl_status_carryover)
    game_state.start_new_round(dealer_idx) # Начинает раунд (обычный или ФЛ)

    # Если первый ход AI в раунде, делаем его сразу
    ai_idx = 1 - human_player_idx
    if game_state.current_player_idx == ai_idx and not game_state.is_round_over():
         print(f"\nAI Player {ai_idx} taking first turn...")
         game_state = run_ai_turn(game_state, ai_idx)

    save_game_state(game_state)
    print(f"New round started. Dealer: {dealer_idx}. FL Status: {game_state.fantasyland_status}")
    frontend_state = get_state_for_frontend(game_state, human_player_idx)
    return jsonify(frontend_state)

def run_ai_turn(current_game_state: GameState, ai_player_index: int) -> GameState:
    """Выполняет ход(ы) AI, пока не настанет очередь человека или раунд не закончится."""
    state = current_game_state
    while not state.is_round_over() and state.current_player_idx == ai_player_index:
        print(f"\nAI Player {ai_player_index} thinking...")
        ai_action = ai_agent.choose_action(state)

        if ai_action is None:
            print(f"AI Player {ai_player_index} could not choose an action. Setting foul.")
            state.boards[ai_player_index].is_foul = True
            state._player_acted_this_street[ai_player_index] = True
            # Если это ФЛ рука, нужно ее "сбросить"
            if state.is_fantasyland_round and state.fantasyland_hands[ai_player_index]:
                 state.discard_pile.extend(state.fantasyland_hands[ai_player_index])
                 state.fantasyland_hands[ai_player_index] = None
            # Передаем ход, если раунд не закончен
            if not all(state._player_acted_this_street) and not state.is_round_over():
                 state.current_player_idx = 1 - ai_player_index
                 if state.cards_dealt_current_street is None and not state.is_fantasyland_round:
                      state._deal_street()
                 elif state.is_fantasyland_round and not state.fantasyland_status[state.current_player_idx] and state.cards_dealt_current_street is None:
                      state._deal_street() # Раздаем обычному игроку в ФЛ раунде
            break # Выходим из цикла AI ходов после фола

        # Обработка разных типов действий AI
        if isinstance(ai_action, tuple) and ai_action[0] == "FANTASYLAND_PLACEMENT":
             _, placement, discarded = ai_action
             print(f"AI applying Fantasyland placement, discarding: {[card_to_str(c) for c in discarded]}")
             state.apply_fantasyland_placement(ai_player_index, placement, discarded)
        elif isinstance(ai_action, tuple) and ai_action[0] == "FANTASYLAND_FOUL":
             _, hand_to_discard = ai_action
             print(f"AI FAILED Fantasyland placement! Fouling.")
             state.boards[ai_player_index].is_foul = True
             state.discard_pile.extend(hand_to_discard)
             state.fantasyland_hands[ai_player_index] = None
             state._player_acted_this_street[ai_player_index] = True
        else:
             # Обычный ход AI
             print(f"AI applied action: {ai_agent._format_action(ai_action)}")
             state = state.apply_action(ai_action) # apply_action возвращает новое состояние

        print(f"After AI action: Player {state.current_player_idx}'s turn, Street {state.street}")

    return state


@app.route('/move', methods=['POST'])
def handle_move():
    human_player_idx = 0
    game_state = load_game_state()
    if game_state is None or game_state.is_round_over() or game_state.current_player_idx != human_player_idx:
        return jsonify({"error": "Not your turn or game state error."}), 400

    move_data = request.json
    print(f"Received move data: {move_data}")
    action = None

    try:
        # --- Парсинг и валидация хода человека ---
        if game_state.is_fantasyland_round and game_state.fantasyland_status[human_player_idx]:
             # Обработка размещения ФЛ
             placement_raw = move_data.get('placement')
             discarded_raw = move_data.get('discarded')
             if not placement_raw or discarded_raw is None: raise ValueError("Missing FL data.")

             placement_dict = {}
             placed_cards_set = set()
             for row, card_strs in placement_raw.items():
                 cards = [card_from_str(s) for s in card_strs]
                 placement_dict[row] = cards
                 placed_cards_set.update(cards)

             discarded_cards = [card_from_str(s) for s in discarded_raw]
             discarded_set = set(discarded_cards)

             original_hand = set(game_state.fantasyland_hands[human_player_idx])
             expected_discard_count = len(original_hand) - 13
             if len(placed_cards_set) != 13: raise ValueError("Must place 13 cards.")
             if len(discarded_cards) != expected_discard_count: raise ValueError(f"Must discard {expected_discard_count} card(s).")
             if not placed_cards_set.union(discarded_set) == original_hand: raise ValueError("Card mismatch.")
             if not placed_cards_set.isdisjoint(discarded_set): raise ValueError("Cannot place and discard same card.")

             # Создаем "действие" для ФЛ
             action = ("FANTASYLAND_PLACEMENT", placement_dict, discarded_cards)

        elif game_state.street == 1:
            placements_raw = move_data.get('placements')
            if not placements_raw or len(placements_raw) != 5: raise ValueError("Street 1 needs 5 placements.")
            placements = []
            placed_hand_cards = set()
            for p in placements_raw:
                card = card_from_str(p['card'])
                if card not in game_state.cards_dealt_current_street: raise ValueError(f"Card {card} not in hand.")
                if card in placed_hand_cards: raise ValueError(f"Card {card} placed multiple times.")
                placed_hand_cards.add(card)
                placements.append((card, p['row'], int(p['index'])))
            action = (placements, [])
        else: # Улицы 2-5
            placements_raw = move_data.get('placements')
            discard_str = move_data.get('discard')
            if not placements_raw or len(placements_raw) != 2 or not discard_str: raise ValueError("Invalid Pineapple move data.")

            discarded_card = card_from_str(discard_str)
            place1_raw = placements_raw[0]; place2_raw = placements_raw[1]
            card1 = card_from_str(place1_raw['card']); card2 = card_from_str(place2_raw['card'])

            hand_set = set(game_state.cards_dealt_current_street)
            action_cards = {card1, card2, discarded_card}
            if len(action_cards) != 3 or not action_cards.issubset(hand_set): raise ValueError("Card mismatch.")

            place1 = (card1, place1_raw['row'], int(place1_raw['index']))
            place2 = (card2, place2_raw['row'], int(place2_raw['index']))
            action = (place1, place2, discarded_card)

        # --- Применение хода человека ---
        if isinstance(action, tuple) and action[0] == "FANTASYLAND_PLACEMENT":
             _, placement, discarded = action
             game_state.apply_fantasyland_placement(human_player_idx, placement, discarded)
             print("Applied human Fantasyland placement.")
        else:
             game_state = game_state.apply_action(action)
             print(f"Applied human action. New state: Player {game_state.current_player_idx}'s turn, Street {game_state.street}")

        # --- Ход(ы) AI ---
        ai_idx = 1 - human_player_idx
        game_state = run_ai_turn(game_state, ai_idx)

        save_game_state(game_state)
        frontend_state = get_state_for_frontend(game_state, human_player_idx)
        return jsonify(frontend_state)

    except ValueError as e:
        print(f"Move Error: {e}")
        # Возвращаем текущее состояние с ошибкой
        current_state = load_game_state() # Загружаем последнее валидное
        frontend_state = get_state_for_frontend(current_state, human_player_idx)
        frontend_state["error_message"] = str(e) # Добавляем сообщение об ошибке
        return jsonify(frontend_state), 400 # Возвращаем 400 Bad Request
    except Exception as e:
        print(f"Unexpected Error during move: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An unexpected server error occurred."}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
