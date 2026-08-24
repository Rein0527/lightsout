import tkinter as tk
from tkinter import messagebox
from collections import deque
from fractions import Fraction
import random

try:
    import sympy as sp
    SYMPY_AVAILABLE = True
except Exception:
    SYMPY_AVAILABLE = False


def is_prime(n: int) -> bool:
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0:
        return False
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def mod_inverse(a: int, p: int) -> int:
    a %= p
    if a == 0:
        raise ZeroDivisionError("0 在模質數下沒有逆元")
    return pow(a, p - 2, p)


class LightsOutGameND:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("開燈遊戲 Lights Out 2D / 3D")

        self.dimension = 2
        self.n = 3
        self.mod = 2
        self.target_value = 1

        # 2D: board[r][c]
        # 3D: board[z][r][c]
        self.board = []
        self.buttons = []
        self.move_count = 0

        self.last_solution_counts = None
        self.last_solution_sequence = None
        self.last_solution_text = ""
        self.last_full_solvable_text = "尚未檢查"
        self.last_current_solvable_text = "尚未檢查"
        self.last_density_text = "尚未檢查"

        control_frame = tk.Frame(root, padx=10, pady=10)
        control_frame.pack(fill="x")

        tk.Label(control_frame, text="維度:").grid(row=0, column=0, sticky="w")
        self.dimension_var = tk.StringVar(value="2")
        self.dimension_menu = tk.OptionMenu(control_frame, self.dimension_var, "2", "3")
        self.dimension_menu.grid(row=0, column=1, padx=5)

        tk.Label(control_frame, text="N (邊長):").grid(row=0, column=2, sticky="w")
        self.n_entry = tk.Entry(control_frame, width=8)
        self.n_entry.grid(row=0, column=3, padx=5)
        self.n_entry.insert(0, "3")

        tk.Label(control_frame, text="元數 (mod):").grid(row=0, column=4, sticky="w")
        self.mod_entry = tk.Entry(control_frame, width=8)
        self.mod_entry.grid(row=0, column=5, padx=5)
        self.mod_entry.insert(0, "2")

        tk.Label(control_frame, text="目標值:").grid(row=0, column=6, sticky="w")
        self.target_entry = tk.Entry(control_frame, width=8)
        self.target_entry.grid(row=0, column=7, padx=5)
        self.target_entry.insert(0, "1")

        tk.Button(control_frame, text="建立新遊戲", command=self.create_new_game).grid(row=0, column=8, padx=8)
        tk.Button(control_frame, text="隨機可解盤面", command=self.shuffle_solvable_board).grid(row=0, column=9, padx=4)
        tk.Button(control_frame, text="隨機任意盤面", command=self.random_any_board).grid(row=0, column=10, padx=4)
        tk.Button(control_frame, text="重設全0", command=self.clear_board).grid(row=0, column=11, padx=4)
        tk.Button(control_frame, text="設為全目標", command=self.fill_target_board).grid(row=0, column=12, padx=4)

        solver_frame = tk.Frame(root, padx=10, pady=5)
        solver_frame.pack(fill="x")

        tk.Button(solver_frame, text="求解", command=self.solve_current_board).pack(side="left", padx=4)
        tk.Button(solver_frame, text="套用解", command=self.apply_last_solution).pack(side="left", padx=4)
        tk.Button(solver_frame, text="提示一步", command=self.apply_one_hint).pack(side="left", padx=4)
        tk.Button(solver_frame, text="檢查是否完全可解", command=self.check_full_solvability).pack(side="left", padx=4)
        tk.Button(solver_frame, text="計算有解密度", command=self.check_solution_density).pack(side="left", padx=4)

        info_frame = tk.Frame(root, padx=10, pady=5)
        info_frame.pack(fill="x")

        self.info_label = tk.Label(info_frame, text="", anchor="w", justify="left")
        self.info_label.pack(fill="x")

        self.board_container = tk.Frame(root, padx=10, pady=10)
        self.board_container.pack()

        self.create_new_game()

    # -----------------------------
    # 維度 / 大小 / 索引
    # -----------------------------
    def total_cells(self) -> int:
        if self.dimension == 2:
            return self.n * self.n
        return self.n * self.n * self.n

    def cell_index(self, *pos) -> int:
        if self.dimension == 2:
            r, c = pos
            return r * self.n + c
        else:
            z, r, c = pos
            return z * self.n * self.n + r * self.n + c

    def index_to_cell(self, idx: int):
        if self.dimension == 2:
            return divmod(idx, self.n)
        else:
            layer_size = self.n * self.n
            z = idx // layer_size
            rem = idx % layer_size
            r = rem // self.n
            c = rem % self.n
            return z, r, c

    def get_all_positions(self):
        if self.dimension == 2:
            return [(r, c) for r in range(self.n) for c in range(self.n)]
        else:
            return [(z, r, c) for z in range(self.n) for r in range(self.n) for c in range(self.n)]

    def get_affected_positions(self, *pos):
        if self.dimension == 2:
            r, c = pos
            candidates = [
                (r, c),
                (r - 1, c),
                (r + 1, c),
                (r, c - 1),
                (r, c + 1),
            ]
            return [
                (rr, cc)
                for rr, cc in candidates
                if 0 <= rr < self.n and 0 <= cc < self.n
            ]
        else:
            z, r, c = pos
            candidates = [
                (z, r, c),
                (z, r - 1, c),
                (z, r + 1, c),
                (z, r, c - 1),
                (z, r, c + 1),
                (z - 1, r, c),
                (z + 1, r, c),
            ]
            return [
                (zz, rr, cc)
                for zz, rr, cc in candidates
                if 0 <= zz < self.n and 0 <= rr < self.n and 0 <= cc < self.n
            ]

    # -----------------------------
    # 建立 / 初始化
    # -----------------------------
    def create_empty_board(self):
        if self.dimension == 2:
            return [[0 for _ in range(self.n)] for _ in range(self.n)]
        else:
            return [[[0 for _ in range(self.n)] for _ in range(self.n)] for _ in range(self.n)]

    def create_target_board(self):
        if self.dimension == 2:
            return [[self.target_value for _ in range(self.n)] for _ in range(self.n)]
        else:
            return [[[self.target_value for _ in range(self.n)] for _ in range(self.n)] for _ in range(self.n)]

    def create_random_board(self):
        if self.dimension == 2:
            return [[random.randrange(self.mod) for _ in range(self.n)] for _ in range(self.n)]
        else:
            return [
                [
                    [random.randrange(self.mod) for _ in range(self.n)]
                    for _ in range(self.n)
                ]
                for _ in range(self.n)
            ]

    # -----------------------------
    # UI / 遊戲流程
    # -----------------------------
    def create_new_game(self) -> None:
        try:
            dimension = int(self.dimension_var.get())
            n = int(self.n_entry.get())
            mod = int(self.mod_entry.get())
            target_value = int(self.target_entry.get())
        except ValueError:
            messagebox.showerror("輸入錯誤", "請輸入整數。")
            return

        if dimension not in (2, 3):
            messagebox.showerror("輸入錯誤", "維度只能是 2 或 3。")
            return
        if n <= 0:
            messagebox.showerror("輸入錯誤", "N 必須大於 0。")
            return
        if mod <= 1:
            messagebox.showerror("輸入錯誤", "元數必須大於 1。")
            return
        if not (0 <= target_value < mod):
            messagebox.showerror("輸入錯誤", f"目標值必須在 0 到 {mod - 1} 之間。")
            return

        self.dimension = dimension
        self.n = n
        self.mod = mod
        self.target_value = target_value
        self.move_count = 0

        self.last_solution_counts = None
        self.last_solution_sequence = None
        self.last_solution_text = ""
        self.last_full_solvable_text = "尚未檢查"
        self.last_current_solvable_text = "尚未檢查"
        self.last_density_text = "尚未檢查"

        self.board = self.create_empty_board()
        self._build_board_ui()
        self.update_all_buttons()
        self.update_info()

    def _build_board_ui(self) -> None:
        for widget in self.board_container.winfo_children():
            widget.destroy()

        self.buttons = []

        if self.dimension == 2:
            frame = tk.Frame(self.board_container)
            frame.pack()

            for r in range(self.n):
                row_buttons = []
                for c in range(self.n):
                    btn = tk.Button(
                        frame,
                        text="0",
                        width=4,
                        height=2,
                        font=("Arial", 14),
                        command=lambda rr=r, cc=c: self.click_cell(rr, cc),
                    )
                    btn.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                    row_buttons.append(btn)
                self.buttons.append(row_buttons)

            for i in range(self.n):
                frame.grid_rowconfigure(i, weight=1)
                frame.grid_columnconfigure(i, weight=1)

        else:
            for z in range(self.n):
                layer_frame = tk.LabelFrame(self.board_container, text=f"Layer z={z}", padx=5, pady=5)
                layer_frame.grid(row=0, column=z, padx=8, pady=8, sticky="n")

                layer_buttons = []
                for r in range(self.n):
                    row_buttons = []
                    for c in range(self.n):
                        btn = tk.Button(
                            layer_frame,
                            text="0",
                            width=4,
                            height=2,
                            font=("Arial", 12),
                            command=lambda zz=z, rr=r, cc=c: self.click_cell(zz, rr, cc),
                        )
                        btn.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                        row_buttons.append(btn)
                    layer_buttons.append(row_buttons)

                for i in range(self.n):
                    layer_frame.grid_rowconfigure(i, weight=1)
                    layer_frame.grid_columnconfigure(i, weight=1)

                self.buttons.append(layer_buttons)

    def reset_analysis_flags(self) -> None:
        self.last_solution_counts = None
        self.last_solution_sequence = None
        self.last_solution_text = ""
        self.last_current_solvable_text = "尚未檢查"

    def click_cell(self, *pos) -> None:
        self.apply_move(*pos)
        self.move_count += 1
        self.reset_analysis_flags()
        self.update_all_buttons()
        self.update_info()

        if self.is_solved():
            messagebox.showinfo("完成", f"恭喜，你已達成目標！\n步數：{self.move_count}")

    def apply_move(self, *pos) -> None:
        for p in self.get_affected_positions(*pos):
            if self.dimension == 2:
                r, c = p
                self.board[r][c] = (self.board[r][c] + 1) % self.mod
            else:
                z, r, c = p
                self.board[z][r][c] = (self.board[z][r][c] + 1) % self.mod

    def shuffle_solvable_board(self) -> None:
        self.board = self.create_empty_board()
        times = max(10, self.total_cells() * 3)
        for _ in range(times):
            pos = random.choice(self.get_all_positions())
            self.apply_move(*pos)

        self.move_count = 0
        self.reset_analysis_flags()
        self.update_all_buttons()
        self.update_info()

    def random_any_board(self) -> None:
        self.board = self.create_random_board()
        self.move_count = 0
        self.reset_analysis_flags()
        self.update_all_buttons()
        self.update_info()

    def clear_board(self) -> None:
        self.board = self.create_empty_board()
        self.move_count = 0
        self.reset_analysis_flags()
        self.update_all_buttons()
        self.update_info()

    def fill_target_board(self) -> None:
        self.board = self.create_target_board()
        self.move_count = 0
        self.reset_analysis_flags()
        self.update_all_buttons()
        self.update_info()

    def is_solved(self) -> bool:
        if self.dimension == 2:
            return all(
                self.board[r][c] == self.target_value
                for r in range(self.n)
                for c in range(self.n)
            )
        else:
            return all(
                self.board[z][r][c] == self.target_value
                for z in range(self.n)
                for r in range(self.n)
                for c in range(self.n)
            )

    def update_all_buttons(self) -> None:
        if self.dimension == 2:
            for r in range(self.n):
                for c in range(self.n):
                    value = self.board[r][c]
                    self.buttons[r][c].config(
                        text=str(value),
                        relief="sunken" if value == self.target_value else "raised"
                    )
        else:
            for z in range(self.n):
                for r in range(self.n):
                    for c in range(self.n):
                        value = self.board[z][r][c]
                        self.buttons[z][r][c].config(
                            text=str(value),
                            relief="sunken" if value == self.target_value else "raised"
                        )

    def update_info(self) -> None:
        status = "已達成目標" if self.is_solved() else "尚未達成"
        solver_status = "尚未求解" if not self.last_solution_text else "已有最近一次求解結果"

        if self.dimension == 2:
            rule_text = f"2D 規則：點一下讓「自己 + 上下左右」全部 +1 (mod {self.mod})"
            size_text = f"2D 棋盤：{self.n}×{self.n}"
        else:
            rule_text = f"3D 規則：點一下讓「自己 + 上下左右 + 前後層」全部 +1 (mod {self.mod})"
            size_text = f"3D 棋盤：{self.n}×{self.n}×{self.n}"

        self.info_label.config(
            text=(
                f"{rule_text}\n"
                f"{size_text}    元數：{self.mod}    目標值：{self.target_value}    步數：{self.move_count}\n"
                f"狀態：{status}    求解器：{solver_status}\n"
                f"目前盤面可解性：{self.last_current_solvable_text}    "
                f"整個系統完全可解性：{self.last_full_solvable_text}\n"
                f"有解密度：{self.last_density_text}"
            )
        )

    # -----------------------------
    # 工具函式
    # -----------------------------
    def flatten_board(self, board_override=None):
        board = self.board if board_override is None else board_override

        if self.dimension == 2:
            return [board[r][c] for r in range(self.n) for c in range(self.n)]
        else:
            return [board[z][r][c] for z in range(self.n) for r in range(self.n) for c in range(self.n)]

    def unflatten_vector(self, vec):
        if self.dimension == 2:
            return [vec[i * self.n:(i + 1) * self.n] for i in range(self.n)]
        else:
            result = []
            idx = 0
            for z in range(self.n):
                layer = []
                for r in range(self.n):
                    row = []
                    for c in range(self.n):
                        row.append(vec[idx])
                        idx += 1
                    layer.append(row)
                result.append(layer)
            return result

    def build_move_matrix(self):
        size = self.total_cells()
        A = [[0 for _ in range(size)] for _ in range(size)]

        for pos in self.get_all_positions():
            col = self.cell_index(*pos)
            for aff in self.get_affected_positions(*pos):
                row = self.cell_index(*aff)
                A[row][col] = (A[row][col] + 1) % self.mod
        return A

    def current_target_delta(self):
        cur = self.flatten_board()
        target = [self.target_value] * self.total_cells()
        return [(target[i] - cur[i]) % self.mod for i in range(self.total_cells())]

    def counts_to_text(self, counts):
        data = self.unflatten_vector(counts)

        if self.dimension == 2:
            lines = ["每格按的次數："]
            for row in data:
                lines.append(" ".join(str(x) for x in row))
        else:
            lines = ["每格按的次數（依 layer 顯示）："]
            for z in range(self.n):
                lines.append(f"Layer z={z}:")
                for row in data[z]:
                    lines.append(" ".join(str(x) for x in row))
                lines.append("")

        total = sum(counts)
        lines.append(f"總按次數（把同一格按多次也算步數）: {total}")
        return "\n".join(lines)

    def counts_to_sequence(self, counts):
        seq = []
        for idx, cnt in enumerate(counts):
            pos = self.index_to_cell(idx)
            for _ in range(cnt):
                seq.append(pos)
        return seq

    # -----------------------------
    # GF(2) rank
    # -----------------------------
    def gf2_rank(self, A):
        if not A:
            return 0

        mat = [row[:] for row in A]
        rows = len(mat)
        cols = len(mat[0])

        rank = 0
        row = 0

        for col in range(cols):
            pivot = None
            for r in range(row, rows):
                if mat[r][col] == 1:
                    pivot = r
                    break

            if pivot is None:
                continue

            if pivot != row:
                mat[row], mat[pivot] = mat[pivot], mat[row]

            for r in range(rows):
                if r != row and mat[r][col] == 1:
                    for k in range(col, cols):
                        mat[r][k] ^= mat[row][k]

            rank += 1
            row += 1
            if row == rows:
                break

        return rank

    # -----------------------------
    # 一般 GF(p) 高斯消去（p 為質數）
    # -----------------------------
    def solve_mod_prime_gaussian(self, A, b, p):
        rows = len(A)
        cols = len(A[0]) if rows > 0 else 0
        aug = [[A[r][c] % p for c in range(cols)] + [b[r] % p] for r in range(rows)]

        pivot_cols = []
        row = 0

        for col in range(cols):
            pivot = None
            for r in range(row, rows):
                if aug[r][col] % p != 0:
                    pivot = r
                    break

            if pivot is None:
                continue

            if pivot != row:
                aug[row], aug[pivot] = aug[pivot], aug[row]

            pivot_val = aug[row][col] % p
            inv_pivot = mod_inverse(pivot_val, p)

            for k in range(col, cols + 1):
                aug[row][k] = (aug[row][k] * inv_pivot) % p

            for r in range(rows):
                if r != row and aug[r][col] % p != 0:
                    factor = aug[r][col] % p
                    for k in range(col, cols + 1):
                        aug[r][k] = (aug[r][k] - factor * aug[row][k]) % p

            pivot_cols.append(col)
            row += 1
            if row == rows:
                break

        for r in range(rows):
            if all((aug[r][c] % p) == 0 for c in range(cols)) and (aug[r][cols] % p) != 0:
                return None

        x = [0] * cols
        for r, col in enumerate(pivot_cols):
            x[col] = aug[r][cols] % p

        return x

    # -----------------------------
    # 完全可解性檢查
    # -----------------------------
    def check_full_solvability(self):
        if not SYMPY_AVAILABLE:
            msg = "未安裝 sympy，無法進行矩陣可逆性檢查。\n請先執行：\npip install sympy"
            messagebox.showwarning("無法檢查", msg)
            return

        A = sp.Matrix(self.build_move_matrix())
        size = self.total_cells()

        try:
            _ = A.inv_mod(self.mod)
            self.last_full_solvable_text = "是"

            if self.dimension == 2:
                board_text = f"{self.n}×{self.n}"
            else:
                board_text = f"{self.n}×{self.n}×{self.n}"

            msg = (
                f"結果：是，完全可解。\n\n"
                f"維度：{self.dimension}D\n"
                f"棋盤：{board_text}\n"
                f"元數：mod {self.mod}\n"
                f"矩陣大小：{size}×{size}\n\n"
                f"代表意義：\n"
                f"- 任意初始盤面都能到任意目標盤面\n"
                f"- 對每個目標差值，都存在唯一解（mod {self.mod} 意義下）"
            )
            messagebox.showinfo("完全可解性", msg)
        except Exception:
            self.last_full_solvable_text = "否"

            if self.dimension == 2:
                board_text = f"{self.n}×{self.n}"
            else:
                board_text = f"{self.n}×{self.n}×{self.n}"

            msg = (
                f"結果：否，不是完全可解。\n\n"
                f"維度：{self.dimension}D\n"
                f"棋盤：{board_text}\n"
                f"元數：mod {self.mod}\n"
                f"矩陣大小：{size}×{size}\n\n"
                f"代表意義：\n"
                f"- 存在某些初始盤面無法到某些目標盤面\n"
                f"- 也可能出現多解盤面\n"
                f"- 原因是操作矩陣在 mod {self.mod} 下不可逆"
            )
            messagebox.showwarning("完全可解性", msg)

        self.update_info()

    # -----------------------------
    # 有解密度
    # -----------------------------
    def check_solution_density(self):
        total_cells = self.total_cells()

        if not is_prime(self.mod):
            msg = (
                "目前這版只對質數 mod 精確計算有解密度。\n\n"
                "原因：\n"
                "- 質數 mod 時可在 GF(p) 上用 rank 計算\n"
                "- 合成數 mod 需要更一般的代數工具，例如 Smith normal form"
            )
            messagebox.showwarning("暫不支援", msg)
            return

        if self.mod == 2:
            A = self.build_move_matrix()
            A2 = [[v & 1 for v in row] for row in A]
            rank = self.gf2_rank(A2)
        else:
            if not SYMPY_AVAILABLE:
                msg = "mod 為質數且大於 2 時，密度計算目前需要 sympy。\n請先執行：\npip install sympy"
                messagebox.showwarning("無法計算", msg)
                return
            A = sp.Matrix(self.build_move_matrix())
            rank = int(A.rank(iszerofunc=lambda x: x % self.mod == 0))

        kernel_dim = total_cells - rank
        density_fraction = Fraction(1, self.mod ** kernel_dim)
        density_float = float(density_fraction)
        density_percent = density_float * 100.0

        self.last_density_text = f"{density_fraction} ({density_percent:.6f}%)"

        if self.dimension == 2:
            board_text = f"{self.n}×{self.n}"
        else:
            board_text = f"{self.n}×{self.n}×{self.n}"

        msg = (
            f"質數 mod 系統有解密度計算結果\n\n"
            f"維度：{self.dimension}D\n"
            f"棋盤：{board_text}\n"
            f"mod：{self.mod}\n"
            f"格子總數 N：{total_cells}\n"
            f"rank(A)：{rank}\n"
            f"kernel 維度：{kernel_dim}\n\n"
            f"有解密度 = mod^(rank - N)\n"
            f"          = {self.mod}^({rank} - {total_cells})\n"
            f"          = 1 / {self.mod}^{kernel_dim}\n"
            f"          = {density_fraction}\n"
            f"          ≈ {density_percent:.6f}%"
        )
        messagebox.showinfo("有解密度", msg)
        self.update_info()

    # -----------------------------
    # 求解器
    # -----------------------------
    def solve_current_board(self):
        if self.is_solved():
            self.last_solution_counts = [0] * self.total_cells()
            self.last_solution_sequence = []
            self.last_solution_text = "目前已經達成目標，不需要操作。"
            self.last_current_solvable_text = "是"
            messagebox.showinfo("求解結果", self.last_solution_text)
            self.update_info()
            return

        result = self.solve_via_matrix_inverse()

        if result is None and is_prime(self.mod):
            result = self.solve_via_mod_prime_gaussian_wrapper()

        if result is None:
            result = self.solve_via_bfs_if_small()

        if result is None:
            msg = (
                "目前無法直接給出解。\n\n"
                "可能原因：\n"
                "1. 目前盤面無解。\n"
                "2. mod 不是質數，尚未支援一般合成數模高斯消去。\n"
                "3. 狀態空間太大，不適合用 BFS 暴力搜尋。\n"
                "4. 若未安裝 sympy，矩陣反元素法可能不可用。"
            )
            self.last_solution_counts = None
            self.last_solution_sequence = None
            self.last_solution_text = ""
            self.last_current_solvable_text = "否"
            messagebox.showwarning("求解失敗", msg)
            self.update_info()
            return

        self.last_solution_counts = result["counts"]
        self.last_solution_sequence = result["sequence"]
        self.last_solution_text = result["text"]
        self.last_current_solvable_text = "是"
        messagebox.showinfo("求解結果", self.last_solution_text)
        self.update_info()

    def solve_via_matrix_inverse(self):
        if not SYMPY_AVAILABLE:
            return None

        try:
            A = sp.Matrix(self.build_move_matrix())
            b = sp.Matrix(self.current_target_delta())

            invA = A.inv_mod(self.mod)
            x = invA * b
            counts = [int(v % self.mod) for v in list(x)]
            seq = self.counts_to_sequence(counts)

            text = (
                f"求解方式：矩陣反元素（mod {self.mod}）\n"
                f"{self.counts_to_text(counts)}"
            )
            return {
                "counts": counts,
                "sequence": seq,
                "text": text,
            }
        except Exception:
            return None

    def solve_via_mod_prime_gaussian_wrapper(self):
        A = self.build_move_matrix()
        b = self.current_target_delta()
        x = self.solve_mod_prime_gaussian(A, b, self.mod)
        if x is None:
            return None

        counts = [int(v % self.mod) for v in x]
        seq = self.counts_to_sequence(counts)

        text = (
            f"求解方式：GF({self.mod}) 高斯消去\n"
            "說明：整個系統未必完全可解，但目前這一盤有解。\n"
            f"{self.counts_to_text(counts)}"
        )
        return {
            "counts": counts,
            "sequence": seq,
            "text": text,
        }

    def solve_via_bfs_if_small(self):
        total_states = self.mod ** self.total_cells()
        max_states = 50000

        if total_states > max_states:
            return None

        start = tuple(self.flatten_board())
        goal = tuple([self.target_value] * self.total_cells())

        if start == goal:
            return {
                "counts": [0] * self.total_cells(),
                "sequence": [],
                "text": "目前已經達成目標，不需要操作。",
            }

        move_effects = []
        for pos in self.get_all_positions():
            effect = [0] * self.total_cells()
            for aff in self.get_affected_positions(*pos):
                effect[self.cell_index(*aff)] = (effect[self.cell_index(*aff)] + 1) % self.mod
            move_effects.append(effect)

        queue = deque([start])
        parent = {start: None}
        move_used = {start: None}

        found = False
        while queue and not found:
            state = queue.popleft()

            for idx, effect in enumerate(move_effects):
                nxt = tuple((state[i] + effect[i]) % self.mod for i in range(self.total_cells()))
                if nxt in parent:
                    continue
                parent[nxt] = state
                move_used[nxt] = idx
                if nxt == goal:
                    found = True
                    break
                queue.append(nxt)

        if goal not in parent:
            return None

        seq_idx = []
        cur = goal
        while parent[cur] is not None:
            seq_idx.append(move_used[cur])
            cur = parent[cur]
        seq_idx.reverse()

        counts = [0] * self.total_cells()
        sequence = []
        for idx in seq_idx:
            counts[idx] += 1
            sequence.append(self.index_to_cell(idx))

        text = (
            f"求解方式：BFS 最短路徑\n"
            f"{self.counts_to_text(counts)}\n"
            f"最短步數：{len(sequence)}"
        )

        return {
            "counts": counts,
            "sequence": sequence,
            "text": text,
        }

    # -----------------------------
    # 套用解 / 提示
    # -----------------------------
    def apply_last_solution(self):
        if not self.last_solution_sequence:
            if self.last_solution_counts == [0] * self.total_cells():
                messagebox.showinfo("套用解", "目前已經是目標盤面。")
            else:
                messagebox.showwarning("套用解", "請先按「求解」。")
            return

        for pos in self.last_solution_sequence:
            self.apply_move(*pos)
            self.move_count += 1

        self.last_solution_counts = None
        self.last_solution_sequence = None
        self.last_solution_text = ""
        self.last_current_solvable_text = "尚未檢查"
        self.update_all_buttons()
        self.update_info()

        if self.is_solved():
            messagebox.showinfo("完成", f"已自動套用解，達成目標！\n步數：{self.move_count}")

    def apply_one_hint(self):
        if not self.last_solution_sequence:
            messagebox.showwarning("提示一步", "請先按「求解」。")
            return

        pos = self.last_solution_sequence.pop(0)
        self.apply_move(*pos)
        self.move_count += 1

        if self.last_solution_counts is not None:
            idx = self.cell_index(*pos)
            if self.last_solution_counts[idx] > 0:
                self.last_solution_counts[idx] -= 1

        self.last_current_solvable_text = "尚未檢查"
        self.update_all_buttons()
        self.update_info()

        if self.is_solved():
            self.last_solution_counts = None
            self.last_solution_sequence = None
            self.last_solution_text = ""
            messagebox.showinfo("完成", f"提示後已達成目標！\n步數：{self.move_count}")


def main() -> None:
    root = tk.Tk()
    LightsOutGameND(root)
    root.mainloop()


if __name__ == "__main__":
    main()