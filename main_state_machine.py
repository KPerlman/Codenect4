import time
from robot_controller import RobotController
from vision_thread import VisionThread
from minimax import Minimax

class GameState:
    WAITING_HUMAN = 0
    TURN_VERIFICATION = 1
    AI_THINKING = 2
    ROBOT_MOVING = 3
    GAME_OVER = 4
    ERROR = 5

def convert_board(vision_board):
    char_board = []
    for r in range(6):
        row = []
        for c in range(7):
            val = vision_board[r][c]
            if val == 1:
                row.append('x')
            elif val == 2:
                row.append('o')
            else:
                row.append(' ')
        char_board.append(row)
    return char_board

def player_made_move(current_board, last_board):
    current_pieces = sum(1 for row in current_board for val in row if val != ' ')
    last_pieces = sum(1 for row in last_board for val in row if val != ' ')
    return current_pieces > last_pieces

def main():
    robot = RobotController()
    vision = VisionThread()
    state = GameState.WAITING_HUMAN
    last_known_board = [[' ' for _ in range(7)] for _ in range(6)]
    
    try:
        while state != GameState.GAME_OVER:
            vision_raw = vision.get_state()
            current_board = convert_board(vision_raw)
            
            if state == GameState.WAITING_HUMAN:
                if player_made_move(current_board, last_known_board):
                    last_known_board = current_board
                    state = GameState.TURN_VERIFICATION
                    
            elif state == GameState.TURN_VERIFICATION:
                solver = Minimax(current_board)
                if solver.game_is_over(current_board):
                    state = GameState.GAME_OVER
                else:
                    state = GameState.AI_THINKING
                    
            elif state == GameState.AI_THINKING:
                solver = Minimax(last_known_board)
                best_col, score = solver.best_move(5, last_known_board, 'o')
                state = GameState.ROBOT_MOVING
                
            elif state == GameState.ROBOT_MOVING:
                if best_col is not None:
                    try:
                        robot.drop_piece(best_col)
                    except TimeoutError as exc:
                        print(f"Robot error: {exc}")
                        state = GameState.ERROR
                        continue
                
                time.sleep(2)
                
                vision_raw = vision.get_state()
                last_known_board = convert_board(vision_raw)
                solver = Minimax(last_known_board)
                
                if solver.game_is_over(last_known_board):
                    state = GameState.GAME_OVER
                else:
                    state = GameState.WAITING_HUMAN

            elif state == GameState.ERROR:
                state = GameState.GAME_OVER
                    
    except KeyboardInterrupt:
        print("Shutting down")
    finally:
        vision.stop()

if __name__ == "__main__":
    main()