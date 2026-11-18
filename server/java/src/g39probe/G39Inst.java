package g39probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 列出一个电路里某类元件（按工厂名精确匹配，如 Register / Splitter / Bank8）
 * 的全部实例端口：索引、坐标、位宽、输入/输出。
 * 生成电路前先用它量准 3.9 的真实端口几何（Register 的 en=+50/clk=+70 就是靠它确认的）。
 * 用法：java -cp <jar>;<build> g39probe.G39Inst <file.circ> <circuit> <factoryName>
 */
public class G39Inst {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        for (Component comp : c.getNonWires()) {
            if (!comp.getFactory().getName().equals(a[2])) continue;
            StringBuilder sb = new StringBuilder(comp.getFactory().getName() + "@" + comp.getLocation() + " :");
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
