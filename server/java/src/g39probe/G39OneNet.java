package g39probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.Wire;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * 列出包含指定坐标点 (x,y) 的网络全部成员（导线段 + 落在该网上的元件端口）。
 * 定位"这条信号到底连到了哪里 / 有没有短路到别的网"时用。
 * 用法：java -cp <jar>;<build> g39probe.G39OneNet <file.circ> <circuit> <x>,<y>
 */
public class G39OneNet {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        String[] target = a[2].split(",");
        int tx = Integer.parseInt(target[0].trim()), ty = Integer.parseInt(target[1].trim());
        List<int[]> segs = new ArrayList<>();
        Map<Integer, List<String>> members = new TreeMap<>();
        int idx = 0;
        for (Component w : c.getWires()) {
            Wire wi = (Wire) w;
            segs.add(new int[]{wi.getEnd0().getX(), wi.getEnd0().getY(),
                               wi.getEnd1().getX(), wi.getEnd1().getY()});
            members.computeIfAbsent(idx, k -> new ArrayList<>()).add(
                String.format("WIRE(%d,%d)-(%d,%d)", segs.get(idx)[0], segs.get(idx)[1],
                              segs.get(idx)[2], segs.get(idx)[3]));
            idx++;
        }
        int[] parent = new int[segs.size()];
        for (int i = 0; i < parent.length; i++) parent[i] = i;
        Map<String, List<Integer>> ends = new HashMap<>();
        for (int i = 0; i < segs.size(); i++)
            for (int k = 0; k < 4; k += 2)
                ends.computeIfAbsent(segs.get(i)[k] + "," + segs.get(i)[k + 1],
                                     kk -> new ArrayList<>()).add(i);
        for (List<Integer> lst : ends.values())
            for (int i = 1; i < lst.size(); i++) {
                int ra = find(parent, lst.get(0)), rb = find(parent, lst.get(i));
                if (ra != rb) parent[ra] = rb;
            }
        for (Component comp : c.getNonWires()) {
            int ei = 0;
            for (EndData e : comp.getEnds()) {
                Location p = e.getLocation();
                int hit = -1;
                for (int i = 0; i < segs.size(); i++)
                    if (onSeg(p.getX(), p.getY(), segs.get(i))) { hit = i; break; }
                String name = String.format("%s@%s#%d w%d %s", comp.getFactory().getName(),
                        comp.getLocation(), ei, e.getWidth().getWidth(),
                        e.isOutput() ? "OUT" : (e.isInput() ? "in" : "io"));
                ei++;
                if (hit >= 0)
                    members.computeIfAbsent(find(parent, hit), k -> new ArrayList<>()).add(name);
                else
                    members.computeIfAbsent(-1000 - ei, k -> new ArrayList<>()).add(name + " 自由端" + p);
            }
        }
        int hit = nearest(segs, tx, ty);
        if (hit < 0) {
            System.out.println("点 (" + tx + "," + ty + ") 不落在任何导线上（自由点/悬空）");
            System.exit(0);
        }
        int root = find(parent, hit);
        System.out.println("目标网成员 (" + tx + "," + ty + "):");
        List<String> lst = members.get(root);
        if (lst == null) System.out.println("   （孤立导线段）");
        else for (String m : lst) System.out.println("   " + m);
        System.exit(0);
    }

    /** 返回包含该点的导线段下标；不在任何导线上返回 -1。 */
    static int nearest(List<int[]> segs, int x, int y) {
        for (int i = 0; i < segs.size(); i++) if (onSeg(x, y, segs.get(i))) return i;
        return -1;
    }

    static int find(int[] p, int x) {
        while (p[x] != x) { p[x] = p[p[x]]; x = p[x]; }
        return x;
    }

    static boolean onSeg(int x, int y, int[] s) {
        if (s[1] == s[3]) return y == s[1] && x >= Math.min(s[0], s[2]) && x <= Math.max(s[0], s[2]);
        if (s[0] == s[2]) return x == s[0] && y >= Math.min(s[1], s[3]) && y <= Math.max(s[1], s[3]);
        return false;
    }
}
