# src/routePlanning/routePlanner.py
# Headless route planning module extracted from draw_map.py.
# No matplotlib dependency — computes routes, positions, and instructions.

import math
import os
from collections import defaultdict
from itertools import product

import networkx as nx

from src.utils.config import cfg


# -------------------- MAP DATA --------------------
# These mirror draw_map.py definitions so the Brain can use the same constants.

INTERSECTIONS = [
    [82, 83, 84],
    [46, 47, 48],
    [55, 56, 57],
    [73, 74, 75],
    [9, 10, 11, 12],
    [37, 38, 39],
    [64, 65, 66],
    [19, 20, 21],
    [28, 29, 30],
]

ROUNDABOUT_NODES = [302, 303, 304, 305, 306, 307, 267, 268, 269, 270, 271]

STOP_LINES = [
    77, 45, 79, 81, 68, 2, 72, 59, 63, 61, 70, 14, 15, 16, 18, 25, 23, 27,
    43, 4, 6, 34, 32, 36, 52, 50, 374, 342, 468, 301, 230, 296, 276, 96, 92,
    199, 264, 54, 41,
]

SIGNS = {
    "traffic_light": [77, 2, 4, 6],
    "stop": [45, 54, 25, 61, 59, 72, 34, 27, 467, 23],
    "priority": [41, 23, 63, 36, 81],
    "highway_entry": [49, 343],
    "highway_exit": [374, 339, 427],
    "roundabout": [342, 301, 230],
    "crosswalk": [296, 276, 96, 92, 199, 264],
    "no_entry": [15, 16, 468],
    "one_way": [8, 7, 426],
    "parking": [161, 182, 164, 177],
}

FORWARD_DEG = cfg.ROUTE_FORWARD_DEG
LANE_WEIGHT_SCALE = cfg.ROUTE_LANE_WEIGHT_SCALE

# MAP dimensions in real-world units (used for coordinate normalisation)
MAP_WIDTH_UNITS = 20.67
MAP_HEIGHT_UNITS = 13.76


# -------------------- GEOMETRY --------------------
def _extract_positions_xy(G):
    pos = {}
    for n, d in G.nodes(data=True):
        if "x" not in d or "y" not in d:
            raise ValueError("GraphML nodes must have 'x' and 'y' attributes.")
        pos[n] = (float(d["x"]), float(d["y"]))
    return pos


def _mirror_over_ox(pos):
    return {n: (x, -y) for n, (x, y) in pos.items()}


def _spread_overlapping_positions(pos, tol=1e-6, spread=None):
    """Slightly shift overlapping nodes so both are visible (same as draw_map.py)."""
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    x_range = (max(xs) - min(xs)) if xs else 1.0
    y_range = (max(ys) - min(ys)) if ys else 1.0
    if spread is None:
        spread = 0.01 * min(x_range, y_range)

    groups = defaultdict(list)
    for n, (x, y) in pos.items():
        key = (round(x / tol) * tol, round(y / tol) * tol)
        groups[key].append(n)

    new_pos = dict(pos)
    for _, nodes in groups.items():
        if len(nodes) <= 1:
            continue
        x0, y0 = pos[nodes[0]]
        k = len(nodes)
        for i, n in enumerate(nodes):
            ang = 2 * math.pi * i / k
            new_pos[n] = (x0 + spread * math.cos(ang), y0 + spread * math.sin(ang))
    return new_pos


def _signed_turn_angle_deg(prev_xy, cur_xy, next_xy):
    ax, ay = cur_xy[0] - prev_xy[0], cur_xy[1] - prev_xy[1]
    bx, by = next_xy[0] - cur_xy[0], next_xy[1] - cur_xy[1]
    la = math.hypot(ax, ay)
    lb = math.hypot(bx, by)
    if la < 1e-12 or lb < 1e-12:
        return 0.0
    ax, ay = ax / la, ay / la
    bx, by = bx / lb, by / lb
    dot = max(-1.0, min(1.0, ax * bx + ay * by))
    cross = ax * by - ay * bx
    return math.degrees(math.atan2(cross, dot))


def _classify_maneuver(angle_deg):
    if abs(angle_deg) <= FORWARD_DEG:
        return "move forward"
    return "turn left" if angle_deg > 0 else "turn right"


# -------------------- LANE HEURISTIC --------------------
def _median(vals):
    vals = sorted(vals)
    n = len(vals)
    if n == 0:
        return 1.0
    if n % 2 == 1:
        return vals[n // 2]
    return 0.5 * (vals[n // 2 - 1] + vals[n // 2])


def _compute_lane_penalties(G, pos, angle_bin_deg=12):
    penalties = defaultdict(float)
    bin_rad = math.radians(angle_bin_deg)

    for u in G.nodes():
        outs = list(G.successors(u)) if G.is_directed() else list(G.neighbors(u))
        if len(outs) <= 1:
            continue

        ux, uy = pos[u]
        items = []
        for v in outs:
            vx, vy = pos[v]
            dx, dy = vx - ux, vy - uy
            L = math.hypot(dx, dy)
            if L < 1e-12:
                continue
            heading = math.atan2(dy, dx)
            mx, my = (ux + vx) * 0.5, (uy + vy) * 0.5
            items.append((v, heading, (mx, my), (dx / L, dy / L)))

        clusters = defaultdict(list)
        for v, heading, mid, dunit in items:
            key = int(round(heading / bin_rad))
            clusters[key].append((v, heading, mid, dunit))

        for cluster in clusters.values():
            if len(cluster) <= 1:
                continue
            mean_dx = sum(d[0] for *_, d in cluster) / len(cluster)
            mean_dy = sum(d[1] for *_, d in cluster) / len(cluster)
            mean_L = math.hypot(mean_dx, mean_dy)
            if mean_L < 1e-12:
                continue
            mean_dx /= mean_L
            mean_dy /= mean_L
            rx, ry = mean_dy, -mean_dx
            mids = [mid for *_, mid, __ in cluster]
            mx0 = sum(m[0] for m in mids) / len(mids)
            my0 = sum(m[1] for m in mids) / len(mids)
            lateral = []
            for v, _, (mx, my), __ in cluster:
                s = (mx - mx0) * rx + (my - my0) * ry
                lateral.append((v, s))
            s_vals = [s for _, s in lateral]
            s_max, s_min = max(s_vals), min(s_vals)
            denom = (s_max - s_min) if (s_max - s_min) > 1e-12 else 1.0
            for v, s in lateral:
                penalties[(u, v)] = (s_max - s) / denom

    return penalties


def _build_weight_and_heuristic(pos_for_cost, lane_penalties, lane_weight):
    def heuristic(a, b):
        ax, ay = pos_for_cost[a]
        bx, by = pos_for_cost[b]
        return math.hypot(ax - bx, ay - by)

    def weight(u, v, attrs):
        ux, uy = pos_for_cost[u]
        vx, vy = pos_for_cost[v]
        base = math.hypot(vx - ux, vy - uy)
        pen = lane_penalties.get((u, v), 0.0)
        return base + lane_weight * pen

    return weight, heuristic


# -------------------- ROUTING --------------------
def _astar_path_or_none(G, src, dst, heuristic, weight):
    try:
        return nx.astar_path(G, src, dst, heuristic=heuristic, weight=weight)
    except nx.NetworkXNoPath:
        return None


def _path_cost(path, weight_fn):
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        total += weight_fn(u, v, {})
    return total


def _solve_ordered_route(G, order, heuristic, weight):
    full = []
    for i in range(len(order) - 1):
        seg = _astar_path_or_none(G, order[i], order[i + 1], heuristic, weight)
        if seg is None:
            raise RuntimeError(f"No path for leg {order[i]} -> {order[i + 1]}.")
        if full:
            seg = seg[1:]
        full.extend(seg)
    return full


def _solve_shortest_any_order(G, start, checkpoints, finish, heuristic, weight):
    C = list(checkpoints)
    m = len(C)
    nodes = [start] + C + [finish]
    INF = 1e18

    pair_path = {}
    pair_cost = {}
    for u, v in product(nodes, nodes):
        if u == v:
            continue
        p = _astar_path_or_none(G, u, v, heuristic, weight)
        pair_path[(u, v)] = p
        pair_cost[(u, v)] = _path_cost(p, weight) if p is not None else INF

    DP = [[INF] * m for _ in range(1 << m)]
    PAR = [[None] * m for _ in range(1 << m)]

    for i in range(m):
        c = pair_cost[(start, C[i])]
        if c < INF:
            DP[1 << i][i] = c
            PAR[1 << i][i] = (None, None)

    for mask in range(1 << m):
        for i in range(m):
            if not (mask & (1 << i)):
                continue
            cur = DP[mask][i]
            if cur >= INF:
                continue
            for j in range(m):
                if mask & (1 << j):
                    continue
                step = pair_cost[(C[i], C[j])]
                if step >= INF:
                    continue
                nmask = mask | (1 << j)
                cand = cur + step
                if cand < DP[nmask][j]:
                    DP[nmask][j] = cand
                    PAR[nmask][j] = (mask, i)

    full_mask = (1 << m) - 1
    best_cost = INF
    best_end = None
    for i in range(m):
        tail = pair_cost[(C[i], finish)]
        if DP[full_mask][i] < INF and tail < INF:
            cand = DP[full_mask][i] + tail
            if cand < best_cost:
                best_cost = cand
                best_end = i

    if best_end is None:
        raise RuntimeError("No feasible route visiting all checkpoints.")

    order = []
    mask_v = full_mask
    i = best_end
    while i is not None:
        order.append(C[i])
        pmask, pi = PAR[mask_v][i]
        mask_v, i = pmask, pi
    order.reverse()

    visit_order = [start] + order + [finish]

    full_path = []
    for a, b in zip(visit_order[:-1], visit_order[1:]):
        seg = pair_path[(a, b)]
        if seg is None:
            raise RuntimeError(f"Unexpected unreachable segment: {a} -> {b}")
        if full_path:
            seg = seg[1:]
        full_path.extend(seg)

    return full_path, visit_order


# -------------------- INSTRUCTIONS --------------------
def _find_prev_stop_line(route, stop_set, entry_idx, max_back=30):
    for j in range(entry_idx - 1, max(entry_idx - max_back, -1), -1):
        if route[j] in stop_set:
            return j, route[j]
    return None, None


def _build_route_instructions(G, route, pos_cost, intersections, roundabout_set, stop_set):
    intersection_sets = [set(map(str, grp)) for grp in intersections]

    # Reverse lookup: node_str -> list of sign types
    sign_at_node = {}
    for sign_type, node_ids in SIGNS.items():
        for nid in node_ids:
            nid_str = str(nid)
            sign_at_node.setdefault(nid_str, []).append(sign_type)

    # Crosswalk node set for pedestrian crossing detection
    crosswalk_set = set(str(n) for n in SIGNS.get("crosswalk", []))

    events = []
    i = 1
    n = len(route)

    while i < n - 1:
        cur = route[i]
        prev = route[i - 1]

        # Roundabout entry
        if cur in roundabout_set and prev not in roundabout_set:
            entry_idx = i
            entry_node = cur
            exit_count = 0
            seen_exit_nodes = set()
            j = i
            while j < n - 1 and route[j] in roundabout_set:
                node_j = route[j]
                if j != entry_idx:
                    has_exit = any(succ not in roundabout_set for succ in G.successors(node_j))
                    if has_exit and node_j not in seen_exit_nodes:
                        seen_exit_nodes.add(node_j)
                        exit_count += 1
                if route[j + 1] not in roundabout_set:
                    exit_idx = j
                    exit_node = route[j]
                    out_node = route[j + 1]
                    break
                j += 1
            else:
                break

            _, stop_node = _find_prev_stop_line(route, stop_set, entry_idx, max_back=30)
            exit_no = max(1, exit_count)
            signs_here = sign_at_node.get(str(stop_node), []) if stop_node else []
            events.append({
                "type": "roundabout",
                "stop_line": stop_node,
                "signs_at_stop": signs_here,
                "entry_node": entry_node,
                "exit_node": exit_node,
                "exit_number": exit_no,
                "out_node": out_node,
                "entry_idx": entry_idx,
                "exit_idx": exit_idx,
            })
            i = exit_idx + 1
            continue

        # Intersection entry
        grp_idx = None
        grp_set = None
        for k, s in enumerate(intersection_sets):
            if cur in s and prev not in s:
                grp_idx = k
                grp_set = s
                break

        if grp_idx is not None:
            entry_idx = i
            j = i
            while j < n - 1 and route[j] in grp_set:
                if route[j + 1] not in grp_set:
                    exit_idx = j
                    break
                j += 1
            else:
                break

            exit_node = route[exit_idx]
            out_node = route[exit_idx + 1]
            prev_node = route[exit_idx - 1] if exit_idx - 1 >= 0 else exit_node

            ang = _signed_turn_angle_deg(pos_cost[prev_node], pos_cost[exit_node], pos_cost[out_node])
            action = _classify_maneuver(ang)

            _, stop_node = _find_prev_stop_line(route, stop_set, entry_idx, max_back=30)
            signs_here = sign_at_node.get(str(stop_node), []) if stop_node else []
            events.append({
                "type": "intersection",
                "intersection_nodes": intersections[grp_idx],
                "stop_line": stop_node,
                "signs_at_stop": signs_here,
                "action": action,
                "exit_node": exit_node,
                "out_node": out_node,
                "entry_idx": entry_idx,
                "exit_idx": exit_idx,
            })
            i = exit_idx + 1
            continue

        # Crosswalk / pedestrian crossing (stop line + crosswalk sign at same node)
        if cur in stop_set and cur in crosswalk_set:
            signs_here = sign_at_node.get(cur, [])
            events.append({
                "type": "crosswalk",
                "stop_line": cur,
                "signs_at_stop": signs_here,
                "entry_idx": i,
                "exit_idx": i,
            })
            i += 1
            continue

        i += 1

    return events


# -------------------- PUBLIC API --------------------

class RoutePlanner:
    """
    Headless route planner for the BFMC competition map.
    Loads the GraphML once, then computes routes on demand.
    """

    def __init__(self, graphml_path: str = None):
        if graphml_path is None:
            graphml_path = cfg.GRAPHML_PATH

        self.graphml_path = graphml_path
        self._G = None
        self._pos_cost = None
        self._lane_penalties = None
        self._lane_weight = None
        self._weight_fn = None
        self._heur_fn = None

        # Build sign-to-node lookup for position tracking
        self._sign_node_map = {}
        for sign_type, node_ids in SIGNS.items():
            for nid in node_ids:
                self._sign_node_map.setdefault(sign_type, []).append(str(nid))

        self._stop_line_set = set(map(str, STOP_LINES))
        self._roundabout_set = set(map(str, ROUNDABOUT_NODES))

        self._load()

    def _load(self):
        G0 = nx.read_graphml(self.graphml_path)
        self._G = G0 if G0.is_directed() else G0.to_directed()
        self._pos_cost = _mirror_over_ox(_extract_positions_xy(self._G))

        self._lane_penalties = _compute_lane_penalties(self._G, self._pos_cost, angle_bin_deg=12)

        edge_lengths = []
        for u, v in self._G.edges():
            ux, uy = self._pos_cost[u]
            vx, vy = self._pos_cost[v]
            edge_lengths.append(math.hypot(vx - ux, vy - uy))
        self._lane_weight = LANE_WEIGHT_SCALE * _median(edge_lengths)

        self._weight_fn, self._heur_fn = _build_weight_and_heuristic(
            self._pos_cost, self._lane_penalties, self._lane_weight
        )

    def compute_route(
        self,
        start_id: int = None,
        finish_id: int = None,
        must_pass: list = None,
        visit_in_order: bool = None,
    ) -> dict:
        """
        Compute a route and return serialisable data.
        route_coords uses the same raw (mirrored/spread) coordinate system
        as get_graph_data() so the route overlays align on the Canvas.
        """
        if start_id is None:
            start_id = cfg.ROUTE_START
        if finish_id is None:
            finish_id = cfg.ROUTE_FINISH
        if must_pass is None:
            must_pass = cfg.ROUTE_CHECKPOINTS
        if visit_in_order is None:
            visit_in_order = cfg.ROUTE_VISIT_IN_ORDER

        start = str(start_id)
        finish = str(finish_id)
        checkpoints = [str(x) for x in must_pass]

        if visit_in_order:
            order = [start] + checkpoints + [finish]
            route = _solve_ordered_route(self._G, order, self._heur_fn, self._weight_fn)
            visit_order = order
        else:
            route, visit_order = _solve_shortest_any_order(
                self._G, start, checkpoints, finish, self._heur_fn, self._weight_fn
            )

        # Use spread positions for visual consistency with graph rendering
        pos_plot = _spread_overlapping_positions(self._pos_cost, tol=1e-6, spread=None)

        # Raw coordinates matching the graph canvas coordinate system
        route_coords = []
        for node_id in route:
            x, y = pos_plot[node_id]
            route_coords.append([round(x, 6), round(y, 6)])

        # Instructions for intersections / roundabouts
        events = _build_route_instructions(
            self._G, route, self._pos_cost,
            INTERSECTIONS, self._roundabout_set, self._stop_line_set,
        )

        instructions = []
        for ev in events:
            instructions.append({
                "type": ev["type"],
                "stop_line": ev.get("stop_line"),
                "signs_at_stop": ev.get("signs_at_stop", []),
                "action": ev.get("action", f"exit {ev.get('exit_number', '?')}"),
                "entry_idx": ev.get("entry_idx"),
                "exit_idx": ev.get("exit_idx"),
            })

        # Build list of stop lines present on the route
        route_set_indices = {}
        for idx, node in enumerate(route):
            if node not in route_set_indices:
                route_set_indices[node] = idx

        stop_lines_on_route = []
        for node in route:
            if node in self._stop_line_set and node in pos_plot:
                x, y = pos_plot[node]
                stop_lines_on_route.append({
                    "node": node,
                    "x": round(x, 6),
                    "y": round(y, 6),
                    "route_idx": route_set_indices.get(node, -1),
                })

        # Deduplicate stop lines (keep first occurrence)
        seen_sl = set()
        unique_sl = []
        for sl in stop_lines_on_route:
            if sl["node"] not in seen_sl:
                seen_sl.add(sl["node"])
                unique_sl.append(sl)
        stop_lines_on_route = unique_sl

        # Build list of signs near or on the route
        # For signs NOT directly on the route, compute the nearest route node
        # so they can still be used for position tracking.
        signs_on_route = []
        for sign_type, node_ids in SIGNS.items():
            for nid in node_ids:
                nid_str = str(nid)
                if nid_str in pos_plot:
                    sx, sy = pos_plot[nid_str]
                    direct_idx = route_set_indices.get(nid_str, -1)

                    # If the sign node is not on the route, find nearest route node
                    nearest_idx = direct_idx
                    nearest_x, nearest_y = round(sx, 6), round(sy, 6)
                    if direct_idx < 0 and route_coords:
                        best_dist = float("inf")
                        for ri, (rx, ry) in enumerate(route_coords):
                            d = math.hypot(rx - sx, ry - sy)
                            if d < best_dist:
                                best_dist = d
                                nearest_idx = ri
                                nearest_x = rx
                                nearest_y = ry

                    # Also note whether this sign node is a stop line
                    is_stop_line = nid_str in self._stop_line_set

                    signs_on_route.append({
                        "type": sign_type,
                        "node": nid_str,
                        "x": round(sx, 6),
                        "y": round(sy, 6),
                        "route_idx": direct_idx,
                        "nearest_route_idx": nearest_idx,
                        "nearest_route_x": nearest_x,
                        "nearest_route_y": nearest_y,
                        "is_stop_line": is_stop_line,
                    })

        # Print human-readable route summary to terminal
        self._print_route_summary(route, events)

        return {
            "route_nodes": route,
            "route_coords": route_coords,
            "visit_order": [int(v) for v in visit_order],
            "instructions": instructions,
            "stop_lines_on_route": stop_lines_on_route,
            "signs_on_route": signs_on_route,
        }

    def _print_route_summary(self, route: list, events: list):
        """
        Print a formatted route summary to the terminal showing the
        direction the car should take at each intersection and roundabout,
        including the traffic signs expected at each stop line.
        """
        CYAN = "\033[1;96m"
        GREEN = "\033[1;92m"
        YELLOW = "\033[1;93m"
        MAGENTA = "\033[1;95m"
        RED = "\033[1;91m"
        BOLD = "\033[1;97m"
        RESET = "\033[0m"

        def _format_signs(ev):
            """Return a coloured string describing signs at the stop line."""
            signs = ev.get("signs_at_stop", [])
            if not signs:
                return ""
            labels = [s.replace("_", " ").upper() for s in signs]
            return f" Signs: {RED}{', '.join(labels)}{RESET}."

        start_node = route[0] if route else "?"
        end_node = route[-1] if route else "?"

        print(f"\n{CYAN}{'=' * 70}")
        print(f"  ROUTE PLAN  ({len(route)} nodes, {len(events)} decision points)")
        print(f"{'=' * 70}{RESET}")
        print(f"{BOLD}Start at node {start_node}.{RESET}")

        for idx, ev in enumerate(events, start=1):
            nn = f"{idx:02d}"
            stop = ev.get("stop_line", "?")
            sign_str = _format_signs(ev)

            if ev["type"] == "intersection":
                nodes = ev["intersection_nodes"]
                action = ev["action"]
                exit_node = ev["exit_node"]
                out_node = ev["out_node"]
                print(
                    f"{GREEN}{nn}. {RESET}"
                    f"Stop line at node {YELLOW}{stop}{RESET}.{sign_str} "
                    f"At intersection {nodes}, "
                    f"{MAGENTA}{action}{RESET} "
                    f"(through node {exit_node} towards node {out_node})."
                )
            elif ev["type"] == "roundabout":
                entry_node = ev["entry_node"]
                exit_node = ev["exit_node"]
                exit_no = ev["exit_number"]
                out_node = ev["out_node"]
                print(
                    f"{GREEN}{nn}. {RESET}"
                    f"Stop line at node {YELLOW}{stop}{RESET}.{sign_str} "
                    f"Enter the roundabout at node {entry_node}, "
                    f"then exit at the {MAGENTA}{exit_no}-th exit{RESET} "
                    f"(via node {exit_node} towards node {out_node})."
                )
            elif ev["type"] == "crosswalk":
                print(
                    f"{GREEN}{nn}. {RESET}"
                    f"Stop line at node {YELLOW}{stop}{RESET}.{sign_str} "
                    f"{MAGENTA}Pedestrian crossing{RESET}."
                )

        print(f"{BOLD}Arrive at node {end_node}.{RESET}")
        print(f"{CYAN}{'=' * 70}{RESET}\n")

    def get_all_node_positions(self) -> dict:
        """Return all node positions normalised to 0-100 for the map overlay."""
        result = {}
        for nid, (x, y) in self._pos_cost.items():
            result[nid] = {
                "x": round(x * 100.0 / MAP_WIDTH_UNITS, 4),
                "y": round(100.0 - y * 100.0 / MAP_HEIGHT_UNITS, 4),
            }
        return result

    def get_stop_line_nodes(self) -> list:
        """Return the set of stop line node IDs as strings."""
        return list(self._stop_line_set)

    def get_sign_positions(self) -> dict:
        """Return all sign positions grouped by type."""
        result = {}
        for sign_type, node_ids in SIGNS.items():
            positions = []
            for nid in node_ids:
                nid_str = str(nid)
                if nid_str in self._pos_cost:
                    x, y = self._pos_cost[nid_str]
                    positions.append({
                        "node": nid_str,
                        "x": round(x * 100.0 / MAP_WIDTH_UNITS, 4),
                        "y": round(100.0 - y * 100.0 / MAP_HEIGHT_UNITS, 4),
                    })
            result[sign_type] = positions
        return result

    def get_graph_data(self) -> dict:
        """
        Return the full graph data for frontend Canvas rendering.
        Mirrors the draw_map.py rendering approach:
        - All nodes with positions (mirrored over OX, spread for overlaps)
        - All edges
        - Stop-line node IDs (drawn in red)
        - Sign positions grouped by type with colours
        - Roundabout node IDs
        - Intersection groups

        Positions are raw (mirrored) coordinates; the frontend
        computes bounding box and scales them to fit the Canvas.
        """
        # Spread overlapping nodes for visual clarity (same as draw_map.py)
        pos_plot = _spread_overlapping_positions(
            self._pos_cost, tol=1e-6, spread=None
        )

        nodes = {}
        for nid, (x, y) in pos_plot.items():
            nodes[nid] = {"x": round(x, 6), "y": round(y, 6)}

        edges = []
        for u, v in self._G.edges():
            edges.append([u, v])

        # Sign data with colours
        sign_colors = {
            "traffic_light": "#e15759",
            "stop": "#f28e2b",
            "priority": "#59a14f",
            "highway_entry": "#4e79a7",
            "highway_exit": "#b07aa1",
            "roundabout": "#9c755f",
            "crosswalk": "#ff9da7",
            "no_entry": "#bab0ac",
            "one_way": "#76b7b2",
            "parking": "#b6992d",
        }

        signs = {}
        for sign_type, node_ids in SIGNS.items():
            entries = []
            for nid in node_ids:
                nid_str = str(nid)
                if nid_str in pos_plot:
                    x, y = pos_plot[nid_str]
                    entries.append({"node": nid_str, "x": round(x, 6), "y": round(y, 6)})
            signs[sign_type] = {
                "color": sign_colors.get(sign_type, "#ffffff"),
                "positions": entries,
            }

        return {
            "nodes": nodes,
            "edges": edges,
            "stop_lines": [str(n) for n in STOP_LINES],
            "roundabout_nodes": [str(n) for n in ROUNDABOUT_NODES],
            "intersections": INTERSECTIONS,
            "signs": signs,
        }
