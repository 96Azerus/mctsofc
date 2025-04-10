# main.py
import time
import random
from typing import List, Set, Optional, Tuple, Any
from card import card_from_str, card_to_str, Card
from game_state import GameState
from mcts_agent import MCTSAgent
from fantasyland_solver import FantasylandSolver # Используется агентом

def get_human_action_street1(hand: List[Card], board: 'PlayerBoard') -> Tuple[List[Tuple[Card, str, int]], List[Card]]:
    """Запрашивает у человека размещение 5 карт."""
    print("\nYour hand:", ", ".join(card_to_str(c) for c in hand))
    placements = []
    placed_indices = set()
    hand_indices_used = set()

    for i in range(5):
        while True:
            card_options = [(idx, card) for idx, card in enumerate(hand) if idx not in hand_indices_used]
            print("Available cards:")
            for idx, card in card_options: print(f"  {idx+1}: {card_to_str(card)}")
            
            card_choice_str = input(f"Choose card {i+1} to place (1-{len(card_options)}): ")
            try:
                card_choice_idx = int(card_choice_str) - 1
                if 0 <= card_choice_idx < len(card_options):
                    hand_idx, chosen_card = card_options[card_choice_idx]
                    break
                else: print("Invalid card choice.")
            except ValueError: print("Invalid input.")

        while True:
            print(f"Place card {card_to_str(chosen_card)}:")
            row_input = input("Enter row (t/m/b) and index (e.g., 't1', 'm3', 'b0'): ").lower().strip()
            if len(row_input) >= 2:
                row_char = row_input[0]
                try:
                    index = int(row_input[1:])
                    row_map = {'t': 'top', 'm': 'middle', 'b': 'bottom'}
                    if row_char in row_map:
                        row_name = row_map[row_char]
                        capacity = board.ROW_CAPACITY[row_name]
                        if 0 <= index < capacity:
                             slot_key = (row_name, index)
                             if board.rows[row_name][index] is None and slot_key not in placed_indices:
                                 placements.append((chosen_card, row_name, index))
                                 placed_indices.add(slot_key)
                                 hand_indices_used.add(hand_idx)
                                 break
                             else: print("Slot is occupied or already chosen this turn.")
                        else: print(f"Invalid index for row {row_name} (0-{capacity-1}).")
                    else: print("Invalid row character (use t, m, or b).")
                except ValueError: print("Invalid index format.")
            else: print("Invalid input format.")

    return placements, []

def get_human_action_pineapple(hand: List[Card], board: 'PlayerBoard') -> Optional[Tuple[Tuple[Card, str, int], Tuple[Card, str, int], Card]]:
    """Запрашивает у человека ход Pineapple."""
    print("\nYour hand:", ", ".join(f"{i+1}:{card_to_str(c)}" for i, c in enumerate(hand)))

    while True:
        discard_choice = input(f"Choose card to discard (1, 2, or 3): ")
        try:
            discard_idx = int(discard_choice) - 1
            if 0 <= discard_idx < 3:
                discarded_card = hand[discard_idx]
                cards_to_place = [(hand[j], j) for j in range(3) if j != discard_idx]
                break
            else: print("Invalid choice.")
        except ValueError: print("Invalid input.")

    print(f"Discarding: {card_to_str(discarded_card)}")
    print(f"Placing: {card_to_str(cards_to_place[0][0])} and {card_to_str(cards_to_place[1][0])}")

    placements = []
    placed_slots = set()
    hand_indices_placed = set()

    for i in range(2):
        while True:
            options = [(card, idx) for card, idx in cards_to_place if idx not in hand_indices_placed]
            print(f"Choose card {i+1} to place:")
            for opt_idx, (card, _) in enumerate(options): print(f"  {opt_idx+1}: {card_to_str(card)}")
            card_choice_str = input(f"Choice (1-{len(options)}): ")
            try:
                card_choice_idx = int(card_choice_str) - 1
                if 0 <= card_choice_idx < len(options):
                    card_to_place, original_hand_idx = options[card_choice_idx]
                    break
                else: print("Invalid card choice.")
            except ValueError: print("Invalid input.")

        while True:
            print(f"Place card {card_to_str(card_to_place)}:")
            row_input = input("Enter row (t/m/b) and index (e.g., 't1', 'm3', 'b0'): ").lower().strip()
            if len(row_input) >= 2:
                row_char = row_input[0]
                try:
                    index = int(row_input[1:])
                    row_map = {'t': 'top', 'm': 'middle', 'b': 'bottom'}
                    if row_char in row_map:
                        row_name = row_map[row_char]
                        capacity = board.ROW_CAPACITY[row_name]
                        if 0 <= index < capacity:
                             if board.rows[row_name][index] is None and (row_name, index) not in placed_slots:
                                 placements.append((card_to_place, row_name, index))
                                 placed_slots.add((row_name, index))
                                 hand_indices_placed.add(original_hand_idx)
                                 break
                             else: print("Slot is occupied or already chosen this turn.")
                        else: print(f"Invalid index for row {row_name} (0-{capacity-1}).")
                    else: print("Invalid row character (use t, m, or b).")
                except ValueError: print("Invalid input.")
            else: print("Invalid input format.")

    # Убедимся, что placements содержит правильные карты в правильном порядке
    # (хотя цикл выше должен это гарантировать)
    if len(placements) != 2: return None # Ошибка

    return (placements[0], placements[1], discarded_card)

def get_human_fantasyland_placement(hand: List[Card]) -> Tuple[Optional[Dict[str, List[Card]]], Optional[List[Card]]]:
     """Запрашивает у человека размещение Фантазии."""
     print("\n--- FANTASYLAND ---")
     print("Your hand:", ", ".join(card_to_str(c) for c in hand))
     n_cards = len(hand)
     n_discard = n_cards - 13
     
     discarded_cards = []
     if n_discard > 0:
         print(f"Choose {n_discard} card(s) to discard.")
         hand_indices_used = set()
         for i in range(n_discard):
             while True:
                 options = [(idx, card) for idx, card in enumerate(hand) if idx not in hand_indices_used]
                 print("Available cards:")
                 for idx, card in options: print(f"  {idx+1}: {card_to_str(card)}")
                 choice_str = input(f"Discard choice {i+1}/{n_discard} (1-{len(options)}): ")
                 try:
                     choice_idx = int(choice_str) - 1
                     if 0 <= choice_idx < len(options):
                         hand_idx, chosen_card = options[choice_idx]
                         discarded_cards.append(chosen_card)
                         hand_indices_used.add(hand_idx)
                         break
                     else: print("Invalid choice.")
                 except ValueError: print("Invalid input.")
         print(f"Discarding: {', '.join(card_to_str(c) for c in discarded_cards)}")

     cards_to_place = [c for c in hand if c not in discarded_cards]
     print("Place the remaining 13 cards:")
     
     placement_dict = {'top': [], 'middle': [], 'bottom': []}
     placed_card_indices = set()

     for i in range(13):
         while True:
             options = [(idx, card) for idx, card in enumerate(cards_to_place) if idx not in placed_card_indices]
             print("Available cards to place:")
             for idx, card in options: print(f"  {idx+1}: {card_to_str(card)}")
             card_choice_str = input(f"Choose card {i+1}/13 to place (1-{len(options)}): ")
             try:
                 card_choice_idx = int(card_choice_str) - 1
                 if 0 <= card_choice_idx < len(options):
                     hand_idx, chosen_card = options[card_choice_idx]
                     break
                 else: print("Invalid card choice.")
             except ValueError: print("Invalid input.")

         while True:
             row_input = input(f"Place {card_to_str(chosen_card)} in row (t/m/b): ").lower().strip()
             row_map = {'t': 'top', 'm': 'middle', 'b': 'bottom'}
             if row_input in row_map:
                 row_name = row_map[row_input]
                 current_len = len(placement_dict[row_name])
                 capacity = PlayerBoard.ROW_CAPACITY[row_name]
                 if current_len < capacity:
                     placement_dict[row_name].append(chosen_card)
                     placed_card_indices.add(hand_idx)
                     print(f"Current {row_name}: {', '.join(card_to_str(c) for c in placement_dict[row_name])}")
                     break
                 else: print(f"Row {row_name} is full.")
             else: print("Invalid row (use t, m, or b).")

     # Проверяем, что все размещено
     if len(placed_card_indices) == 13:
         # Проверяем валидность (без фола) перед возвратом
         if not check_board_foul(placement_dict['top'], placement_dict['middle'], placement_dict['bottom']):
             return placement_dict, discarded_cards
         else:
             print("Error: Foul hand detected! Please re-enter placement.")
             # В реальной игре нужно дать переделать, здесь возвращаем ошибку
             return None, None
     else:
         print("Error: Did not place exactly 13 cards.")
         return None, None


def play_game():
    num_players = 2
    human_player_idx = 0 # 0 или 1, или None для AI vs AI
    ai_player = MCTSAgent(time_limit_ms=5000, rave_k=500)
    fl_solver = FantasylandSolver()

    game_score = [0, 0]
    dealer_idx = random.choice([0, 1])
    # Сохраняем статус ФЛ между раундами
    fantasyland_status_carryover = [False] * num_players

    round_num = 0
    while True:
        round_num += 1
        print(f"\n===== ROUND {round_num} =====")
        dealer_idx = 1 - dealer_idx
        print(f"Dealer is Player {dealer_idx}")

        # Инициализация состояния раунда
        current_state = GameState(dealer_idx=dealer_idx, fantasyland_status=list(fantasyland_status_carryover))
        print(f"Initial Fantasyland Status: {current_state.fantasyland_status}")

        # --- Розыгрыш Фантазии ---
        if current_state.is_fantasyland_round:
            print("--- Fantasyland Round ---")
            current_state._deal_fantasyland_hands() # Раздаем карты ФЛ и обычные (если нужно)

            # Сохраняем результаты размещений ФЛ
            fl_results = {} # player_idx -> (placement, discarded)

            # Сначала ходят обычные игроки (если есть)
            for p_idx in range(num_players):
                 if not current_state.fantasyland_status[p_idx]:
                      print(f"\nPlayer {p_idx}'s turn (Regular hand during Fantasyland)")
                      current_state.current_player_idx = p_idx
                      if current_state.street == 1 and current_state.cards_dealt_current_street is None:
                           current_state._deal_street() # Раздаем 5 карт

                      while not current_state.boards[p_idx].is_complete():
                           print(f"\nPlayer {p_idx} - Street {current_state.street}")
                           print("Current Board:")
                           print(current_state.boards[p_idx])

                           action = None
                           if p_idx == human_player_idx:
                               if current_state.street == 1:
                                   action = get_human_action_street1(current_state.cards_dealt_current_street, current_state.boards[p_idx])
                               else:
                                   action = get_human_action_pineapple(current_state.cards_dealt_current_street, current_state.boards[p_idx])
                           else: # AI
                                print(f"AI Player {p_idx} thinking...")
                                action = ai_player.choose_action(current_state)
                                print(f"AI chose: {ai_player._format_action(action)}")

                           if action is None: break
                           current_state = current_state.apply_action(action)
                           # Раздаем следующую улицу этому же игроку, если он не закончил
                           if not current_state.boards[p_idx].is_complete() and current_state.cards_dealt_current_street is None:
                                current_state._deal_street()

                      print(f"Player {p_idx} finished regular hand.")
                      print(current_state.boards[p_idx])
                      current_state._player_acted_this_street[p_idx] = True # Отмечаем, что игрок закончил

            # Теперь размещают руки игроки в Фантазии
            for p_idx in range(num_players):
                 if current_state.fantasyland_status[p_idx]:
                      hand = current_state.fantasyland_hands[p_idx]
                      if hand:
                           print(f"\nPlayer {p_idx}'s turn (Fantasyland)")
                           placement, discarded = None, None
                           if p_idx == human_player_idx:
                               placement, discarded = get_human_fantasyland_placement(hand)
                           else: # AI
                                print(f"AI Player {p_idx} solving Fantasyland...")
                                placement, discarded = fl_solver.solve(hand)

                           if placement:
                                print(f"Player {p_idx} placed Fantasyland, discarded: {[card_to_str(c) for c in discarded]}")
                                fl_results[p_idx] = (placement, discarded)
                           else:
                                print(f"Player {p_idx} FAILED Fantasyland placement! (Foul)")
                                fl_results[p_idx] = (None, hand) # Передаем None и все карты для сброса

            # Применяем результаты ФЛ ко всем доскам ОДНОВРЕМЕННО (или последовательно, не важно для счета)
            for p_idx, result in fl_results.items():
                 placement, discarded = result
                 if placement:
                     current_state.apply_fantasyland_placement(p_idx, placement, discarded)
                 else: # Фол
                     current_state.boards[p_idx].is_foul = True
                     current_state.discard_pile.extend(discarded) # Сбрасываем все карты
                     current_state.fantasyland_hands[p_idx] = None
                     current_state._player_acted_this_street[p_idx] = True


            # --- Подсчет очков ФЛ раунда ---
            print("\n--- Fantasyland Round Over ---")
            print("Final Boards:")
            print("Player 0:")
            print(current_state.boards[0])
            print("Player 1:")
            print(current_state.boards[1])
            
            score_diff = current_state.get_terminal_score()
            print(f"Fantasyland Round Score (P0 vs P1): {score_diff}")
            game_score[0] += score_diff
            game_score[1] -= score_diff
            print(f"Total Score: P0={game_score[0]}, P1={game_score[1]}")

            # Обновляем статус ФЛ для СЛЕДУЮЩЕГО раунда
            fantasyland_status_carryover = list(current_state.next_fantasyland_status)

        # --- Обычный раунд ---
        else:
            print("--- Regular Round ---")
            # Состояние уже инициализировано в start_new_round
            if current_state.cards_dealt_current_street is None:
                 current_state._deal_street() # Раздаем первому игроку

            while not current_state.is_round_over():
                player_idx = current_state.current_player_idx
                print(f"\nPlayer {player_idx}'s turn - Street {current_state.street}")
                print("Current Board:")
                print(current_state.boards[player_idx])
                print("Opponent Board:")
                print(current_state.boards[1-player_idx])

                action = None
                if player_idx == human_player_idx:
                    if current_state.street == 1:
                        action = get_human_action_street1(current_state.cards_dealt_current_street, current_state.boards[player_idx])
                    else:
                        action = get_human_action_pineapple(current_state.cards_dealt_current_street, current_state.boards[player_idx])
                else: # AI
                    print(f"AI Player {player_idx} thinking...")
                    action = ai_player.choose_action(current_state)
                    print(f"AI chose: {ai_player._format_action(action)}")

                if action is None:
                    print(f"Player {player_idx} could not make a move.")
                    # Авто-фол или другая логика? Пока завершаем раунд.
                    # Устанавливаем фол для этого игрока, чтобы корректно посчитать очки
                    current_state.boards[player_idx].is_foul = True
                    # Завершаем раунд искусственно
                    while not current_state.is_round_over():
                         # Заполняем оставшиеся слоты фиктивными картами (не из колоды)
                         # или просто ломаем цикл - get_terminal_score обработает фол
                         break
                    break

                current_state = current_state.apply_action(action)

            # --- Подсчет очков обычного раунда ---
            if current_state.is_round_over():
                 print("\n--- Regular Round Over ---")
                 print("Final Boards:")
                 print("Player 0:")
                 print(current_state.boards[0])
                 print("Player 1:")
                 print(current_state.boards[1])

                 score_diff = current_state.get_terminal_score()
                 print(f"Round Score (P0 vs P1): {score_diff}")
                 game_score[0] += score_diff
                 game_score[1] -= score_diff
                 print(f"Total Score: P0={game_score[0]}, P1={game_score[1]}")

                 # Обновляем статус ФЛ для СЛЕДУЮЩЕГО раунда
                 fantasyland_status_carryover = list(current_state.next_fantasyland_status)
                 print(f"Next round Fantasyland status: {fantasyland_status_carryover}")
            else:
                 print("\n--- Round Incomplete (Error?) ---")
                 # Если вышли из цикла не по is_round_over, значит была проблема
                 fantasyland_status_carryover = [False] * num_players # Сбрасываем ФЛ на всякий случай

        # Запрос на следующий раунд
        cont = input("Play another round? (y/n): ").lower()
        if cont != 'y':
            break

    print("\n===== GAME OVER =====")
    print(f"Final Score: Player 0: {game_score[0]}, Player 1: {game_score[1]}")

if __name__ == "__main__":
    # Установка кодировки для Windows, если необходимо
    import sys, io
    if sys.stdout.encoding != 'utf-8':
         sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
         sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    play_game()
