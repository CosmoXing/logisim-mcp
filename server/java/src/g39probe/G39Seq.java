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
import java.util.ArrayList;
import java.util.List;

/**
 * 用 3.9 内核跑脚本化时序功能测试（比 -w 测试向量强：支持多拍时序）。
 * 用法：java -cp <jar>;<build> g39probe.G39Seq <file.circ> <circuit> "<step;step;...>"
 *   step: pin=val,pin=val   设引脚（值支持 0x 十六进制；全部设完再统一传播）
 *         t                 一个时钟周期（clk 是引脚 → 手动 0→1→0；有 Clock 组件 → 两次翻转）
 *         r                 打印全部输出引脚
 * 环境变量 W="(x,y);(x,y)" 可在每个 r 步附加打印指定坐标的线值（调试布线用）。
 * 注意：目标电路必须是文件的 <main>（或对子电路单测时引脚驱动不完全可靠，
 * 正式验证一律走顶层 main）。引脚设值后必须 markComponentAsDirty + markPointAsDirty。
 */
public class G39Seq {
    static CircuitState cs;
    static Propagator prop;
    static Circuit circ;
    static Component clkPin;
    static List<Component> outs = new ArrayList<>();
    static List<Component> disps = new ArrayList<>();

    public static void main(String[] a) throws Exception {
        Loader l = new Loader(null) {
            @Override public void showError(String m) { System.out.println("### LOAD ERROR: " + m); }
        };
        LogisimFile lf = l.openLogisimFile(new File(a[0]));
        Project p = new Project(lf);
        circ = lf.getCircuit(a[1]);
        cs = p.getCircuitState(circ);
        prop = cs.getPropagator();
        for (Component c : circ.getNonWires()) {
            if (!(c.getFactory() instanceof Pin)) {
                if (c.getFactory().getName().equals("Hex Digit Display")) disps.add(c);
                continue;
            }
            if ("true".equals(at(c, "output"))) outs.add(c);
        }
        clkPin = find("clk");
        prop.propagate();
        System.out.println("[" + circ.getName() + "] out=" + names());
        for (String step : a[2].split(";")) {
            step = step.trim();
            if (step.isEmpty()) continue;
            if (step.equals("t")) { tick(); continue; }
            if (step.equals("r")) {
                System.out.println("   -> " + read());
                if (System.getenv("W") != null)
                    for (String xy : System.getenv("W").split(";")) {
                        Value v = cs.getValue(Location.parse(xy.trim()));
                        System.out.println("      " + xy + " = " + (v == null ? "null" : v.toHexString()));
                    }
                continue;
            }
            for (String kv : step.split(",")) {
                String[] s = kv.split("=", 2);
                if (s.length == 2) set(find(s[0].trim()), Long.decode(s[1].trim()));
            }
            prop.propagate();
        }
        System.out.println("end: " + read());
        System.out.println("oscillating=" + prop.isOscillating());
        System.exit(0);
    }

    static String names() {
        List<String> r = new ArrayList<>();
        for (Component c : outs) r.add(at(c, "label"));
        return r.toString();
    }

    static Component find(String label) {
        for (Component c : circ.getNonWires())
            if (c.getFactory() instanceof Pin && label.equals(at(c, "label"))) return c;
        return null;
    }

    static void set(Component comp, long v) {
        if (comp == null) { System.out.println("### 引脚不存在（label 写错或该电路没有此引脚）"); return; }
        int w = 1;
        try { w = Integer.parseInt(at(comp, "width")); } catch (Exception ignore) { }
        Pin.FACTORY.setValue(cs.getInstanceState(comp), Value.createKnown(BitWidth.create(w), v));
        cs.markComponentAsDirty(comp);
        cs.markPointAsDirty(comp.getLocation());
    }

    static void tick() {
        if (clkPin != null) {
            set(clkPin, 1); prop.propagate();
            set(clkPin, 0); prop.propagate();
        } else {
            prop.toggleClocks(); prop.propagate();
            prop.toggleClocks(); prop.propagate();
        }
    }

    static String read() {
        StringBuilder sb = new StringBuilder();
        for (Component c : outs) {
            Value v = cs.getValue(c.getLocation());
            sb.append(at(c, "label")).append("=0x").append(v == null ? "?" : v.toHexString()).append(' ');
        }
        for (Component c : disps) {
            Value v = cs.getValue(c.getLocation());
            sb.append('d').append(at(c, "label")).append('=').append(v == null ? "?" : v.toHexString()).append(' ');
        }
        return sb.toString();
    }

    static String at(Component c, String n) {
        for (Attribute<?> at : c.getAttributeSet().getAttributes())
            if (at.getName().equals(n)) {
                Object v = c.getAttributeSet().getValue(at);
                return v == null ? "" : String.valueOf(v);
            }
        return "";
    }
}
