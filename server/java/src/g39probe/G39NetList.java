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
 * 扫描一个电路里所有"同一个网出现 2 个以上输出端"的网络 —— 真实短路。
 * 这是定位生成电路短路的决定性判据（比逐网观察取值快得多）。
 * 注意：输出端口径含 OUT 端与恒驱动源（Constant/Ground 的 io 口按 OUT 计）。
 * 用法：java -cp <jar>;<build> g39probe.G39NetList <file.circ> <circuit>
 */
public class G39NetList {
    static int[] parent;

    static int find(int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    }

    static void union(int a, int b) {
        int ra = find(a), rb = find(b);
        if (ra != rb) parent[ra] = rb;
    }

    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        List<int[]> segs = new ArrayList<>();
        Map<Integer, List<String>> members = new TreeMap<>();
        int idx = 0;
        for (Component w : c.getWires()) {
            Wire wi = (Wire) w;
            segs.add(new int[]{wi.getEnd0().getX(), wi.getEnd0().getY(),
                               wi.getEnd1().getX(), wi.getEnd1().getY()});
            int id = idx++;
            members.computeIfAbsent(id, k -> new ArrayList<>()).add(
                String.format("WIRE(%d,%d)-(%d,%d)", segs.get(id)[0], segs.get(id)[1],
                              segs.get(id)[2], segs.get(id)[3]));
        }
        parent = new int[segs.size()];
        for (int i = 0; i < parent.length; i++) parent[i] = i;
        Map<String, List<Integer>> ends = new HashMap<>();
        for (int i = 0; i < segs.size(); i++)
            for (int k = 0; k < 4; k += 2) {
                int px = segs.get(i)[k], py = segs.get(i)[k + 1];
                ends.computeIfAbsent(px + "," + py, kk -> new ArrayList<>()).add(i);
            }
        for (List<Integer> lst : ends.values())
            for (int i = 1; i < lst.size(); i++) union(lst.get(0), lst.get(i));
        int freeId = -1000;   // 自由端（没接任何导线的端口）各自独占一个桶，避免互相误并入假网
        for (Component comp : c.getNonWires()) {
            String fname = comp.getFactory().getName();
            boolean drv = fname.equals("Constant") || fname.equals("Ground");
            // 3.9 里 Splitter 的 EndData 两端都是 isOutput，但它是无源直通元件
            // （扇出分线器 → 合并分线器同网是正常接法），不能按驱动源计。
            boolean passive = fname.equals("Splitter") || fname.equals("Tunnel");
            int ei = 0;
            for (EndData e : comp.getEnds()) {
                Location p = e.getLocation();
                int hit = -1;
                for (int i = 0; i < segs.size(); i++)
                    if (onSeg(p.getX(), p.getY(), segs.get(i))) { hit = i; break; }
                String tag = passive ? "io" : (e.isOutput() ? "OUT" : (drv ? "OUT" : (e.isInput() ? "in" : "io")));
                String name = String.format("%s@%s#%d w%d %s", fname,
                        comp.getLocation(), ei++, e.getWidth().getWidth(), tag);
                if (hit >= 0)
                    members.computeIfAbsent(find(hit), k -> new ArrayList<>()).add(name);
                else
                    members.computeIfAbsent(freeId++, k -> new ArrayList<>()).add(name + " 自由端" + p);
            }
        }
        int multi = 0;
        for (Map.Entry<Integer, List<String>> e : members.entrySet()) {
            int cnt = 0;
            for (String m : e.getValue()) if (m.contains("OUT")) cnt++;
            if (cnt >= 2) {
                multi++;
                System.out.println("== 多驱动网 (OUT x" + cnt + ") ==");
                for (String m : e.getValue()) System.out.println("    " + m);
            }
        }
        System.out.println("完成。网数=" + members.size() + "  多驱动网=" + multi);
        System.exit(0);
    }

    static boolean onSeg(int x, int y, int[] s) {
        if (s[1] == s[3]) return y == s[1] && x >= Math.min(s[0], s[2]) && x <= Math.max(s[0], s[2]);
        if (s[0] == s[2]) return x == s[0] && y >= Math.min(s[1], s[3]) && y <= Math.max(s[1], s[3]);
        return false;
    }
}
