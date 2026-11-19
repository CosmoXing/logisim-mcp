import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.BitWidth;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.instance.InstanceState;
import com.cburch.logisim.proj.Project;
import com.cburch.logisim.std.wiring.Pin;

import java.io.File;
import java.io.PrintStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;

/** 驱动 CLK 引脚若干拍，打印 TTY 每行文本。 */
public class TtyRead {
    static PrintStream out;

    static final class ProbeLoader extends Loader {
        ProbeLoader() { super(null); }
        @Override public void showError(String msg) { System.err.println("LOADERR " + msg); }
    }

    static void writePin(CircuitState st, Component comp, int w, int v) {
        Value val = Value.createKnown(BitWidth.create(w), v);
        InstanceState is = st.getInstanceState(comp);
        Pin f = (Pin) comp.getFactory();
        f.setValue(is, val);
        f.propagate(is);
        st.markComponentAsDirty(comp);
        st.setValue(comp.getLocation(), val, comp, 0);
    }

    static void deepPropagate(CircuitState st) {
        st.getPropagator().propagate();
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out), true, StandardCharsets.UTF_8);
        String file = null, cname = null, pinName = "CLK", setSpec = null, probeSpec = null;
        int cycles = 32;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--file")) file = args[++i];
            else if (args[i].equals("--circuit")) cname = args[++i];
            else if (args[i].equals("--pin")) pinName = args[++i];
            else if (args[i].equals("--cycles")) cycles = Integer.parseInt(args[++i]);
            else if (args[i].equals("--set")) setSpec = args[++i];
            else if (args[i].equals("--probe")) probeSpec = args[++i];
        }
        Loader loader = new ProbeLoader();
        LogisimFile lf = loader.openLogisimFile(new File(file));
        Project proj = new Project(lf);
        Circuit c = null;
        for (Circuit cc : lf.getCircuits()) if (cc.getName().equals(cname)) c = cc;
        if (c == null) { out.println("no circuit"); return; }
        proj.setCurrentCircuit(c);
        CircuitState st = proj.getCircuitState(c);
        if (st == null) st = new CircuitState(proj, c);

        Component clk = null;
        for (Component comp : c.getNonWires()) {
            String n = comp.getFactory().getName();
            if (n.equals("Pin")) {
                Object lab = comp.getAttributeSet().getValue(com.cburch.logisim.instance.StdAttr.LABEL);
                if (pinName.equals(lab)) { clk = comp; break; }
            }
        }
        if (clk == null) {
            for (int i = 0; i < cycles; i++) proj.getSimulator().tick();
        } else {
            Component rst = null;
            for (Component comp : c.getNonWires()) {
                if (!comp.getFactory().getName().equals("Pin")) continue;
                Object lab = comp.getAttributeSet().getValue(com.cburch.logisim.instance.StdAttr.LABEL);
                if ("RST".equals(lab)) { rst = comp; break; }
            }
            if (setSpec != null) {
                for (String kv : setSpec.split(",")) {
                    String[] np = kv.trim().split("=");
                    if (np.length != 2) continue;
                    for (Component comp : c.getNonWires()) {
                        if (!comp.getFactory().getName().equals("Pin")) continue;
                        Object lab = comp.getAttributeSet().getValue(com.cburch.logisim.instance.StdAttr.LABEL);
                        if (!np[0].trim().equals(lab)) continue;
                        int w = comp.getEnds().get(0).getWidth().getWidth();
                        String v = np[1].trim();
                        int val = v.startsWith("0x") ? Integer.parseInt(v.substring(2), 16) : Integer.parseInt(v);
                        writePin(st, comp, w, val);
                        break;
                    }
                }
                deepPropagate(st);
            }
            writePin(st, clk, 1, 0);
            deepPropagate(st);
            if (rst != null) {
                writePin(st, rst, 1, 1);
                for (int i = 0; i < 2; i++) {
                    writePin(st, clk, 1, 1); deepPropagate(st);
                    writePin(st, clk, 1, 0); deepPropagate(st);
                }
                writePin(st, rst, 1, 0);
                deepPropagate(st);
            }
            for (int i = 0; i < cycles; i++) {
                writePin(st, clk, 1, 1);
                deepPropagate(st);
                writePin(st, clk, 1, 0);
                deepPropagate(st);
            }
        }

        if (probeSpec != null) {
            deepPropagate(st);
            for (String p : probeSpec.split(";")) {
                String[] t = p.trim().split(",");
                if (t.length < 2) continue;
                int w = t.length > 2 ? Integer.parseInt(t[2].trim()) : 1;
                com.cburch.logisim.data.Value v = st.getValue(
                        Location.create(Integer.parseInt(t[0].trim()), Integer.parseInt(t[1].trim())));
                out.println("PROBE " + t[0] + "," + t[1] + "=" + (v == null ? "null" : v.toHexString()));
            }
        }
        for (Component comp : c.getNonWires()) {
            if (!comp.getFactory().getName().equals("TTY")) continue;
            try { st.getInstanceState(comp); } catch (Throwable ignored) {}
            try { st.getPropagator().propagate(); } catch (Throwable ignored) {}
            Object data = st.getData(comp);
            if (data == null) { out.println("TTY no data"); continue; }
            Method rows = data.getClass().getDeclaredMethod("getRowString", int.class);
            rows.setAccessible(true);
            out.println("=== TTY rows ===");
            for (int r = 0; r < 8; r++) {
                try { out.println("|" + rows.invoke(data, r) + "|"); } catch (Throwable ex) { }
            }
        }
        out.flush();
        System.exit(0);
    }
}