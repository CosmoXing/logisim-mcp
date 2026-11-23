// Logisim-evolution 3.9 无头探针：加载 .circ → 设引脚 → 打拍 → 读输出 → 预装/导出 RAM。
//
// 用法：
//   javac -cp <logisim39.jar> -d out Probe39.java
//   java -Djava.awt.headless=true -cp "<logisim39.jar>;out" Probe39 \
//        <file.circ> <circuit> <cycles> [ram=xxx.hex] [pin=value ...]
//
// 说明：
// 1) 引脚设值必须 Pin.setValue + setPort + markComponentAsDirty + propagate，
//    只 setPort 会被 Pin.propagate 用旧 intendedValue 覆盖。
// 2) 打拍用 clk 输入引脚手动 0→1→0；不要用 Simulator.tick()（无头会走 Swing）。
// 3) RAM 内容不随 .circ 保存，ram=xxx.hex 会在开跑前写入 RAM 的 MemContents。
// 4) 每拍打印 dbg_* 输出引脚（没有则打印全部输出）；停止后导出 RAM 非零字。

import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.circuit.Simulator;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.BitWidth;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.instance.Instance;
import com.cburch.logisim.instance.InstanceState;
import com.cburch.logisim.instance.StdAttr;
import com.cburch.logisim.proj.Project;
import com.cburch.logisim.std.memory.MemContents;
import com.cburch.logisim.std.memory.Ram;
import com.cburch.logisim.std.wiring.Pin;

import java.io.File;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.Map;

public class Probe39 {
    static final Map<String, Instance> pins = new LinkedHashMap<>();
    static final Map<String, InstanceState> states = new LinkedHashMap<>();
    static CircuitState cs;
    static Simulator sim;

    public static void main(String[] args) throws Exception {
        String path = args[0];
        String cname = args.length > 1 ? args[1] : "main";
        int cycles = args.length > 2 ? Integer.parseInt(args[2]) : 0;
        String ramFile = null;
        java.util.List<String> sets = new java.util.ArrayList<>();
        for (int i = 3; i < args.length; i++) {
            if (args[i].startsWith("ram=")) ramFile = args[i].substring(4);
            else sets.add(args[i]);
        }

        Loader loader = new Loader(null);
        LogisimFile file = loader.openLogisimFile(new File(path));
        Circuit circuit = file.getCircuit(cname);
        if (circuit == null) {
            System.out.println("NOCIRCUIT " + cname);
            return;
        }
        for (Component comp : circuit.getNonWires()) {
            if (comp.getFactory() instanceof Pin) {
                Instance inst = Instance.getInstanceFor(comp);
                String label = inst.getAttributeValue(StdAttr.LABEL);
                pins.put(label == null ? "" : label, inst);
            }
        }

        Project proj = new Project(file);
        sim = proj.getSimulator();
        cs = proj.getCircuitState(circuit);
        for (String k : pins.keySet()) states.put(k, cs.getInstanceState(pins.get(k)));

        // 复位（Reset 或 reset），异步清零后释放
        String r = pins.containsKey("Reset") ? "Reset" : (pins.containsKey("reset") ? "reset" : null);
        if (r != null) {
            set(r, 1);
            set("clk", 0);
            prop();
            set(r, 0);
            prop();
        }

        if (ramFile != null) preloadRam(ramFile);
        for (String s : sets) {
            int eq = s.indexOf('=');
            if (eq > 0) set(s.substring(0, eq), Long.parseLong(s.substring(eq + 1).replace("0x", ""), 16));
        }
        prop();

        boolean hasDbg = pins.keySet().stream().anyMatch(k -> k.startsWith("dbg_"));
        for (int i = 0; i <= cycles; i++) {
            StringBuilder sb = new StringBuilder().append(i);
            for (String k : pins.keySet()) {
                if (hasDbg && !k.startsWith("dbg_")) continue;
                if (!hasDbg && (k.equals("clk") || k.equals("Reset") || k.equals("reset"))) continue;
                sb.append(" ").append(k.startsWith("dbg_") ? k.substring(4) : k).append("=").append(get(k));
            }
            System.out.println(sb);
            if (i == cycles) break;
            pulse();
        }
        System.out.println("OSC " + sim.isOscillating());
        dumpRam();
        System.exit(0);
    }

    static void set(String label, long v) {
        Instance inst = pins.get(label);
        if (inst == null) return;
        BitWidth w = inst.getAttributeValue(StdAttr.WIDTH);
        Value val = Value.createKnown(w, v);
        InstanceState st = states.get(label);
        ((Pin) inst.getFactory()).setValue(st, val);
        st.setPort(0, val, 1);
        cs.markComponentAsDirty(inst.getComponent());
        cs.getPropagator().propagate();
    }

    static void prop() {
        for (int i = 0; i < 20; i++) {
            if (!cs.getPropagator().propagate()) break;
        }
    }

    static void pulse() {
        if (pins.containsKey("clk")) {
            set("clk", 1);
            prop();
            set("clk", 0);
            prop();
        } else {
            // 有 Clock 组件时：两次 toggle 组成一个完整脉冲
            cs.getPropagator().toggleClocks();
            prop();
            cs.getPropagator().toggleClocks();
            prop();
        }
    }

    static String get(String label) {
        Instance inst = pins.get(label);
        if (inst == null) return "NOPIN";
        Value v = cs.getValue(inst.getLocation());
        return v == null ? "NULL" : v.toHexString();
    }

    /** 在任意层子电路里找 RAM 的 InstanceState（默认找名为 DM 的子电路）。 */
    static InstanceState findRamState(String subName) {
        for (CircuitState sub : cs.getSubStates()) {
            if (subName != null && !sub.getCircuit().getName().equals(subName)) continue;
            for (Component c : sub.getCircuit().getNonWires()) {
                if (c.getFactory() instanceof Ram) {
                    return sub.getInstanceState(Instance.getInstanceFor(c));
                }
            }
        }
        return null;
    }

    static void preloadRam(String hexPath) throws Exception {
        long[] words = new long[16384];
        for (String line : Files.readAllLines(new File(hexPath).toPath())) {
            line = line.trim();
            if (!line.contains(":")) continue;
            String[] parts = line.split(":", 2);
            int base = Integer.parseInt(parts[0].trim(), 16);
            String[] toks = parts[1].trim().split("\\s+");
            for (int i = 0; i < toks.length; i++) {
                if (!toks[i].isEmpty() && base + i < words.length) {
                    words[base + i] = Long.parseLong(toks[i], 16);
                }
            }
        }
        InstanceState st = findRamState("DM");
        if (st == null) {
            System.out.println("NORAM");
            return;
        }
        MemContents mc = ((Ram) st.getInstance().getFactory()).getContents(st);
        for (int i = 0; i < words.length; i++) if (words[i] != 0) mc.set(i, words[i]);
        System.out.println("RAM loaded");
    }

    static void dumpRam() {
        InstanceState st = findRamState("DM");
        if (st == null) return;
        MemContents mc = ((Ram) st.getInstance().getFactory()).getContents(st);
        System.out.println("MEMDUMP");
        for (int i = 0; i < 4096; i++) {
            long v = mc.get(i);
            if (v != 0) System.out.println(i + " " + String.format("%08x", v));
        }
        System.out.println("ENDDUMP");
    }
}