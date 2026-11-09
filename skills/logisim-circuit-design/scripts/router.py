"""通道布线器：给每个网络安排"水平 → 垂直 → 水平"的走线，自动避开冲突。

Logisim 连通规则（实测）：
  十字交叉 不连
  端点压在别的线上 会连
  共线重叠 会连
因此布线器只允许：不同网络的线段正交交叉；禁止共线重叠；禁止端点落在别的网络上。
"""


class Router:
    def __init__(self, x_pool, y_pool):
        self.x_pool = list(x_pool)
        self.y_pool = list(y_pool)
        self.segs = []      # [(x1,y1,x2,y2,net)]
        self.obstacles = [] # 端口禁区：线段或退化点
        self.rejected = []

    # ---------- 几何判定 ----------
    @staticmethod
    def _norm(s):
        x1, y1, x2, y2 = s[:4]
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    @classmethod
    def _collinear_overlap(cls, a, b):
        ax1, ay1, ax2, ay2 = cls._norm(a)
        bx1, by1, bx2, by2 = cls._norm(b)
        if ax1 == ax2 == bx1 == bx2:
            return max(ay1, by1) < min(ay2, by2)
        if ay1 == ay2 == by1 == by2:
            return max(ax1, bx1) < min(ax2, bx2)
        return False

    @classmethod
    def _point_on(cls, p, s):
        x, y = p
        x1, y1, x2, y2 = cls._norm(s)
        if x1 == x2:
            return x == x1 and y1 <= y <= y2
        if y1 == y2:
            return y == y1 and x1 <= x <= x2
        return False

    def add_obstacle(self, *pts):
        self.obstacles.append(pts)

    def _hit_obstacle(self, seg, allow):
        for ob in self.obstacles:
            ox1, oy1, ox2, oy2 = ob
            if self._collinear_overlap(seg, (ox1, oy1, ox2, oy2)):
                return True
            for p in ((seg[0], seg[1]), (seg[2], seg[3])):
                if p in allow:
                    continue
                if self._point_on(p, (ox1, oy1, ox2, oy2)):
                    return True
            for p in ((ox1, oy1), (ox2, oy2)):
                if p in allow:
                    continue
                if self._point_on(p, seg):
                    return True
        return False

    def _bad(self, seg, net, allow_touch=()):
        if self._hit_obstacle(seg, allow_touch):
            return True
        for s in self.segs:
            if s[4] == net:
                continue                     # 同一网络内部允许重叠/连接
            if self._collinear_overlap(seg, s):
                return True
            for p in ((seg[0], seg[1]), (seg[2], seg[3])):
                if self._point_on(p, s) and p not in allow_touch:
                    return True
            for p in ((s[0], s[1]), (s[2], s[3])):
                if self._point_on(p, seg):
                    return True
        return False

    def add(self, seg, net, allow_touch=()):
        if self._bad(seg, net, allow_touch):
            return False
        if (seg[0], seg[1]) == (seg[2], seg[3]):
            return True
        self.segs.append((*seg, net))
        return True

    # ---------- 布线 ----------
    def route(self, net, src, dst, allow_touch=(), prefer=None):
        sx, sy = src
        dx, dy = dst
        if sy == dy and sx != dx:
            seg = (sx, sy, dx, dy)
            if not self._bad(seg, net, allow_touch):
                self.add(seg, net, allow_touch)
                return [seg]
            return None
        cands = list(self.x_pool)
        if prefer is not None:
            cands.sort(key=lambda x: (abs(x - prefer), x))
        else:
            cands.sort(key=lambda x: abs(x - (sx + dx) / 2))
        for tx in cands:
            segs = [(sx, sy, tx, sy), (tx, sy, tx, dy), (tx, dy, dx, dy)]
            if any(self._bad(s, net, allow_touch) for s in segs):
                continue
            for s in segs:
                self.add(s, net, allow_touch)
            return segs
        return None

    def route_multi(self, net, src, dsts, allow_touch=()):
        """扇出：先布到第一个目标，再从已布线段上分接其余目标"""
        first = self.route(net, src, dsts[0], allow_touch)
        if first is None:
            return None
        out = list(first)
        if len(first) == 1:
            x1, y1, x2, y2 = first[0]
            junctions = list(range(min(x1, x2) + 20, max(x1, x2) - 10, 20))
            trunk = None
        else:
            trunk = first[1][0]
            junctions = [trunk]
        for d in dsts[1:]:
            dx, dy = d
            done = False
            for tx in junctions:
                ty = first[0][1] if len(first) == 1 else first[-1][3]
                if len(first) == 1:
                    ty = first[0][1]
                segs = [(tx, ty, tx, dy), (tx, dy, dx, dy)]
                if any(self._bad(s, net, allow_touch) for s in segs):
                    continue
                for s in segs:
                    self.add(s, net, allow_touch)
                out += segs
                done = True
                break
            if not done:
                return None
        return out

    def route_v(self, net, src, dst, allow_touch=()):
        """先竖后横（用于从已有水平干线上分接）"""
        sx, sy = src
        dx, dy = dst
        cands = sorted(self.x_pool, key=lambda x: abs(x - sx))
        for tx in cands:
            if tx == sx:
                segs = [(sx, sy, sx, dy), (sx, dy, dx, dy)]
            else:
                segs = [(sx, sy, tx, sy), (tx, sy, tx, dy), (tx, dy, dx, dy)]
            if any(self._bad(s, net, allow_touch) for s in segs):
                continue
            for s in segs:
                self.add(s, net, allow_touch)
            return segs
        return None
