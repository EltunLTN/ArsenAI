# flake8: noqa: E501

"""Matplotlib-based 4-way AI traffic simulation for hackathon demo.

Features:
- Main vertical flow (top<->bottom), low horizontal flow (right->left)
- AI signal timing around base cycle (20s vertical, 5s horizontal)
- Smooth stopping and queue formation at red lights
- Emergency preemption mode for ambulance
- Pedestrian crossing when roads are empty with adaptive extension
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle


@dataclass
class Car:
    car_id: int
    direction: str  # N2S, S2N, E2W
    lane: str
    pos: float
    speed: float
    max_speed: float
    color: str
    is_ambulance: bool = False
    waiting: bool = False
    prev_waiting: bool = False

    def xy(self, geom: dict) -> tuple[float, float]:
        if self.direction == "N2S":
            return geom["lane_x"][self.lane], self.pos
        if self.direction == "S2N":
            return geom["lane_x"][self.lane], self.pos
        return self.pos, geom["e2w_y"]


class TrafficSimulation:
    def __init__(self) -> None:
        self.colors = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444"]
        self.dt = 0.10  # seconds per frame

        self.phase = "NS_GREEN"
        self.phase_timer = 20.0
        self.phase_elapsed = 0.0
        self.sim_time = 0.0

        self.cars: list[Car] = []
        self.next_id = 1
        self.passed_count = 0
        self.stop_count = 0

        self.ai_message = "AI: Prioritizing vertical main road"
        self.state_text = "Vertical Green"

        self.east_spawned_this_cycle = False
        self.manual_east_pending = 0

        self.emergency_requested = False
        self.emergency_active = False
        self.next_emergency_time = random.uniform(35, 55)

        self.ped_active = False
        self.ped_type = "normal"
        self.pedestrians: list[dict] = []
        self.extended_crossing = False

        self.fig, self.ax = plt.subplots(figsize=(12, 7))
        manager = getattr(self.fig.canvas, "manager", None)
        if manager is not None and hasattr(manager, "set_window_title"):
            manager.set_window_title("AI Traffic Simulation")
        self._setup_plot()
        self._spawn_ns_wave()

    def _geom(self) -> dict:
        return {
            "cx": 0.0,
            "cy": 0.0,
            "inter_half": 8.0,
            "stop_n2s": 10.0,
            "stop_s2n": -10.0,
            "stop_e2w": 10.0,
            "e2w_y": -2.5,
            "lane_x": {
                "N2S_0": -3.8,
                "N2S_1": -1.8,
                "S2N_0": 1.8,
                "S2N_1": 3.8,
                "E2W": 2.2,
            },
        }

    def _setup_plot(self) -> None:
        self.ax.set_xlim(-60, 60)
        self.ax.set_ylim(-40, 40)
        self.ax.set_aspect("equal")
        self.ax.set_facecolor("#d4e8c2")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.set_title("AI-based 4-way Intersection Traffic Simulation", fontsize=14, weight="bold")

        # Roads
        self.ax.add_patch(Rectangle((-6, -40), 12, 80, color="#5a5a5a", zorder=0))
        self.ax.add_patch(Rectangle((-60, -6), 120, 12, color="#5a5a5a", zorder=0))

        # Zebra crossings (soft)
        for y in (-11.5, 11.5):
            for i in range(-9, 10, 2):
                self.ax.add_patch(Rectangle((i, y), 1, 1, color="white", alpha=0.25, zorder=0))
        for x in (-11.5, 11.5):
            for i in range(-9, 10, 2):
                self.ax.add_patch(Rectangle((x, i), 1, 1, color="white", alpha=0.25, zorder=0))

        # Cars and pedestrians
        self.car_scatter = self.ax.scatter([], [], s=58, c=[], edgecolors="black", linewidths=0.3, zorder=5)
        self.amb_scatter = self.ax.scatter([], [], s=95, c="#ffffff", edgecolors="#ef4444", linewidths=1.4, zorder=6)
        self.ped_scatter = self.ax.scatter([], [], s=45, c="#111827", zorder=6)

        # Bigger traffic lights
        self.ns_light_n = Circle((-9.5, 9.5), 1.3, color="gray", zorder=7)
        self.ns_light_s = Circle((9.5, -9.5), 1.3, color="gray", zorder=7)
        self.ew_light = Circle((9.5, -2.5), 1.3, color="gray", zorder=7)
        self.ax.add_patch(self.ns_light_n)
        self.ax.add_patch(self.ns_light_s)
        self.ax.add_patch(self.ew_light)

        # Labels and dynamic text
        self.phase_txt = self.ax.text(-58, 36.2, "", fontsize=12, weight="bold", color="#0f172a")
        self.ai_txt = self.ax.text(-58, 33.0, "", fontsize=10, color="#334155")
        self.wait_txt = self.ax.text(-58, 29.8, "", fontsize=10, color="#334155")
        self.counter_txt = self.ax.text(-58, 26.6, "", fontsize=10, color="#334155")
        self.cross_txt = self.ax.text(-58, 23.4, "", fontsize=10, color="#0f766e", weight="bold")

        self.ax.text(-58, -36.5, "Directions: Vertical heavy flow, horizontal low flow", fontsize=9, color="#475569")
        self.ax.text(-58, -38.5, "Emergency and pedestrian AI enabled", fontsize=9, color="#475569")

    def _signal_for(self, road: str) -> str:
        # road: NS or EW
        if self.phase == "PED_CROSS":
            return "RED"
        if self.phase == "EMERGENCY_YELLOW":
            return "YELLOW"
        if self.phase == "EMERGENCY_GREEN":
            return "GREEN" if road == "EW" else "RED"
        if road == "NS":
            if self.phase == "NS_GREEN":
                return "GREEN"
            if self.phase == "NS_YELLOW":
                return "YELLOW"
            return "RED"
        if self.phase == "EW_GREEN":
            return "GREEN"
        if self.phase == "EW_YELLOW":
            return "YELLOW"
        return "RED"

    def _set_phase(self, phase: str, duration: float) -> None:
        self.phase = phase
        self.phase_timer = duration
        self.phase_elapsed = 0.0

        if phase == "NS_GREEN":
            self.state_text = "Vertical Green"
            self.east_spawned_this_cycle = False
            self._spawn_ns_wave()
            self.ai_message = "AI: Main road priority (20s base)"
        elif phase == "NS_YELLOW":
            self.state_text = "Vertical Yellow"
            self.ai_message = "Transition: prepare horizontal release"
        elif phase == "EW_GREEN":
            self.state_text = "Horizontal Green"
            self.ai_message = "AI: Short horizontal release"
        elif phase == "EW_YELLOW":
            self.state_text = "Horizontal Yellow"
            self.ai_message = "Transition: return to main road"
        elif phase == "EMERGENCY_YELLOW":
            self.state_text = "Emergency Mode Activated"
            self.ai_message = "AI: Clearing junction for ambulance"
        elif phase == "EMERGENCY_GREEN":
            self.state_text = "Emergency Mode Activated"
            self.ai_message = "AI: Ambulance lane green"
            self._spawn_ambulance()
        elif phase == "PED_CROSS":
            self.state_text = "Pedestrian Crossing"
            self.ai_message = "AI: All-red crossing interval"

    def _spawn_car(self, direction: str, lane: str, pos: float, color: str | None = None, emergency: bool = False) -> None:
        c = Car(
            car_id=self.next_id,
            direction=direction,
            lane=lane,
            pos=pos,
            speed=0.0,
            max_speed=(135.0 if emergency else (80.0 + random.random() * 24.0)),
            color=(color or random.choice(self.colors)),
            is_ambulance=emergency,
        )
        self.next_id += 1
        self.cars.append(c)

    def _spawn_ns_wave(self) -> None:
        # 10-14 vehicles, split as 5-7 for each vertical direction
        n_count = random.randint(5, 7)
        s_count = random.randint(5, 7)

        offset = 0.0
        for _ in range(n_count):
            offset += random.uniform(3.2, 4.4)
            lane = random.choice(["N2S_0", "N2S_1"])
            self._spawn_car("N2S", lane, 40 + offset)

        offset = 0.0
        for _ in range(s_count):
            offset += random.uniform(3.2, 4.4)
            lane = random.choice(["S2N_0", "S2N_1"])
            self._spawn_car("S2N", lane, -40 - offset)

    def _spawn_east_low_traffic(self) -> None:
        # low traffic road: 1 car comes and waits during NS green
        east_cars = [c for c in self.cars if c.direction == "E2W"]
        start = 55.0
        if east_cars:
            start = max(start, max(c.pos for c in east_cars) + random.uniform(3.4, 4.6))
        self._spawn_car("E2W", "E2W", start, color="#f97316")

    def _spawn_ambulance(self) -> None:
        self._spawn_car("E2W", "E2W", 58.0, color="#ffffff", emergency=True)
        self.emergency_active = True

    def _distance_to_stop(self, car: Car, g: dict) -> float:
        if car.direction == "N2S":
            return car.pos - g["stop_n2s"]
        if car.direction == "S2N":
            return g["stop_s2n"] - car.pos
        return car.pos - g["stop_e2w"]

    def _beyond_stop(self, car: Car, g: dict) -> bool:
        if car.direction == "N2S":
            return car.pos <= g["stop_n2s"]
        if car.direction == "S2N":
            return car.pos >= g["stop_s2n"]
        return car.pos <= g["stop_e2w"]

    def _inside_intersection(self, car: Car, g: dict) -> bool:
        x, y = car.xy(g)
        ih = g["inter_half"]
        return (-ih < x < ih) and (-ih < y < ih)

    def _gap_ahead(self, me: Car, other: Car) -> float:
        if me.direction != other.direction or me.lane != other.lane:
            return -1.0
        if me.direction == "N2S" and other.pos < me.pos:
            return me.pos - other.pos
        if me.direction == "S2N" and other.pos > me.pos:
            return other.pos - me.pos
        if me.direction == "E2W" and other.pos < me.pos:
            return me.pos - other.pos
        return -1.0

    def _move_cars(self) -> None:
        g = self._geom()

        for car in self.cars:
            road = "EW" if car.direction == "E2W" else "NS"
            signal = self._signal_for(road)
            dist = self._distance_to_stop(car, g)
            beyond = self._beyond_stop(car, g)
            inside = self._inside_intersection(car, g)

            target = car.max_speed

            if not car.is_ambulance:
                if signal == "RED":
                    if not beyond and not inside:
                        target = 0.0
                elif signal == "YELLOW":
                    # Yellow behavior:
                    # far (>40px equivalent) before line => decelerate/stop
                    # near line => pass
                    if not beyond and not inside and dist > 4.0:
                        target = 0.0

            nearest = float("inf")
            for other in self.cars:
                if other.car_id == car.car_id:
                    continue
                gap = self._gap_ahead(car, other)
                if 0 < gap < nearest:
                    nearest = gap

            if nearest < float("inf") and not car.is_ambulance:
                safe = 2.4
                if nearest < safe:
                    target = min(target, 0.0)
                elif nearest < safe + 3.0:
                    target = min(target, (nearest - safe) / 3.0 * car.max_speed)

            # Critical rule: never stop inside center box.
            if inside:
                target = max(target, car.max_speed * 0.60)

            accel = 140.0 if target > car.speed else 180.0
            max_delta = accel * self.dt
            if car.speed < target:
                car.speed = min(target, car.speed + max_delta)
            else:
                car.speed = max(target, car.speed - max_delta)

            car.waiting = car.speed < 1.5 and not inside and not beyond
            if (not car.prev_waiting) and car.waiting:
                self.stop_count += 1
            car.prev_waiting = car.waiting

            if car.direction == "N2S":
                car.pos -= car.speed * self.dt
            elif car.direction == "S2N":
                car.pos += car.speed * self.dt
            else:
                car.pos -= car.speed * self.dt

        kept: list[Car] = []
        for car in self.cars:
            x, y = car.xy(g)
            out = x < -65 or x > 65 or y < -45 or y > 45
            if out:
                self.passed_count += 1
                if car.is_ambulance:
                    self.emergency_active = False
            else:
                kept.append(car)
        self.cars = kept

    def _roads_empty(self) -> bool:
        # For demo, treat roads as empty if only a very small number of non-emergency vehicles remain.
        non_em = [c for c in self.cars if not c.is_ambulance]
        return len(non_em) <= 2

    def _start_ped_crossing(self) -> None:
        self.ped_active = True
        self.extended_crossing = False
        self.ped_type = random.choices(["normal", "slow"], weights=[0.7, 0.3])[0]
        duration = 4.0
        if self.ped_type == "slow":
            duration += 2.0
            self.extended_crossing = True
            self.ai_message = "Extended Crossing Time"

        self.pedestrians = [
            {"x": -16.0, "y": 11.5, "dir": 1.0},
            {"x": 16.0, "y": -11.5, "dir": -1.0},
        ]
        self._set_phase("PED_CROSS", duration)

    def _move_pedestrians(self) -> None:
        if not self.ped_active:
            return
        speed = 2.6 if self.ped_type == "normal" else 1.7
        for p in self.pedestrians:
            p["x"] += p["dir"] * speed * self.dt

    def _update_phase_logic(self) -> None:
        self.sim_time += self.dt
        self.phase_elapsed += self.dt
        self.phase_timer -= self.dt

        # Automatic emergency events for demo.
        if self.sim_time >= self.next_emergency_time and not self.emergency_requested and not self.emergency_active:
            self.emergency_requested = True
            self.next_emergency_time = self.sim_time + random.uniform(35, 55)

        # If emergency requested, preempt with short all-yellow.
        if self.emergency_requested and self.phase not in {"EMERGENCY_YELLOW", "EMERGENCY_GREEN"}:
            self.emergency_requested = False
            self._set_phase("EMERGENCY_YELLOW", 1.2)
            return

        # Spawn low-traffic east car at 10th second of NS green.
        if self.phase == "NS_GREEN" and (not self.east_spawned_this_cycle) and self.phase_elapsed >= 10.0:
            self._spawn_east_low_traffic()
            self.east_spawned_this_cycle = True

        if self.phase_timer > 0:
            return

        if self.phase == "NS_GREEN":
            self._set_phase("NS_YELLOW", 2.0)
            return

        if self.phase == "NS_YELLOW":
            waiting_e = sum(1 for c in self.cars if c.direction == "E2W" and c.waiting)
            ew_green = min(7.0, 5.0 + 0.7 * min(waiting_e, 3))
            self.ai_message = f"AI decision: horizontal wait={waiting_e}, EW green={ew_green:.1f}s"
            self._set_phase("EW_GREEN", ew_green)
            return

        if self.phase == "EW_GREEN":
            self._set_phase("EW_YELLOW", 2.0)
            return

        if self.phase == "EW_YELLOW":
            if self._roads_empty():
                self._start_ped_crossing()
                return

            waiting_v = sum(1 for c in self.cars if c.direction in {"N2S", "S2N"} and c.waiting)
            ns_green = min(28.0, 20.0 + 0.5 * min(waiting_v, 16))
            self.ai_message = f"AI decision: vertical load={waiting_v}, NS green={ns_green:.1f}s"
            self._set_phase("NS_GREEN", ns_green)
            return

        if self.phase == "EMERGENCY_YELLOW":
            self._set_phase("EMERGENCY_GREEN", 6.0)
            return

        if self.phase == "EMERGENCY_GREEN":
            self._set_phase("NS_YELLOW", 2.0)
            return

        if self.phase == "PED_CROSS":
            self.ped_active = False
            self.pedestrians = []
            self._set_phase("NS_GREEN", 20.0)

    def _update_lights_visual(self) -> None:
        ns = self._signal_for("NS")
        ew = self._signal_for("EW")

        def color(sig: str) -> str:
            if sig == "GREEN":
                return "#16a34a"
            if sig == "YELLOW":
                return "#f59e0b"
            return "#dc2626"

        self.ns_light_n.set_color(color(ns))
        self.ns_light_s.set_color(color(ns))
        self.ew_light.set_color(color(ew))

    def _update_text(self) -> None:
        waiting_v = sum(1 for c in self.cars if c.direction in {"N2S", "S2N"} and c.waiting)
        waiting_h = sum(1 for c in self.cars if c.direction == "E2W" and c.waiting)

        if self.phase == "EMERGENCY_GREEN" or self.phase == "EMERGENCY_YELLOW":
            phase_label = "Emergency Mode"
        elif self.phase == "PED_CROSS":
            phase_label = "Pedestrian Crossing"
        elif self.phase == "NS_GREEN":
            phase_label = "Vertical Green"
        elif self.phase == "EW_GREEN":
            phase_label = "Horizontal Green"
        elif self.phase == "NS_YELLOW":
            phase_label = "Vertical Yellow"
        else:
            phase_label = "Horizontal Yellow"

        extra = ""
        if self.extended_crossing and self.phase == "PED_CROSS":
            extra = " | Extended Crossing Time"

        self.phase_txt.set_text(f"State: {phase_label} | t={self.phase_timer:04.1f}s{extra}")
        self.ai_txt.set_text(self.ai_message)
        self.wait_txt.set_text(f"Waiting counters -> Vertical: {waiting_v}, Horizontal: {waiting_h}")
        self.counter_txt.set_text(f"Passed: {self.passed_count} | Stops: {self.stop_count} | Cars on map: {len(self.cars)}")

        if self.phase == "PED_CROSS":
            p_label = "Pedestrians crossing (slow)" if self.ped_type == "slow" else "Pedestrians crossing"
            self.cross_txt.set_text(p_label)
        else:
            self.cross_txt.set_text("")

    def _update_artists(self):
        g = self._geom()
        normal_xy = []
        normal_colors = []
        amb_xy = []

        for c in self.cars:
            x, y = c.xy(g)
            if c.is_ambulance:
                amb_xy.append((x, y))
            else:
                normal_xy.append((x, y))
                normal_colors.append(c.color)

        if normal_xy:
            self.car_scatter.set_offsets(normal_xy)
            self.car_scatter.set_color(normal_colors)
        else:
            self.car_scatter.set_offsets([])

        if amb_xy:
            self.amb_scatter.set_offsets(amb_xy)
        else:
            self.amb_scatter.set_offsets([])

        if self.ped_active and self.pedestrians:
            ped_xy = [(p["x"], p["y"]) for p in self.pedestrians]
            self.ped_scatter.set_offsets(ped_xy)
        else:
            self.ped_scatter.set_offsets([])

    def step(self, _frame: int):
        self._update_phase_logic()
        self._move_cars()
        self._move_pedestrians()
        self._update_lights_visual()
        self._update_text()
        self._update_artists()
        return (
            self.car_scatter,
            self.amb_scatter,
            self.ped_scatter,
            self.ns_light_n,
            self.ns_light_s,
            self.ew_light,
            self.phase_txt,
            self.ai_txt,
            self.wait_txt,
            self.counter_txt,
            self.cross_txt,
        )

    def run(self) -> None:
        FuncAnimation(self.fig, self.step, interval=int(self.dt * 1000), blit=False)
        plt.show()


if __name__ == "__main__":
    sim = TrafficSimulation()
    sim.run()
