import itertools
import math
import random
import tkinter as tk
from tkinter import messagebox

import networkx as nx
import numpy as np


class PolyhedraLightsOutApp:
    BG = "#111318"
    PANEL = "#1a1f29"
    PANEL_2 = "#232b38"
    TEXT = "#e8ecf1"
    MUTED = "#aab4c3"
    EDGE = "#607087"
    EXTRA_EDGE = "#d97cff"
    EXTRA_EDGE_HOVER = "#ff9cff"
    OFF = "#2d3442"
    ON = "#ffd24a"
    HOVER = "#5db0ff"
    SOL_HINT = "#ff7a7a"
    GOOD = "#8de38f"
    WARN = "#ffb86b"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("多面體 Lights Out")
        self.root.geometry("1440x920")
        self.root.minsize(1180, 760)
        self.root.configure(bg=self.BG)

        self.models = self._build_model_catalog()
        self.model_names = list(self.models.keys())
        self.current_model_name = self.model_names[0]

        self.state = []
        self.start_state = []
        self.moves = 0
        self.hover_idx = None
        self.projected = []
        self.solution_marks = []

        self.yaw = 0.78
        self.pitch = -0.48
        self.dragging = False
        self.last_mouse = None
        self.drag_total = 0
        self.zoom = 1.0

        self.base_adj = []
        self.extra_edges = set()
        self.force_mode = False

        self._build_ui()
        self.load_model(self.current_model_name)

    # --------------------------- 幾何 / 圖結構 ---------------------------
    def _signed_perms(self, values):
        out = set()
        for signs in itertools.product([1, -1], repeat=len(values)):
            signed = tuple(signs[i] * values[i] for i in range(len(values)))
            for p in set(itertools.permutations(signed)):
                out.add(tuple(float(x) for x in p))
        return sorted(out)

    def _graph_from_coords(self, coords, tol=1e-7):
        n = len(coords)
        ds = []
        for i in range(n):
            for j in range(i + 1, n):
                dsq = sum((coords[i][k] - coords[j][k]) ** 2 for k in range(3))
                if dsq > 1e-12:
                    ds.append(dsq)
        edge_dsq = min(ds)
        adj = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dsq = sum((coords[i][k] - coords[j][k]) ** 2 for k in range(3))
                if abs(dsq - edge_dsq) < tol:
                    adj[i][j] = 1
                    adj[j][i] = 1
        return adj

    def _normalize_coords(self, coords):
        max_abs = max(max(abs(v) for v in p) for p in coords) or 1.0
        scale = 1.0 / max_abs
        return [tuple(float(v * scale) for v in p) for p in coords]

    def _coords_from_graph_layout(self, g, seed=7):
        pos = nx.spring_layout(g, dim=3, seed=seed)
        coords = [pos[i] for i in range(len(g.nodes()))]
        return self._normalize_coords(coords)

    def _nx_to_adj(self, g):
        nodes = list(g.nodes())
        index = {node: i for i, node in enumerate(nodes)}
        n = len(nodes)
        adj = [[0] * n for _ in range(n)]
        for u, v in g.edges():
            i = index[u]
            j = index[v]
            adj[i][j] = 1
            adj[j][i] = 1
        return adj

    def _remap_graph_to_ints(self, g):
        mapping = {node: i for i, node in enumerate(g.nodes())}
        return nx.relabel_nodes(g, mapping)

    def _coords_to_graph(self, coords):
        adj = self._graph_from_coords(coords)
        return nx.from_numpy_array(np.array(adj, dtype=int))

    def _planar_faces(self, g):
        ok, emb = nx.check_planarity(g)
        if not ok:
            raise ValueError("圖不是平面圖，無法取出面。")

        visited = set()
        faces = []
        for u in emb:
            for v in emb.neighbors_cw_order(u):
                if (u, v) in visited:
                    continue
                face = emb.traverse_face(u, v)
                faces.append(face)
                m = len(face)
                for i in range(m):
                    a = face[i]
                    b = face[(i + 1) % m]
                    visited.add((a, b))
        return faces

    def _dual_graph(self, g):
        ok, emb = nx.check_planarity(g)
        if not ok:
            raise ValueError("圖不是平面圖，無法建立對偶圖。")

        halfedge_face = {}
        visited = set()
        faces = []
        for u in emb:
            for v in emb.neighbors_cw_order(u):
                if (u, v) in visited:
                    continue
                face = emb.traverse_face(u, v)
                face_id = len(faces)
                faces.append(face)
                m = len(face)
                for i in range(m):
                    a = face[i]
                    b = face[(i + 1) % m]
                    visited.add((a, b))
                    halfedge_face[(a, b)] = face_id

        dg = nx.Graph()
        dg.add_nodes_from(range(len(faces)))
        for u, v in g.edges():
            f1 = halfedge_face.get((u, v))
            f2 = halfedge_face.get((v, u))
            if f1 is not None and f2 is not None and f1 != f2:
                dg.add_edge(f1, f2)
        return self._remap_graph_to_ints(dg)

    def _truncation_graph(self, g):
        ok, emb = nx.check_planarity(g)
        if not ok:
            raise ValueError("圖不是平面圖，無法建立截角圖。")

        node_of = {}
        idx = 0
        for u in emb:
            for v in emb.neighbors_cw_order(u):
                node_of[(u, v)] = idx
                idx += 1

        tg = nx.Graph()
        tg.add_nodes_from(range(idx))

        for u, v in g.edges():
            tg.add_edge(node_of[(u, v)], node_of[(v, u)])

        for u in emb:
            ns = list(emb.neighbors_cw_order(u))
            d = len(ns)
            for i in range(d):
                a = node_of[(u, ns[i])]
                b = node_of[(u, ns[(i + 1) % d])]
                tg.add_edge(a, b)

        return self._remap_graph_to_ints(tg)

    def _truncation_graph_with_coords(self, g, coords, t=1.0 / 3.0):
        ok, emb = nx.check_planarity(g)
        if not ok:
            raise ValueError("圖不是平面圖，無法建立截角圖。")

        coords = np.array(coords, dtype=float)
        node_of = {}
        out_coords = []
        idx = 0
        for u in emb:
            for v in emb.neighbors_cw_order(u):
                node_of[(u, v)] = idx
                out_coords.append((1.0 - t) * coords[u] + t * coords[v])
                idx += 1

        tg = nx.Graph()
        tg.add_nodes_from(range(idx))

        for u, v in g.edges():
            tg.add_edge(node_of[(u, v)], node_of[(v, u)])

        for u in emb:
            ns = list(emb.neighbors_cw_order(u))
            d = len(ns)
            for i in range(d):
                a = node_of[(u, ns[i])]
                b = node_of[(u, ns[(i + 1) % d])]
                tg.add_edge(a, b)

        return self._remap_graph_to_ints(tg), self._normalize_coords(out_coords)

    def _rectified_graph_with_coords(self, g, coords):
        lg = nx.line_graph(g)
        edge_nodes = list(lg.nodes())
        coords = np.array(coords, dtype=float)
        out_coords = []
        for u, v in edge_nodes:
            out_coords.append((coords[u] + coords[v]) / 2.0)
        mapping = {node: i for i, node in enumerate(edge_nodes)}
        lg = nx.relabel_nodes(lg, mapping)
        return lg, self._normalize_coords(out_coords)

    def _dual_coords_from_primal(self, g, coords):
        coords = np.array(coords, dtype=float)
        faces = self._planar_faces(g)
        dual_coords = []
        for face in faces:
            pts = coords[face]
            center = np.mean(pts, axis=0)
            if len(pts) < 3:
                dual_coords.append(center)
                continue
            normal = np.cross(pts[1] - pts[0], pts[2] - pts[0])
            norm = np.linalg.norm(normal)
            if norm < 1e-12:
                dual_coords.append(center)
                continue
            normal = normal / norm
            if float(np.dot(normal, center)) < 0.0:
                normal = -normal
            offset = float(np.dot(normal, pts[0]))
            if abs(offset) < 1e-12:
                dual_coords.append(center)
            else:
                dual_coords.append(normal / offset)
        return self._normalize_coords(dual_coords)

    def _make_model_from_graph(self, *, name, family, g, desc, seed=7):
        g = self._remap_graph_to_ints(g)
        return {
            "name": name,
            "family": family,
            "adj": self._nx_to_adj(g),
            "coords": self._coords_from_graph_layout(g, seed=seed),
            "desc": desc,
        }

    def _make_model_from_graph_and_coords(self, *, name, family, g, coords, desc):
        g = self._remap_graph_to_ints(g)
        return {
            "name": name,
            "family": family,
            "adj": self._nx_to_adj(g),
            "coords": self._normalize_coords(coords),
            "desc": desc,
        }

    def _make_model_from_coords(self, *, name, family, coords, desc):
        coords = self._normalize_coords(coords)
        return {
            "name": name,
            "family": family,
            "adj": self._graph_from_coords(coords),
            "coords": coords,
            "desc": desc,
        }

    def _make_dual_model(self, *, name, family, primal_graph, primal_coords, desc):
        dual_graph = self._dual_graph(primal_graph)
        dual_coords = self._dual_coords_from_primal(primal_graph, primal_coords)
        return self._make_model_from_graph_and_coords(
            name=name,
            family=family,
            g=dual_graph,
            coords=dual_coords,
            desc=desc,
        )

    # --------------------------- 基本座標 ---------------------------
    def _tetrahedron_coords(self):
        return [
            (1.0, 1.0, 1.0),
            (-1.0, -1.0, 1.0),
            (-1.0, 1.0, -1.0),
            (1.0, -1.0, -1.0),
        ]

    def _cube_coords(self):
        return [tuple(float(v) for v in p) for p in itertools.product([-1.0, 1.0], repeat=3)]

    def _octahedron_coords(self):
        return [
            (1.0, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, -1.0),
        ]

    def _dodecahedron_coords(self):
        phi = (1.0 + math.sqrt(5.0)) / 2.0
        inv = 1.0 / phi
        coords = list(itertools.product([-1.0, 1.0], repeat=3))
        coords += [(0.0, s1 * inv, s2 * phi) for s1 in [1.0, -1.0] for s2 in [1.0, -1.0]]
        coords += [(s1 * inv, s2 * phi, 0.0) for s1 in [1.0, -1.0] for s2 in [1.0, -1.0]]
        coords += [(s1 * phi, 0.0, s2 * inv) for s1 in [1.0, -1.0] for s2 in [1.0, -1.0]]
        return [tuple(float(v) for v in p) for p in coords]

    def _icosahedron_coords(self):
        phi = (1.0 + math.sqrt(5.0)) / 2.0
        coords = []
        coords += [(0.0, s1, s2 * phi) for s1 in [1.0, -1.0] for s2 in [1.0, -1.0]]
        coords += [(s1, s2 * phi, 0.0) for s1 in [1.0, -1.0] for s2 in [1.0, -1.0]]
        coords += [(s1 * phi, 0.0, s2) for s1 in [1.0, -1.0] for s2 in [1.0, -1.0]]
        return [tuple(float(v) for v in p) for p in coords]

    # --------------------------- 模型建立 ---------------------------
    def _make_cuboctahedron(self):
        primal_coords = self._cube_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        g, coords = self._rectified_graph_with_coords(primal_graph, primal_coords)
        return self._make_model_from_graph_and_coords(
            name="立方八面體（Cuboctahedron）",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="已改為真實幾何座標版；已驗證為完全排列，可直接產生任意亂數盤面。",
        )

    def _make_icosidodecahedron(self):
        primal_coords = self._dodecahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        g, coords = self._rectified_graph_with_coords(primal_graph, primal_coords)
        return self._make_model_from_graph_and_coords(
            name="二十十二面體（Icosidodecahedron）",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="已改為真實幾何座標版；已驗證為完全排列，可直接產生任意亂數盤面。",
        )

    def _make_truncated_tetrahedron(self):
        primal_coords = self._tetrahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        g, coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_model_from_graph_and_coords(
            name="截角四面體",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="已改為真實幾何座標版；不是完全排列；建議只用合法打亂盤面出題。",
        )

    def _make_truncated_cube(self):
        primal_coords = self._cube_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        g, coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_model_from_graph_and_coords(
            name="截角立方體",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="已改為真實幾何座標版；不是完全排列；任意盤面不一定可解。",
        )

    def _make_truncated_octahedron(self):
        coords = self._signed_perms((0.0, 1.0, 2.0))
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="截角八面體",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；不是完全排列；建議使用可解盤面生成。",
        )

    def _make_rhombicuboctahedron(self):
        s2 = math.sqrt(2.0)
        coords = self._signed_perms((1.0, 1.0, 1.0 + s2))
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="小斜方立方八面體（Rhombicuboctahedron）",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；可玩，但不是所有盤面都能到達。",
        )

    def _make_truncated_cuboctahedron(self):
        s2 = math.sqrt(2.0)
        coords = self._signed_perms((1.0, 1.0 + s2, 1.0 + 2.0 * s2))
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="大斜方立方八面體（Truncated Cuboctahedron）",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；頂點很多，旋轉立體感很強；不是完全排列。",
        )

    def _make_truncated_dodecahedron(self):
        primal_coords = self._dodecahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        g, coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_model_from_graph_and_coords(
            name="截角十二面體",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="已改為真實幾何座標版；由正十二面體做均勻截角生成。",
        )

    def _make_truncated_icosahedron(self):
        primal_coords = self._icosahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        g, coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_model_from_graph_and_coords(
            name="截角二十面體（巴克球 / 足球烯）",
            family="阿基米德立體",
            g=g,
            coords=coords,
            desc="已改為真實幾何座標版；巴克球模型。不是完全排列，只能保證合法打亂盤面可解。",
        )

    def _make_tetrahedron(self):
        coords = self._tetrahedron_coords()
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="正四面體",
            family="柏拉圖立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；作為基準模型。",
        )

    def _make_cube(self):
        coords = self._cube_coords()
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="正六面體",
            family="柏拉圖立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；經典立方體骨架。",
        )

    def _make_octahedron(self):
        coords = self._octahedron_coords()
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="正八面體",
            family="柏拉圖立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；對稱性高，適合觀察 Lights Out 的圖結構。",
        )

    def _make_dodecahedron(self):
        coords = self._dodecahedron_coords()
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="正十二面體",
            family="柏拉圖立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；頂點 20，邊 30。",
        )

    def _make_icosahedron(self):
        coords = self._icosahedron_coords()
        g = self._coords_to_graph(coords)
        return self._make_model_from_graph_and_coords(
            name="正二十面體",
            family="柏拉圖立體",
            g=g,
            coords=coords,
            desc="真實幾何座標版；頂點 12，邊 30。",
        )

    def _make_rhombic_dodecahedron(self):
        primal_coords = self._cube_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        rect_graph, rect_coords = self._rectified_graph_with_coords(primal_graph, primal_coords)
        return self._make_dual_model(
            name="菱形十二面體",
            family="卡塔蘭立體",
            primal_graph=rect_graph,
            primal_coords=rect_coords,
            desc="已改為對應真實幾何的對偶座標版；立方八面體的對偶。",
        )

    def _make_triakis_tetrahedron(self):
        primal_coords = self._tetrahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        trunc_graph, trunc_coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_dual_model(
            name="三角錐四面體（Triakis Tetrahedron）",
            family="卡塔蘭立體",
            primal_graph=trunc_graph,
            primal_coords=trunc_coords,
            desc="已改為對應真實幾何的對偶座標版；截角四面體的對偶。",
        )

    def _make_triakis_octahedron(self):
        primal_coords = self._cube_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        trunc_graph, trunc_coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_dual_model(
            name="三角錐八面體（Triakis Octahedron）",
            family="卡塔蘭立體",
            primal_graph=trunc_graph,
            primal_coords=trunc_coords,
            desc="已改為對應真實幾何的對偶座標版；截角立方體的對偶。",
        )

    def _make_tetrakis_hexahedron(self):
        primal_coords = self._signed_perms((0.0, 1.0, 2.0))
        primal_graph = self._coords_to_graph(primal_coords)
        return self._make_dual_model(
            name="四角錐立方體（Tetrakis Hexahedron）",
            family="卡塔蘭立體",
            primal_graph=primal_graph,
            primal_coords=primal_coords,
            desc="已改為對應真實幾何的對偶座標版；截角八面體的對偶。",
        )

    def _make_deltoidal_icositetrahedron(self):
        s2 = math.sqrt(2.0)
        primal_coords = self._signed_perms((1.0, 1.0, 1.0 + s2))
        primal_graph = self._coords_to_graph(primal_coords)
        return self._make_dual_model(
            name="鳶形二十四面體（Deltoidal Icositetrahedron）",
            family="卡塔蘭立體",
            primal_graph=primal_graph,
            primal_coords=primal_coords,
            desc="已改為對應真實幾何的對偶座標版；小斜方立方八面體的對偶。",
        )

    def _make_disdyakis_dodecahedron(self):
        s2 = math.sqrt(2.0)
        primal_coords = self._signed_perms((1.0, 1.0 + s2, 1.0 + 2.0 * s2))
        primal_graph = self._coords_to_graph(primal_coords)
        return self._make_dual_model(
            name="雙錐十二面體（Disdyakis Dodecahedron）",
            family="卡塔蘭立體",
            primal_graph=primal_graph,
            primal_coords=primal_coords,
            desc="已改為對應真實幾何的對偶座標版；大斜方立方八面體的對偶。",
        )

    def _make_rhombic_triacontahedron(self):
        primal_coords = self._dodecahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        rect_graph, rect_coords = self._rectified_graph_with_coords(primal_graph, primal_coords)
        return self._make_dual_model(
            name="菱形三十面體",
            family="卡塔蘭立體",
            primal_graph=rect_graph,
            primal_coords=rect_coords,
            desc="已改為對應真實幾何的對偶座標版；二十十二面體的對偶。",
        )

    def _make_triakis_icosahedron(self):
        primal_coords = self._dodecahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        trunc_graph, trunc_coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_dual_model(
            name="三角錐二十面體（Triakis Icosahedron）",
            family="卡塔蘭立體",
            primal_graph=trunc_graph,
            primal_coords=trunc_coords,
            desc="已改為對應真實幾何的對偶座標版；截角十二面體的對偶。",
        )

    def _make_pentakis_dodecahedron(self):
        primal_coords = self._icosahedron_coords()
        primal_graph = self._coords_to_graph(primal_coords)
        trunc_graph, trunc_coords = self._truncation_graph_with_coords(primal_graph, primal_coords)
        return self._make_dual_model(
            name="五角錐十二面體（Pentakis Dodecahedron）",
            family="卡塔蘭立體",
            primal_graph=trunc_graph,
            primal_coords=trunc_coords,
            desc="已改為對應真實幾何的對偶座標版；巴克球（截角二十面體）的對偶。",
        )

    def _build_toggle_matrix(self, adj):
        n = len(adj)
        m = [[0] * n for _ in range(n)]
        for i in range(n):
            m[i][i] = 1
            for j in range(n):
                if adj[i][j]:
                    m[j][i] = 1
        return m

    def _rank_mod2(self, m):
        a = [row[:] for row in m]
        rows = len(a)
        cols = len(a[0]) if rows else 0
        r = 0
        for c in range(cols):
            pivot = None
            for i in range(r, rows):
                if a[i][c]:
                    pivot = i
                    break
            if pivot is None:
                continue
            a[r], a[pivot] = a[pivot], a[r]
            for i in range(rows):
                if i != r and a[i][c]:
                    for j in range(c, cols):
                        a[i][j] ^= a[r][j]
            r += 1
            if r == rows:
                break
        return r

    def _edge_key(self, i, j):
        return (i, j) if i < j else (j, i)

    def _copy_adj(self, adj):
        return [row[:] for row in adj]

    def _analyze_adj(self, adj):
        toggle_matrix = self._build_toggle_matrix(adj)
        n = len(adj)
        rank = self._rank_mod2(toggle_matrix)
        return {
            "adj": adj,
            "toggle_matrix": toggle_matrix,
            "n": n,
            "rank": rank,
            "full": rank == n,
        }

    def _apply_graph_state(self, adj, extra_edges=None, force_mode=False):
        info = self._analyze_adj(adj)
        self.adj = info["adj"]
        self.n = info["n"]
        self.toggle_matrix = info["toggle_matrix"]
        self.is_full_reachable = info["full"]
        self.extra_edges = set(extra_edges or [])
        self.force_mode = force_mode

    def _find_best_force_edges(self, base_adj):
        adj = self._copy_adj(base_adj)
        n = len(adj)
        current_rank = self._rank_mod2(self._build_toggle_matrix(adj))
        added = []

        while current_rank < n:
            best_edge = None
            best_rank = current_rank

            for i in range(n):
                for j in range(i + 1, n):
                    if adj[i][j]:
                        continue
                    adj[i][j] = 1
                    adj[j][i] = 1
                    rank = self._rank_mod2(self._build_toggle_matrix(adj))
                    adj[i][j] = 0
                    adj[j][i] = 0

                    if rank > best_rank:
                        best_rank = rank
                        best_edge = (i, j)
                        if rank == n:
                            break
                if best_rank == n:
                    break

            if best_edge is None:
                break

            i, j = best_edge
            adj[i][j] = 1
            adj[j][i] = 1
            added.append(best_edge)
            current_rank = best_rank

        return added, current_rank

    def _build_model_catalog(self):
        builders = [
            self._make_cuboctahedron,
            self._make_icosidodecahedron,
            self._make_truncated_tetrahedron,
            self._make_truncated_cube,
            self._make_truncated_octahedron,
            self._make_truncated_dodecahedron,
            self._make_truncated_icosahedron,
            self._make_rhombicuboctahedron,
            self._make_truncated_cuboctahedron,
            self._make_rhombic_dodecahedron,
            self._make_triakis_tetrahedron,
            self._make_triakis_octahedron,
            self._make_tetrakis_hexahedron,
            self._make_deltoidal_icositetrahedron,
            self._make_disdyakis_dodecahedron,
            self._make_rhombic_triacontahedron,
            self._make_triakis_icosahedron,
            self._make_pentakis_dodecahedron,
            self._make_tetrahedron,
            self._make_cube,
            self._make_octahedron,
            self._make_dodecahedron,
            self._make_icosahedron,
        ]
        catalog = {}
        for fn in builders:
            model = fn()
            info = self._analyze_adj(model["adj"])
            model["toggle_matrix"] = info["toggle_matrix"]
            model["n"] = info["n"]
            model["rank"] = info["rank"]
            model["full"] = info["full"]
            catalog[model["name"]] = model
        return catalog

    def load_model(self, name):
        self.current_model_name = name
        self.model = self.models[name]
        self.vertices = self.model["coords"]
        self.base_adj = self._copy_adj(self.model["adj"])
        self._apply_graph_state(self._copy_adj(self.base_adj), extra_edges=set(), force_mode=False)

        self.state = [0] * self.n
        self.start_state = [0] * self.n
        self.moves = 0
        self.hover_idx = None
        self.projected = [(0, 0, 0) for _ in range(self.n)]
        self.solution_marks = []

        self.yaw = 0.78
        self.pitch = -0.48
        self.zoom = 1.0

        self.model_var.set(name)
        self.root.title(f"多面體 Lights Out（中文） - {name}")
        self._refresh_info_labels()
        self.random_btn.config(state="normal")
        self.restore_edges_btn.config(state="disabled")
        self.new_game(scramble_moves=max(8, min(22, self.n // 2)))

    def _rotate_point(self, p):
        x, y, z = p
        cy = math.cos(self.yaw)
        sy = math.sin(self.yaw)
        x, z = x * cy + z * sy, -x * sy + z * cy
        cp = math.cos(self.pitch)
        sp = math.sin(self.pitch)
        y, z = y * cp - z * sp, y * sp + z * cp
        return x, y, z

    def _project_all(self):
        w = max(self.canvas.winfo_width(), 480)
        h = max(self.canvas.winfo_height(), 480)
        cx, cy = w / 2, h / 2
        scale = min(w, h) * 0.22 * self.zoom
        camera = 6.8
        projected = []
        for p in self.vertices:
            x, y, z = self._rotate_point(p)
            f = camera / (camera - z)
            sx = cx + x * scale * f
            sy = cy - y * scale * f
            projected.append((sx, sy, z))
        self.projected = projected

    # --------------------------- GF(2) 求解 ---------------------------
    def solve_state(self, state):
        n = self.n
        target = [1] * n
        b = [state[r] ^ target[r] for r in range(n)]
        mat = [self.toggle_matrix[r][:] + [b[r]] for r in range(n)]
        row = 0
        pivot_cols = []
        for col in range(n):
            pivot = None
            for r in range(row, n):
                if mat[r][col]:
                    pivot = r
                    break
            if pivot is None:
                continue
            mat[row], mat[pivot] = mat[pivot], mat[row]
            pivot_cols.append(col)
            for r in range(n):
                if r != row and mat[r][col]:
                    for c in range(col, n + 1):
                        mat[r][c] ^= mat[row][c]
            row += 1
            if row == n:
                break
        for r in range(n):
            if all(v == 0 for v in mat[r][:n]) and mat[r][n]:
                return None
        x = [0] * n
        for r, c in enumerate(pivot_cols):
            x[c] = mat[r][n]
        return x

    # --------------------------- 補邊功能 ---------------------------
    def enable_force_solvable(self):
        if self.force_mode:
            self.status_var.set("目前已經在強制可解模式。")
            return

        if self.model["full"]:
            self.status_var.set("這個模型原本就是完全排列，不需要補邊。")
            messagebox.showinfo("不用補邊", "這個模型原本就是完全排列。")
            return

        added_edges, final_rank = self._find_best_force_edges(self.base_adj)
        if final_rank < self.n:
            self.status_var.set("嘗試補邊，但仍無法達到完全排列。")
            messagebox.showwarning("補邊失敗", "目前的貪婪補邊策略沒有找到完全排列解。")
            return

        new_adj = self._copy_adj(self.base_adj)
        for i, j in added_edges:
            new_adj[i][j] = 1
            new_adj[j][i] = 1

        self._apply_graph_state(new_adj, extra_edges=set(added_edges), force_mode=True)
        self.solution_marks = []
        self.start_state = self.state[:]
        self.restore_edges_btn.config(state="normal")
        self._refresh_info_labels()
        self.draw()

        self.status_var.set(f"已啟用強制可解：新增 {len(added_edges)} 條補邊，現在是完全排列。")

    def restore_original_graph(self):
        if not self.force_mode:
            self.status_var.set("目前沒有補邊，不需要復原。")
            return

        self._apply_graph_state(self._copy_adj(self.base_adj), extra_edges=set(), force_mode=False)
        self.solution_marks = []
        self.start_state = self.state[:]
        self.restore_edges_btn.config(state="disabled")
        self._refresh_info_labels()
        self.draw()
        self.status_var.set("已復原原始模型連線。")

    # --------------------------- 遊戲邏輯 ---------------------------
    def press(self, idx, count_move=True):
        toggle = [idx] + [j for j in range(self.n) if self.adj[idx][j]]
        for j in toggle:
            self.state[j] ^= 1
        if count_move:
            self.moves += 1
            self.solution_marks = []
        self._update_labels()
        self.draw()
        if self.is_solved():
            self.status_var.set(f"已完成：共 {self.moves} 步。")
            messagebox.showinfo("過關", f"你已經解開 {self.current_model_name}\n總步數：{self.moves}")

    def is_solved(self):
        return all(v == 1 for v in self.state)

    def scramble(self, moves=10):
        self.state = [0] * self.n
        for _ in range(moves):
            self.press(random.randrange(self.n), count_move=False)
        self.start_state = self.state[:]
        self.moves = 0
        self.solution_marks = []
        self._update_labels()
        self.draw()
        self.status_var.set(f"已用 {moves} 次合法操作打亂，保證可解。")

    def new_game(self, scramble_moves=10):
        self.scramble(scramble_moves)

    def reset_game(self):
        self.state = self.start_state[:]
        self.moves = 0
        self.solution_marks = []
        self._update_labels()
        self.draw()
        self.status_var.set("已重設回本局初始盤面。")

    def randomize_any_state(self):
        self.state = [random.randint(0, 1) for _ in range(self.n)]
        self.start_state = self.state[:]
        self.moves = 0
        self.solution_marks = []
        self._update_labels()
        self.draw()

        sol = self.solve_state(self.state)
        if sol is None:
            self.status_var.set("已生成任意亂數盤面（此盤面可能無解，且目前判定為無解）。")
        else:
            self.status_var.set("已生成任意亂數盤面（此盤面可解）。")

    def show_solution(self):
        sol = self.solve_state(self.state)
        if sol is None:
            self.status_var.set("這個盤面無解。")
            messagebox.showwarning("無解", "目前盤面無解。")
            return
        self.solution_marks = [i for i, bit in enumerate(sol) if bit]
        self.draw()
        self.status_var.set(f"已標出解答，共 {len(self.solution_marks)} 個要按的頂點。")

    def apply_solution(self):
        sol = self.solve_state(self.state)
        if sol is None:
            self.status_var.set("這個盤面無解。")
            return
        self.solution_marks = []
        for i, bit in enumerate(sol):
            if bit:
                self.press(i, count_move=True)
        self.status_var.set("已直接套用求解結果。")

    # --------------------------- UI ---------------------------
    def _build_ui(self):
        top = tk.Frame(self.root, bg=self.BG)
        top.pack(fill="both", expand=True, padx=16, pady=16)

        left = tk.Frame(top, bg=self.PANEL)
        left.pack(side="left", fill="y", padx=(0, 16))

        right = tk.Frame(top, bg=self.PANEL)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(
            left,
            text="多面體 Lights Out（中文）",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Microsoft JhengHei UI", 18, "bold"),
            pady=12,
        ).pack(fill="x")

        picker = tk.Frame(left, bg=self.PANEL)
        picker.pack(fill="x", padx=12, pady=(4, 8))

        tk.Label(
            picker,
            text="切換模型：",
            bg=self.PANEL,
            fg=self.TEXT,
            font=("Microsoft JhengHei UI", 11, "bold"),
        ).pack(anchor="w")

        self.model_var = tk.StringVar(value="")
        opt = tk.OptionMenu(picker, self.model_var, *self.model_names, command=self.on_model_change)
        opt.config(
            bg=self.PANEL_2,
            fg=self.TEXT,
            activebackground="#304057",
            activeforeground=self.TEXT,
            relief="flat",
            font=("Microsoft JhengHei UI", 10, "bold"),
            highlightthickness=0,
            width=28,
        )
        opt["menu"].config(bg=self.PANEL_2, fg=self.TEXT, font=("Microsoft JhengHei UI", 10))
        opt.pack(fill="x", pady=(6, 0))

        self.rule_label = tk.Label(
            left,
            text="",
            justify="left",
            anchor="nw",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Microsoft JhengHei UI", 10),
            padx=14,
            pady=8,
            wraplength=360,
        )
        self.rule_label.pack(fill="x")

        btns = tk.Frame(left, bg=self.PANEL)
        btns.pack(fill="x", padx=12, pady=8)

        def add_btn(text, cmd):
            b = tk.Button(
                btns,
                text=text,
                command=cmd,
                bg=self.PANEL_2,
                fg=self.TEXT,
                activebackground="#304057",
                activeforeground=self.TEXT,
                relief="flat",
                font=("Microsoft JhengHei UI", 10, "bold"),
                padx=10,
                pady=8,
                cursor="hand2",
            )
            b.pack(fill="x", pady=4)
            return b

        add_btn("新遊戲（普通）", lambda: self.new_game(max(8, min(22, self.n // 2))))
        add_btn("新遊戲（更亂）", lambda: self.new_game(max(12, min(30, self.n))))
        self.random_btn = add_btn("任意亂數盤面", self.randomize_any_state)
        add_btn("重設", self.reset_game)
        add_btn("顯示解答", self.show_solution)
        add_btn("直接求解", self.apply_solution)
        add_btn("強制可解（自動補邊）", self.enable_force_solvable)
        self.restore_edges_btn = add_btn("復原原始連線", self.restore_original_graph)

        info = tk.Frame(left, bg=self.PANEL)
        info.pack(fill="x", padx=14, pady=10)

        self.moves_var = tk.StringVar(value="步數：0")
        self.on_var = tk.StringVar(value="亮燈數：0 / 0")
        self.rank_var = tk.StringVar(value="GF(2) rank：0 / 0")
        self.reach_var = tk.StringVar(value="可達性：")
        self.extra_var = tk.StringVar(value="補邊：0")
        self.status_var = tk.StringVar(value="準備完成。")

        for var, font in [
            (self.moves_var, ("Microsoft JhengHei UI", 11, "bold")),
            (self.on_var, ("Microsoft JhengHei UI", 11)),
            (self.rank_var, ("Consolas", 10)),
            (self.reach_var, ("Microsoft JhengHei UI", 10, "bold")),
            (self.extra_var, ("Microsoft JhengHei UI", 10)),
        ]:
            tk.Label(info, textvariable=var, bg=self.PANEL, fg=self.TEXT, anchor="w", font=font).pack(fill="x", pady=2)

        tk.Label(
            left,
            text=(
                "操作說明\n"
                "• 點一個頂點：翻轉自己與所有相鄰頂點\n"
                "• 滑鼠左鍵拖曳：旋轉立體\n"
                "• 滑鼠滾輪：縮放\n"
                "• 黃色 = 亮燈，深色 = 熄燈\n"
                "• 藍色 = 滑鼠懸停 / 受影響區\n"
                "• 紅圈 = 求解器標記的頂點\n"
                "• 紫色邊 = 強制可解模式新增的補邊\n"
                "• 可用「復原原始連線」回到原始模型"
            ),
            justify="left",
            anchor="nw",
            bg=self.PANEL,
            fg=self.MUTED,
            font=("Microsoft JhengHei UI", 10),
            padx=14,
            pady=8,
        ).pack(fill="x")

        tk.Label(
            left,
            textvariable=self.status_var,
            justify="left",
            anchor="nw",
            bg=self.PANEL,
            fg=self.GOOD,
            font=("Microsoft JhengHei UI", 10, "bold"),
            padx=14,
            pady=10,
            wraplength=360,
        ).pack(fill="x")

        self.canvas = tk.Canvas(right, bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_by(1.08))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_by(1 / 1.08))

    def on_model_change(self, value):
        if value != self.current_model_name:
            self.load_model(value)

    def _refresh_info_labels(self):
        mode_text = "（已啟用強制可解補邊）" if self.force_mode else ""
        self.rule_label.config(
            text=(
                f"目前模型：{self.current_model_name}{mode_text}\n"
                f"類別：{self.model['family']}\n"
                f"頂點數：{self.n}\n"
                f"說明：{self.model['desc']}"
            )
        )
        self.rank_var.set(f"GF(2) rank(I+A)：{self._rank_mod2(self.toggle_matrix)} / {self.n}")
        if self.is_full_reachable:
            self.reach_var.set("可達性：完全排列（任何盤面都可達）")
        else:
            self.reach_var.set("可達性：非完全排列（任意盤面不一定可達）")
        if self.force_mode:
            self.extra_var.set(f"補邊：{len(self.extra_edges)}（目前啟用）")
        else:
            self.extra_var.set("補邊：0")
        self._update_labels()

    def _update_labels(self):
        self.moves_var.set(f"步數：{self.moves}")
        self.on_var.set(f"亮燈數：{sum(self.state)} / {self.n}")

    # --------------------------- 互動 ---------------------------
    def on_mouse_down(self, event):
        self.dragging = True
        self.last_mouse = (event.x, event.y)
        self.drag_total = 0

    def on_mouse_drag(self, event):
        if not self.dragging:
            return
        if self.last_mouse is None:
            self.last_mouse = (event.x, event.y)
            return
        dx = event.x - self.last_mouse[0]
        dy = event.y - self.last_mouse[1]
        self.last_mouse = (event.x, event.y)
        self.drag_total += abs(dx) + abs(dy)
        self.yaw += dx * 0.012
        self.pitch += dy * 0.012
        self.pitch = max(-1.45, min(1.45, self.pitch))
        self.draw()

    def on_mouse_up(self, event):
        if not self.dragging:
            return
        moved = self.drag_total
        self.dragging = False
        self.last_mouse = None
        self.drag_total = 0
        idx = self.pick_vertex(event.x, event.y)
        if idx is not None and moved < 6:
            self.press(idx, count_move=True)
        else:
            self.draw()

    def on_mouse_move(self, event):
        idx = self.pick_vertex(event.x, event.y)
        if idx != self.hover_idx:
            self.hover_idx = idx
            self.draw()

    def on_wheel(self, event):
        if event.delta > 0:
            self.zoom_by(1.08)
        elif event.delta < 0:
            self.zoom_by(1 / 1.08)

    def zoom_by(self, factor):
        self.zoom *= factor
        self.zoom = max(0.34, min(3.2, self.zoom))
        self.draw()

    def pick_vertex(self, x, y):
        self._project_all()
        best = None
        best_d = 10**18
        for i, (sx, sy, z) in enumerate(self.projected):
            d = (sx - x) ** 2 + (sy - y) ** 2
            if d < best_d:
                best_d = d
                best = i
        radius = 18 if self.n <= 36 else 14 if self.n <= 80 else 11
        if best is not None and best_d <= radius ** 2:
            return best
        return None

    # --------------------------- 繪圖 ---------------------------
    def draw(self):
        self.canvas.delete("all")
        self._project_all()

        items = []
        for i in range(self.n):
            for j in range(i + 1, self.n):
                if self.adj[i][j]:
                    x1, y1, z1 = self.projected[i]
                    x2, y2, z2 = self.projected[j]
                    items.append(("edge", (z1 + z2) / 2, i, j))
        for i, (sx, sy, z) in enumerate(self.projected):
            items.append(("node", z, i, None))
        items.sort(key=lambda t: t[1])

        hover_neighbors = set()
        if self.hover_idx is not None:
            hover_neighbors = {self.hover_idx} | {j for j in range(self.n) if self.adj[self.hover_idx][j]}

        for kind, _, i, j in items:
            if kind == "edge":
                x1, y1, _ = self.projected[i]
                x2, y2, _ = self.projected[j]
                ek = self._edge_key(i, j)
                is_extra = ek in self.extra_edges
                color = self.EXTRA_EDGE if is_extra else self.EDGE
                width = 3 if is_extra else 2
                if i in hover_neighbors and j in hover_neighbors:
                    color = self.EXTRA_EDGE_HOVER if is_extra else self.HOVER
                    width = 5 if is_extra else 4
                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)
            else:
                x, y, z = self.projected[i]
                base = 12 if self.n <= 36 else 10 if self.n <= 80 else 8
                r = base + 3 * ((z + 1.8) / 3.6)
                fill = self.ON if self.state[i] else self.OFF
                outline = "#dce4ef"
                ow = 2
                if i == self.hover_idx:
                    outline = self.HOVER
                    ow = 4
                    r += 1.5
                elif i in hover_neighbors:
                    outline = self.HOVER
                    ow = 3
                self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=fill, outline=outline, width=ow)
                if i in self.solution_marks:
                    rr = r + 5
                    self.canvas.create_oval(x - rr, y - rr, x + rr, y + rr, outline=self.SOL_HINT, width=3)
                show_num = self.n <= 80
                if show_num:
                    self.canvas.create_text(
                        x,
                        y,
                        text=str(i),
                        fill="#0b0d11" if self.state[i] else self.TEXT,
                        font=("Segoe UI", 7 if self.n > 36 else 8, "bold"),
                    )

        mode_text = "強制可解模式 ON" if self.force_mode else "原始模型"
        self.canvas.create_text(
            18,
            18,
            anchor="nw",
            fill=self.TEXT,
            font=("Microsoft JhengHei UI", 11, "bold"),
            text=f"拖曳旋轉 • 滾輪縮放 • 點頂點翻轉自己與鄰點 • {mode_text}",
        )
        self.canvas.create_text(
            18,
            42,
            anchor="nw",
            fill=self.MUTED,
            font=("Microsoft JhengHei UI", 10),
            text=f"目前模型：{self.current_model_name}    類別：{self.model['family']}    亮燈：{sum(self.state)}/{self.n}    補邊：{len(self.extra_edges)}",
        )
        if self.hover_idx is not None:
            nbrs = [j for j in range(self.n) if self.adj[self.hover_idx][j]]
            self.canvas.create_text(
                18,
                66,
                anchor="nw",
                fill=self.MUTED,
                font=("Consolas", 10),
                text=f"懸停頂點 {self.hover_idx}：會翻轉 {sorted([self.hover_idx] + nbrs)}",
            )


def main():
    root = tk.Tk()
    app = PolyhedraLightsOutApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
