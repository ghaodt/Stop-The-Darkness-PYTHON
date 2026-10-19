from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

Neighbor = Tuple[str, int]
Amounts = Dict[str, float]


class Cost:
    """Một khoản phí (vd: 6 wood + 2 rock). Bất biến, có thể nhân hệ số và trừ vào kho."""

    __slots__ = ("_a",)

    def __init__(self, **amounts: float):
        self._a = {k: v for k, v in amounts.items() if v}

    def as_dict(self) -> Dict[str, float]:
        return dict(self._a)

    def scaled(self, factor: float) -> "Cost":
        """Nhân hệ số rồi làm tròn: <10 làm tròn số nguyên, >=10 làm tròn bội của 5."""
        out = {}
        for k, v in self._a.items():
            x = v * factor
            out[k] = max(1, int(round(x))) if x < 10 else int(round(x / 5) * 5)
        return Cost(**out)

    def can_afford(self, resources: Amounts) -> bool:
        return all(resources.get(k, 0) >= v for k, v in self._a.items())

    def missing(self, resources: Amounts) -> Dict[str, float]:
        return {k: v - resources.get(k, 0) for k, v in self._a.items() if resources.get(k, 0) < v}

    def pay(self, resources: Amounts) -> None:
        if not self.can_afford(resources):
            raise ValueError("Not enough resources")
        for k, v in self._a.items():
            resources[k] -= v

    def text(self) -> str:
        return ", ".join(f"{v:g} {k}" for k, v in self._a.items()) or "free"

    def __add__(self, other: "Cost") -> "Cost":
        total = dict(self._a)
        for k, v in other._a.items():
            total[k] = total.get(k, 0) + v
        return Cost(**total)

    def __bool__(self) -> bool:
        return bool(self._a)

    def __repr__(self) -> str:
        return f"Cost({self.text()})"


class UpgradeCostPolicy:
    """
    Logic phí nâng cấp: giá để LÊN cấp L = base * growth ** (L - first_level), làm tròn.
    Nghĩa là cấp đầu tiên có thể nâng (first_level, thường là 2) tốn đúng `base`,
    mỗi cấp sau đắt gấp ~`growth` lần. Có thể ghi đè giá của một cấp bằng `overrides`
    (giống bảng COSTS viết tay trong main.py).
    """

    def __init__(self, base: Cost, growth: float = 2.4, first_level: int = 2,
                 overrides: Optional[Dict[int, Cost]] = None):
        self.base, self.growth, self.first_level = base, growth, first_level
        self.overrides = overrides or {}

    def cost_for(self, level: int) -> Optional[Cost]:
        """Giá để nâng LÊN `level`; None nếu cấp này không phải trả phí."""
        if level < self.first_level:
            return None
        if level in self.overrides:
            return self.overrides[level]
        return self.base.scaled(self.growth ** (level - self.first_level))

    def total_to(self, level: int) -> Cost:
        """Tổng phí nâng từ cấp 1 lên `level`."""
        total = Cost()
        for lv in range(self.first_level, level + 1):
            c = self.cost_for(lv)
            if c:
                total = total + c
        return total


# ============================================================ Base class
def count(neighbors: Sequence[Neighbor], name: str, min_level: int = 1) -> int:
    return sum(1 for n, lv in neighbors if n == name and lv >= min_level)


class Building:
    """Lớp cha của mọi công trình. Lớp con chỉ cần khai báo dữ liệu + ghi đè `requirement_error`."""

    name = "Building"
    label = "??"                      # nhãn 2 chữ vẽ trên ô
    color = (200, 200, 200)
    terrain = "Field"                 # loại ô gốc được phép xây lên
    field_priority = 0                # ưu tiên khi nhiều công trình cùng hợp lệ trên 1 ô Field
    max_level = 1
    level_names: Tuple[str, ...] = ()  # tên hiển thị theo cấp (nếu có)
    build_cost = Cost()
    production_table: Dict[int, Amounts] = {}    # level -> {resource: số/phút}
    boost_table: Dict[int, Amounts] = {}         # level -> {resource: +% cho ô kề (0.25 = 25%)}
    upgrade_policy: Optional[UpgradeCostPolicy] = None

    # ---- thông tin theo cấp ----
    def display_name(self, level: int) -> str:
        if self.level_names:
            return self.level_names[min(level, len(self.level_names)) - 1]
        return self.name

    def production(self, level: int) -> Amounts:
        return dict(self.production_table.get(level, {}))

    def boost_to_adjacent(self, level: int) -> Amounts:
        return dict(self.boost_table.get(level, {}))

    # ---- xây mới ----
    def requirement_error(self, terrain: str, neighbors: Sequence[Neighbor]) -> Optional[str]:
        """Trả về thông báo lỗi nếu KHÔNG xây được, None nếu xây được."""
        if terrain != self.terrain:
            return f"{self.name} must be built on {self.terrain}."
        return None

    def can_build(self, terrain: str, neighbors: Sequence[Neighbor]) -> bool:
        return self.requirement_error(terrain, neighbors) is None

    # ---- nâng cấp ----
    def upgrade_cost(self, level: int) -> Optional[Cost]:
        """Giá nâng từ `level` lên `level + 1`; None nếu đã tối đa hoặc không có dữ liệu."""
        if level >= self.max_level or self.upgrade_policy is None:
            return None
        return self.upgrade_policy.cost_for(level + 1)

    def upgrade_error(self, level: int, neighbors: Sequence[Neighbor],
                      resources: Amounts) -> Optional[str]:
        if level >= self.max_level:
            return f"{self.display_name(level)} is at max level."
        cost = self.upgrade_cost(level)
        if cost is None:
            return "Upgrade cost not supplied."
        if not cost.can_afford(resources):
            return f"Need {cost.text()}."
        return None

    def total_cost_to(self, level: int) -> Cost:
        extra = self.upgrade_policy.total_to(level) if self.upgrade_policy else Cost()
        return self.build_cost + extra

    # ---- sản lượng có tính bonus ô kề ----
    def production_with_neighbors(self, level: int, neighbors: Sequence[Neighbor]) -> Amounts:
        result = self.production(level)
        for resource in result:
            bonus = sum(REGISTRY.adjacency_bonus(resource, n, lv) for n, lv in neighbors)
            result[resource] *= 1 + bonus
        return result

    def __repr__(self) -> str:
        return f"<{type(self).__name__} '{self.name}' max_level={self.max_level}>"


# ============================================================ Registry
class BuildingRegistry:
    """Danh sách tất cả công trình; main.py chỉ cần hỏi registry thay vì hard-code từng loại."""

    def __init__(self):
        self._items: Dict[str, Building] = {}

    def register(self, cls):
        inst = cls()
        self._items[inst.name] = inst
        return cls

    def get(self, name: str) -> Optional[Building]:
        return self._items.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def all(self) -> List[Building]:
        return list(self._items.values())

    def adjacency_bonus(self, resource: str, name: str, level: int) -> float:
        b = self._items.get(name)
        return b.boost_to_adjacent(level).get(resource, 0.0) if b else 0.0

    def target_for(self, terrain: str, neighbors: Sequence[Neighbor]) -> Optional[str]:
        """Công trình sẽ xuất hiện khi bấm nâng cấp ô `terrain` với các ô kề này (ưu tiên cao nhất)."""
        options = [b for b in self._items.values() if b.can_build(terrain, neighbors)]
        if not options:
            return None
        return max(options, key=lambda b: b.field_priority).name

    # ---- xuất dữ liệu sang định dạng của main.py ----
    def export_production(self) -> Dict[Tuple[str, int], Amounts]:
        return {(b.name, lv): b.production(lv) for b in self.all() for lv in b.production_table}

    def export_costs(self) -> Dict[str, Dict[int, Dict[str, float]]]:
        out = {}
        for b in self.all():
            levels = {}
            for lv in range(2, b.max_level + 1):
                c = b.upgrade_cost(lv - 1)
                if c:
                    levels[lv] = c.as_dict()
            out[b.name] = levels
        return out

    def export_colors(self) -> Dict[str, Tuple[int, int, int]]:
        return {b.name: b.color for b in self.all()}


REGISTRY = BuildingRegistry()


# ============================================================ Công trình cụ thể
@REGISTRY.register
class Village(Building):
    name, label, color = "Village", "VI", (192, 151, 92)
    field_priority = 10
    max_level = 3
    level_names = ("Village", "Town", "City")
    build_cost = Cost(wood=3)
    production_table = {1: {"wood": 2}, 2: {"wood": 5, "rock": 1}, 3: {"wood": 10, "rock": 3}}
    boost_table = {1: {"wood": .10}, 2: {"wood": .25}, 3: {"wood": .50}}
    upgrade_policy = UpgradeCostPolicy(Cost(wood=6, rock=2), growth=2.5)

    def requirement_error(self, terrain, neighbors):
        return super().requirement_error(terrain, neighbors) or (
            None if count(neighbors, "Forest") else "Village needs an adjacent Forest.")


@REGISTRY.register
class MiningVillage(Building):
    name, label, color = "Mining Village", "MV", (153, 129, 109)
    field_priority = 30
    max_level = 3
    level_names = ("Mining Village", "Mining Town", "Mining City")
    build_cost = Cost(wood=3)
    production_table = {1: {"rock": 3}, 2: {"rock": 7}, 3: {"rock": 14}}
    boost_table = {1: {"rock": .10}, 2: {"rock": .25}, 3: {"rock": .50}}
    upgrade_policy = UpgradeCostPolicy(Cost(wood=5, rock=5), growth=2.4)

    def requirement_error(self, terrain, neighbors):
        return super().requirement_error(terrain, neighbors) or (
            None if count(neighbors, "Rocks") >= 2 else "Mining Village requires at least 2 adjacent Rocks.")


@REGISTRY.register
class MagicalVillage(Building):
    name, label, color = "Magical Village", "MG", (177, 112, 195)
    field_priority = 40
    max_level = 3
    level_names = ("Magical Village", "Magical Town", "Magical City")
    build_cost = Cost(wood=3)
    production_table = {1: {"magic": 2}, 2: {"magic": 5, "wood": 1}, 3: {"magic": 10, "wood": 3}}
    boost_table = {1: {"magic": .10}, 2: {"magic": .25}, 3: {"magic": .50}}
    upgrade_policy = UpgradeCostPolicy(Cost(wood=5, magic=4), growth=2.5)

    def requirement_error(self, terrain, neighbors):
        return super().requirement_error(terrain, neighbors) or (
            None if count(neighbors, "Mushroom Forest") else "Magical Village needs an adjacent Mushroom Forest.")


@REGISTRY.register
class Docks(Building):
    name, label, color = "Docks", "DO", (169, 135, 91)
    terrain = "Water"
    max_level = 2
    level_names = ("Docks", "Large Docks")
    build_cost = Cost(wood=5)
    production_table = {1: {"wood": 3}, 2: {"wood": 6, "rock": 2}}
    boost_table = {1: {"wood": .10}, 2: {"wood": .25}}
    upgrade_policy = UpgradeCostPolicy(Cost(wood=6, rock=2), growth=2.0)

    def requirement_error(self, terrain, neighbors):
        return super().requirement_error(terrain, neighbors) or (
            None if count(neighbors, "Village") else "Water needs adjacent Village for Docks.")


@REGISTRY.register
class PortVillage(Building):
    """Làng cảng: xây trên ô Field nằm cạnh Docks, buôn bán gỗ + đá."""
    name, label, color = "Port Village", "PV", (86, 150, 170)
    field_priority = 20
    max_level = 3
    level_names = ("Port Village", "Port Town", "Port City")
    build_cost = Cost(wood=6)
    production_table = {1: {"wood": 3, "rock": 1}, 2: {"wood": 7, "rock": 3}, 3: {"wood": 14, "rock": 6}}
    boost_table = {1: {"wood": .15}, 2: {"wood": .30}, 3: {"wood": .50}}
    upgrade_policy = UpgradeCostPolicy(Cost(wood=8, rock=3), growth=2.4)

    def requirement_error(self, terrain, neighbors):
        return super().requirement_error(terrain, neighbors) or (
            None if count(neighbors, "Docks") else "Port Village needs an adjacent Docks.")


@REGISTRY.register
class TowerOfLight(Building):
    """Xây cạnh Magical Village cấp 2 trở lên. Sản xuất magic và tăng mọi tài nguyên cho ô kề."""
    name, label, color = "Tower of Light", "TL", (250, 232, 150)
    field_priority = 50
    max_level = 4
    build_cost = Cost(wood=20, rock=20, magic=10)
    production_table = {1: {"magic": 3}, 2: {"magic": 7}, 3: {"magic": 14}, 4: {"magic": 25}}
    boost_table = {lv: {r: v for r in ("wood", "rock", "magic")}
                   for lv, v in ((1, .10), (2, .25), (3, .50), (4, 1.00))}
    upgrade_policy = UpgradeCostPolicy(Cost(rock=10, magic=10), growth=2.5)
    light_power = {1: 1, 2: 2, 3: 3, 4: 5}   # móc dành cho sau này (vd: làm chậm bóng tối)

    def requirement_error(self, terrain, neighbors):
        return super().requirement_error(terrain, neighbors) or (
            None if count(neighbors, "Magical Village", min_level=2)
            else "Tower of Light needs an adjacent Magical Village Level 2.")


# ============================================================ Xem nhanh bảng số liệu
if __name__ == "__main__":
    for b in REGISTRY.all():
        print(f"\n== {b.name} (terrain: {b.terrain}, max level {b.max_level}) ==")
        print("  Build cost:", b.build_cost.text())
        for lv in range(1, b.max_level + 1):
            up = b.upgrade_cost(lv)
            print(f"  L{lv} {b.display_name(lv):<16} prod/min={b.production(lv)} "
                  f"boost={ {k: f'{v:.0%}' for k, v in b.boost_to_adjacent(lv).items()} } "
                  f"-> next: {up.text() if up else '-'}")
        print("  Total to max:", b.total_cost_to(b.max_level).text())
