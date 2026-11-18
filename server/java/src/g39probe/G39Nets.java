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

/**
 * 用 3.9 内核的真实端口坐标检查接线：元件端点必须落在某根导线上，
 * 或与另一个端口同点直连；否则报"未接线端口"。可一次扫全部电路（circuit 传 all）。
 * 用法：java -cp <jar>;<build> g39probe.G39Nets <file.circ> [circuit|all]
 */
public class G39Nets {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### LOAD ERROR: " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        List<String> names = new ArrayList<>();
        if (a.length > 1 && !a[1].equals("all")) names.add(a[1]);
        else for (Circuit c : lf.getCircuits()) names.add(c.getName());

        for (String cn : names) {
            Circuit c = lf.getCircuit(cn);
            if (c == null) { System.out.println("缺电路 " + cn); continue; }
            List<int[]> segs = new ArrayList<>();
            for (Component w : c.getWires()) {
                Wire wi = (Wire) w;
                Location p = wi.getEnd0(), q = wi.getEnd1();
                segs.add(new int[]{p.getX(), p.getY(), q.getX(), q.getY()});
            }
            Map<String, Integer> endCount = new HashMap<>();
            for (Component comp : c.getNonWires())
                for (EndData e : comp.getEnds()) {
                    Location p = e.getLocation();
                    endCount.merge(p.getX() + "," + p.getY(), 1, Integer::sum);
                }
            List<String> bad = new ArrayList<>();
            for (Component comp : c.getNonWires()) {
                if (comp instanceof Wire) continue;
                for (EndData e : comp.getEnds()) {
                    Location p = e.getLocation();
                    if (onAnyWire(p.getX(), p.getY(), segs)) continue;
                    if (endCount.getOrDefault(p.getX() + "," + p.getY(), 0) > 1) continue;
                    bad.add(String.format("%s@%s 端口%s(%d位%s)", comp.getFactory().getName(),
                            comp.getLocation(), p, e.getWidth().getWidth(),
                            e.isOutput() ? "出" : (e.isInput() ? "入" : "双向")));
                }
            }
            System.out.println("=== " + cn + " 元件" + c.getNonWires().size()
                    + " 导线" + segs.size() + " 未接线端口 " + bad.size());
            for (String s : bad) System.out.println("   ! " + s);
        }
        System.exit(0);
    }

    static boolean onAnyWire(int x, int y, List<int[]> segs) {
        for (int[] s : segs) {
            int x1 = s[0], y1 = s[1], x2 = s[2], y2 = s[3];
            if (y1 == y2) {
                if (y == y1 && x >= Math.min(x1, x2) && x <= Math.max(x1, x2)) return true;
            } else if (x1 == x2) {
                if (x == x1 && y >= Math.min(y1, y2) && y <= Math.max(y1, y2)) return true;
            }
        }
        return false;
    }
}
