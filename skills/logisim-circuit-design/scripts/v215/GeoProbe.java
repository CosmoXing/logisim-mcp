import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.ComponentFactory;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.data.Bounds;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.tools.AddTool;
import com.cburch.logisim.tools.Library;
import com.cburch.logisim.tools.Tool;

import java.io.File;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;

/** 打印 Logisim-ITA 组件真实几何（bounds + 端口相对偏移）与属性表。 */
public class GeoProbe {
    static PrintStream out;

    static final class ProbeLoader extends Loader {
        ProbeLoader() { super(null); }
        @Override public void showError(String msg) { System.err.println("LOADERR " + msg); }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(new java.io.FileOutputStream(java.io.FileDescriptor.out), true, StandardCharsets.UTF_8);
        String file = null, want = null;
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--file")) file = args[++i];
            else if (args[i].equals("--comp")) want = args[++i];
        }
        if (file == null) { System.err.println("need --file"); System.exit(2); }
        Loader loader = new ProbeLoader();
        LogisimFile lf = loader.openLogisimFile(new File(file));
        if (lf == null) { System.err.println("cannot load"); System.exit(2); }
        String[] extra = {"com.cburch.logisim.std.io.Io",
                "com.cburch.logisim.std.memory.Memory",
                "com.cburch.logisim.std.plexers.Plexers",
                "com.cburch.logisim.std.arith.Arithmetic",
                "com.cburch.logisim.std.gates.Gates",
                "com.cburch.logisim.std.wiring.Wiring"};
        for (String cn : extra) {
            try {
                Class<?> c = Class.forName(cn);
                Object inst = c.getDeclaredConstructor().newInstance();
                if (inst instanceof Library) scan((Library) inst, want, 0);
            } catch (Throwable ex) {
                out.println("## cannot load " + cn + " : " + ex);
            }
        }
    }

    static void scan(Library lib, String want, int depth) {
        if (depth > 2) return;
        for (Tool t : lib.getTools()) {
            if (want != null && !t.getName().equalsIgnoreCase(want)) continue;
            if (want == null && !interesting(t.getName())) continue;
            try {
                AttributeSet attrs = t.getAttributeSet();
                if (attrs == null) { out.println("-- " + t.getName() + " (no attrs)"); continue; }
                ComponentFactory fac = (t instanceof AddTool) ? ((AddTool) t).getFactory() : null;
                if (fac == null) continue;
                Component comp = fac.createComponent(Location.create(0, 0), attrs);
                Bounds b = comp.getBounds();
                out.println("== " + lib.getName() + " / " + t.getName()
                        + "  body=(" + b.getX() + "," + b.getY() + ","
                        + b.getWidth() + "," + b.getHeight() + ")");
                if (fac instanceof com.cburch.logisim.instance.InstanceFactory) {
                    java.util.List<com.cburch.logisim.instance.Port> plist =
                            ((com.cburch.logisim.instance.InstanceFactory) fac).getPorts();
                    StringBuilder sb = new StringBuilder("   portaliases:");
                    for (com.cburch.logisim.instance.Port p : plist) {
                        sb.append(" [").append(p.getToolTip() == null ? "?" : p.getToolTip()).append("]");
                    }
                    out.println(sb);
                }
                for (EndData e : comp.getEnds()) {
                    Location l = e.getLocation();
                    out.println("   port d=(" + l.getX() + "," + l.getY() + ") width="
                            + e.getWidth().getWidth() + " type=" + e.getType());
                }
                out.print("   attrs:");
                for (Attribute<?> a : attrs.getAttributes()) {
                    Object v;
                    try { v = attrs.getValue(a); } catch (Throwable ex) { v = "?"; }
                    out.print(" [" + a.getName() + "=" + v + "]");
                }
                out.println();
            } catch (Throwable ex) {
                out.println("!! " + t.getName() + " -> " + ex);
            }
        }
        for (Library sub : lib.getLibraries()) scan(sub, want, depth + 1);
    }

    static boolean interesting(String n) {
        return n.equals("TTY") || n.equals("Keyboard") || n.equals("Button") || n.equals("LED")
                || n.equals("DotMatrix") || n.equals("Seven Segment Display") || n.equals("Switch")
                || n.equals("Hex Digit Display") || n.equals("Buzzer") || n.equals("Clock")
                || n.equals("Dip Switch") || n.equals("RGB LED");
    }
}