import random
import tkinter as tk
from tkinter import messagebox


class CrossFlipPuzzle:
    def __init__(self, root):
        self.root = root
        self.root.title("Cross Flip Puzzle")
        self.root.geometry("980x700")
        self.root.minsize(900, 650)

        self.size = 5
        self.cell_size = 70
        self.moves = 0

        self.current_board = []
        self.start_board = []
        self.target_board = []

        self.current_buttons = []
        self.target_labels = []

        self.hover_row = -1
        self.hover_col = -1

        self.main_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.main_frame.pack(fill="both", expand=True)

        self.build_ui()
        self.new_game()

    # =========================
    # UI
    # =========================
    def build_ui(self):
        top_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        top_frame.pack(fill="x", padx=16, pady=12)

        title = tk.Label(
            top_frame,
            text="Cross Flip Puzzle",
            font=("Arial", 22, "bold"),
            fg="white",
            bg="#1e1e1e"
        )
        title.pack(anchor="w")

        rule_text = (
            "玩法：點左邊任一格，該格所在的整行與整列都會翻轉。\n"
            "目標：讓左邊棋盤和右邊目標圖案完全一致。"
        )
        self.rule_label = tk.Label(
            top_frame,
            text=rule_text,
            font=("Arial", 12),
            fg="#d0d0d0",
            bg="#1e1e1e",
            justify="left"
        )
        self.rule_label.pack(anchor="w", pady=(6, 0))

        control_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        control_frame.pack(fill="x", padx=16, pady=(0, 10))

        self.size_var = tk.IntVar(value=self.size)

        tk.Label(
            control_frame,
            text="棋盤大小：",
            font=("Arial", 12),
            fg="white",
            bg="#1e1e1e"
        ).pack(side="left")

        size_menu = tk.OptionMenu(control_frame, self.size_var, 3, 4, 5, 6, 7)
        size_menu.config(font=("Arial", 11), width=5)
        size_menu.pack(side="left", padx=(6, 12))

        tk.Button(
            control_frame,
            text="新遊戲",
            font=("Arial", 12, "bold"),
            width=10,
            command=self.change_size_and_new_game
        ).pack(side="left", padx=5)

        tk.Button(
            control_frame,
            text="重設",
            font=("Arial", 12),
            width=10,
            command=self.reset_board
        ).pack(side="left", padx=5)

        tk.Button(
            control_frame,
            text="提示",
            font=("Arial", 12),
            width=10,
            command=self.show_hint
        ).pack(side="left", padx=5)

        tk.Button(
            control_frame,
            text="直接求解",
            font=("Arial", 12),
            width=10,
            command=self.solve_board
        ).pack(side="left", padx=5)

        self.move_label = tk.Label(
            control_frame,
            text="步數：0",
            font=("Arial", 12, "bold"),
            fg="#ffd866",
            bg="#1e1e1e"
        )
        self.move_label.pack(side="left", padx=(20, 0))

        self.status_label = tk.Label(
            control_frame,
            text="",
            font=("Arial", 12),
            fg="#7bd88f",
            bg="#1e1e1e"
        )
        self.status_label.pack(side="left", padx=(20, 0))

        board_area = tk.Frame(self.main_frame, bg="#1e1e1e")
        board_area.pack(fill="both", expand=True, padx=16, pady=10)

        self.left_panel = tk.Frame(board_area, bg="#1e1e1e")
        self.left_panel.pack(side="left", expand=True)

        self.middle_panel = tk.Frame(board_area, bg="#1e1e1e", width=40)
        self.middle_panel.pack(side="left", fill="y")

        self.right_panel = tk.Frame(board_area, bg="#1e1e1e")
        self.right_panel.pack(side="left", expand=True)

        tk.Label(
            self.left_panel,
            text="你的棋盤",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#1e1e1e"
        ).pack(pady=(0, 10))

        tk.Label(
            self.right_panel,
            text="目標圖案",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#1e1e1e"
        ).pack(pady=(0, 10))

        self.current_grid_frame = tk.Frame(self.left_panel, bg="#1e1e1e")
        self.current_grid_frame.pack()

        self.target_grid_frame = tk.Frame(self.right_panel, bg="#1e1e1e")
        self.target_grid_frame.pack()

        legend = tk.Frame(self.main_frame, bg="#1e1e1e")
        legend.pack(fill="x", padx=16, pady=(0, 12))

        tk.Label(
            legend,
            text="■ 亮格    □ 暗格    滑鼠移到左邊格子上可預覽會影響的行列",
            font=("Arial", 11),
            fg="#bbbbbb",
            bg="#1e1e1e"
        ).pack(anchor="w")

    # =========================
    # Game setup
    # =========================
    def change_size_and_new_game(self):
        self.size = self.size_var.get()
        self.new_game()

    def new_game(self):
        self.moves = 0
        self.hover_row = -1
        self.hover_col = -1

        self.current_board = [[0 for _ in range(self.size)] for _ in range(self.size)]
        self.target_board = [[0 for _ in range(self.size)] for _ in range(self.size)]

        # 生成可解目標：從全 0 棋盤開始，隨機套用合法操作
        steps = random.randint(self.size + 2, self.size * 3 + 3)
        for _ in range(steps):
            r = random.randrange(self.size)
            c = random.randrange(self.size)
            self.apply_move_to_board(self.target_board, r, c)

        # 再隨機生成玩家起始盤面，也保證可解
        start_steps = random.randint(self.size, self.size * 2 + 2)
        for _ in range(start_steps):
            r = random.randrange(self.size)
            c = random.randrange(self.size)
            self.apply_move_to_board(self.current_board, r, c)

        self.start_board = self.copy_board(self.current_board)

        self.build_board_widgets()
        self.update_all_views()
        self.set_status("開始新遊戲")

    def reset_board(self):
        self.current_board = self.copy_board(self.start_board)
        self.moves = 0
        self.hover_row = -1
        self.hover_col = -1
        self.update_all_views()
        self.set_status("已重設到初始盤面")

    # =========================
    # Board widgets
    # =========================
    def build_board_widgets(self):
        for widget in self.current_grid_frame.winfo_children():
            widget.destroy()
        for widget in self.target_grid_frame.winfo_children():
            widget.destroy()

        self.current_buttons = []
        self.target_labels = []

        font_size = max(14, min(22, 110 // self.size))

        for r in range(self.size):
            row_buttons = []
            row_labels = []

            for c in range(self.size):
                btn = tk.Label(
                    self.current_grid_frame,
                    text="",
                    width=4,
                    height=2,
                    relief="raised",
                    bd=2,
                    font=("Arial", font_size, "bold"),
                    cursor="hand2"
                )
                btn.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

                btn.bind("<Button-1>", lambda e, rr=r, cc=c: self.click_cell(rr, cc))
                btn.bind("<Enter>", lambda e, rr=r, cc=c: self.on_hover(rr, cc))
                btn.bind("<Leave>", lambda e: self.on_leave())

                row_buttons.append(btn)

                lbl = tk.Label(
                    self.target_grid_frame,
                    text="",
                    width=4,
                    height=2,
                    relief="solid",
                    bd=2,
                    font=("Arial", font_size, "bold")
                )
                lbl.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
                row_labels.append(lbl)

            self.current_buttons.append(row_buttons)
            self.target_labels.append(row_labels)

        for i in range(self.size):
            self.current_grid_frame.grid_rowconfigure(i, weight=1)
            self.current_grid_frame.grid_columnconfigure(i, weight=1)
            self.target_grid_frame.grid_rowconfigure(i, weight=1)
            self.target_grid_frame.grid_columnconfigure(i, weight=1)

    # =========================
    # Game logic
    # =========================
    def apply_move_to_board(self, board, row, col):
        # 翻轉整行
        for c in range(self.size):
            board[row][c] ^= 1

        # 翻轉整列，但交點不要翻第二次
        for r in range(self.size):
            if r != row:
                board[r][col] ^= 1

    def click_cell(self, row, col):
        self.apply_move_to_board(self.current_board, row, col)
        self.moves += 1
        self.update_all_views()

        if self.is_win():
            self.set_status("過關了！")
            messagebox.showinfo(
                "恭喜",
                f"你成功完成拼圖！\n\n棋盤大小：{self.size} x {self.size}\n總步數：{self.moves}"
            )
        else:
            self.set_status(f"已操作 ({row + 1}, {col + 1})")

    def is_win(self):
        for r in range(self.size):
            for c in range(self.size):
                if self.current_board[r][c] != self.target_board[r][c]:
                    return False
        return True

    def copy_board(self, board):
        return [row[:] for row in board]

    # =========================
    # Hover preview
    # =========================
    def on_hover(self, row, col):
        self.hover_row = row
        self.hover_col = col
        self.update_current_board_view()

    def on_leave(self):
        self.hover_row = -1
        self.hover_col = -1
        self.update_current_board_view()

    # =========================
    # Rendering
    # =========================
    def update_all_views(self):
        self.move_label.config(text=f"步數：{self.moves}")
        self.update_current_board_view()
        self.update_target_board_view()

    def update_current_board_view(self):
        for r in range(self.size):
            for c in range(self.size):
                value = self.current_board[r][c]
                widget = self.current_buttons[r][c]

                affected = (r == self.hover_row or c == self.hover_col)
                is_hover_center = (r == self.hover_row and c == self.hover_col)

                if value == 1:
                    bg = "#ffd866"
                    fg = "#222222"
                    text = "■"
                else:
                    bg = "#3a3a3a"
                    fg = "#f0f0f0"
                    text = "□"

                if affected:
                    if value == 1:
                        bg = "#ff9d00"
                    else:
                        bg = "#5c7cfa"

                if is_hover_center:
                    bg = "#ff6188"
                    fg = "white"

                widget.config(bg=bg, fg=fg, text=text)

    def update_target_board_view(self):
        for r in range(self.size):
            for c in range(self.size):
                value = self.target_board[r][c]
                widget = self.target_labels[r][c]

                if value == 1:
                    widget.config(bg="#7bd88f", fg="#1e1e1e", text="■")
                else:
                    widget.config(bg="#2f2f2f", fg="#f0f0f0", text="□")

    def set_status(self, text):
        self.status_label.config(text=text)

    # =========================
    # Solver (GF(2))
    # =========================
    def board_diff_vector(self):
        vec = []
        for r in range(self.size):
            for c in range(self.size):
                vec.append(self.current_board[r][c] ^ self.target_board[r][c])
        return vec

    def build_operation_matrix(self):
        n = self.size * self.size
        matrix = []

        for move_r in range(self.size):
            for move_c in range(self.size):
                col_vec = [0] * n

                # 這個 move 會影響哪些格子
                for c in range(self.size):
                    idx = move_r * self.size + c
                    col_vec[idx] ^= 1

                for r in range(self.size):
                    if r != move_r:
                        idx = r * self.size + move_c
                        col_vec[idx] ^= 1

                matrix.append(col_vec)

        return matrix

    def solve_gf2(self, A_cols, b):
        """
        解 A x = b over GF(2)
        A_cols: 以「欄」表示的矩陣，每個欄代表一個操作
        轉成 row form 後做高斯消去
        """
        n_rows = len(b)
        n_cols = len(A_cols)

        # 轉成 row-major augmented matrix
        mat = []
        for r in range(n_rows):
            row = [A_cols[c][r] for c in range(n_cols)]
            row.append(b[r])
            mat.append(row)

        pivot_cols = []
        row = 0

        for col in range(n_cols):
            pivot = -1
            for r in range(row, n_rows):
                if mat[r][col] == 1:
                    pivot = r
                    break

            if pivot == -1:
                continue

            mat[row], mat[pivot] = mat[pivot], mat[row]
            pivot_cols.append(col)

            for r in range(n_rows):
                if r != row and mat[r][col] == 1:
                    for cc in range(col, n_cols + 1):
                        mat[r][cc] ^= mat[row][cc]

            row += 1
            if row == n_rows:
                break

        # 檢查無解
        for r in range(n_rows):
            all_zero = True
            for c in range(n_cols):
                if mat[r][c] != 0:
                    all_zero = False
                    break
            if all_zero and mat[r][n_cols] != 0:
                return None

        # 回填一組解（自由變數設 0）
        x = [0] * n_cols
        for r, col in enumerate(pivot_cols):
            x[col] = mat[r][n_cols]

        return x

    def get_solution_moves(self):
        b = self.board_diff_vector()
        A_cols = self.build_operation_matrix()
        sol = self.solve_gf2(A_cols, b)
        if sol is None:
            return None

        moves = []
        for idx, v in enumerate(sol):
            if v == 1:
                r = idx // self.size
                c = idx % self.size
                moves.append((r, c))
        return moves

    def show_hint(self):
        if self.is_win():
            messagebox.showinfo("提示", "你已經完成了，不需要提示。")
            return

        moves = self.get_solution_moves()
        if not moves:
            messagebox.showinfo("提示", "目前找不到提示，或此盤面已完成。")
            return

        r, c = moves[0]
        self.set_status(f"提示：試試點第 {r + 1} 行，第 {c + 1} 列")
        messagebox.showinfo(
            "提示",
            f"建議下一步：\n第 {r + 1} 行，第 {c + 1} 列"
        )

    def solve_board(self):
        if self.is_win():
            messagebox.showinfo("求解", "這盤已經完成。")
            return

        moves = self.get_solution_moves()
        if moves is None:
            messagebox.showwarning("求解", "這個盤面找不到解。")
            return

        if not moves:
            messagebox.showinfo("求解", "目前盤面已等於目標。")
            return

        answer = messagebox.askyesno(
            "直接求解",
            f"將自動套用 {len(moves)} 步解法。\n要直接完成嗎？"
        )
        if not answer:
            return

        for r, c in moves:
            self.apply_move_to_board(self.current_board, r, c)
            self.moves += 1

        self.update_all_views()

        if self.is_win():
            self.set_status("已自動求解")
            messagebox.showinfo(
                "完成",
                f"已自動完成拼圖。\n總步數：{self.moves}"
            )


def main():
    root = tk.Tk()
    app = CrossFlipPuzzle(root)
    root.mainloop()


if __name__ == "__main__":
    main()