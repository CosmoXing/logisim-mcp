package g39probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import java.io.File;

/**
 * 列出一个电路全部元件的工厂名、定位点与包围盒 —— 检查元件体是否压线
 * （Ground 压在时钟干线上会被 WireRepair 裁线）时用。
 * 用法：java -cp <jar>;<build> g39probe.G39Bounds <file.circ> <circuit>
 */
public class G39Bounds {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Circuit c = lf.getCircuit(a[1]);
        for (Component comp : c.getNonWires())
            System.out.printf("%-22s %-12s %s%n", comp.getFactory().getName(),
                    comp.getLocation(), comp.getBounds());
        System.exit(0);
    }
}
