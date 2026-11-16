import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.circuit.Propagator;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.data.BitWidth;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.instance.Instance;
import com.cburch.logisim.instance.InstanceState;
import com.cburch.logisim.instance.StdAttr;
import com.cburch.logisim.proj.Project;
import com.cburch.logisim.std.wiring.Pin;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Headless 仿真探针，专为 Logisim-ITA 2.16.x（2.7.1 分支）编写。
 * 用法：
 *   java -cp "Logisim-ITA.jar;classes" ITAProbe --file X.circ [--circuit NAME] --list
 *   java -cp ... ITAProbe --file X.circ --set "A=0x1,WE=1" [--read "Y"]
 *   java -cp ... ITAProbe --file X.circ --vector V.vec [--clk CLK]
 */
public class ITAProbe {

    static final class P {
        final Component comp;
        final String name;
        final boolean input;
        final int width;
        P(Component c, String n, boolean in, int w) {
            comp = c; name = n; input = in; width = w;
        }
    }

    static PrintStream out;

    public static void main(String[] args) {
        out = new PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out), true, StandardCharsets.UTF_8);
        String file = null, circuitName = null, setSpec = null, readSpec = null, vector = null, clkName = null, probeSpec = null;
        boolean dump = false, ends = false, errors = false;
        boolean list = false;
        try {
            for (int i = 0; i < args.length; i++) {
                String a = args[i];
                switch (a) {
                    case "--file": file = args[++i]; break;
                    case "--circuit": circuitName = args[++i]; break;
                    case "--set": setSpec = args[++i]; break;
                    case "--read": readSpec = args[++i]; break;
                    case "--vector": vector = args[++i]; break;
                    case "--clk": clkName = args[++i]; break;
                    case "--probe": probeSpec = args[++i]; break;
                    case "--dump": dump = true; break;
                    case "--ends": ends = true; break;
                    case "--errors": errors = true; break;
                    case "--list": list = true; break;
                    default: die("unknown arg " + a);
                }
            }
            if (file == null) die("--file required");

            Loader loader = new Loader(null);
            LogisimFile lf = loader.openLogisimFile(new File(file));
            if (lf == null) die("cannot load " + file);
            Project proj = new Project(lf);

            Circuit circuit;
            if (circuitName != null) {
                circuit = pickCircuit(lf, circuitName);
                if (circuit == null) {
                    StringBuilder sb = new StringBuilder();
                    for (Circuit c : lf.getCircuits()) sb.append(" [").append(c.getName()).append("]");
                    die("circuit not found: " + circuitName + " candidates:" + sb);
                }
            } else {
                circuit = lf.getMainCircuit();
                if (circuit == null) die("no main circuit");
            }

            // 先把 Project 切到目标电路，再取"当前状态"——只有它才是被 simulator
            // 挂接、Propagator 认的活状态；自己 new 的游离 state 读不到也驱动不了任何网络。
            try {
                proj.setCurrentCircuit(circuit);
            } catch (Throwable ignored) {
            }
            CircuitState st = proj.getCircuitState();
            if (st == null) st = proj.getCircuitState(circuit);
            if (st == null) st = new CircuitState(proj, circuit);
            if (System.getenv("ITA_TRACE") != null) {
                System.err.println("DBG currentCircuit="
                        + (proj.getCurrentCircuit() == null ? "null" : proj.getCurrentCircuit().getName())
                        + " | projState=" + (proj.getCircuitState() == null ? "null"
                        : proj.getCircuitState().getCircuit().getName())
                        + " | same=" + (proj.getCircuitState() == st)
                        + " | wires=" + circuit.getWires().size());
            }
            Propagator prop = st.getPropagator();
            if (prop == null) die("no propagator");
            prop.propagate();

            List<P> pins = collect(circuit, st);

            if (list) {
                out.println("CIRCUIT " + circuit.getName() + " pins=" + pins.size()
                        + " comps=" + circuit.getNonWires().size()
                        + " wires=" + circuit.getWires().size());
                for (P p : pins) {
                    out.println("PIN " + p.name + " " + (p.input ? "in" : "out") + " " + p.width
                            + " " + p.comp.getLocation());
                }
                out.println("SUMMARY circuits=" + lf.getCircuits().size());
                System.exit(0);
            }

            if (errors) {
                java.util.LinkedHashSet<Location> pts = new java.util.LinkedHashSet<>();
                for (com.cburch.logisim.circuit.Wire w : circuit.getWires()) {
                    pts.add(w.getEnd0());
                    pts.add(w.getEnd1());
                }
                for (Component c : circuit.getNonWires()) {
                    for (com.cburch.logisim.comp.EndData e : c.getEnds()) pts.add(e.getLocation());
                }
                int n = 0;
                for (Component c : circuit.getNonWires()) {
                    for (com.cburch.logisim.comp.EndData e : c.getEnds()) {
                        Value v = st.getValue(e.getLocation());
                        if (v != null && v.isErrorValue()) {
                            out.println("ERR " + c.getFactory().getName() + " @" + c.getLocation()
                                    + " port " + e.getLocation() + " w" + e.getWidth().getWidth());
                            n++;
                        }
                    }
                }
                out.println("ERRCOUNT " + n);
                System.exit(0);
            }

            if (ends) {
                for (Component c : circuit.getNonWires()) {
                    out.println("COMP " + c.getFactory().getName() + " @" + c.getLocation());
                    for (com.cburch.logisim.comp.EndData e : c.getEnds()) {
                        out.println("   END " + e.getLocation() + " w" + e.getWidth().getWidth()
                                + (e.isInput() ? " in" : "") + (e.isOutput() ? " out" : ""));
                    }
                }
                System.exit(0);
            }

            if (dump) {
                for (P p : pins) {
                    out.println("DUMPPIN " + p.name + " " + (p.input ? "in" : "out") + " w" + p.width
                            + "=" + fmt(readPin(st, p), p.width));
                }
                java.util.LinkedHashSet<Location> pts = new java.util.LinkedHashSet<>();
                for (com.cburch.logisim.circuit.Wire w : circuit.getWires()) {
                    pts.add(w.getEnd0());
                    pts.add(w.getEnd1());
                }
                for (Location l : pts) {
                    Value v = st.getValue(l);
                    if (v == null) continue;
                    if (!v.isFullyDefined() && !v.isErrorValue()) continue;
                    out.println("DUMPPT " + l + "=" + fmt(v, v.getWidth()));
                }
            }

            if (probeSpec != null) {
                for (String p : probeSpec.split(";")) {
                    String[] t = p.trim().split(",");
                    if (t.length < 2) continue;
                    Location loc = Location.create(Integer.parseInt(t[0].trim()), Integer.parseInt(t[1].trim()));
                    int w = t.length > 2 ? Integer.parseInt(t[2].trim()) : 1;
                    out.println("PROBE " + t[0].trim() + "," + t[1].trim() + "=" + fmt(st.getValue(loc), w));
                }
            }

            if (vector != null) {
                int[] rc = runVector(st, prop, pins, vector, clkName);
                out.println("SUMMARY rows=" + rc[0] + " pass=" + rc[1] + " fail=" + rc[2]);
                System.exit(rc[2] == 0 ? 0 : 1);
                return;
            }

            // 单次求值
            Map<String, P> byName = new LinkedHashMap<>();
            for (P p : pins) byName.put(p.name, p);

            if (setSpec != null) {
                applyInputs(st, prop, byName, parseAssign(setSpec), null);
            } else {
                prop.propagate();
            }

            List<String> want = new ArrayList<>();
            if (readSpec != null) {
                for (String s : readSpec.split(",")) if (!s.trim().isEmpty()) want.add(s.trim());
            }
            int printed = 0;
            for (P p : pins) {
                if (p.input) continue;
                if (!want.isEmpty() && !want.contains(p.name)) continue;
                out.println("OUT " + p.name + "=" + fmt(readPin(st, p), p.width));
                printed++;
            }
            if (printed == 0) out.println("OUT <none>");
            System.exit(0);

        } catch (Throwable t) {
            System.err.println("ERROR " + t.getClass().getName() + ": " + t.getMessage());
            t.printStackTrace(System.err);
            System.exit(2);
        }
    }

    // ---------------- 引脚 ----------------

    /**
     * Windows 下 JVM 用系统 ANSI(GBK) 解码命令行参数，UTF-8 中文会变乱码。
     * 把乱码串按 GBK 还原成字节再以 UTF-8 解码，即可拿回原字面量。
     */
    static String tryFix(String s) {
        if (s == null) return null;
        boolean ascii = true;
        for (int i = 0; i < s.length(); i++) {
            if (s.charAt(i) > 0x7F) { ascii = false; break; }
        }
        if (ascii) return s;
        try {
            String t = new String(s.getBytes("GBK"), StandardCharsets.UTF_8);
            if (!t.equals(s) && t.indexOf('\uFFFD') < 0) return t;
        } catch (Exception ignored) {
        }
        return s;
    }

    /** 精确匹配 → 编码还原后匹配 → 唯一前缀匹配。 */
    static Circuit pickCircuit(LogisimFile lf, String want) {
        String alt = tryFix(want);
        for (Circuit c : lf.getCircuits()) {
            if (c.getName().equals(want) || c.getName().equals(alt)) return c;
        }
        Circuit only = null;
        int hits = 0;
        for (Circuit c : lf.getCircuits()) {
            String n = c.getName();
            if (n.startsWith(want) || n.startsWith(alt) || n.contains(want) || n.contains(alt)) {
                only = c;
                hits++;
            }
        }
        return hits == 1 ? only : null;
    }

    static List<P> collect(Circuit c, CircuitState st) {
        List<P> list = new ArrayList<>();
        for (Component comp : c.getNonWires()) {
            if (!(comp.getFactory() instanceof Pin)) continue;
            AttributeSet attrs = comp.getAttributeSet();
            String name = attrs.getValue(StdAttr.LABEL);
            if (name == null) name = "";
            InstanceState is = st.getInstanceState(comp);
            if (is == null) continue;
            Instance inst = is.getInstance();
            boolean input = ((Pin) comp.getFactory()).isInputPin(inst);
            BitWidth bw = is.getAttributeSet().getValue(StdAttr.WIDTH);
            int w = bw == null ? 1 : bw.getWidth();
            list.add(new P(comp, name, input, w));
        }
        return list;
    }

    static Value readPin(CircuitState st, P p) {
        InstanceState is = st.getInstanceState(p.comp);
        if (is == null) return null;
        return ((Pin) p.comp.getFactory()).getValue(is);
    }

    static void writePin(CircuitState st, P p, int v) {
        Value val = Value.createKnown(BitWidth.create(p.width), v);
        InstanceState is = st.getInstanceState(p.comp);
        if (is == null) return;
        Pin f = (Pin) p.comp.getFactory();
        f.setValue(is, val);
        // Pin.setValue 只改 PinState；必须再 propagate 一次才会把值写到端口上
        // （GUI 里 poke 引脚走的就是这条路）。只靠 CircuitState.setValue 在大电路上不生效。
        f.propagate(is);
        st.markComponentAsDirty(p.comp);
        st.setValue(p.comp.getLocation(), val, p.comp, 0);
        if (System.getenv("ITA_TRACE") != null) {
            System.err.println("SET " + p.name + " @" + p.comp.getLocation() + " w" + p.width + " = " + val.toHexString());
        }
    }


    /** 子电路状态不会自动递归传播：先把子电路实例标脏走标准链路，再逐层递归。 */
    static void deepPropagate(CircuitState st) {
        for (Component c : st.getCircuit().getNonWires()) {
            if (c.getFactory() instanceof com.cburch.logisim.circuit.SubcircuitFactory) {
                st.markComponentAsDirty(c);
            }
        }
        st.getPropagator().propagate();
        for (Component c : st.getCircuit().getNonWires()) {
            if (!(c.getFactory() instanceof com.cburch.logisim.circuit.SubcircuitFactory)) continue;
            try {
                InstanceState is = st.getInstanceState(c);
                if (is == null) continue;
                com.cburch.logisim.circuit.SubcircuitFactory f =
                        (com.cburch.logisim.circuit.SubcircuitFactory) c.getFactory();
                CircuitState sub = f.getSubstate(st, is.getInstance());
                if (sub != null) deepPropagate(sub);
            } catch (Throwable ignored) {
            }
        }
    }

    static Map<String, Integer> parseAssign(String spec) {
        Map<String, Integer> m = new LinkedHashMap<>();
        for (String kv : spec.split("[,;]")) {
            kv = kv.trim();
            if (kv.isEmpty()) continue;
            int eq = kv.indexOf('=');
            if (eq < 0) throw new IllegalArgumentException("bad assignment: " + kv);
            m.put(kv.substring(0, eq).trim(), parseVal(kv.substring(eq + 1).trim()));
        }
        return m;
    }

    static int parseVal(String s) {
        s = s.trim();
        boolean neg = false;
        if (s.startsWith("-")) { neg = true; s = s.substring(1); }
        long v;
        if (s.startsWith("0x") || s.startsWith("0X")) v = Long.parseLong(s.substring(2), 16);
        else if (s.startsWith("0b") || s.startsWith("0B")) v = Long.parseLong(s.substring(2), 2);
        else v = Long.parseLong(s);
        if (neg) v = -v;
        return (int) v;
    }

    /** 先设非时钟输入并传播，再设时钟并传播；保证数据比时钟沿先稳定。 */
    static void applyInputs(CircuitState st, Propagator prop, Map<String, P> byName,
                            Map<String, Integer> vals, String clkName) {
        // 1) 非时钟输入
        for (Map.Entry<String, Integer> e : vals.entrySet()) {
            if (clkName != null && e.getKey().equals(clkName)) continue;
            P p = byName.get(e.getKey());
            if (p == null) throw new IllegalArgumentException("no such pin: " + e.getKey());
            if (!p.input) throw new IllegalArgumentException("not an input pin: " + e.getKey());
            writePin(st, p, e.getValue());
        }
        deepPropagate(st);
        // 2) 时钟输入
        if (clkName != null && vals.containsKey(clkName)) {
            P p = byName.get(clkName);
            if (p == null) throw new IllegalArgumentException("no such pin: " + clkName);
            writePin(st, p, vals.get(clkName));
            deepPropagate(st);
        }
    }

    // ---------------- 向量 ----------------

    static int[] runVector(CircuitState st, Propagator prop, List<P> pins, String path, String clkArg) throws Exception {
        Map<String, P> byName = new LinkedHashMap<>();
        for (P p : pins) byName.put(p.name, p);

        List<String> lines = new ArrayList<>();
        try (BufferedReader r = new BufferedReader(new InputStreamReader(
                new FileInputStream(path), StandardCharsets.UTF_8))) {
            String ln;
            while ((ln = r.readLine()) != null) {
                String t = ln.trim();
                if (t.isEmpty() || t.startsWith("#") || t.startsWith("//")) continue;
                lines.add(t);
            }
        }
        if (lines.isEmpty()) throw new IllegalArgumentException("empty vector file");

        String[] head = lines.get(0).split("\\s+");
        String[] names = new String[head.length];
        for (int i = 0; i < head.length; i++) {
            String n = head[i];
            int br = n.indexOf('[');
            if (br > 0) n = n.substring(0, br);
            names[i] = n;
            if (!byName.containsKey(n)) {
                throw new IllegalArgumentException("vector header pin not found in circuit: " + n
                        + " (circuit pins: " + byName.keySet() + ")");
            }
        }
        // 时钟列（用于分段设置）
        String clk = clkArg;
        if (clk == null) {
            for (String n : names) {
                if (n.equalsIgnoreCase("clk") || n.equalsIgnoreCase("clock")) { clk = n; break; }
            }
        }
        out.println("CLK " + (clk == null ? "<none>" : clk));

        int rows = 0, pass = 0, fail = 0;
        for (int li = 1; li < lines.size(); li++) {
            String[] tok = lines.get(li).split("\\s+");
            if (tok.length != names.length) {
                out.println("ROW " + li + " FAIL bad-column-count want=" + names.length + " got=" + tok.length);
                fail++; rows++;
                continue;
            }
            Map<String, Integer> vals = new LinkedHashMap<>();
            List<String> expects = new ArrayList<>();
            for (int i = 0; i < tok.length; i++) {
                P p = byName.get(names[i]);
                String t = tok[i];
                if (isDC(t)) continue;
                if (p.input) {
                    vals.put(names[i], parseVal(t));
                } else {
                    expects.add(names[i] + "=" + t);
                }
            }
            applyInputs(st, prop, byName, vals, clk);

            List<String> bad = new ArrayList<>();
            for (String e : expects) {
                int eq = e.indexOf('=');
                String nm = e.substring(0, eq);
                int want = parseVal(e.substring(eq + 1));
                P p = byName.get(nm);
                Value got = readPin(st, p);
                if (got == null || !got.isFullyDefined() || got.toIntValue() != want) {
                    bad.add(nm + " exp=" + hex(want) + " got=" + fmt(got, p.width));
                }
            }
            rows++;
            if (bad.isEmpty()) {
                pass++;
                if (System.getenv("ITA_VERBOSE") != null) out.println("ROW " + li + " OK");
            } else {
                fail++;
                out.println("ROW " + li + " FAIL " + String.join(" | ", bad));
            }
        }
        return new int[]{rows, pass, fail};
    }

    static boolean isDC(String s) {
        return s.equals("<DC>") || s.equalsIgnoreCase("x") || s.equals("-") || s.equals("*")
                || s.equalsIgnoreCase("dc");
    }

    static String hex(int v) {
        return "0x" + Integer.toHexString(v);
    }

    static String fmt(Value v, int w) {
        if (v == null) return "U";
        if (v.isErrorValue()) return "E";
        if (!v.isFullyDefined()) return "U";
        return hex(v.toIntValue());
    }

    static void die(String msg) {
        System.err.println("ERROR " + msg);
        System.exit(2);
    }
}
