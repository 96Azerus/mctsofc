
# -*- coding: utf-8 -*-
# Этот файл содержит функцию для оценки 3-карточной руки OFC
# Он ИМПОРТИРУЕТ таблицу поиска из ofc_3card_lookup.py

from ofc_3card_lookup import three_card_lookup # Импортируем сгенерированную таблицу

# Константы, необходимые для функции
RANKS = '23456789TJQKA'
RANK_MAP = {rank: i for i, rank in enumerate(RANKS)}

# Класс Card (если используется phevaluator, иначе можно убрать или заменить)
# Добавляем простой класс Card для примера, если phevaluator не установлен
try:
    from phevaluator import Card as PhevaluatorCard
except ImportError:
    # print("Библиотека phevaluator не найдена, используется базовый класс Card.") # Можно раскомментировать для отладки
    class PhevaluatorCard:
        def __init__(self, value):
            if isinstance(value, str) and len(value) == 2:
                self.rank_char = value[0].upper()
                self.suit_char = value[1].lower()
                if self.rank_char not in RANK_MAP:
                    raise ValueError(f"Неверный ранг карты: {self.rank_char}")
                self.id_ = RANK_MAP[self.rank_char] * 4 # Примерный ID, масть не важна для OFC top
            elif isinstance(card, int): # Если передали ID карты
                 if 0 <= card <= 51:
                     self.id_ = card
                     self.rank_char = '?' # Не определяем для простоты
                     self.suit_char = '?'
                 else:
                     raise ValueError(f"Неверный ID карты: {card}")
            else:
                 raise TypeError("Неподдерживаемый тип для Card")
        def __str__(self):
             return f"{self.rank_char}{self.suit_char}"


def evaluate_3_card_ofc(card1, card2, card3):
    """
    Оценивает 3-карточную руку по правилам OFC, используя предрасчитанную таблицу.
    Карты могут быть строками ('Ah', 'Td'), int ID или объектами Card.
    Возвращает кортеж: (rank, type_string, rank_string).
    Меньший ранг соответствует более сильной руке.
    """
    ranks = []
    for card in [card1, card2, card3]:
        if isinstance(card, str):
            rank_char = card[0].upper()
            if rank_char not in RANK_MAP:
                 raise ValueError(f"Неверный ранг карты в строке: {card}")
            ranks.append(RANK_MAP[rank_char])
        # Проверяем наличие атрибута id_, чтобы быть совместимым с phevaluator.Card
        elif hasattr(card, 'id_') and isinstance(card.id_, int):
             ranks.append(card.id_ // 4)
        elif isinstance(card, int): # Если передали ID карты
             if 0 <= card <= 51:
                 ranks.append(card // 4)
             else:
                 raise ValueError(f"Неверный ID карты: {card}")
        else:
            raise TypeError(f"Неподдерживаемый тип карты: {type(card)}. Ожидалась строка, int ID или объект Card.")

    if len(ranks) != 3:
         raise ValueError("Должно быть передано ровно 3 карты")

    # Канонический ключ - отсортированный по убыванию кортеж рангов
    lookup_key = tuple(sorted(ranks, reverse=True))

    result = three_card_lookup.get(lookup_key)
    if result is None:
        # Этого не должно произойти, если таблица сгенерирована правильно
        raise ValueError(f"Не найдена комбинация для ключа: {lookup_key} (исходные ранги: {ranks})")

    return result

# Пример использования внутри модуля (для тестирования)
if __name__ == '__main__':
    # Тестируем разные руки
    hand1 = ('Ah', 'Ad', 'As') # Трипс тузов (лучшая)
    hand7 = ('5h', '3d', '2c') # 532 старшие (худшая)
    tests = [hand1, hand7]
    results = []
    for i, hand in enumerate(tests):
        try:
            rank, type_str, rank_str = evaluate_3_card_ofc(*hand)
            print(f"Тест {i+1}: {hand} -> Ранг: {rank}, Тип: {type_str}, Строка: {rank_str}")
            results.append(rank)
        except Exception as e:
            print(f"Ошибка при тесте {i+1} {hand}: {e}")
    print("Функция оценки работает.")
