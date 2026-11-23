package g41probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 列出电路里某类元件（按工厂名精确匹配）的全部实例端口：索引、坐标、位宽、方向。
 * 用于生成/解析 .circ 前量准 4.1 的真实端口几何（子电路是固定 220 宽、20px 间距）。
 * 用法：java -cp <4.1 jar>;<build> g41probe.G41Ports <file.circ> <circuit> [factoryName]
 */
public class G41Ports {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        if (c == null) {
            System.out.println("no such circuit: " + a[1]);
            System.exit(1);
        }
        String want = a.length > 2 ? a[2] : "";
        for (Component comp : c.getNonWires()) {
            String name = comp.getFactory().getName();
            if (!want.isEmpty() && !name.equals(want)) continue;
            StringBuilder sb = new StringBuilder(name + "@" + comp.getLocation()
                    + " bounds=" + comp.getBounds() + " :");
            int i = 0;
            for (EndData e : comp.getEnds())
                sb.append(" #").append(i++).append("=").append(e.getLocation())
                  .append(" w").append(e.getWidth().getWidth())
                  .append(e.isOutput() ? "OUT" : "in");
            System.out.println(sb);
        }
        System.exit(0);
    }
}
