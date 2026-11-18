package g39probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.Wire;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 导出 3.9 内核【加载后】的导线清单 —— 关键工具：XML 里的 <wire> 与加载后的
 * 实际导线可能不同（Logisim 的 WireRepair 会裁掉穿过元件体的线、合并共线段）。
 * 把本输出与文件里的 wire 逐条 diff，缺的那条就是被裁掉的。
 * 用法：java -cp <jar>;<build> g39probe.G39Wires <file.circ> <circuit>
 */
public class G39Wires {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        for (Component w : c.getWires()) {
            Wire wi = (Wire) w;
            System.out.println(wi.getEnd0() + " - " + wi.getEnd1());
        }
        System.exit(0);
    }
}
