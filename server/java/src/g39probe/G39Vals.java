package g39probe;

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.circuit.Propagator;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.BitWidth;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.proj.Project;
import com.cburch.logisim.std.wiring.Pin;
import java.io.File;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 设一组输入引脚后，打印指定坐标的线值（位宽 + 是否 E 错误值）与输出引脚值。
 * 逐点观察"这条线上到底是什么、什么时候变成 E/U"的坐标级调试。
 * 用法：java -cp <jar>;<build> g39probe.G39Vals <file.circ> <circuit> "pin=val,..." "(x,y);(x,y);..."
 */
public class G39Vals {
    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Project p = new Project(lf);
        Circuit c = lf.getCircuit(a[1]);
        CircuitState cs = p.getCircuitState(c);
        Propagator prop = cs.getPropagator();
        Map<String, Long> want = new LinkedHashMap<>();
        for (String kv : a[2].split(",")) {
            String[] s = kv.split("=");
            want.put(s[0].trim(), Long.decode(s[1].trim()));
        }
        for (Component comp : c.getNonWires()) {
            if (comp.getFactory() instanceof Pin && want.containsKey(label(comp))) {
                int w = 1;
                try { w = Integer.parseInt(attr(comp, "width")); } catch (Exception ignore) { }
                Pin.FACTORY.setValue(cs.getInstanceState(comp),
                        Value.createKnown(BitWidth.create(w), want.get(label(comp))));
                cs.markComponentAsDirty(comp);
                cs.markPointAsDirty(comp.getLocation());
            }
        }
        prop.propagate();
        System.out.println("--- 坐标值 ---");
        for (String xy : a[3].split(";")) {
            Location loc = Location.parse(xy.trim());
            Value v = cs.getValue(loc);
            System.out.println("  " + xy + " -> " + (v == null ? "null"
                    : v.toHexString() + " w=" + v.getWidth() + " err=" + v.isErrorValue()));
        }
        System.out.println("--- 输出引脚 ---");
        for (Component comp : c.getNonWires()) {
            if (comp.getFactory() instanceof Pin && "true".equals(attr(comp, "output")))
                System.out.println("  " + label(comp) + " = "
                        + Pin.FACTORY.getValue(cs.getInstanceState(comp)).toHexString()
                        + "  线值=" + cs.getValue(comp.getLocation()).toHexString());
        }
        System.exit(0);
    }

    static String label(Component c) { return attr(c, "label"); }

    static String attr(Component c, String n) {
        for (Attribute<?> at : c.getAttributeSet().getAttributes())
            if (at.getName().equals(n)) {
                Object v = c.getAttributeSet().getValue(at);
                return v == null ? "" : String.valueOf(v);
            }
        return "";
    }
}
