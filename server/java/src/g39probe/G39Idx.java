package g39probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 按工厂名子串过滤元件，打印端口索引与坐标（out/in/io）。
 * 与 G39Inst 的区别：这里是子串模糊匹配，可一次看全一类（如 "Gate"）。
 * 用法：java -cp <jar>;<build> g39probe.G39Idx <file.circ> <circuit> <名字子串>
 */
public class G39Idx {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        for (Component comp : c.getNonWires()) {
            String n = comp.getFactory().getName();
            if (!n.contains(a[2])) continue;
            StringBuilder sb = new StringBuilder(n + "@" + comp.getLocation() + " :");
            int i = 0;
            for (EndData e : comp.getEnds())
                sb.append(" #").append(i++).append("=").append(e.getLocation())
                  .append(e.isOutput() ? "out" : (e.isInput() ? "in" : "io"));
            System.out.println(sb);
        }
        System.exit(0);
    }
}
